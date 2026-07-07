import csv
import io
import json
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.ai.providers.base import AIProvider

_DATE_FMTS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%m-%d-%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%d %b %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%m/%d/%y",
    "%d/%m/%y",
    "%d-%b-%Y",
    "%d-%b-%y",
]

_DATE_COLS = {
    "date", "transaction date", "trans date", "trans. date",
    "posted date", "posting date", "post date",
    "value date", "settlement date", "effective date", "cleared date",
}
_DESC_PRIMARY_COLS = {
    "description", "memo", "narrative", "details", "detail", "payee",
    "transaction description", "transaction narrative", "transaction details",
    "bai description", "remarks", "particulars", "name",
}
_DESC_FALLBACK_COLS = {
    "reference", "customer ref", "customer reference", "ref",
}
_AMOUNT_COLS = {
    "amount", "transaction amount", "net amount", "value",
    "transaction value", "net",
}
_DEBIT_COLS = {
    "debit", "debit amount", "withdrawal", "withdrawals",
    "charge", "charges", "out", "dr", "dr.", "debits",
    "money out",
}
_CREDIT_COLS = {
    "credit", "credit amount", "deposit", "deposits",
    "payment", "in", "cr", "cr.", "credits",
    "money in",
}

_AI_SYSTEM_PROMPT = (
    "You are a financial CSV column mapping assistant. "
    "Given CSV headers and sample rows, identify which column contains each type of financial data. "
    "Respond with ONLY a valid JSON object — no explanation, no markdown fences, no extra text."
)

_AI_USER_TEMPLATE = """\
Identify the column roles in this CSV from a bank statement or transaction export.

Headers: {headers}

Sample rows (CSV format):
{sample_rows}

Return a JSON object with exactly these keys. Each value must be an exact header string \
from the list above (including any leading/trailing spaces), or null if that role is not present:
{{
  "date": "<transaction date column or null>",
  "description": "<description / memo / payee column or null>",
  "amount": "<single signed amount column or null>",
  "debit": "<money-out / withdrawal / charge column or null>",
  "credit": "<money-in / deposit / payment column or null>"
}}

Rules:
- Use amount when there is one signed amount column (positive=income, negative=expense).
- Use debit and/or credit when money-in and money-out are in separate columns.
- date and description must be non-null.
- At least one of amount, debit, or credit must be non-null.\
"""


@dataclass
class ParsedTransaction:
    date: date
    description: str
    amount: Decimal
    transaction_type: str  # "income" | "expense"
    vendor_name: str | None


@dataclass
class ParseResult:
    transactions: list[ParsedTransaction]
    warnings: list[str]
    detected_columns: dict[str, str]
    skipped_rows: int
    used_ai: bool = False


# ── internal helpers ──────────────────────────────────────────────────────────

def _parse_amount(raw: str) -> Decimal | None:
    s = raw.strip()
    if not s:
        return None
    parenthetical = s.startswith("(") and s.endswith(")")
    s = re.sub(r"[$£€¥₹,\s()]", "", s)
    if s.endswith("-"):
        s = "-" + s[:-1]
    try:
        val = Decimal(s)
        return -val if parenthetical else val
    except InvalidOperation:
        return None


def _parse_date(raw: str) -> date | None:
    s = raw.strip()
    if not s:
        return None
    for fmt in _DATE_FMTS:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _decode_csv(content: bytes) -> str | None:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return None


def _detect_columns_heuristic(headers: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    fallback_desc: str | None = None
    for header in headers:
        norm = header.strip().lower()
        if norm in _DATE_COLS and "date" not in result:
            result["date"] = header
        elif norm in _DESC_PRIMARY_COLS and "description" not in result:
            result["description"] = header
        elif norm in _DESC_FALLBACK_COLS and fallback_desc is None:
            fallback_desc = header
        elif norm in _AMOUNT_COLS and "amount" not in result:
            result["amount"] = header
        elif norm in _DEBIT_COLS and "debit" not in result:
            result["debit"] = header
        elif norm in _CREDIT_COLS and "credit" not in result:
            result["credit"] = header
    if "description" not in result and fallback_desc is not None:
        result["description"] = fallback_desc
    return result


def _detection_errors(col_map: dict[str, str], headers: list[str]) -> list[str]:
    """Return a list of human-readable problems with a column map."""
    errors: list[str] = []
    if "date" not in col_map:
        errors.append(f"Could not detect a date column. Found headers: {headers}")
    if "description" not in col_map:
        errors.append(f"Could not detect a description column. Found headers: {headers}")
    has_amount = "amount" in col_map
    has_debit_credit = "debit" in col_map or "credit" in col_map
    if not has_amount and not has_debit_credit:
        errors.append(f"Could not detect amount, debit, or credit columns. Found headers: {headers}")
    return errors


def _parse_rows(
    text: str,
    col_map: dict[str, str],
) -> tuple[list[ParsedTransaction], list[str], int]:
    reader = csv.DictReader(io.StringIO(text))
    has_amount = "amount" in col_map
    has_debit_credit = "debit" in col_map or "credit" in col_map

    transactions: list[ParsedTransaction] = []
    warnings: list[str] = []
    skipped = 0

    for row_num, row in enumerate(reader, start=2):
        date_raw = row.get(col_map["date"], "")
        parsed_date = _parse_date(date_raw)
        if parsed_date is None:
            warnings.append(f"Row {row_num}: skipped — could not parse date '{date_raw}'")
            skipped += 1
            continue

        description = row.get(col_map["description"], "").strip()
        if not description:
            warnings.append(f"Row {row_num}: skipped — empty description")
            skipped += 1
            continue

        amount: Decimal | None = None

        if has_amount:
            amount = _parse_amount(row.get(col_map["amount"], ""))

        if amount is None and has_debit_credit:
            debit_raw = row.get(col_map["debit"], "") if "debit" in col_map else ""
            credit_raw = row.get(col_map["credit"], "") if "credit" in col_map else ""
            debit_val = _parse_amount(debit_raw)
            credit_val = _parse_amount(credit_raw)

            debit_nonzero = debit_val is not None and debit_val != Decimal("0")
            credit_nonzero = credit_val is not None and credit_val != Decimal("0")

            if debit_nonzero and not credit_nonzero:
                amount = -abs(debit_val)  # type: ignore[arg-type]
            elif credit_nonzero and not debit_nonzero:
                amount = abs(credit_val)  # type: ignore[arg-type]
            elif debit_nonzero and credit_nonzero:
                amount = abs(credit_val) - abs(debit_val)  # type: ignore[arg-type]

        if amount is None:
            warnings.append(f"Row {row_num}: skipped — could not parse amount")
            skipped += 1
            continue

        if amount == Decimal("0"):
            skipped += 1
            continue

        transaction_type = "income" if amount > 0 else "expense"
        transactions.append(
            ParsedTransaction(
                date=parsed_date,
                description=description,
                amount=amount,
                transaction_type=transaction_type,
                vendor_name=None,
            )
        )

    return transactions, warnings, skipped


# ── public AI fallback ────────────────────────────────────────────────────────

def detect_columns_with_ai(
    headers: list[str],
    sample_rows: list[dict[str, str]],
    provider: "AIProvider",
    model: str,
) -> dict[str, str] | None:
    """Ask the AI to map column roles. Returns a validated col_map or None on failure."""
    # Format sample rows as CSV lines so the AI sees data alongside headers
    sample_lines: list[str] = []
    for row in sample_rows[:5]:
        sample_lines.append(", ".join(str(row.get(h, "")) for h in headers))

    prompt = _AI_USER_TEMPLATE.format(
        headers=headers,
        sample_rows="\n".join(sample_lines) or "(no data rows)",
    )

    try:
        raw = provider.complete(
            messages=[
                {"role": "system", "content": _AI_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            model=model,
        )
    except Exception:
        return None

    # Strip markdown code fences if present
    raw = re.sub(r"```(?:json)?\s*", "", raw).strip()
    raw = raw.strip("`").strip()

    try:
        mapping: dict = json.loads(raw)
    except json.JSONDecodeError:
        return None

    header_set = set(headers)
    col_map: dict[str, str] = {}
    for role in ("date", "description", "amount", "debit", "credit"):
        val = mapping.get(role)
        if isinstance(val, str) and val in header_set:
            col_map[role] = val

    # Validate minimum required roles
    if "date" not in col_map or "description" not in col_map:
        return None
    if "amount" not in col_map and "debit" not in col_map and "credit" not in col_map:
        return None

    return col_map


# ── public entry point ────────────────────────────────────────────────────────

def parse_transaction_csv(
    content: bytes,
    col_map: dict[str, str] | None = None,
) -> ParseResult:
    """Parse a CSV bank statement.

    If col_map is provided (e.g. from detect_columns_with_ai), column detection
    is skipped and the supplied mapping is used directly.
    """
    text = _decode_csv(content)
    if text is None:
        return ParseResult([], ["Could not decode CSV file as UTF-8 or Latin-1."], {}, 0)

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return ParseResult([], ["CSV file has no headers."], {}, 0)

    headers = list(reader.fieldnames)

    if col_map is None:
        col_map = _detect_columns_heuristic(headers)
        errors = _detection_errors(col_map, headers)
        if errors:
            return ParseResult([], errors, col_map, 0)

    transactions, warnings, skipped = _parse_rows(text, col_map)
    return ParseResult(
        transactions=transactions,
        warnings=warnings,
        detected_columns=col_map,
        skipped_rows=skipped,
    )


def get_csv_headers_and_samples(
    content: bytes,
) -> tuple[list[str], list[dict[str, str]]] | None:
    """Decode a CSV and return (headers, first 5 data rows). None on failure."""
    text = _decode_csv(content)
    if text is None:
        return None
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return None
    headers = list(reader.fieldnames)
    samples = [dict(row) for _, row in zip(range(5), reader)]
    return headers, samples
