# HOA AI Assistant — Build Notes

## Short Progress Report

The FastAPI and React/Vite foundation is complete. Docker runs the backend,
frontend, PostgreSQL, and Redis; Firebase provides Google authentication.
Authenticated document upload, document listing, text extraction, the
full contract-review API, AI provider abstraction with OpenRouter, the
contract review UI at `/contracts`, inline edit/delete of reviews, and a
dedicated per-review detail page at `/contracts/:id/review` with PDF export
are implemented. The current Alembic revision is `20260628_0002`, and all
22 backend tests pass.

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

## Next Work

1. Decide when to move document binaries from local storage to Firebase Cloud
   Storage.
