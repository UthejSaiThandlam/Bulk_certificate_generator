# Bulk Certificate Generator API & Engine

A high-performance, production-ready backend service built with **Python 3.12+**, **FastAPI**, **ReportLab**, and **SQLite/SQLAlchemy** for asynchronously generating, validating, distributing, and verifying bulk credentials and certificates in PDF format.

Includes an **interactive web dashboard**, Swagger & ReDoc OpenAPI documentation, background batch processing, and unique cryptographic verification codes for instant authentication.

---

## 🏛 Architecture Overview

```
                  ┌───────────────────────────────┐
                  │   Client / Web UI / CSV / API │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                    ┌───────────────────────────┐
                    │     FastAPI Endpoints     │
                    │   (/api/certificates/...) │
                    └─────────────┬─────────────┘
                                  │
                                  ▼
                   ┌─────────────────────────────┐
                   │     Pydantic Validation     │
                   │ (Names, Emails, Dates, etc.)│
                   └──────────────┬──────────────┘
                                  │
                                  ▼
                   ┌─────────────────────────────┐
                   │    Job Initialized in DB    │
                   │     (Status: PENDING)       │
                   └──────────────┬──────────────┘
                                  │
                     (FastAPI BackgroundTasks)
                                  │
                                  ▼
                   ┌─────────────────────────────┐
                   │     Job Processor Worker    │
                   │    (Status: PROCESSING)     │
                   └──────────────┬──────────────┘
                                  │
                                  ▼
                   ┌─────────────────────────────┐
                   │    Certificate Generator    │
                   │   (ReportLab Vector Engine) │
                   └──────────────┬──────────────┘
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
     ┌────────────────────────┐      ┌─────────────────────────┐
     │  Vector PDF Documents  │      │ Bundled ZIP Archive     │
     │ (generated/{job_id}/*.pdf) │  │(generated/{job_id}/*.zip)│
     └────────────┬───────────┘      └────────────┬────────────┘
                  │                               │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                   ┌─────────────────────────────┐
                   │   Job Status: COMPLETED     │
                   │   (Stored in SQLite / DB)   │
                   └──────────────┬──────────────┘
                                  │
                                  ▼
                   ┌─────────────────────────────┐
                   │  Status Polling, Download   │
                   │   and Public Verification   │
                   └─────────────────────────────┘
```

---

## 🛠 Technology Stack

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI** | Modern, asynchronous, high-throughput, native OpenAPI / Swagger integration. |
| **Language** | **Python 3.12+** | Clean syntax, robust standard library, typing support. |
| **Data Validation** | **Pydantic v2** | Strict schema validation, sanitization, and descriptive error messages. |
| **Database & ORM** | **SQLite + SQLAlchemy 2.0** | Zero-configuration persistence, ACID transactions, robust relational schema. |
| **Certificate Engine** | **ReportLab 5.0+** | High-precision vector graphics, print-ready 300+ DPI PDF generation without heavy external browser dependencies. |
| **Image & Assets** | **Pillow** | Image processing, watermark embedding, and banner processing. |
| **Async Processing** | **FastAPI BackgroundTasks** | Non-blocking asynchronous task execution with zero Redis/Celery dependency overhead. |
| **Testing** | **Pytest** | Modular unit and integration test suite with isolated fixtures. |

---

## 📁 Repository Structure

```
bulk-certificate-generator/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI application setup, CORS, lifespan & Dashboard UI
│   │   ├── database.py                 # SQLite engine, session maker, get_db dependency
│   │   ├── models.py                   # SQLAlchemy ORM models (GenerationJob, CertificateRecord)
│   │   ├── schemas.py                  # Pydantic request, response, and validation schemas
│   │   │
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   └── certificates.py         # REST endpoints (batch generate, CSV upload, status, download, verify)
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── certificate_generator.py # ReportLab PDF vector rendering engine
│   │   │   └── job_processor.py        # Asynchronous job worker & ZIP bundler
│   │   │
│   │   └── utils/
│   │       ├── __init__.py
│   │       └── validators.py           # Email, recipient name, course, and date validators
│   │
│   ├── templates/
│   │   └── certificate_template.pdf    # Baseline certificate sample template
│   │
│   ├── generated/                      # Target storage for job folders, PDFs, and ZIP bundles
│   │   └── .gitkeep
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                 # Shared test client and isolated SQLite database fixture
│   │   ├── test_jobs.py                # Job creation, background execution, and CSV upload tests
│   │   ├── test_validation.py          # Data validation & Pydantic schema tests
│   │   ├── test_generation.py          # ReportLab PDF creation and verification code tests
│   │   └── test_retrieval.py           # PDF download, ZIP download, and verification endpoint tests
│   │
│   └── requirements.txt                # Backend dependencies
│
├── frontend/                           # Reserved for dedicated frontend apps
├── requirements.txt                    # Root-level requirements file
├── .gitignore                          # Git ignore rules for virtualenv, PDFs, and caches
└── README.md                           # Complete documentation and setup guide
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.12+** installed on your system
- `git` installed

### 2. Clone the Repository
```bash
git clone https://github.com/<your-username>/bulk-certificate-generator.git
cd bulk-certificate-generator
```

### 3. Create and Activate Virtual Environment
```bash
# On Windows (PowerShell)
python -m venv venv
venv\Scripts\Activate.ps1

# On Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r backend/requirements.txt
```

### 5. Running the Backend API
Run using `python -m uvicorn` (recommended on Windows to avoid PATH issues):

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```
*(Or double-click `run_backend.bat` in the project root)*

The API server will start on **http://127.0.0.1:8000**:
- **Health Check**: `http://127.0.0.1:8000/health`
- **Interactive Swagger Docs**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

---

### 6. Running the Dedicated Frontend
You can launch the frontend application using Python's built-in HTTP server:

```bash
cd frontend
python -m http.server 3000
```
*(Or double-click `run_frontend.bat` in the project root)*

Then open **http://localhost:3000** in your browser.

*(You can also simply open `frontend/index.html` directly in any web browser, as it connects directly to `http://127.0.0.1:8000` via CORS).*

---

## 📡 API Reference

### 1. Submit Bulk Generation Job (JSON)
- **Endpoint:** `POST /api/certificates/generate`
- **Status Code:** `202 Accepted`
- **Request Body:**
```json
{
  "template_name": "classic",
  "issuer_name": "Academic Certification Authority",
  "recipients": [
    {
      "recipient_name": "Alice Johnson",
      "recipient_email": "alice@example.com",
      "course_name": "Distributed Systems Architecture",
      "issue_date": "2025-06-15"
    },
    {
      "recipient_name": "Bob Dylan",
      "recipient_email": "bob@example.com",
      "course_name": "Modern Cloud Computing",
      "issue_date": "2025-06-15"
    }
  ]
}
```
- **Response:**
```json
{
  "id": "3b29c9fe-1763-4416-b8cb-4f40f287e07a",
  "template_name": "classic",
  "status": "PENDING",
  "total_count": 2,
  "processed_count": 0,
  "failed_count": 0,
  "progress_percentage": 0.0,
  "download_zip_url": null,
  "created_at": "2025-06-15T10:00:00Z"
}
```

---

### 2. Submit Bulk Generation Job (CSV Upload)
- **Endpoint:** `POST /api/certificates/upload-csv`
- **Status Code:** `202 Accepted`
- **Content-Type:** `multipart/form-data`
- **Form Fields:**
  - `file`: CSV file (`recipients.csv`)
  - `issuer_name` (optional): `Global Tech Academy`
  - `template_name` (optional): `classic`

**CSV Format Example (`recipients.csv`):**
```csv
recipient_name,recipient_email,course_name,issue_date
Carol White,carol@example.com,Data Science with Python,2025-06-15
David Black,david@example.com,Cloud DevOps & Kubernetes,2025-06-15
```

---

### 3. Check Job Status & Retrieve Certificates
- **Endpoint:** `GET /api/certificates/jobs/{job_id}`
- **Response:**
```json
{
  "id": "3b29c9fe-1763-4416-b8cb-4f40f287e07a",
  "template_name": "classic",
  "status": "COMPLETED",
  "total_count": 2,
  "processed_count": 2,
  "failed_count": 0,
  "progress_percentage": 100.0,
  "download_zip_url": "/api/certificates/jobs/3b29c9fe-1763-4416-b8cb-4f40f287e07a/download-zip",
  "created_at": "2025-06-15T10:00:00Z",
  "completed_at": "2025-06-15T10:00:02Z",
  "certificates": [
    {
      "id": "a901ff2a-...",
      "job_id": "3b29c9fe-...",
      "certificate_code": "CERT-8D2A-4F91",
      "recipient_name": "Carol White",
      "recipient_email": "carol@example.com",
      "course_name": "Data Science with Python",
      "issue_date": "2025-06-15",
      "issuer_name": "Academic Certification Authority",
      "status": "SUCCESS",
      "download_url": "/api/certificates/a901ff2a-.../download",
      "created_at": "2025-06-15T10:00:01Z"
    }
  ]
}
```

---

### 4. Download Single Certificate PDF
- **Endpoint:** `GET /api/certificates/{certificate_id}/download`
- **Response:** PDF Binary Stream (`application/pdf`)

---

### 5. Download All Certificates as ZIP Archive
- **Endpoint:** `GET /api/certificates/jobs/{job_id}/download-zip`
- **Response:** ZIP Binary Stream (`application/zip`)

---

### 6. Verify Certificate Authenticity
- **Endpoint:** `GET /api/certificates/verify/{certificate_code}`
- **Example:** `GET /api/certificates/verify/CERT-8D2A-4F91`
- **Response:**
```json
{
  "is_valid": true,
  "certificate_code": "CERT-8D2A-4F91",
  "recipient_name": "Carol White",
  "course_name": "Data Science with Python",
  "issuer_name": "Academic Certification Authority",
  "issue_date": "2025-06-15",
  "verification_timestamp": "2025-06-15T10:05:00Z",
  "download_url": "/api/certificates/a901ff2a-.../download"
}
```

---

## 🧪 Running Automated Tests

Run the complete test suite with `pytest`:

```bash
python -m pytest tests/ -v
```

The test suite covers:
- **`test_validation.py`**: Name normalization, email regex constraints, date format variations, schema validations.
- **`test_generation.py`**: ReportLab PDF canvas output, header integrity (`%PDF-`), verification code uniqueness.
- **`test_jobs.py`**: Background asynchronous task execution, state transitions (`PENDING` -> `COMPLETED`), CSV upload parsing.
- **`test_retrieval.py`**: Single PDF download, ZIP bundle archive download, and public credential verification.

---

## 💡 Design Decisions & Trade-offs

1. **Vector Drawing (ReportLab) vs HTML-to-PDF (WeasyPrint / Puppeteer)**:
   - *Decision*: Used ReportLab canvas primitives.
   - *Why*: ReportLab generates crisp, lightweight vector PDFs in milliseconds without requiring Chromium, Node.js, or complex C-level font dependencies on Windows/Linux environments.

2. **FastAPI BackgroundTasks vs Celery/Redis**:
   - *Decision*: Used FastAPI `BackgroundTasks`.
   - *Why*: Allows immediate HTTP 202 responses while generating bulk certificates in the background with zero external infrastructure setup. The modular worker service (`process_bulk_generation_job`) is decoupled and can be plugged into Celery/RQ if multi-server scaling is required.

3. **Isolated SQLite Database Architecture**:
   - *Decision*: SQLite with SQLAlchemy 2.0.
   - *Why*: Provides zero-friction local setup, simple file backups, and clean schema migrations, while remaining fully compatible with PostgreSQL/MySQL via an environment variable (`DATABASE_URL`).

4. **Fault Tolerance per Recipient**:
   - *Decision*: Individual certificate failure does not fail the entire batch.
   - *Why*: Errors are caught per record, logged to the certificate table, and the remaining certificates continue processing to completion.

---

## 📈 Learning & Future Scope

### Key Learnings
- Efficient vector rendering in ReportLab for high-aesthetic certificate layouts.
- Decoupling long-running PDF compilation from HTTP request cycles using non-blocking background workers.
- Handling multipart file streaming and CSV data sanitization in FastAPI.

### Future Scope
- **Dynamic Template Designer**: Drag-and-drop web designer to position text, custom signatures, and logos visually.
- **Automated Email Dispatch**: Automated dispatch of certificates to recipient emails via SMTP/SendGrid upon job completion.
- **QR Code Stamping**: Embedding dynamic QR codes that link directly to the `/api/certificates/verify/{code}` verification URL.
- **Cloud Storage Integration**: Storing generated PDFs and ZIPs on AWS S3 or Google Cloud Storage with presigned download links.
