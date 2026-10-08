import io
import os
from app.services.job_processor import process_bulk_generation_job
from app.models import JobStatus


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
    assert data["total_count"] == 2
    assert data["status"] in (JobStatus.PENDING, JobStatus.PROCESSING, JobStatus.COMPLETED)

    # Process job synchronously to verify execution
    job_id = data["id"]
    process_bulk_generation_job(job_id)

    status_resp = client.get(f"/api/certificates/jobs/{job_id}")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["status"] == JobStatus.COMPLETED
    assert status_data["processed_count"] == 2
    assert status_data["failed_count"] == 0
    assert status_data["download_zip_url"] is not None


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
    assert res_data["total_count"] == 2
    job_id = res_data["id"]

    # Run processing
    process_bulk_generation_job(job_id)

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
