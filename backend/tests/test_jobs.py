import io
import pytest
from unittest.mock import patch
from app.services.job_processor import process_bulk_generation_job, resume_interrupted_jobs
from app.services.certificate_generator import CertificateGenerator
from app.models import JobStatus, CertificateStatus


def test_create_generation_job_json(client):
    payload = {
        "template_name": "classic",
        "issuer_name": "Test Academy",
        "recipients": [
            {
                "recipient_name": "Bob Dylan",
                "recipient_email": "bob@example.com",
                "course_name": "Modern Poetry & Songwriting",
                "issue_date": "2025-03-01",
            },
            {
                "recipient_name": "Alice Cooper",
                "recipient_email": "alice@example.com",
                "course_name": "Classic Rock Production",
                "issue_date": "2025-03-01",
            },
        ],
    }

    response = client.post("/api/certificates/generate", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert "id" in data
    assert data["total"] == 2
    assert data["status"] in (JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.COMPLETED)

    job_id = data["id"]
    status_resp = client.get(f"/api/certificates/jobs/{job_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == JobStatus.COMPLETED
    assert status_data["successful"] == 2
    assert status_data["failed"] == 0
    assert status_data["download_zip_url"] is not None


def test_individual_failure_isolation(client):
    """
    CRITICAL RELIABILITY TEST:
    When 1 certificate in a batch fails, it must NOT kill the entire job.
    Job must finish with COMPLETED_WITH_ERRORS, with remaining certificates generated successfully.
    """
    payload = {
        "recipients": [
            {
                "recipient_name": "Passing Student One",
                "recipient_email": "pass1@example.com",
                "course_name": "Computer Science 101",
            },
            {
                "recipient_name": "Faulty Recipient",
                "recipient_email": "fail@example.com",
                "course_name": "Faulty Course",
            },
            {
                "recipient_name": "Passing Student Two",
                "recipient_email": "pass2@example.com",
                "course_name": "Computer Science 101",
            },
        ]
    }

    # Intercept PDF generation for 'Faulty Recipient' to simulate a rendering failure
    original_gen = CertificateGenerator.generate_certificate_pdf

    def faulty_generator(*args, **kwargs):
        if kwargs.get("recipient_name") == "Faulty Recipient" or (len(args) > 1 and args[1] == "Faulty Recipient"):
            raise ValueError("Simulated PDF font rendering corruption error")
        return original_gen(*args, **kwargs)

    with patch.object(CertificateGenerator, "generate_certificate_pdf", side_effect=faulty_generator):
        response = client.post("/api/certificates/generate", json=payload)
        assert response.status_code == 202
        job_id = response.json()["id"]

    # Check resulting job status
    status_resp = client.get(f"/api/certificates/jobs/{job_id}")
    assert status_resp.status_code == 200
    data = status_resp.json()

    # Must be COMPLETED_WITH_ERRORS
    assert data["status"] == JobStatus.COMPLETED_WITH_ERRORS
    assert data["total"] == 3
    assert data["successful"] == 2
    assert data["failed"] == 1

    # Check certificate item breakdown
    certs = data["certificates"]
    assert len(certs) == 3

    failed_certs = [c for c in certs if c["status"] == CertificateStatus.FAILED]
    success_certs = [c for c in certs if c["status"] == CertificateStatus.SUCCESS]

    assert len(failed_certs) == 1
    assert "Simulated PDF font" in failed_certs[0]["error_message"]
    assert len(success_certs) == 2
    assert success_certs[0]["download_url"] is not None


def test_deduplication_by_email(client):
    """Verify duplicate recipient emails within the same batch are deduplicated."""
    payload = {
        "deduplicate_by_email": True,
        "recipients": [
            {
                "recipient_name": "Rahul Sharma",
                "recipient_email": "rahul@example.com",
                "course_name": "Data Analytics",
            },
            {
                "recipient_name": "Rahul Sharma Duplicate",
                "recipient_email": "rahul@example.com",
                "course_name": "Data Analytics",
            },
            {
                "recipient_name": "Priya Patel",
                "recipient_email": "priya@example.com",
                "course_name": "Data Analytics",
            },
        ],
    }

    response = client.post("/api/certificates/generate", json=payload)
    assert response.status_code == 202
    data = response.json()
    assert data["total"] == 2  # Deduplicated from 3 to 2


def test_idempotency_key(client):
    """Verify resending a job with identical idempotency_key returns the original job without duplicate work."""
    payload = {
        "idempotency_key": "idempotent-key-unique-789",
        "recipients": [
            {
                "recipient_name": "Idempotent User",
                "recipient_email": "idempotent@example.com",
                "course_name": "Distributed Systems",
            }
        ],
    }

    resp1 = client.post("/api/certificates/generate", json=payload)
    assert resp1.status_code == 202
    job1_id = resp1.json()["id"]

    # Submit second identical request
    resp2 = client.post("/api/certificates/generate", json=payload)
    assert resp2.status_code == 202
    job2_id = resp2.json()["id"]

    assert job1_id == job2_id


def test_upload_csv_generation(client):
    csv_content = """recipient_name,recipient_email,course_name,issue_date
Carol White,carol@example.com,Data Structures & Algorithms,2025-04-10
David Black,david@example.com,Database Systems & SQL,2025-04-10
"""
    files = {
        "file": ("recipients.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv"),
    }
    data = {
        "issuer_name": "Tech Institute",
        "template_name": "classic",
    }

    response = client.post("/api/certificates/upload-csv", files=files, data=data)
    assert response.status_code == 202
    res_data = response.json()
    assert res_data["total"] == 2
    job_id = res_data["id"]

    status_resp = client.get(f"/api/certificates/jobs/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == JobStatus.COMPLETED


def test_upload_invalid_csv_headers(client):
    csv_content = "unknown_col1,unknown_col2\nfoo,bar\n"
    files = {
        "file": ("invalid.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv"),
    }
    response = client.post("/api/certificates/upload-csv", files=files)
    assert response.status_code == 400
