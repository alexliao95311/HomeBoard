# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HomeBoard helps HOA boards review contracts, monitor finances, detect unusual
transactions, and generate board-ready reports with AI assistance.

## Development Commands

### Backend (from `backend/`)

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload          # starts on :8000
alembic upgrade head               # apply migrations
alembic revision --autogenerate -m "description"  # new migration
pytest                             # all tests
pytest tests/test_documents.py     # single test file
pytest tests/test_documents.py::test_upload_list_and_get_document  # single test
```

### Frontend (from `frontend/`)

```bash
npm install
npm run dev          # starts on :5173
npm run build        # TypeScript check + Vite build
npm run typecheck    # type check only
```

### Docker Compose (full stack, from repo root)

```bash
docker compose --env-file .env -f infra/docker-compose.yml up --build
docker compose --env-file .env -f infra/docker-compose.yml down
```

The Compose backend entrypoint runs `alembic upgrade head` before starting uvicorn. Add `--volumes` to `down` only when intentionally wiping local Postgres/Redis data.

## Architecture

### Backend (`backend/`)

Entry point: `app/main.py` → `create_app()` which wires CORS middleware, routes, and the startup lifespan hook (DB connection check + `Base.metadata.create_all`).

**Routing:**
- `/health` — unauthenticated health check
- `/documents/*` — unversioned alias for the document router (no auth middleware on path itself; auth is injected per-endpoint via `Depends`)
- `/api/v1/*` — versioned API prefix; includes auth and future contract/financial routes

**Auth flow:** All protected endpoints use `get_current_user` (`app/api/routes/auth.py`), which reads the `Authorization: Bearer` header and calls Firebase Admin SDK's `auth.verify_id_token()`. The decoded token is returned as `AuthenticatedUser`.

**Organization provisioning** (`app/services/organization_service.py`): `get_current_organization` is a FastAPI dependency that auto-provisions a `User` row and a default `Organization` + `OrganizationMembership` on the user's first request. All document queries are scoped to `organization_id`.

**Document pipeline:**
1. `POST /documents/upload` — validates content type (PDF/CSV/DOCX/XLSX, ≤25 MB), streams file to `storage/uploads/{org_id}/{doc_id}_{safe_filename}` using atomic rename, writes `Document` row + `AuditLog` in one transaction.
2. `POST /documents/{id}/process` — calls `text_extraction_service.extract_document_text()` then `chunk_extracted_text()` (1,500–2,500 char chunks), stores `DocumentTextChunk` rows, updates status to `processed` or `failed`.
3. `GET /documents/{id}/text` — returns ordered `DocumentTextChunk` rows.

**Models** (`app/models/`): `User`, `Organization`, `OrganizationMembership`, `Document`, `DocumentTextChunk`, `AuditLog`. All share the same `Base` from `app/database.py`.

**Settings** (`app/config.py`): Single frozen `Settings` dataclass read from env vars. Key env vars: `DATABASE_URL`, `DOCUMENT_STORAGE_PATH`, `REDIS_URL`, `FIREBASE_PROJECT_ID`, `GOOGLE_APPLICATION_CREDENTIALS`, `CORS_ORIGINS`.

**Alembic** (`backend/alembic/`): Migrations live in `alembic/versions/`. Run from `backend/` directory. Two existing migrations: baseline schema + document text chunks table.

### Frontend (`frontend/src/`)

**Routing** (`App.tsx`): Three routes — `/` (DashboardPage), `/documents` (DocumentsPage), `/documents/:documentId` (DocumentTextPage).

**Auth** (`context/AuthContext.tsx` + `firebase.ts`): Firebase Google sign-in. `AuthContext` exposes `user`, `loading`, `signInWithGoogle`, `signOut`. Firebase ID token is retrieved on each API call via `user.getIdToken()`.

**API client** (`api/client.ts`): Thin fetch wrappers for every backend endpoint. Uses `VITE_API_URL` env var (defaults to `http://localhost:8000`). The frontend calls the unversioned `/documents/*` paths (not `/api/v1/documents/*`).

**Types** (`types/api.ts`): TypeScript interfaces matching backend Pydantic schemas (`Document`, `DocumentTextChunk`, `AuthenticatedUser`, etc.).

### Testing

Tests use FastAPI's `TestClient` with SQLite in-memory (via `StaticPool`) and override three dependencies: `get_database_session`, `get_current_user`, and `get_upload_root`. No real Firebase or PostgreSQL needed for tests. `pytest` is run from `backend/`.

### Infrastructure

`infra/docker-compose.yml` defines: `backend` (FastAPI), `frontend` (Vite dev server), `postgres:16-alpine`, `redis:7-alpine`. The `secrets/` directory is mounted read-only into the backend container for Firebase service account JSON. Git-ignores files in `secrets/`.

### Required `.env` Variables (repo root)

```
DATABASE_URL
POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DB
FIREBASE_PROJECT_ID
GOOGLE_APPLICATION_CREDENTIALS   # path inside container, e.g. /run/secrets/firebase-key.json
VITE_FIREBASE_API_KEY
VITE_FIREBASE_AUTH_DOMAIN
VITE_FIREBASE_PROJECT_ID
VITE_FIREBASE_STORAGE_BUCKET
VITE_FIREBASE_MESSAGING_SENDER_ID
VITE_FIREBASE_APP_ID
```
