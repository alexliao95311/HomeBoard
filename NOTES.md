# HOA AI Assistant — Build Notes

## Short Progress Report

The FastAPI and React/Vite foundation is complete. Docker runs the backend,
frontend, PostgreSQL, and Redis; Firebase provides Google authentication.
Authenticated document upload, document listing, text extraction, the
full contract-review API with a fake placeholder reviewer, and the contract
review UI at `/contracts` are implemented.
The current Alembic revision is `20260628_0002`, and all 22 backend tests pass.

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

## Next Work

1. Replace the fake reviewer with a real AI review flow.
2. Decide when to move document binaries from local storage to Firebase Cloud
   Storage.
