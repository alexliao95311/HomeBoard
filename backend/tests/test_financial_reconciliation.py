from decimal import Decimal

from app.services.financial_reconciliation import reconcile_financial_files

_OPERATING_HEADER = "Post Date, Customer Ref, Debit, Credit, BAI Description, Detail, Account Number"
_RESERVE_HEADER = _OPERATING_HEADER
_INVOICE_HEADER = "Vendor Name,Amount,Invoice Date,Due Date,Status,Invoice,Reference,AccountNumber"


def _csv(header: str, *rows: str) -> bytes:
    return ("\n".join([header, *rows]) + "\n").encode("utf-8")


def _flags_of_type(result, flag_type):
    return [f for f in result.duplicate_flags if f.flag_type == flag_type]


def _matches_of_type(result, match_type):
    return [m for m in result.reconciliation_matches if m.match_type == match_type]


# ── Part 8.1: exact duplicate inside operating file ─────────────────────────

def test_exact_duplicate_inside_operating_file():
    content = _csv(
        _OPERATING_HEADER,
        '08/01/2025,"REF001",,500.00,"LOCKBOX DEPOSIT","","8050388751"',
        '08/01/2025,"REF001",,500.00,"LOCKBOX DEPOSIT","","8050388751"',
    )
    result = reconcile_financial_files([("operating_activity.csv", content)])

    exact_dups = _flags_of_type(result, "exact_duplicate")
    assert len(exact_dups) == 1
    assert exact_dups[0].confidence == "high"
    assert exact_dups[0].should_double_count is False
    assert len(exact_dups[0].record_ids) == 2

    assert result.summary.exact_duplicate_count == 1
    assert result.summary.total_income == Decimal("500.00")


# ── Part 8.2: invoice matched to operating bank payment ────────────────────

def test_invoice_matched_to_bank_payment():
    invoice_content = _csv(
        _INVOICE_HEADER,
        'ABC Landscaping,800.00,08/01/2025,08/20/2025,Paid,INV-100,,1234',
    )
    operating_content = _csv(
        _OPERATING_HEADER,
        '08/05/2025,"REF555",800.00,,"CHECK ABC LANDSCAPING","","8050388751"',
    )
    result = reconcile_financial_files([
        ("invoice_export.csv", invoice_content),
        ("operating_activity.csv", operating_content),
    ])

    matches = _matches_of_type(result, "invoice_payment_match")
    assert len(matches) == 1
    assert matches[0].confidence == "high"
    assert matches[0].should_double_count is False
    assert matches[0].amount == Decimal("800.00")

    assert result.summary.matched_invoice_count == 1
    assert result.summary.unmatched_invoice_count == 0
    # bank record is the source of truth for cash — the invoice must not add a second expense
    assert result.summary.total_expenses == Decimal("800.00")


# ── Part 8.3: invoice not matched (different amount) ────────────────────────

def test_invoice_not_matched_different_amount():
    invoice_content = _csv(
        _INVOICE_HEADER,
        'ABC Landscaping,800.00,08/01/2025,08/20/2025,Paid,INV-100,,1234',
    )
    operating_content = _csv(
        _OPERATING_HEADER,
        '08/05/2025,"REF555",950.00,,"CHECK ABC LANDSCAPING","","8050388751"',
    )
    result = reconcile_financial_files([
        ("invoice_export.csv", invoice_content),
        ("operating_activity.csv", operating_content),
    ])

    assert _matches_of_type(result, "invoice_payment_match") == []
    unmatched = _flags_of_type(result, "unmatched_invoice")
    assert len(unmatched) == 1
    assert result.summary.matched_invoice_count == 0
    assert result.summary.unmatched_invoice_count == 1


# ── Part 8.4: operating/reserve internal transfer ───────────────────────────

def test_operating_reserve_internal_transfer():
    operating_content = _csv(
        _OPERATING_HEADER,
        '08/10/2025,"XFER1",5000.00,,"TRANSFER TO RESERVE","","8050388751"',
    )
    reserve_content = _csv(
        _RESERVE_HEADER,
        '08/10/2025,"XFER1",,5000.00,"TRANSFER FROM OPERATING","","8410320037"',
    )
    result = reconcile_financial_files([
        ("operating_activity.csv", operating_content),
        ("reserve_activity.csv", reserve_content),
    ])

    transfers = _matches_of_type(result, "internal_transfer")
    assert len(transfers) == 1
    transfer = transfers[0]
    assert transfer.confidence == "high"
    assert transfer.net_effect == Decimal("0")
    assert transfer.should_count_as_income is False
    assert transfer.should_count_as_expense is False

    assert result.summary.internal_transfer_total == Decimal("5000.00")
    assert result.summary.total_income == Decimal("0")
    assert result.summary.total_expenses == Decimal("0")
    assert result.summary.operating_net == Decimal("-5000.00")
    assert result.summary.reserve_net == Decimal("5000.00")


# ── Part 8.5: similar deposits are not automatically duplicates ─────────────

def test_similar_deposits_are_not_duplicates():
    content = _csv(
        _OPERATING_HEADER,
        '07/29/2025,"000005250878292",,250.00,"LOCKBOX DEPOSIT","","8050388751"',
        '07/31/2025,"000005250118787",,250.00,"LOCKBOX DEPOSIT","","8050388751"',
        '08/04/2025,"000005250665779",,250.00,"LOCKBOX DEPOSIT","","8050388751"',
    )
    result = reconcile_financial_files([("operating_activity.csv", content)])

    assert _flags_of_type(result, "exact_duplicate") == []
    assert _flags_of_type(result, "possible_duplicate_same_amount_date") == []
    assert result.summary.exact_duplicate_count == 0
    assert result.summary.possible_duplicate_count == 0
    assert result.summary.total_income == Decimal("750.00")


# ── Part 8.6: same amount/date, different refs -> possible duplicate only

def test_same_amount_and_date_different_refs():
    content = _csv(
        _OPERATING_HEADER,
        '08/10/2025,"REF001",,300.00,"HOMEOWNER PAYMENT SMITH","","8050388751"',
        '08/10/2025,"REF002",,300.00,"HOMEOWNER PAYMENT SMITH","","8050388751"',
        '08/10/2025,"REF003",,300.00,"LATE FEE ADJUSTMENT","","8050388751"',
    )
    result = reconcile_financial_files([("operating_activity.csv", content)])

    # different refs -> not an exact duplicate, never auto-removed
    assert _flags_of_type(result, "exact_duplicate") == []

    possible = _flags_of_type(result, "possible_duplicate_same_amount_date")
    assert len(possible) == 1
    assert possible[0].should_double_count is True
    ids = set(possible[0].record_ids)
    assert ids == {"operating_activity.csv#2", "operating_activity.csv#3"}

    # both still counted — nothing silently removed
    assert result.summary.total_income == Decimal("900.00")


# ── extra: vendor normalization / column-alias flexibility ──────────────────

def test_normalizes_alternate_bank_column_names():
    # a differently-shaped bank export: single signed "Amount" column,
    # "Trans Date" instead of "Post Date", "Memo" instead of "BAI Description"
    content = (
        "Trans Date,Reference,Amount,Memo,Account\n"
        "09/01/2025,REF900,-125.50,ACH DEBIT UTILITY CO,555000111\n"
    ).encode("utf-8")
    result = reconcile_financial_files([("checking_export.csv", content)])

    assert len(result.normalized_records) == 1
    record = result.normalized_records[0]
    assert record.amount == Decimal("-125.50")
    assert record.description == "ACH DEBIT UTILITY CO"
    assert record.customer_ref == "REF900"
    assert record.source_type == "operating_activity"
