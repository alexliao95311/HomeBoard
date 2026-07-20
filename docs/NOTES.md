# HomeBoard — Build Notes

## Short Progress Report

The FastAPI and React/Vite foundation is complete. Docker runs the backend,
frontend, PostgreSQL, and Redis; Firebase provides Google authentication.
Authenticated document upload, document listing, text extraction, the
full contract-review API, AI provider abstraction with OpenRouter, the
contract review UI at `/contracts`, inline edit/delete of reviews, and a
dedicated per-review detail page at `/contracts/:id/review` with PDF export
are implemented. The financial module now covers transaction CSV import
(single-file and multi-file reconciled), manual transaction entry, rule-based
+ AI categorization, a reconciliation engine that catches cross-file
duplicate/invoice/transfer overlaps, and board-facing report generation with
a `/financial` Reports tab (now with a Budgets tab too, for simple manual
budget entry). Reconciliation now works incrementally across separate
imports, not just within one batch. Reports now include a fiscal-year-aware
Month/YTD/Annual-Budget comparison and Operating/Reserve fund sections,
modeled on a real professional HOA financial report. The current Alembic
revision is `20260717_0007`, and all 52 backend tests pass.

## Start the Project

From the repository root:

```bash
docker compose --env-file .env -f infra/docker-compose.yml up --build
```

| Service | Address |
|---|---|
| Frontend | <http://localhost:5173> |
| Backend | <http://localhost:8000> |
| API documentation | <http://localhost:8000/docs> |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

Stop the project with:

```bash
docker compose --env-file .env -f infra/docker-compose.yml down
```

## Completed Steps

### 1. Project Structure

- [x] Created the FastAPI backend.
- [x] Created the React, TypeScript, and Vite frontend.
- [x] Added the Docker Compose infrastructure and project documentation.
- [x] Standardized development ports: backend `8000`, frontend `5173`.

### 2. Backend Health Check

- [x] Added the FastAPI application metadata and CORS configuration.
- [x] Added `GET /health`, returning:

```json
{"status": "ok"}
```

Run outside Docker:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app
```

### 3. Frontend Health Check

- [x] Added the homepage and backend health display.
- [x] Added the TypeScript API client.

Run outside Docker:

```bash
cd frontend
npm install
npm run dev
```

### 4. Docker Compose

- [x] Added FastAPI, Vite, PostgreSQL 16, and Redis services.
- [x] Added simple backend and frontend Dockerfiles.
- [x] Configured services through the repository-root `.env`.
- [x] Installed backend packages inside a Python virtual environment in the
  backend image.

MinIO is **not used**. It was removed from the Docker stack. Firebase is the
selected managed provider for authentication and future cloud file storage.
The current document implementation stores files locally under
`backend/storage/uploads/`.

### 5. Database and Migrations

- [x] Added SQLAlchemy 2 models and session management.
- [x] Added Alembic migrations.
- [x] Added organizations, users, memberships, documents, and audit logs.
- [x] Docker applies `alembic upgrade head` before FastAPI starts.

Run migrations manually:

```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

### 6. Firebase Google Authentication

- [x] Replaced the originally planned local JWT/password flow with Firebase.
- [x] Added Google popup login to the frontend.
- [x] Added Firebase ID-token verification to FastAPI.
- [x] Added protected dashboard and document pages.
- [x] Added automatic local user and organization provisioning.

Firebase Authentication is external and does not run in Docker. The Firebase
service-account JSON is mounted read-only from `secrets/` and must never be
committed.

### 7. Frontend Authentication

- [x] Added `AuthContext`.
- [x] Added protected client-side routes.
- [x] Added login, logout, and current-user handling.
- [x] Added the dashboard navigation.

### 8. Authenticated Document Upload

- [x] Added `POST /documents/upload`.
- [x] Added organization-scoped document listing and metadata endpoints.
- [x] Added PDF, CSV, DOCX, and XLSX validation.
- [x] Added the 25 MB limit, safe filenames, and SHA-256 hashes.
- [x] Added database rows and upload audit events.

Files currently use local backend storage:

```text
backend/storage/uploads/{organization_id}/{document_id}_{safe_filename}
```

Firebase Cloud Storage replaces the old MinIO plan when cloud object storage
is integrated. It is not yet wired into the document upload service.

### 9. Frontend Document Workspace

- [x] Added the `/documents` route.
- [x] Added file selection and document-type controls.
- [x] Added upload progress, error display, and document listing.
- [x] Linked the workspace from the dashboard.

### 10. Document Text Extraction

- [x] Added the `DocumentTextChunk` model and migration.
- [x] Added PDF extraction with PyMuPDF.
- [x] Added DOCX extraction with `python-docx`.
- [x] Added CSV preview extraction.
- [x] Added XLSX extraction with `openpyxl`.
- [x] Added processing and extracted-text endpoints.
- [x] Added frontend controls to process documents and inspect chunks.

The backend creates chunks of roughly 1,500–2,500 characters and changes the
document status to `processed` or `failed`.

### 11. Contract Review Database Schema

- [x] Added `Contract`.
- [x] Added `ContractReview`.
- [x] Added `ContractRubricScore`.
- [x] Added `ContractRiskFlag`.
- [x] Added and applied Alembic revision `20260628_0002`.
- [x] Confirmed the PostgreSQL schema has no migration drift.

### 12. Contract Review API

- [x] Added `POST /api/v1/contracts/review` with document ownership check and
  processed-status guard.
- [x] Added `GET /api/v1/contracts`, `GET /api/v1/contracts/{id}`, and
  `GET /api/v1/contracts/{id}/review`.
- [x] Added fake placeholder reviewer (score 75, 5 rubric categories, 2 risk
  flags).
- [x] Added `app/schemas/contract.py` with request and response Pydantic models.
- [x] Added 7 new backend tests (22 total).
- [x] Added `/contracts` React page with document picker, review form, and
  inline review panel showing score, rubric table, and risk flags.

## Current Document API

All endpoints require a Firebase bearer token.

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/documents/upload` | Upload a document |
| `GET` | `/documents` | List organization documents |
| `GET` | `/documents/{id}` | Get document metadata |
| `POST` | `/documents/{id}/process` | Extract and chunk text |
| `GET` | `/documents/{id}/text` | Get extracted chunks |

The `/api/v1/documents` equivalents are also available.

### 13. Frontend Contract Review UI

- [x] Added `/contracts` route and nav link.
- [x] Added document picker dropdown filtered to processed documents.
- [x] Added vendor name and contract type inputs.
- [x] Calls `POST /api/v1/contracts/review` and displays the result inline.
- [x] Shows total score, risk level, executive summary, recommendation, rubric
  table with score bars, and risk flags with severity badges.
- [x] Lists past contract reviews from `GET /api/v1/contracts` with expandable
  review panels.
- [x] Added "Review contracts" link from the dashboard.

### 14A. AI Provider Abstraction for Contract Review

- [x] Added `app/ai/providers/base.py` with `AIProvider` ABC (`complete` method).
- [x] Added `app/ai/providers/openrouter_provider.py` with HTTP error, timeout,
  and malformed-response handling.
- [x] Added `app/ai/agents/contract_reviewer.py` with `ContractReviewResult`
  Pydantic output model, strict JSON-only prompt, and `run_ai_review` /
  `run_fake_review` functions.
- [x] Added `USE_FAKE_AI`, `DEFAULT_MODEL`, and `OPENROUTER_API_KEY` to
  `app/config.py` and `.env`.
- [x] Updated `POST /api/v1/contracts/review` to branch on `USE_FAKE_AI`;
  real path calls OpenRouter and returns `502` with a clear message on any
  AI failure.
- [x] Moved `httpx` from the dev section to main dependencies in
  `requirements.txt`.
- [x] Updated the frontend review panel to show the model name and adjust the
  disclaimer text for real vs. placeholder reviews.

To switch to real AI: set `USE_FAKE_AI=false` in `.env` and restart Docker.

### 15. Contract Review Edit and Delete

- [x] Added `PATCH /api/v1/contracts/{id}` — updates `vendor_name` and
  `contract_type`; uses `model_fields_set` so omitted fields are untouched.
- [x] Added `PATCH /api/v1/contracts/{id}/review` — updates
  `executive_summary`, `recommendation`, `risk_level`, and `total_score` on
  the most recent review; returns the full review with rubric scores and risk
  flags.
- [x] Added `DELETE /api/v1/contracts/{id}` — permanently removes the contract
  row; PostgreSQL CASCADE deletes the linked review, rubric scores, and risk
  flags.
- [x] Added 4 new backend tests (26 total).
- [x] Updated the contract table row with inline Edit mode (vendor name and
  type become inputs) and a Delete button with a `window.confirm` guard.
- [x] Updated the review panel with an "Edit review" toggle that makes
  summary and recommendation textareas, risk level a select, and score a
  number input; changes are saved via PATCH without a page reload.

### 16. Contract Review Detail Page and PDF Export

- [x] Added `GET /api/v1/contracts/{id}` single-contract endpoint (already present
  from Step 12; added `getContract` client function).
- [x] Added `frontend/src/pages/ContractReviewPage.tsx` — dedicated full-page
  review view at `/contracts/:contractId/review`; fetches contract and review in
  parallel; renders score, risk badge, rubric table, risk flags, and disclaimer.
- [x] Added route `/contracts/:contractId/review` in `App.tsx`.
- [x] Added "Open in new tab" (`Link target="_blank"`) and "Export as PDF"
  (`<a href="...?print=1" target="_blank">`) buttons to the inline `ReviewPanel`
  header in `ContractsPage.tsx`.
- [x] "Export as PDF" opens the detail page with `?print=1`, which auto-triggers
  `window.print()` after data loads (200 ms delay for paint).
- [x] Added `@media print` CSS: hides site header, footer, and `.no-print`
  elements; sets white background; adds `break-inside: avoid` on sections and
  risk flags for clean page breaks.
- [x] Added `.review-page` layout styles (max-width 900 px, topbar with back link
  and export button, header with score block, body with 780 px content column).

### 17. Improved Contract Review AI Prompt

- [x] Rewrote `_SYSTEM_PROMPT`: establishes HOA contract review assistant role (not a
  lawyer), forbids invented facts, requires citations from contract text, mandates
  JSON-only output.
- [x] Rewrote `_USER_PROMPT_TEMPLATE`: 8-category rubric (Price/Value 20, Scope
  Clarity 15, Term/Cancellation 15, Liability/Insurance 15, Vendor Obligations 10,
  Payment Terms 10, Compliance/Doc Completeness 10, HOA Flexibility 5 = 100 pts);
  `total_score` must equal exact rubric sum; first sentence of executive_summary must
  state "not legal advice"; citation fields required throughout.
- [x] Added `board_questions` and `negotiation_points` lists to `ContractReviewResult`
  Pydantic model and to the prompt output schema.
- [x] Updated fake result to 8 rubric categories (scores sum to 75) with sample
  board_questions and negotiation_points.
- [x] Updated `ContractReviewResponse` schema to include `board_questions` and
  `negotiation_points` (pulled from `raw_output_json` at read time; no new DB columns
  needed).
- [x] Updated `_build_review_response` to read the two lists from `raw_output_json`.
- [x] Updated `ContractReview` TypeScript interface with the two new list fields.
- [x] Added "Questions for the vendor" and "Negotiation points" sections to
  `ContractReviewPage.tsx`.
- [x] All 11 contract tests pass.

### 18. Contract Comparison

- [x] Added `app/ai/agents/contract_comparator.py` — reads all selected
  contract texts (up to 7 k chars each) plus rubric scores, calls the AI with
  a single prompt, and returns `summary` (board-ready markdown), `per_contract`
  (per-vendor strengths / weaknesses / verdict), and `critical_differences`.
  Falls back to a deterministic fake when `USE_FAKE_AI=true`.
- [x] Added `POST /api/v1/contracts/compare` — accepts 2–5 contract UUIDs,
  verifies org ownership, loads latest reviews + rubric scores + document text
  chunks for each contract, calls the AI comparator, then also computes
  code-based rankings and a side-by-side rubric table.
- [x] Response fields: `ai_summary`, `ai_model`, `ai_per_contract`,
  `ai_critical_differences` (AI-generated), plus `ranked_contracts`,
  `side_by_side_table`, `best_overall`, `lowest_risk`, `best_value`,
  `key_differences` (code-generated from rubric scores).
- [x] Added dedicated `/contracts/compare` page (`ContractComparePage.tsx`)
  with a card-based selection UI (checkbox cards, 2–5 contracts, max-5 guard),
  an AI analysis block at the top (summary prose + critical differences +
  per-contract verdict cards), followed by callout cards, rankings, and
  side-by-side rubric table.
- [x] `ContractsPage` simplified: checkboxes and inline `ComparePanel` removed;
  a "Compare contracts →" link appears in the list header when 2+ reviews exist.
- [x] All 11 existing backend contract tests pass.

### 19. Fixed Contract Text Truncation Bug

- [x] Root cause: `contract_reviewer.py` silently truncated contract text to
  the first 14,000 characters (`contract_comparator.py` to 7,000 per
  contract) before sending it to the AI. Term/Renewal, Cancellation, and
  Insurance/Liability clauses typically appear later in a contract, so they
  were often cut off — the AI then correctly but misleadingly reported the
  document as "silent" on topics it never saw.
- [x] Added `app/ai/agents/text_reduction.py` with `reduce_text_to_budget()`:
  returns the text unchanged if it fits the budget; otherwise splits it into
  ~90K-character chunks, runs a fact-extraction AI pass over each chunk
  (verbatim quotes + section locators, no truncation), and returns the
  combined extraction to stand in for the raw text.
- [x] `contract_reviewer.py`: raised the single-call budget from 14,000 to
  350,000 characters (~87K tokens — safe under every model in
  `ALLOWED_MODELS`, all of which have 100K+ token context windows) and
  replaced the hard truncation with `reduce_text_to_budget()`, so the map-reduce
  path only kicks in for documents larger than ~350K characters.
- [x] `contract_comparator.py`: replaced the flat 7,000-char-per-contract cap
  with a 350,000-character budget shared across all compared documents
  (divided evenly per contract, same map-reduce fallback for oversized
  documents).

### 20. Financial Transactions, Categorization, and Manual Entry

- [x] Added `BankAccount`, `Transaction`, `Budget`, `BudgetLine`, `FinancialReport`,
  and `AnomalyAlert` models and migration `20260707_0006`.
- [x] Added `POST /api/v1/financials/transactions/upload-csv` — single-file CSV
  import with heuristic column detection (date/description/amount or
  debit+credit), AI column-detection fallback, per-batch duplicate skipping
  (exact date+amount+description match against existing rows), and a
  `force_expense` flag for invoice/bill-style files.
- [x] Added `POST /api/v1/financials/transactions` (manual add, with the same
  duplicate check and a 409 + "add anyway" override), `PATCH`/`DELETE`
  `/transactions/{id}`, `POST /transactions/bulk-delete`, and
  `GET /transactions` with date-range filtering.
- [x] Added `app/services/categorization_service.py` — keyword-rule
  categorization plus `POST /transactions/ai-categorize` (vendor-memory sweep,
  then batched AI calls for anything still uncategorized).
- [x] Added the `/financial` React page: CSV import panel, manual add-transaction
  panel (with duplicate-warning + "Add anyway"), summary bar, filters, AI
  categorize button, and a sortable/editable transaction table with bulk
  delete.

### 21. Financial Reconciliation Engine

- [x] Added `app/services/financial_reconciliation.py` — normalizes rows from
  `invoice_export` / `operating_activity` / `reserve_activity` (and
  similarly-shaped `unknown`) CSVs into a common record shape, then finds:
  - exact duplicates (same file, date, amount, description, ref, account)
  - possible duplicates (same amount/date, near-identical description, no
    automatic merge)
  - invoice-to-bank-payment matches (amount + vendor-name match + date
    window, confidence-scored high/medium/low)
  - operating↔reserve internal transfers (equal-and-opposite amount, date
    within business-day window, transfer keywords)
  - a summary (income/expenses excluding transfers, per-account nets,
    matched/unmatched invoice counts, duplicate counts)
- [x] 7 tests in `test_financial_reconciliation.py`, including the "three
  same-amount lockbox deposits on different dates are NOT duplicates" and
  "same amount/date but different refs is only a *possible* duplicate"
  cases from the design brief.
- [x] **Bug found and fixed**: this engine originally existed only as a
  tested standalone module — the live `/transactions/upload-csv` endpoint
  never called it. Verified empirically that importing
  `invoice_export.csv` + `operating_activity.csv` + `reserve_activity.csv`
  one at a time (as the UI's single-file flow required) double-counted a
  paid invoice (once as the invoice, once as the matching bank payment) and
  double-counted an operating→reserve transfer (once as an operating
  expense, once as reserve income).
- [x] Added `POST /api/v1/financials/transactions/import-reconciled` —
  accepts multiple `document_ids`, runs them through the reconciliation
  engine together, then commits transactions while: skipping exact-duplicate
  extras, skipping invoice rows that matched a bank payment (the bank row is
  the source of truth for cash), and inserting internal-transfer legs with
  `transaction_type="transfer"` instead of income/expense.
- [x] Updated `financial_report_service.py` to exclude
  `transaction_type == "transfer"` from income/expense totals and category
  breakdowns.
- [x] Added a "Reconcile multiple files" mode to the `/financial` import
  panel — checkbox file picker, reconciliation summary (imported / exact
  duplicates skipped / invoices matched / transfers detected), and a
  human-readable reason per match/flag.
- [x] 3 new tests in `test_financial_reconciled_import.py` reproducing the
  exact overlap scenario end-to-end (import → correct transaction rows →
  correct report totals) plus an ownership-check test.
- [x] Added `source_type`, `external_ref`, `external_account_number` columns
  to `transactions` (migration `20260717_0007`) so a committed transaction
  remembers which kind of file/account it came from.
- [x] Added incremental (cross-import) reconciliation:
  `reconcile_against_history()` matches newly-imported rows against
  transactions already committed from EARLIER imports — catches an invoice
  matched to a bank payment (or vice versa) imported weeks apart, an
  operating↔reserve transfer whose other leg already exists (retroactively
  reclassifying the earlier-committed leg to `transaction_type="transfer"`),
  and exact duplicates from a re-exported bank file with an overlapping date
  range (matched by bank account, not filename). 8 tests across
  `test_financial_history_reconciliation.py`.
- [x] Added `match_same_account_reversals()` — catches a deposit misdirected
  into the wrong account and corrected a few days later by an
  equal-and-opposite entry in that SAME account (found via real Cottages at
  DRV data: a $50,000 deposit landed in Reserve by bank error, then got
  moved to Operating 2 days later). Deliberately requires an explicit
  correction/reversal keyword in the transaction text before matching —
  amount+date alone is too risky given how often HOA assessment payments
  repeat the same round-number amounts. Fixed a related ordering bug: when
  one leg of what looks like an operating↔reserve transfer is actually the
  correction-side of a same-account reversal, the transfer match must not
  also fire, or the OTHER account's leg (e.g. operating genuinely receiving
  new income) gets wrongly excluded too. 4 tests.
- [x] **Validated against real data**: imported the actual Cottages at DRV
  `Invoice_Export.csv` / `Operating-8751-Account_Activity.csv` /
  `Reserve-0037-Account_Activity.csv` and compared the May 2026 totals
  against a professionally-prepared PDF financial report for the same
  period. Found and fixed the reversal-ordering bug above. Remaining gap is
  a real business-classification issue, not a code bug: ~$80k in insurance
  settlement deposits are booked by the property manager as a **credit
  against Legal expense**, not as income — inferable only from domain
  knowledge, not from a bank line reading `"DEPOSIT"`. Also confirmed
  structurally out of reach: the PDF's `$55,000.00` flat Assessments figure
  is accrual-basis billed revenue (vs. our cash-basis lockbox/ACH deposits),
  and its `($79,575.00)` Legal credit is a manual GL journal entry — neither
  exists in any bank statement or vendor invoice export. Cash-basis
  reporting from CSV imports is the accepted ceiling; matching an
  accrual-basis professional report exactly would require ingesting a
  general-ledger/journal-entry export as a new input type.
- [x] Added amount + description editing to transaction PATCH
  (`TransactionUpdateRequest.amount` / `.description`) and the inline edit
  row, so a transaction like the settlement deposit above can be manually
  reclassified (flip the amount's sign, retag the category) — report math
  keys off the amount's sign, not the `transaction_type` label, so this is
  what actually lets a user fix a miscategorized cash-basis entry.

### 22. Financial Report Generation

- [x] Added `app/services/financial_report_service.py` — computes total
  income/expenses/net income, expenses/income by category, and (if a
  `budget_id` is given) budget-vs-actual per category, from committed
  `Transaction` rows in a date range. Pure code/math, no AI.
- [x] Added `POST /api/v1/financials/reports/generate`,
  `GET /api/v1/financials/reports`, `GET /api/v1/financials/reports/{id}`,
  persisting to the existing `FinancialReport.report_json` column.
- [x] 4 tests in `test_financial_reports.py` covering income/expense/variance
  math, the no-budget case, inverted-period rejection, and 404.
- [x] Added lightweight manual budget entry: `POST /api/v1/financials/budgets`
  (fiscal year + a list of category/monthly_budget lines),
  `GET /api/v1/financials/budgets`, `GET /api/v1/financials/budgets/{id}`.
  Deliberately minimal — no upload/parsing, no edit/delete — just enough for
  `budget_vs_actual` to have real data. 3 tests in `test_budgets.py`,
  including report generation actually picking up a created budget.

### 23. Financial Reports UI

- [x] Added **Transactions** / **Budgets** / **Reports** tabs to `/financial`.
- [x] Budgets tab: fiscal-year input + a table of categories with an
  optional monthly-budget field each (blank categories are skipped), plus a
  list of saved budgets.
- [x] Reports tab: date-range generate form with a budget picker (populated
  from the Budgets tab's saved budgets), past-reports list, executive
  summary cards, expenses-by-category and income-by-category tables, and a
  budget-vs-actual table (only rendered when present) with over-budget rows
  highlighted.
- [ ] PDF export of a report (webpage version shipped first, PDF deferred).

### 24. Report Structure Upgrade (Modeled on a Real Professional HOA Report)

Compared the app's report against an actual professionally-prepared monthly
HOA financial package ("The Cottages at DRV — Preliminary Financial Report")
to decide what a board-facing report should really include.

- [x] Added a cover-page-style header to `report_json`: `organization_name`,
  `fiscal_year`, `ytd_start` (fiscal year runs Oct 1 → Sep 30, labeled by the
  calendar year it ends in — matches the real report's convention).
- [x] Added `ytd_summary` — income/expenses/net income from fiscal-year-start
  through `period_end`, alongside the existing single-period
  `executive_summary`.
- [x] Added `operating` / `reserve` sections (`FundSection`: executive
  summary + expenses/income by category), splitting the report the same way
  the real one has two separate Operating and Reserve statements — uses the
  `fund_type` column already populated by reconciled imports.
- [x] Extended `budget_vs_actual` with `ytd_budget_amount`,
  `ytd_actual_amount`, `ytd_variance`, `annual_budget_amount` alongside the
  existing month figures — mirrors the real report's Month/YTD/Annual-Budget
  column layout. Frontend table now has grouped "This month" / "Year to
  date" column headers plus an Annual Budget column, and highlights a row as
  over-budget if either the month OR the YTD variance is negative.
- [x] Added automatic notes: when transactions in the period are tagged
  `transaction_type="transfer"` (internal transfers or same-account
  reversals), the report now says how many and that they were excluded from
  income/expenses — a lightweight stand-in for the real report's Journal
  Voucher / adjustment log, using data the reconciliation engine already
  produces rather than a new audit-log table.
- [x] Added a "View transactions for this period" link from a generated
  report straight to the Transactions tab, pre-filtered to that date range —
  a cheap proxy for the real report's General Ledger / transaction-detail
  appendix, reusing the existing client-side date filter instead of
  embedding a full transaction list in `report_json`.
- [x] 1 new test (`test_report_includes_fiscal_year_ytd_and_fund_split`)
  covering fiscal year/YTD math, the Operating/Reserve split, and the
  transfer-exclusion note, plus fixed UI alignment issues found on the
  Budgets/Reports tabs while building this (rigid 4-column form grid reused
  for a 2-field form left dead grid tracks; numeric table columns were never
  right-aligned; the summary card grid had a phantom empty 4th slot).
- [ ] **Deliberately not attempted** — would need substantial new data
  modeling, not a report tweak: full Balance Sheet (assets/liabilities/
  equity — we only track cash transactions), AR Aging / delinquency (needs
  per-unit owner/assessment records — no such model exists), Check Register
  (needs a real check-number field), and a coded General Ledger (we use
  free-text categories, not a chart of accounts). Tracked as a future
  initiative, not out of scope permanently — see Next Work.

## Next Work

1. Decide when to move document binaries from local storage to Firebase Cloud
   Storage.
2. Add PDF export for financial reports.
3. Future initiative: full Balance Sheet, AR Aging/delinquency tracking,
   Check Register, and a coded General Ledger — each requires new data
   models (units/owners/assessments, chart of accounts, check numbers) well
   beyond the current transaction-and-budget schema.

---

## Financial Module Plan

> **Status update:** the plan below (`FinancialDocumentParse`, `Invoice`,
> `DelinquencyAccount`, the classify → extract → review-gate → normalize
> pipeline) was superseded — CSV/XLSX transaction ingestion was built more
> directly instead. See Steps 20–23 above for what actually exists today:
> CSV import (single-file and multi-file reconciled), manual entry,
> categorization, the reconciliation engine, and report generation. PDF
> invoice/delinquency parsing and the dedicated review-gate UI described
> below were never built. Treat this section as historical design context,
> not current status.

### Supported Input Types

| Document type | Formats | Priority |
|---|---|---|
| Bank statement | PDF, CSV | 2 (CSV first, PDF after) |
| Transaction export | CSV | 1 (highest) |
| Budget | CSV, XLSX | 1 |
| Invoice | PDF, DOCX | 3 |
| Delinquency report | PDF, CSV, XLSX | 2 |
| Prior financial report | PDF | 3 |
| Reserve study | PDF | 3 |

### Design Principles

- **Structured data, not text summaries.** All financial reports are generated
  from database rows computed by Python/Pandas/SQL — never from AI-generated
  prose directly.
- **AI assists, does not calculate.** AI classifies document type, extracts
  tables from unstructured PDFs, and explains reports in plain English.
  Arithmetic (totals, variances, anomaly thresholds) is always done in code.
- **CSV/XLSX before PDF.** Tabular formats are parsed deterministically and
  require no OCR or table-detection heuristics. PDF bank statement parsing is
  added only after CSV ingestion is proven reliable.
- **User review gate.** After AI parses a document, the user sees a preview of
  extracted rows and can correct or discard them before they are committed to
  the database.
- **Scanned PDFs are deferred.** OCR (e.g. Tesseract or a cloud vision API) is
  a future phase once native PDF parsing is stable.

### Intake Pipeline (per document)

```
Upload financial document
        │
        ▼
[1] financial_document_classifier.py
    · AI reads first ~2 k chars + filename
    · Returns: document_type, confidence, fund_type hint
    · Writes FinancialDocumentParse row (status=classifying)
        │
        ▼
[2] text_extraction_service.py  (existing, reused)
    · PDF → PyMuPDF text + table blocks
    · CSV/XLSX → raw rows via pandas
    · DOCX → python-docx paragraphs + tables
    · Writes DocumentTextChunk rows (existing)
        │
        ▼
[3] financial_extraction_service.py
    · Dispatches to the right parser by document_type:
      ├─ transaction_parser.py   → List[TransactionRow]
      ├─ budget_parser.py        → List[BudgetLineRow]
      ├─ invoice_parser.py       → List[InvoiceRow]
      └─ delinquency_parser.py   → List[DelinquencyRow]
    · Each parser returns typed dataclass rows + a parse_warnings list
    · Writes raw output to FinancialDocumentParse.extracted_json
    · Sets status=needs_review
        │
        ▼
[4] User reviews parsed rows in the UI
    · Editable table: correct amounts, dates, categories, fund_type
    · User clicks "Confirm" or "Discard"
        │
        ▼
[5] financial_normalization_service.py
    · On confirm: upserts normalized rows into:
      Transaction, BudgetLine, Invoice, DelinquencyAccount
    · Sets FinancialDocumentParse.status = committed
    · Logs to AuditLog
        │
        ▼
[6] financial_report_service.py
    · Reads committed rows from DB
    · Computes totals, variance vs budget, fund balances using SQL/Pandas
    · Writes FinancialReport row (report_json)
    · AI optionally adds a plain-English narrative via a separate call
        │
        ▼
[7] anomaly_detection_service.py
    · Runs after each transaction batch commit
    · Rules: duplicate amounts, amounts > threshold, vendor not on approved list, etc.
    · Writes AnomalyAlert rows
```

### Planned Services

| File | Responsibility |
|---|---|
| `financial_document_classifier.py` | AI call → classify document type + fund_type |
| `financial_extraction_service.py` | Dispatch to per-type parsers, write FinancialDocumentParse |
| `transaction_parser.py` | CSV/XLSX → `List[TransactionRow]`; PDF bank statements (phase 2) |
| `budget_parser.py` | CSV/XLSX → `List[BudgetLineRow]` with category + annual/monthly amounts |
| `invoice_parser.py` | PDF/DOCX → `List[InvoiceRow]` (vendor, amount, line items) |
| `delinquency_parser.py` | PDF/CSV/XLSX → `List[DelinquencyRow]` (unit, owner, balance, status) |
| `financial_normalization_service.py` | Insert confirmed rows into Transaction / Invoice / DelinquencyAccount |
| `financial_report_service.py` | SQL/Pandas → FinancialReport JSON + optional AI narrative |
| `anomaly_detection_service.py` | Rule-based + optional AI anomaly scan → AnomalyAlert rows |

### Additional Models Needed

**`FinancialDocumentParse`** — tracks one parse attempt per uploaded document:

| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| organization_id | UUID FK | → organizations |
| document_id | UUID FK | → documents |
| document_type | string | classifier output |
| confidence_score | numeric nullable | classifier confidence |
| extracted_json | JSON nullable | raw parser output (rows + warnings) |
| status | string | `classifying` / `needs_review` / `committed` / `failed` |
| created_at | datetime | |

**`Invoice`** — one row per invoice document:

| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| organization_id | UUID FK | |
| source_document_id | UUID FK nullable | → documents |
| vendor_name | string | |
| invoice_number | string nullable | |
| invoice_date | date nullable | |
| due_date | date nullable | |
| amount | numeric | total |
| status | string | `pending` / `approved` / `paid` |
| fund_type | string nullable | |
| created_at | datetime | |

**`DelinquencyAccount`** — one row per unit/owner in a delinquency report:

| Column | Type | Notes |
|---|---|---|
| id | UUID | PK |
| organization_id | UUID FK | |
| source_document_id | UUID FK nullable | → documents |
| report_date | date | date of the report |
| unit_identifier | string | unit number or address |
| owner_name | string nullable | |
| balance_owed | numeric | |
| days_overdue | int nullable | |
| status | string nullable | e.g. `lien_filed`, `payment_plan` |
| created_at | datetime | |

### Implementation Order

**Phase 1 — CSV/XLSX ingestion (build first)**
1. `transaction_parser.py` — detect column headers, map to `TransactionRow`
2. `budget_parser.py` — detect category + amount columns
3. `financial_normalization_service.py` — commit confirmed rows
4. `FinancialDocumentParse` model + migration
5. User review UI: editable parsed-rows table per document

**Phase 2 — Reports and anomalies**
6. `financial_report_service.py` — income statement, balance summary, budget vs actual
7. `anomaly_detection_service.py` — duplicate, threshold, and unknown-vendor rules
8. Frontend financial dashboard: summary cards, transaction table, alert list

**Phase 3 — PDF and DOCX inputs**
9. `financial_document_classifier.py` — AI classification step
10. `transaction_parser.py` — PDF bank statement table extraction (PyMuPDF `find_tables`)
11. `invoice_parser.py` — PDF/DOCX invoice extraction
12. `delinquency_parser.py` — delinquency report extraction
13. `Invoice` + `DelinquencyAccount` models + migration

**Phase 4 — Scanned PDFs (deferred)**
14. OCR integration (Tesseract or Google Document AI) for image-only PDFs
