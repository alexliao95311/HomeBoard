# HOA AI Assistant

A secure AI-powered assistant for HOA boards to review vendor contracts, compare proposals, monitor finances, detect abnormal transactions, and generate board-ready reports.

This project is designed for HOA board members, treasurers, and property managers who need a more organized way to review documents, understand financial activity, and prepare materials for board meetings.

## Overview

HOA boards often deal with large amounts of paperwork: vendor contracts, proposals, bank statements, invoices, budgets, delinquency reports, reserve studies, and monthly financial packets. Reviewing all of this manually is slow and error-prone.

The HOA AI Assistant helps by:

- Uploading and organizing HOA documents
- Extracting text from contracts and financial files
- Reviewing contracts with AI-assisted risk analysis
- Comparing vendors using a clear scoring rubric
- Ingesting transactions from bank statements or CSV files
- Categorizing income and expenses
- Comparing actual expenses against the budget
- Detecting abnormal or suspicious transactions
- Generating board-ready summaries and reports
- Maintaining audit logs and secure organization-level access

AI outputs are intended to assist board review. They are not legal, accounting, or financial advice.

---

## Core Features

### 1. Secure User Accounts

The app should support secure accounts for HOA board members and administrators.

Planned features:

- User registration and login
- JWT-based authentication
- Role-based access control
- Organization-level data separation
- Admin, board member, treasurer, viewer, and auditor roles
- Audit logs for sensitive actions
- Future support for multi-factor authentication

---

### 2. Document Upload and Management

Users should be able to upload and manage HOA-related documents.

Supported document types:

- Vendor contracts
- Vendor proposals
- Insurance certificates
- Bank statements
- Transaction CSV files
- Budgets
- Invoices
- Delinquency reports
- Reserve studies
- Prior financial reports

Planned features:

- Secure file upload
- File type validation
- File size limits
- SHA-256 file hashing
- Document classification
- Document status tracking
- Original file storage
- Extracted text storage
- Organization-specific access control

Supported formats:

- PDF
- DOCX
- CSV
- XLSX

---

### 3. Contract Review

The contract review system helps board members understand vendor contracts before approval.

Input:

- Vendor contracts
- Vendor proposals
- Scope of work documents
- Insurance documents

Output:

- Executive summary
- Contract risk analysis
- Key terms extraction
- Rubric-based score
- Risk level
- Suggested board questions
- Suggested negotiation points
- Board-ready recommendation

Contract fields to extract:

- Vendor name
- Contract type
- Effective date
- Expiration date
- Renewal terms
- Total cost
- Payment terms
- Scope of work
- Termination clause
- Insurance requirements
- Indemnity clause
- Liability limitations
- Dispute resolution
- Missing exhibits or attachments

---

### 4. Contract Scoring Rubric

Each contract should be graded out of 100 using a clear rubric.

| Category | Weight | Description |
|---|---:|---|
| Price / Value | 20 | Total cost, recurring fees, hidden fees, and price increases |
| Scope Clarity | 15 | Clear deliverables, frequency, exclusions, and service standards |
| Term / Cancellation | 15 | Contract length, renewal terms, termination rights, and notice periods |
| Liability / Insurance | 15 | Insurance coverage, indemnity, workers compensation, and HOA risk exposure |
| Vendor Obligations | 10 | Response times, reporting, cleanup, and performance requirements |
| Payment Terms | 10 | Due dates, deposits, late fees, and payment triggers |
| Compliance / Completeness | 10 | Licenses, insurance certificates, exhibits, and required signatures |
| HOA Flexibility | 5 | Ability to adjust scope, pause service, reject work, or terminate for cause |

---

### 5. Vendor Comparison

The app should allow the board to compare multiple vendor contracts or proposals side by side.

Planned comparison outputs:

- Ranked vendor list
- Total score for each vendor
- Risk level for each vendor
- Cost comparison
- Scope comparison
- Term and cancellation comparison
- Insurance and liability comparison
- Missing document comparison
- Best overall option
- Lowest-risk option
- Best-value option
- Final board recommendation

Example output:

```text
1. Vendor B — 87/100 — Best overall
2. Vendor A — 76/100 — Lower cost but weaker scope
3. Vendor C — 61/100 — Highest legal and financial risk
```

---

### 6. AI Contract Agent Flow

The contract system should use multiple AI-assisted steps rather than one large prompt.

Planned agents:

1. **Document Parser Agent**
   - Extracts contract terms and important clauses.

2. **Risk Reviewer Agent**
   - Flags risky, vague, missing, or one-sided clauses.

3. **Rubric Scorer Agent**
   - Scores the contract using the standard rubric.

4. **Comparator Agent**
   - Compares multiple vendor contracts side by side.

5. **Board Packet Writer Agent**
   - Converts the review into a board-ready memo.

6. **Optional Adversarial Review Agent**
   - One agent argues the contract is acceptable.
   - Another agent argues it is risky.
   - A judge agent produces the final risk assessment.

---

### 7. Financial Oversight

The financial module helps the HOA board monitor income, expenses, budgets, and abnormal activity.

Input:

- Raw bank transactions
- Bank statement CSV files
- Budget files
- Invoice files
- Delinquency reports
- Prior monthly reports

Output:

- Monthly financial summary
- Income and expense report
- Budget vs actual report
- Expense category breakdown
- Delinquency summary
- Abnormal transaction alerts
- Board-ready financial narrative

---

### 8. Financial Reports

The system should generate standard HOA-style financial reports.

Planned report sections:

#### Executive Dashboard

- Total income
- Total expenses
- Net income
- Operating cash estimate
- Reserve cash estimate
- Budget variance
- Largest expense categories
- Open anomaly alerts

#### Income and Expense Report

- Assessment income
- Late fees
- Other income
- Landscaping
- Utilities
- Insurance
- Repairs and maintenance
- Management fees
- Legal and accounting
- Pool, security, or gate expenses
- Reserve contributions

#### Budget vs Actual Report

For each category:

- Monthly budget
- Monthly actual
- Monthly variance
- Year-to-date budget
- Year-to-date actual
- Year-to-date variance
- Percent used

#### Balance Sheet-Style Summary

Planned fields:

- Operating cash
- Reserve cash
- Accounts receivable
- Accounts payable
- Prepaid expenses
- Loans or liabilities
- Fund balance

#### Delinquency / Aging Report

Planned fields:

- 0–30 days late
- 31–60 days late
- 61–90 days late
- 90+ days late
- Total delinquent amount
- Number of delinquent owners
- Repeat delinquent accounts

---

### 9. Transaction Ingestion

The financial system should ingest raw bank data and normalize it into a clean transaction table.

Supported input:

- CSV exports
- Bank statement tables
- Future PDF statement parsing

Transaction fields:

- Date
- Description
- Amount
- Transaction type
- Vendor name
- Category
- Fund type
- Source document
- Confidence score

Planned transaction categories:

- Assessment Income
- Late Fees
- Landscaping
- Utilities
- Insurance
- Repairs and Maintenance
- Management Fees
- Legal
- Accounting
- Pool Maintenance
- Security
- Bank Fees
- Reserve Contribution
- Uncategorized

---

### 10. Abnormal Transaction Detection

The app should flag transactions that may require board review.

Planned detection rules:

- Duplicate payments
- Same vendor and same amount within a short period
- Large expense above threshold
- New vendor not previously seen
- Uncategorized transaction
- Missing invoice
- Expense much higher than historical average
- Payment from reserve fund for operating expense
- Bank fee spike
- Transfer mismatch
- Check number gaps
- Round-number suspicious payments
- Transactions outside normal timing

Each alert should include:

- Alert type
- Severity
- Explanation
- Related transaction
- Suggested next step
- Status: open, resolved, or dismissed

---

### 11. Human Review and Corrections

The system should allow users to correct AI or rule-based outputs.

Planned features:

- Edit transaction category
- Edit vendor name
- Mark anomaly as resolved
- Mark anomaly as dismissed
- Edit contract metadata
- Mark risk as addressed
- Save user corrections
- Use corrections to improve future categorization rules

---

### 12. Board Packet Generator

The app should generate board-ready summaries.

Planned exports:

- Contract review memo
- Vendor comparison memo
- Monthly financial report
- Treasurer report
- Anomaly summary
- Board action item list

Initial export format:

- Markdown

Future export formats:

- PDF
- DOCX
- Excel

---

## Tech Stack

### Backend

- FastAPI
- Python 3.12
- Pydantic
- SQLAlchemy
- Alembic
- PostgreSQL
- Redis
- Celery or RQ for background processing
- Pandas for financial calculations
- OpenPyXL for Excel parsing
- PyMuPDF or pdfplumber for PDF parsing
- python-docx for DOCX parsing
- Firebase Cloud Storage for private document storage

---

### Frontend

- React
- TypeScript
- Vite
- React Router
- TanStack Table
- Recharts
- React Hook Form
- Zod
- Tailwind CSS
- shadcn/ui, optional later

---

### Database

- PostgreSQL
- SQLAlchemy ORM
- Alembic migrations
- Future support for pgvector for document search and embeddings

---

### AI Layer

The app should use a provider abstraction so different AI models can be tested.

Planned providers:

- OpenRouter
- OpenAI
- Anthropic
- Google Gemini

Planned AI use cases:

- Contract term extraction
- Contract risk review
- Rubric scoring
- Vendor comparison
- Board memo writing
- Financial narrative summaries
- Ambiguous transaction categorization
- Anomaly explanation

The system should support:

- Fake AI mode for local testing
- Real AI mode for production testing
- Model run logging
- Prompt version tracking
- Structured JSON outputs
- Pydantic validation of AI responses

---

### Local Infrastructure

Local development should use Docker Compose.

Services:

- FastAPI backend
- React frontend
- PostgreSQL
- Redis
- Firebase Cloud Storage for managed object storage

---

## Planned Project Structure

```text
hoa-ai-assistant/
  backend/
    app/
      main.py
      config.py
      database.py
      api/
        auth.py
        documents.py
        contracts.py
        financials.py
        audit.py
      models/
        user.py
        organization.py
        document.py
        contract.py
        financial.py
        audit_log.py
      schemas/
        auth.py
        document.py
        contract.py
        financial.py
      services/
        auth_service.py
        document_service.py
        text_extraction_service.py
        contract_review_service.py
        financial_report_service.py
        anomaly_detection_service.py
      ai/
        providers/
        agents/
        evals/
      utils/
      tests/
    alembic/
    requirements.txt
    Dockerfile

  frontend/
    src/
      api/
      components/
      context/
      pages/
      routes/
      types/
      utils/
    package.json
    vite.config.ts
    Dockerfile

  infra/
    docker-compose.yml

  docs/
    MVP_SPEC.md
    DEMO_SCRIPT.md
    SECURITY_NOTES.md
    demo-data/

  README.md
  .env                        # local configuration (not committed)
  .gitignore
```

---

## Security Goals

Because the app may handle contracts, bank statements, invoices, homeowner delinquency data, and legal documents, security is a core requirement.

Planned protections:

- Authentication required for all sensitive routes
- Organization-level data isolation
- Role-based permissions
- Secure password hashing
- File type validation
- File size limits
- Private document storage
- SHA-256 file hashing
- Audit logs for sensitive actions
- Environment-based secrets
- No hardcoded API keys
- AI prompt-injection defenses
- Human review required for all AI conclusions

Future production protections:

- Multi-factor authentication
- Encrypted file storage
- Encrypted database backups
- Private Firebase Storage buckets with controlled download URLs
- Rate limiting
- Deployment behind HTTPS
- Separate development and production environments
- Least-privilege cloud IAM permissions
- Monitoring and error logging

---

## AI Safety and Reliability Principles

The app should follow these rules:

- Uploaded documents are untrusted data.
- The AI must not follow instructions inside uploaded documents.
- The AI must not invent missing contract terms.
- The AI should cite document sections or text snippets when possible.
- Financial math should be done with code, not AI.
- AI should explain financial reports but not calculate core totals.
- AI outputs should be treated as drafts.
- Legal and accounting outputs require human review.
- Every AI run should be logged with model name, prompt version, and output.

---

## MVP Roadmap

### Phase 1: Project Foundation

- Create monorepo
- Add FastAPI backend
- Add React frontend
- Add Docker Compose
- Add PostgreSQL
- Add database migrations
- Add authentication

### Phase 2: Document System

- Secure document upload
- Document listing
- PDF/DOCX/CSV/XLSX text extraction
- Document status tracking
- Audit logs

### Phase 3: Contract Review MVP

- Contract review models
- AI contract review agent
- Contract scoring rubric
- Contract risk flags
- Contract review UI
- Vendor comparison
- Markdown board packet export

### Phase 4: Financial Oversight MVP

- Transaction CSV ingestion
- Transaction categorization
- Budget upload
- Budget vs actual report
- Monthly financial report
- Anomaly detection
- Financial dashboard UI

### Phase 5: AI Summaries and Board Packets

- AI financial summary
- Contract recommendation memo
- Treasurer report
- Board action items
- Markdown export
- Future PDF/DOCX export

### Phase 6: Security and Production Readiness

- Admin audit log page
- Stronger role permissions
- Firebase Cloud Storage integration
- MFA
- Rate limiting
- Deployment configuration
- Production security review

---

## Development Philosophy

Build one small step at a time.

Do not build the full app in one prompt. Each feature should be implemented, tested, and committed before moving to the next feature.

Recommended order:

1. Backend health check
2. Frontend health check
3. Docker Compose
4. Database setup
5. Authentication
6. Document upload
7. Document text extraction
8. Contract review placeholder
9. Contract review AI
10. Contract comparison
11. Financial CSV upload
12. Financial report generation
13. Anomaly detection
14. Board packet export
15. Security hardening

---

## Current Status

The project foundation, health checks, Docker development stack, and Firebase
Google authentication flow are scaffolded. The frontend signs in with Google
and the FastAPI backend verifies the resulting Firebase ID token.
Authenticated document upload and organization-scoped document metadata are
also available. Text extraction is not implemented yet.

No production use yet.

---

## Local Development

Start the backend on its default port, `8000`:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app
```

Confirm the backend is running at `http://localhost:8000/health`. It should
return:

```json
{"status": "ok"}
```

In a second terminal, start the frontend on port `5173`:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. FastAPI documentation is available at
`http://localhost:8000/docs`. The homepage automatically calls
`http://localhost:8000/health` and displays the backend status.

After signing in with Google, open `http://localhost:5173/documents` to upload
PDF, CSV, DOCX, or XLSX files and view the current organization's document
list. The dashboard includes a direct link to this workspace.

### Docker Compose

Configure the repository-root `.env` file, then start the complete local stack:

```bash
docker compose --env-file .env -f infra/docker-compose.yml up --build
```

Local services:

| Service | Address |
|---|---|
| Frontend | `http://localhost:5173` |
| Backend | `http://localhost:8000` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |

#### Firebase Google authentication setup

1. Create or select a project in the Firebase console.
2. Open **Build → Authentication → Sign-in method**.
3. Add and enable the **Google** provider, select a support email, and save.
4. Under **Authentication → Settings → Authorized domains**, ensure
   `localhost` is present. Add the production domain before deployment.
5. Open **Project settings → Service accounts**, select **Generate new private
   key**, and download the JSON credentials.
6. Save the JSON file in `secrets/`. Set `GOOGLE_APPLICATION_CREDENTIALS` in
   `.env` to `/run/secrets/<your-service-account-filename>.json`. JSON files in
   this directory are ignored by Git and mounted read-only into the backend
   container.
7. Restart the frontend and backend after changing Firebase configuration.

Google authentication does not require Cloud Storage to be enabled. The React
app sends its Firebase ID token as a bearer token to
`GET /api/v1/auth/me`; FastAPI verifies the token before returning the user
profile.

#### Document API

All document endpoints require a Firebase ID token in the
`Authorization: Bearer <token>` header.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/documents/upload` | Upload a document and create its metadata |
| `GET` | `/documents` | List documents in the current organization |
| `GET` | `/documents/{id}` | Get organization-scoped document metadata |

The versioned `/api/v1/documents` equivalents are also available. Uploads use
`multipart/form-data` with a `file` field and a user-provided `document_type`
field such as `contract`, `bank_statement`, `budget`, or `invoice`.

Accepted content types are PDF, CSV, DOCX, and XLSX, with a 25 MB maximum.
Files are stored under
`backend/storage/uploads/{organization_id}/{document_id}_{safe_filename}`.
The backend computes a SHA-256 hash, creates the `Document` row with status
`uploaded`, and records a `document.uploaded` audit event in the same database
transaction. No document text is processed yet.

For the MVP, a user's first document request provisions a private default
organization and an admin membership. Explicit organization creation,
invitations, and organization switching will be added later.

#### Firebase Storage setup (later document phase)

1. Upgrade the project to the Blaze plan if prompted. Cloud Storage for
   Firebase requires billing to be enabled.
2. Open **Build → Storage**, select **Get started**, choose a permanent bucket
   location, and keep the bucket in locked mode.
3. Copy the bucket name from the Storage **Files** tab into
   `FIREBASE_STORAGE_BUCKET` in `.env`. Use only the bucket name, without
   `gs://`.
4. Restart the backend after changing the bucket.

The Firebase Admin SDK runs as a privileged server credential. Document
authorization and organization isolation must therefore be enforced by the
backend before each storage operation. Do not expose the service-account JSON
or Admin SDK credentials to the frontend.

Stop the stack with:

```bash
docker compose --env-file .env -f infra/docker-compose.yml down
```

Named Docker volumes preserve local PostgreSQL, Redis, and frontend
dependency data between restarts. Add `--volumes` to the `down` command only
when you intentionally want to delete that local data.

---

## Disclaimer

This application is intended to help HOA boards organize information, identify issues, and prepare draft reports. It does not provide legal, accounting, tax, financial, or professional management advice. All AI-generated outputs should be reviewed by qualified humans before board action.
