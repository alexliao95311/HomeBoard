"""Reconciliation for multi-file HOA financial CSV imports.

Normalizes rows from invoice_export / operating_activity / reserve_activity
(and similarly-shaped unknown) CSVs into a common record shape, then finds
exact duplicates, invoice-to-bank-payment matches, and operating<->reserve
internal transfers so summary totals don't double-count the same real-world
cash event.
"""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from typing import Literal

from app.services.transaction_parser import _decode_csv, _parse_amount, _parse_date

SourceType = Literal["invoice_export", "operating_activity", "reserve_activity", "unknown"]
Confidence = Literal["high", "medium", "low"]

# ── column alias tables ─────────────────────────────────────────────────────
# Deliberately broad: real-world exports (banks, accounting systems) vary a
# lot in header naming, so each field has many accepted spellings.

_POST_DATE_ALIASES = {
    "post date", "posting date", "posted date", "value date",
    "settlement date", "effective date", "cleared date",
}
_DUE_DATE_ALIASES = {"due date", "payment due date", "net due date"}
_PAID_DATE_ALIASES = {
    "pay date", "paydate", "paid date", "payment date", "check date", "date paid",
}
_DATE_ALIASES = {
    "date", "transaction date", "trans date", "trans. date", "invoice date",
    "bill date", "gl date", "created date", "activity date",
}
_DEBIT_ALIASES = {
    "debit", "debit amount", "withdrawal", "withdrawals", "charge", "charges",
    "out", "dr", "dr.", "debits", "money out", "payments", "disbursement",
    "disbursements",
}
_CREDIT_ALIASES = {
    "credit", "credit amount", "deposit", "deposits", "payment", "in", "cr",
    "cr.", "credits", "money in", "receipts",
}
_AMOUNT_ALIASES = {
    "amount", "transaction amount", "net amount", "value", "transaction value",
    "net", "invoice amount", "amount due", "bill amount", "gl amount",
    "total amount", "total",
}
_VENDOR_ALIASES = {
    "vendor name", "vendor", "payee", "merchant", "merchant name",
    "company name", "supplier", "supplier name", "paid to",
}
_INVOICE_NUMBER_ALIASES = {
    "invoice", "invoice number", "invoice #", "invoice no", "invoice no.",
    "bill number", "doc number", "document number",
}
_CUSTOMER_REF_ALIASES = {
    "customer ref", "customer reference", "reference", "ref", "ref number",
    "ref #", "transaction ref", "trace number",
}
_ACCOUNT_NUMBER_ALIASES = {
    "account number", "accountnumber", "acct number", "acct #",
    "bank account number",
}
_DESCRIPTION_ALIASES = {
    "description", "memo", "memo 1", "memo1", "narrative", "payee",
    "transaction description", "bai description", "remarks", "particulars",
    "name", "transaction narrative",
}
_DETAIL_ALIASES = {
    "detail", "memo 2", "memo2", "additional detail", "transaction detail",
    "check stub notes", "notes",
}
_STATUS_ALIASES = {"status", "payment status", "invoice status"}
_CHECK_NUMBER_ALIASES = {"check number", "check #", "check no", "check no.", "chk #"}

_CREDIT_MEMO_KEYWORDS = ("credit memo", "refund", "reversal", "credit note", "reimbursement")
_TRANSFER_KEYWORDS = ("transfer", "reserve", "operating", "xfer", "online transfer", "funds transfer")
_VENDOR_SUFFIXES = {"inc", "llc", "co", "corp", "corporation", "company", "ltd", "llp", "pc"}

_INVOICE_FILENAME_HINTS = ("invoice", "payable", "ap export", "bills")
_RESERVE_FILENAME_HINTS = ("reserve", "savings", "capital reserve")
_OPERATING_FILENAME_HINTS = ("operating", "checking", "general fund")


# ── normalized record ───────────────────────────────────────────────────────

@dataclass
class NormalizedFinancialRecord:
    id: str
    source_file: str
    source_type: SourceType
    date: date_cls | None
    post_date: date_cls | None
    amount: Decimal
    debit: Decimal | None
    credit: Decimal | None
    description: str | None
    detail: str | None
    vendor_name: str | None
    invoice_number: str | None
    customer_ref: str | None
    account_number: str | None
    raw_row: dict
    due_date: date_cls | None = None
    paid_date: date_cls | None = None
    status: str | None = None
    check_number: str | None = None

    def effective_date(self) -> date_cls | None:
        return self.date or self.post_date or self.due_date

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "source_file": self.source_file,
            "source_type": self.source_type,
            "date": self.date.isoformat() if self.date else None,
            "post_date": self.post_date.isoformat() if self.post_date else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "amount": float(self.amount),
            "debit": float(self.debit) if self.debit is not None else None,
            "credit": float(self.credit) if self.credit is not None else None,
            "description": self.description,
            "detail": self.detail,
            "vendor_name": self.vendor_name,
            "invoice_number": self.invoice_number,
            "customer_ref": self.customer_ref,
            "account_number": self.account_number,
            "status": self.status,
            "check_number": self.check_number,
            "raw_row": self.raw_row,
        }


@dataclass
class FinancialMatch:
    match_type: Literal["invoice_payment_match", "internal_transfer", "same_account_reversal"]
    confidence: Confidence
    amount: Decimal
    should_double_count: bool
    reason: str
    invoice_record_id: str | None = None
    bank_record_id: str | None = None
    from_record_id: str | None = None
    to_record_id: str | None = None
    net_effect: Decimal | None = None
    should_count_as_income: bool | None = None
    should_count_as_expense: bool | None = None

    def to_dict(self) -> dict:
        result = {
            "match_type": self.match_type,
            "confidence": self.confidence,
            "amount": float(self.amount),
            "should_double_count": self.should_double_count,
            "reason": self.reason,
        }
        if self.match_type == "invoice_payment_match":
            result["invoice_record_id"] = self.invoice_record_id
            result["bank_record_id"] = self.bank_record_id
        else:
            result["from_record_id"] = self.from_record_id
            result["to_record_id"] = self.to_record_id
            result["net_effect"] = float(self.net_effect) if self.net_effect is not None else 0.0
            result["should_count_as_income"] = self.should_count_as_income
            result["should_count_as_expense"] = self.should_count_as_expense
        return result


@dataclass
class FinancialReviewFlag:
    flag_type: str
    confidence: Confidence
    record_ids: list[str]
    amount: Decimal | None
    reason: str
    should_double_count: bool

    def to_dict(self) -> dict:
        return {
            "flag_type": self.flag_type,
            "confidence": self.confidence,
            "record_ids": self.record_ids,
            "amount": float(self.amount) if self.amount is not None else None,
            "reason": self.reason,
            "should_double_count": self.should_double_count,
        }


@dataclass
class ReconciliationSummary:
    total_income: Decimal
    total_expenses: Decimal
    net_cash_flow: Decimal
    operating_net: Decimal
    reserve_net: Decimal
    internal_transfer_total: Decimal
    matched_invoice_count: int
    unmatched_invoice_count: int
    exact_duplicate_count: int
    possible_duplicate_count: int

    def to_dict(self) -> dict:
        return {
            "total_income": float(self.total_income),
            "total_expenses": float(self.total_expenses),
            "net_cash_flow": float(self.net_cash_flow),
            "operating_net": float(self.operating_net),
            "reserve_net": float(self.reserve_net),
            "internal_transfer_total": float(self.internal_transfer_total),
            "matched_invoice_count": self.matched_invoice_count,
            "unmatched_invoice_count": self.unmatched_invoice_count,
            "exact_duplicate_count": self.exact_duplicate_count,
            "possible_duplicate_count": self.possible_duplicate_count,
        }


@dataclass
class ReconciliationResult:
    normalized_records: list[NormalizedFinancialRecord]
    duplicate_flags: list[FinancialReviewFlag]
    reconciliation_matches: list[FinancialMatch]
    summary: ReconciliationSummary
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "normalized_records": [r.to_dict() for r in self.normalized_records],
            "duplicate_flags": [f.to_dict() for f in self.duplicate_flags],
            "reconciliation_matches": [m.to_dict() for m in self.reconciliation_matches],
            "summary": self.summary.to_dict(),
            "warnings": self.warnings,
        }


@dataclass
class FileParseResult:
    records: list[NormalizedFinancialRecord]
    warnings: list[str]
    skipped_rows: int
    source_type: SourceType
    detected_columns: dict[str, str]


# ── helpers ──────────────────────────────────────────────────────────────

def _normalize_header(header: str) -> str:
    return re.sub(r"\s+", " ", header.strip().lower())


def normalize_vendor_name(name: str | None) -> str:
    if not name:
        return ""
    lowered = re.sub(r"[^\w\s]", " ", name.lower())
    tokens = [t for t in lowered.split() if t not in _VENDOR_SUFFIXES]
    return " ".join(tokens).strip()


def _vendor_match_strength(vendor_name: str | None, bank_text: str) -> Literal["strong", "weak", "none"]:
    normalized_vendor = normalize_vendor_name(vendor_name)
    normalized_bank = normalize_vendor_name(bank_text)
    if not normalized_vendor or not normalized_bank:
        return "none"
    if normalized_vendor in normalized_bank:
        return "strong"
    significant_tokens = [t for t in normalized_vendor.split() if len(t) >= 4]
    if significant_tokens and any(t in normalized_bank for t in significant_tokens):
        return "strong"
    ratio = SequenceMatcher(None, normalized_vendor, normalized_bank).ratio()
    return "weak" if ratio >= 0.55 else "none"


def _business_days_between(first: date_cls, second: date_cls) -> int:
    start, end = (first, second) if first <= second else (second, first)
    days = 0
    current = start
    while current < end:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days += 1
    return days


def _record_text(record: NormalizedFinancialRecord) -> str:
    return " ".join(filter(None, [record.description, record.detail])).lower()


def detect_source_type(filename: str, headers: list[str]) -> SourceType:
    lower_name = filename.lower()
    if any(hint in lower_name for hint in _INVOICE_FILENAME_HINTS):
        return "invoice_export"
    if any(hint in lower_name for hint in _RESERVE_FILENAME_HINTS):
        return "reserve_activity"
    if any(hint in lower_name for hint in _OPERATING_FILENAME_HINTS):
        return "operating_activity"

    normalized_headers = {_normalize_header(h) for h in headers}
    if "invoice" in normalized_headers or (
        "vendor name" in normalized_headers and "amount" in normalized_headers
    ):
        return "invoice_export"
    return "unknown"


def _build_column_map(headers: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for header in headers:
        norm = _normalize_header(header)
        if not norm:
            continue
        if norm in _POST_DATE_ALIASES and "post_date" not in result:
            result["post_date"] = header
        elif norm in _DUE_DATE_ALIASES and "due_date" not in result:
            result["due_date"] = header
        elif norm in _PAID_DATE_ALIASES and "paid_date" not in result:
            result["paid_date"] = header
        elif norm in _DATE_ALIASES and "date" not in result:
            result["date"] = header
        elif norm in _DEBIT_ALIASES and "debit" not in result:
            result["debit"] = header
        elif norm in _CREDIT_ALIASES and "credit" not in result:
            result["credit"] = header
        elif norm in _AMOUNT_ALIASES and "amount" not in result:
            result["amount"] = header
        elif norm in _INVOICE_NUMBER_ALIASES and "invoice_number" not in result:
            result["invoice_number"] = header
        elif norm in _CUSTOMER_REF_ALIASES and "customer_ref" not in result:
            result["customer_ref"] = header
        elif norm in _ACCOUNT_NUMBER_ALIASES and "account_number" not in result:
            result["account_number"] = header
        elif norm in _VENDOR_ALIASES and "vendor_name" not in result:
            result["vendor_name"] = header
        elif norm in _DESCRIPTION_ALIASES and "description" not in result:
            result["description"] = header
        elif norm in _DETAIL_ALIASES and "detail" not in result:
            result["detail"] = header
        elif norm in _STATUS_ALIASES and "status" not in result:
            result["status"] = header
        elif norm in _CHECK_NUMBER_ALIASES and "check_number" not in result:
            result["check_number"] = header
    return result


def _looks_like_credit(text: str) -> bool:
    return any(keyword in text for keyword in _CREDIT_MEMO_KEYWORDS)


def _resolve_amount(
    getter,
    col_map: dict[str, str],
    source_type: SourceType,
) -> tuple[Decimal, Decimal | None, Decimal | None] | None:
    if source_type == "invoice_export":
        if "amount" not in col_map:
            return None
        raw = _parse_amount(getter("amount"))
        if raw is None or raw == Decimal("0"):
            return None
        context = " ".join(filter(None, [getter("status"), getter("description"), getter("detail")])).lower()
        if _looks_like_credit(context):
            return abs(raw), None, abs(raw)
        return -abs(raw), abs(raw), None

    debit_val = _parse_amount(getter("debit")) if "debit" in col_map else None
    credit_val = _parse_amount(getter("credit")) if "credit" in col_map else None
    debit_nonzero = debit_val is not None and debit_val != Decimal("0")
    credit_nonzero = credit_val is not None and credit_val != Decimal("0")

    if debit_nonzero or credit_nonzero:
        amount = (credit_val or Decimal("0")) - (debit_val or Decimal("0"))
        return amount, (debit_val if debit_nonzero else None), (credit_val if credit_nonzero else None)

    if "amount" in col_map:
        raw = _parse_amount(getter("amount"))
        if raw is None or raw == Decimal("0"):
            return None
        return raw, (abs(raw) if raw < 0 else None), (raw if raw > 0 else None)

    return None


def _normalize_row(
    row: dict[str, str],
    col_map: dict[str, str],
    source_type: SourceType,
    source_file: str,
    record_id: str,
) -> NormalizedFinancialRecord | None:
    def get(field_name: str) -> str:
        col = col_map.get(field_name)
        return row.get(col, "").strip() if col else ""

    resolved = _resolve_amount(get, col_map, source_type)
    if resolved is None:
        return None
    amount, debit, credit = resolved

    return NormalizedFinancialRecord(
        id=record_id,
        source_file=source_file,
        source_type=source_type,
        date=_parse_date(get("date")) if "date" in col_map else None,
        post_date=_parse_date(get("post_date")) if "post_date" in col_map else None,
        due_date=_parse_date(get("due_date")) if "due_date" in col_map else None,
        paid_date=_parse_date(get("paid_date")) if "paid_date" in col_map else None,
        amount=amount,
        debit=debit,
        credit=credit,
        description=get("description") or None,
        detail=get("detail") or None,
        vendor_name=get("vendor_name") or None,
        invoice_number=get("invoice_number") or None,
        customer_ref=get("customer_ref") or None,
        account_number=get("account_number") or None,
        status=get("status") or None,
        check_number=get("check_number") or None,
        raw_row=dict(row),
    )


# ── part 1: normalization entry point ───────────────────────────────────────

def normalize_financial_csv(
    content: bytes,
    filename: str,
    source_type: SourceType | None = None,
) -> FileParseResult:
    text = _decode_csv(content)
    if text is None:
        return FileParseResult([], ["Could not decode CSV file as UTF-8 or Latin-1."], 0, source_type or "unknown", {})

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return FileParseResult([], ["CSV file has no headers."], 0, source_type or "unknown", {})

    headers = list(reader.fieldnames)
    resolved_type = source_type or detect_source_type(filename, headers)
    col_map = _build_column_map(headers)

    if "amount" not in col_map and "debit" not in col_map and "credit" not in col_map:
        warning = f"Could not detect amount, debit, or credit columns in '{filename}'. Found headers: {headers}"
        return FileParseResult([], [warning], 0, resolved_type, col_map)

    records: list[NormalizedFinancialRecord] = []
    skipped = 0
    for row_num, row in enumerate(reader, start=2):
        record_id = f"{filename}#{row_num}"
        normalized = _normalize_row(row, col_map, resolved_type, filename, record_id)
        if normalized is None:
            skipped += 1
            continue
        records.append(normalized)

    return FileParseResult(records, [], skipped, resolved_type, col_map)


# ── part 2: exact duplicates ────────────────────────────────────────────────

def _default_scope_key(record: NormalizedFinancialRecord) -> str:
    """Default duplicate-grouping scope: the file a row came from."""
    return record.source_file


def _account_scope_key(record: NormalizedFinancialRecord) -> str:
    """Duplicate-grouping scope for cross-import matching: the bank account a
    row belongs to (or blank for invoice/unrecognized rows), so a transaction
    re-appearing in a later export of the *same account* is still caught even
    though it's a different file.
    """
    return (record.account_number or "").strip().lower()


def _dedup_key(record: NormalizedFinancialRecord, scope_key_fn=_default_scope_key) -> tuple:
    effective_date = record.effective_date()
    return (
        scope_key_fn(record),
        effective_date.isoformat() if effective_date else None,
        str(record.amount.quantize(Decimal("0.01"))),
        (record.description or "").strip().lower(),
        (record.customer_ref or "").strip().lower(),
        (record.account_number or "").strip().lower(),
    )


def find_exact_duplicates(
    records: list[NormalizedFinancialRecord],
    scope_key_fn=_default_scope_key,
) -> list[FinancialReviewFlag]:
    groups: dict[tuple, list[NormalizedFinancialRecord]] = {}
    for record in records:
        groups.setdefault(_dedup_key(record, scope_key_fn), []).append(record)

    flags: list[FinancialReviewFlag] = []
    for key, group in groups.items():
        # require a real date and description before treating rows as duplicates —
        # blank/unparsed rows sharing "empty" keys are not evidence of duplication.
        if len(group) < 2 or key[1] is None or not key[3]:
            continue
        flags.append(FinancialReviewFlag(
            flag_type="exact_duplicate",
            confidence="high",
            record_ids=[r.id for r in group],
            amount=group[0].amount,
            reason=(
                f"This row appears to be an exact duplicate because the date, amount, "
                f"description, reference number, and account number are identical to "
                f"{len(group) - 1} other already-recorded row(s)."
            ),
            should_double_count=False,
        ))
    return flags


def _duplicate_extra_ids(exact_duplicate_flags: list[FinancialReviewFlag]) -> set[str]:
    excluded: set[str] = set()
    for flag in exact_duplicate_flags:
        for record_id in flag.record_ids[1:]:
            excluded.add(record_id)
    return excluded


# ── part 6 (partial): possible duplicates ───────────────────────────────────

def find_possible_duplicates(
    records: list[NormalizedFinancialRecord],
    scope_key_fn=_default_scope_key,
) -> list[FinancialReviewFlag]:
    groups: dict[tuple, list[NormalizedFinancialRecord]] = {}
    for record in records:
        effective_date = record.effective_date()
        if effective_date is None:
            continue
        key = (scope_key_fn(record), effective_date.isoformat(), str(record.amount.quantize(Decimal("0.01"))))
        groups.setdefault(key, []).append(record)

    flags: list[FinancialReviewFlag] = []
    seen_pairs: set[tuple[str, str]] = set()
    for group in groups.values():
        if len(group) < 2:
            continue
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                first, second = group[i], group[j]
                if _dedup_key(first, scope_key_fn) == _dedup_key(second, scope_key_fn):
                    continue  # already an exact duplicate
                desc_a = (first.description or "").strip().lower()
                desc_b = (second.description or "").strip().lower()
                if not desc_a or not desc_b:
                    continue
                if SequenceMatcher(None, desc_a, desc_b).ratio() < 0.9:
                    continue
                pair_key = tuple(sorted((first.id, second.id)))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                flags.append(FinancialReviewFlag(
                    flag_type="possible_duplicate_same_amount_date",
                    confidence="medium",
                    record_ids=[first.id, second.id],
                    amount=first.amount,
                    reason=(
                        f"These rows share the same date and amount and have very similar "
                        f"descriptions, but different reference numbers — this may be a "
                        f"duplicate, but it has not been merged automatically."
                    ),
                    should_double_count=True,
                ))
    return flags


# ── part 3: invoice-to-bank-payment matching ────────────────────────────────

def _invoice_match_reason(
    confidence: Confidence,
    exact_amount: bool,
    date_in_window: bool,
    vendor_strength: Literal["strong", "weak", "none"],
) -> str:
    amount_desc = "the same amount" if exact_amount else "a very close amount"
    vendor_desc = {
        "strong": "similar vendor names",
        "weak": "a vendor name that partially matches",
        "none": "no vendor confirmation in the bank description",
    }[vendor_strength]
    date_desc = "within the expected payment window" if date_in_window else "outside the usual payment window"
    return (
        f"This invoice was matched to a bank payment ({confidence} confidence) because the "
        f"bank record has {amount_desc}, {vendor_desc}, and the payment date is {date_desc} "
        f"relative to the invoice date."
    )


_CONFIDENCE_RANK = {"high": 2, "medium": 1, "low": 0}


def match_invoices_to_bank_payments(
    invoices: list[NormalizedFinancialRecord],
    bank_records: list[NormalizedFinancialRecord],
    date_window_days: int = 45,
) -> tuple[list[FinancialMatch], list[FinancialReviewFlag]]:
    matches: list[FinancialMatch] = []
    review_flags: list[FinancialReviewFlag] = []
    consumed_bank_ids: set[str] = set()
    payment_candidates = [b for b in bank_records if b.amount < 0]

    for invoice in invoices:
        invoice_amount = abs(invoice.amount)
        best: tuple[Confidence, NormalizedFinancialRecord, str] | None = None
        best_rank = -1

        for bank in payment_candidates:
            if bank.id in consumed_bank_ids:
                continue
            bank_amount = abs(bank.amount)
            bank_date = bank.effective_date()

            exact_amount = abs(bank_amount - invoice_amount) <= Decimal("0.01")
            close_amount = (not exact_amount) and abs(bank_amount - invoice_amount) <= max(
                Decimal("1.00"), invoice_amount * Decimal("0.02")
            )
            if not exact_amount and not close_amount:
                continue

            date_in_window = False
            if bank_date is not None:
                if invoice.date is not None and invoice.date <= bank_date <= invoice.date + timedelta(days=date_window_days):
                    date_in_window = True
                if not date_in_window and invoice.due_date is not None and (
                    invoice.due_date - timedelta(days=10) <= bank_date <= invoice.due_date + timedelta(days=date_window_days)
                ):
                    date_in_window = True

            vendor_strength = _vendor_match_strength(invoice.vendor_name, _record_text(bank))

            if exact_amount and date_in_window:
                confidence: Confidence = "high" if vendor_strength == "strong" else "medium"
            elif (exact_amount and not date_in_window) or (close_amount and (date_in_window or vendor_strength != "none")):
                confidence = "low"
            else:
                continue

            rank = _CONFIDENCE_RANK[confidence]
            if rank > best_rank:
                best_rank = rank
                reason = _invoice_match_reason(confidence, exact_amount, date_in_window, vendor_strength)
                best = (confidence, bank, reason)

        if best is None:
            review_flags.append(FinancialReviewFlag(
                flag_type="unmatched_invoice",
                confidence="medium",
                record_ids=[invoice.id],
                amount=invoice.amount,
                reason=(
                    f"No bank payment was found matching invoice "
                    f"{invoice.invoice_number or invoice.id} for "
                    f"{invoice.vendor_name or 'an unknown vendor'} (amount {invoice_amount})."
                ),
                should_double_count=True,
            ))
            continue

        confidence, bank, reason = best
        if confidence in ("high", "medium"):
            matches.append(FinancialMatch(
                match_type="invoice_payment_match",
                confidence=confidence,
                amount=invoice_amount,
                should_double_count=False,
                reason=reason,
                invoice_record_id=invoice.id,
                bank_record_id=bank.id,
            ))
            consumed_bank_ids.add(bank.id)
        else:
            review_flags.append(FinancialReviewFlag(
                flag_type="possible_invoice_payment_match",
                confidence="low",
                record_ids=[invoice.id, bank.id],
                amount=invoice_amount,
                reason=reason,
                should_double_count=True,
            ))

    return matches, review_flags


# ── part 4: internal transfer matching ──────────────────────────────────────

def match_internal_transfers(
    operating_records: list[NormalizedFinancialRecord],
    reserve_records: list[NormalizedFinancialRecord],
    max_business_days: int = 3,
    excluded_ids: set[str] = frozenset(),
) -> tuple[list[FinancialMatch], list[FinancialReviewFlag]]:
    """`excluded_ids` lets a caller keep a record out of transfer-pairing —

    used so a leg already explained by `match_same_account_reversals` (an
    external deposit misdirected into the wrong account, then corrected) isn't
    ALSO paired here as a deliberate operating<->reserve fund transfer. If it
    were, the *other* leg of that "transfer" (e.g. the operating side
    receiving the corrected funds) would be wrongly excluded from income too.
    """
    matches: list[FinancialMatch] = []
    review_flags: list[FinancialReviewFlag] = []
    consumed_reserve_ids: set[str] = set()

    operating_candidates = [r for r in operating_records if r.amount != Decimal("0") and r.id not in excluded_ids]
    reserve_candidates = [r for r in reserve_records if r.amount != Decimal("0") and r.id not in excluded_ids]

    for operating in operating_candidates:
        operating_date = operating.effective_date()
        best: tuple[Confidence, NormalizedFinancialRecord, bool, int] | None = None
        best_rank = -1

        for reserve in reserve_candidates:
            if reserve.id in consumed_reserve_ids:
                continue
            if abs(operating.amount + reserve.amount) > Decimal("0.01"):
                continue  # not equal-and-opposite

            reserve_date = reserve.effective_date()
            if operating_date is None or reserve_date is None:
                continue
            business_days = _business_days_between(operating_date, reserve_date)
            if business_days > max_business_days:
                continue

            combined_text = _record_text(operating) + " " + _record_text(reserve)
            has_keyword = any(keyword in combined_text for keyword in _TRANSFER_KEYWORDS)

            if business_days == 0:
                confidence: Confidence = "high" if has_keyword else "medium"
            else:
                confidence = "medium" if has_keyword else "low"

            rank = _CONFIDENCE_RANK[confidence]
            if rank > best_rank:
                best_rank = rank
                best = (confidence, reserve, has_keyword, business_days)

        if best is None:
            continue

        confidence, reserve, has_keyword, business_days = best
        amount = abs(operating.amount)
        reason = (
            f"This appears to be an internal transfer because the operating account "
            f"{'decreased' if operating.amount < 0 else 'increased'} by {amount} and the "
            f"reserve account {'increased' if reserve.amount > 0 else 'decreased'} by "
            f"{amount} "
            + ("on the same date" if business_days == 0 else f"within {business_days} business day(s)")
            + (", and the transaction descriptions reference a transfer" if has_keyword else "")
            + "."
        )

        if confidence in ("high", "medium"):
            matches.append(FinancialMatch(
                match_type="internal_transfer",
                confidence=confidence,
                amount=amount,
                should_double_count=False,
                reason=reason,
                from_record_id=operating.id if operating.amount < 0 else reserve.id,
                to_record_id=reserve.id if operating.amount < 0 else operating.id,
                net_effect=Decimal("0"),
                should_count_as_income=False,
                should_count_as_expense=False,
            ))
            consumed_reserve_ids.add(reserve.id)
        else:
            review_flags.append(FinancialReviewFlag(
                flag_type="possible_internal_transfer",
                confidence="low",
                record_ids=[operating.id, reserve.id],
                amount=amount,
                reason=reason,
                should_double_count=True,
            ))

    return matches, review_flags


# ── same-account reversal matching ──────────────────────────────────────────
# A deposit that lands in the wrong account and gets corrected a few days later
# by an equal-and-opposite entry in that SAME account (e.g. "misdirected
# deposit, moved back out") isn't income or an expense — it's a wash. This is
# distinct from match_internal_transfers, which pairs opposite legs across the
# operating/reserve accounts; here both legs are in the same physical account.
#
# Deliberately conservative: requires an explicit reversal/correction keyword
# in the transaction text before ever matching, rather than amount+date alone
# — recurring assessment payments share round-number amounts (e.g. $275/$550)
# constantly, and matching on amount+date proximity alone would misfire on them.
_REVERSAL_KEYWORDS = (
    "error", "correction", "corrected", "revers", "returned", "return",
    "book transfer", "move to", "misapplied", "misdirected", "void",
)


def match_same_account_reversals(
    bank_records: list[NormalizedFinancialRecord],
    consumed_ids: set[str],
    max_days: int = 14,
) -> tuple[list[FinancialMatch], list[FinancialReviewFlag]]:
    matches: list[FinancialMatch] = []
    review_flags: list[FinancialReviewFlag] = []
    consumed: set[str] = set()

    by_account: dict[str, list[NormalizedFinancialRecord]] = {}
    for record in bank_records:
        if record.id in consumed_ids or record.amount == Decimal("0"):
            continue
        account_key = (record.account_number or "").strip().lower()
        if not account_key:
            continue
        by_account.setdefault(account_key, []).append(record)

    for records in by_account.values():
        ordered = sorted(records, key=lambda r: r.effective_date() or date_cls.min)
        for i, first in enumerate(ordered):
            if first.id in consumed:
                continue
            first_date = first.effective_date()
            if first_date is None:
                continue

            for second in ordered[i + 1:]:
                if second.id in consumed:
                    continue
                second_date = second.effective_date()
                if second_date is None:
                    continue
                days_apart = (second_date - first_date).days
                if days_apart > max_days:
                    break  # ordered by date — no later record will be closer
                if abs(first.amount + second.amount) > Decimal("0.01"):
                    continue  # not equal-and-opposite

                combined_text = _record_text(first) + " " + _record_text(second)
                if not any(keyword in combined_text for keyword in _REVERSAL_KEYWORDS):
                    continue  # no reversal/correction language — too risky to match

                confidence: Confidence = "high" if days_apart <= 5 else "medium"
                amount = abs(first.amount)
                reason = (
                    f"This appears to be a same-account correction, not real income or an "
                    f"expense: a {'deposit' if first.amount > 0 else 'debit'} of {amount} was "
                    f"reversed by an equal-and-opposite entry {days_apart} day(s) later in the "
                    f"same account, and the transaction text references a correction."
                )
                matches.append(FinancialMatch(
                    match_type="same_account_reversal",
                    confidence=confidence,
                    amount=amount,
                    should_double_count=False,
                    reason=reason,
                    from_record_id=first.id,
                    to_record_id=second.id,
                    net_effect=Decimal("0"),
                    should_count_as_income=False,
                    should_count_as_expense=False,
                ))
                consumed.add(first.id)
                consumed.add(second.id)
                break

    return matches, review_flags


# ── part 6 (remaining): unmatched bank check payments ───────────────────────

def find_unmatched_check_payments(
    bank_records: list[NormalizedFinancialRecord],
    consumed_ids: set[str],
) -> list[FinancialReviewFlag]:
    flags: list[FinancialReviewFlag] = []
    for record in bank_records:
        if record.id in consumed_ids or record.amount >= 0:
            continue
        text = _record_text(record)
        if "check" not in text and "chk" not in text:
            continue
        effective_date = record.effective_date()
        flags.append(FinancialReviewFlag(
            flag_type="unmatched_bank_payment",
            confidence="low",
            record_ids=[record.id],
            amount=record.amount,
            reason=(
                f"This check payment of {abs(record.amount)} in {record.source_file} on "
                f"{effective_date.isoformat() if effective_date else 'an unknown date'} did "
                f"not match any invoice record and may need a corresponding bill entered."
            ),
            should_double_count=True,
        ))
    return flags


# ── parts 5 & 9: summary and orchestration ──────────────────────────────────

def _build_summary(
    records: list[NormalizedFinancialRecord],
    matches: list[FinancialMatch],
    flags: list[FinancialReviewFlag],
    duplicate_exclusion_ids: set[str],
) -> ReconciliationSummary:
    transfer_leg_ids: set[str] = set()
    internal_transfer_total = Decimal("0")
    for match in matches:
        if match.match_type in ("internal_transfer", "same_account_reversal"):
            transfer_leg_ids.add(match.from_record_id)
            transfer_leg_ids.add(match.to_record_id)
            internal_transfer_total += match.amount

    def counted_records(source_types: set[SourceType]) -> list[NormalizedFinancialRecord]:
        return [
            r for r in records
            if r.source_type in source_types and r.id not in duplicate_exclusion_ids
        ]

    bank_records = counted_records({"operating_activity", "reserve_activity", "unknown"})
    income_records = [r for r in bank_records if r.amount > 0 and r.id not in transfer_leg_ids]
    expense_records = [r for r in bank_records if r.amount < 0 and r.id not in transfer_leg_ids]

    total_income = sum((r.amount for r in income_records), Decimal("0"))
    total_expenses = sum((abs(r.amount) for r in expense_records), Decimal("0"))

    operating_net = sum((r.amount for r in counted_records({"operating_activity"})), Decimal("0"))
    reserve_net = sum((r.amount for r in counted_records({"reserve_activity"})), Decimal("0"))

    matched_invoice_ids = {m.invoice_record_id for m in matches if m.match_type == "invoice_payment_match"}
    invoice_records = [r for r in records if r.source_type == "invoice_export"]
    matched_invoice_count = sum(1 for r in invoice_records if r.id in matched_invoice_ids)
    unmatched_invoice_count = len(invoice_records) - matched_invoice_count

    possible_duplicate_count = sum(
        1 for f in flags if f.flag_type == "possible_duplicate_same_amount_date"
    )

    return ReconciliationSummary(
        total_income=total_income,
        total_expenses=total_expenses,
        net_cash_flow=total_income - total_expenses,
        operating_net=operating_net,
        reserve_net=reserve_net,
        internal_transfer_total=internal_transfer_total,
        matched_invoice_count=matched_invoice_count,
        unmatched_invoice_count=unmatched_invoice_count,
        exact_duplicate_count=len(duplicate_exclusion_ids),
        possible_duplicate_count=possible_duplicate_count,
    )


def reconcile_financial_files(
    files: list[tuple[str, bytes]],
    source_types: dict[str, SourceType] | None = None,
) -> ReconciliationResult:
    """Normalize and reconcile a batch of HOA financial CSV files.

    `files` is a list of (filename, raw_bytes) tuples. `source_types` can force
    the source type for a given filename instead of relying on detection.
    """
    all_records: list[NormalizedFinancialRecord] = []
    warnings: list[str] = []

    for filename, content in files:
        forced_type = (source_types or {}).get(filename)
        parsed = normalize_financial_csv(content, filename, source_type=forced_type)
        all_records.extend(parsed.records)
        warnings.extend(parsed.warnings)

    exact_duplicate_flags = find_exact_duplicates(all_records)
    duplicate_exclusion_ids = _duplicate_extra_ids(exact_duplicate_flags)
    possible_duplicate_flags = find_possible_duplicates(all_records)

    invoices = [r for r in all_records if r.source_type == "invoice_export"]
    operating = [r for r in all_records if r.source_type == "operating_activity"]
    reserve = [r for r in all_records if r.source_type == "reserve_activity"]
    other_bank = [r for r in all_records if r.source_type == "unknown"]
    bank_records = operating + reserve + other_bank

    # same-account reversals are resolved FIRST: if a leg is really the
    # correction of a misdirected external deposit (not the HOA deliberately
    # moving its own money), it must not also be treated as an
    # internal_transfer leg — that would wrongly exclude the OTHER account's
    # matching entry (e.g. the operating side actually receiving new income)
    # from income/expense too.
    reversal_matches, reversal_flags = match_same_account_reversals(bank_records, duplicate_exclusion_ids)
    reversal_consumed_ids: set[str] = set()
    for match in reversal_matches:
        reversal_consumed_ids.add(match.from_record_id)
        reversal_consumed_ids.add(match.to_record_id)

    invoice_bank_pool = [r for r in bank_records if r.id not in reversal_consumed_ids]
    invoice_matches, invoice_flags = match_invoices_to_bank_payments(invoices, invoice_bank_pool)
    transfer_matches, transfer_flags = match_internal_transfers(
        operating, reserve, excluded_ids=reversal_consumed_ids,
    )

    consumed_ids = set(duplicate_exclusion_ids) | reversal_consumed_ids
    for match in invoice_matches:
        consumed_ids.add(match.invoice_record_id)
        consumed_ids.add(match.bank_record_id)
    for match in transfer_matches:
        consumed_ids.add(match.from_record_id)
        consumed_ids.add(match.to_record_id)
    for flag in invoice_flags + transfer_flags:
        consumed_ids.update(flag.record_ids)

    unmatched_bank_flags = find_unmatched_check_payments(bank_records, consumed_ids)

    all_flags = (
        exact_duplicate_flags + possible_duplicate_flags + invoice_flags
        + transfer_flags + reversal_flags + unmatched_bank_flags
    )
    all_matches = invoice_matches + transfer_matches + reversal_matches

    summary = _build_summary(all_records, all_matches, all_flags, duplicate_exclusion_ids)

    return ReconciliationResult(
        normalized_records=all_records,
        duplicate_flags=all_flags,
        reconciliation_matches=all_matches,
        summary=summary,
        warnings=warnings,
    )


# ── cross-import history matching ───────────────────────────────────────────
# Reconciles freshly-normalized records against transactions already committed
# from EARLIER imports, so overlaps are caught even when related files (e.g.
# an invoice export and the operating-account export that pays it) are
# imported weeks apart rather than in the same batch.

@dataclass
class HistoryReconciliationResult:
    matches: list[FinancialMatch]
    flags: list[FinancialReviewFlag]
    exact_duplicate_new_ids: set[str]
    invoice_matched_new_ids: set[str]
    transfer_new_ids: set[str]
    # existing (already-committed) transaction ids whose transaction_type should
    # be retroactively updated to "transfer" now that their pair has arrived —
    # unlike duplicate/invoice exclusion, this never deletes a committed row.
    transfer_existing_ids_to_reclassify: set[str]


def existing_record_from_transaction(
    transaction_id: str,
    date_value: date_cls,
    amount: Decimal,
    description: str | None,
    vendor_name: str | None,
    source_type: SourceType | None,
    external_ref: str | None,
    external_account_number: str | None,
) -> NormalizedFinancialRecord:
    """Build a NormalizedFinancialRecord standing in for an already-committed
    transaction, so it can be matched against newly-imported rows using the
    same logic used within a single import batch.
    """
    return NormalizedFinancialRecord(
        id=f"tx:{transaction_id}",
        source_file="existing",
        source_type=source_type or "unknown",
        date=date_value,
        post_date=None,
        amount=amount,
        debit=None,
        credit=None,
        description=description,
        detail=None,
        vendor_name=vendor_name,
        invoice_number=None,
        customer_ref=external_ref,
        account_number=external_account_number,
        raw_row={},
    )


def reconcile_against_history(
    new_records: list[NormalizedFinancialRecord],
    existing_records: list[NormalizedFinancialRecord],
) -> HistoryReconciliationResult:
    """Match freshly-normalized `new_records` against `existing_records` already
    committed from earlier imports. Only returns matches/flags involving at
    least one new record — pairs entirely within `new_records` are the job of
    `reconcile_financial_files`, and pairs entirely within `existing_records`
    were (or should have been) resolved when they were originally imported.
    """
    new_ids = {r.id for r in new_records}
    combined = new_records + existing_records

    exact_duplicate_flags = [
        flag for flag in find_exact_duplicates(combined, scope_key_fn=_account_scope_key)
        if any(rid in new_ids for rid in flag.record_ids)
    ]
    # only the NEW half of an exact-duplicate group is ever excluded — an
    # already-committed transaction is never re-flagged for removal.
    exact_duplicate_new_ids = {
        rid for flag in exact_duplicate_flags for rid in flag.record_ids if rid in new_ids
    }

    possible_duplicate_flags = [
        flag for flag in find_possible_duplicates(combined, scope_key_fn=_account_scope_key)
        if any(rid in new_ids for rid in flag.record_ids)
    ]

    # invoice arrives after its bank payment: exclude the new invoice, the
    # existing bank payment already represents the cash.
    new_invoices = [r for r in new_records if r.source_type == "invoice_export"]
    existing_bank = [
        r for r in existing_records
        if r.source_type in ("operating_activity", "reserve_activity", "unknown")
    ]
    invoice_after_matches, invoice_after_flags = match_invoices_to_bank_payments(new_invoices, existing_bank)
    invoice_matched_new_ids = {m.invoice_record_id for m in invoice_after_matches}

    # bank payment arrives after its invoice: exclude the new bank payment, the
    # existing invoice already represents the same expense.
    existing_invoices = [r for r in existing_records if r.source_type == "invoice_export"]
    new_bank = [
        r for r in new_records
        if r.source_type in ("operating_activity", "reserve_activity", "unknown")
    ]
    invoice_before_matches, invoice_before_flags = match_invoices_to_bank_payments(existing_invoices, new_bank)
    invoice_matched_new_ids |= {m.bank_record_id for m in invoice_before_matches}

    invoice_matches = invoice_after_matches + invoice_before_matches
    invoice_flags = invoice_after_flags + invoice_before_flags

    new_operating = [r for r in new_records if r.source_type == "operating_activity"]
    new_reserve = [r for r in new_records if r.source_type == "reserve_activity"]
    existing_operating = [r for r in existing_records if r.source_type == "operating_activity"]
    existing_reserve = [r for r in existing_records if r.source_type == "reserve_activity"]

    raw_transfer_matches, raw_transfer_flags = match_internal_transfers(
        new_operating + existing_operating, new_reserve + existing_reserve,
    )
    # keep only pairs with exactly one new leg — new+new was already handled by
    # reconcile_financial_files, and existing+existing isn't actionable here.
    transfer_matches = [
        m for m in raw_transfer_matches
        if (m.from_record_id in new_ids) != (m.to_record_id in new_ids)
    ]
    transfer_flags = [
        f for f in raw_transfer_flags
        if len(f.record_ids) == 2 and (f.record_ids[0] in new_ids) != (f.record_ids[1] in new_ids)
    ]
    transfer_new_ids: set[str] = set()
    transfer_existing_ids_to_reclassify: set[str] = set()
    for m in transfer_matches:
        if m.from_record_id in new_ids:
            transfer_new_ids.add(m.from_record_id)
            transfer_existing_ids_to_reclassify.add(m.to_record_id)
        else:
            transfer_new_ids.add(m.to_record_id)
            transfer_existing_ids_to_reclassify.add(m.from_record_id)

    return HistoryReconciliationResult(
        matches=invoice_matches + transfer_matches,
        flags=exact_duplicate_flags + possible_duplicate_flags + invoice_flags + transfer_flags,
        exact_duplicate_new_ids=exact_duplicate_new_ids,
        invoice_matched_new_ids=invoice_matched_new_ids,
        transfer_new_ids=transfer_new_ids,
        transfer_existing_ids_to_reclassify=transfer_existing_ids_to_reclassify,
    )
