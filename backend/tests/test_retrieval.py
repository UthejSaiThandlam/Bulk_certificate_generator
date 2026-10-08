from app.services.job_processor import process_bulk_generation_job


def test_job_and_certificate_retrieval_and_download(client):
    # 1. Create and process a job
    create_resp = client.post(
        "/api/certificates/generate",
        json={
            "recipients": [
                {
                    "recipient_name": "Eva Green",
                    "recipient_email": "eva@example.com",
                    "course_name": "Cinema and Art History",
                    "issue_date": "2025-02-14",
                }
            ]
        },
    )
    assert create_resp.status_code == 202
    job_id = create_resp.json()["id"]

    # Process job
    process_bulk_generation_job(job_id)

    # 2. Get Job Details
    job_resp = client.get(f"/api/certificates/jobs/{job_id}")
    assert job_resp.status_code == 200
    job_data = job_resp.json()
    assert len(job_data["certificates"]) == 1

    cert = job_data["certificates"][0]
    cert_id = cert["id"]
    cert_code = cert["certificate_code"]

    # 3. Download Single Certificate PDF
    pdf_resp = client.get(f"/api/certificates/{cert_id}/download")
    assert pdf_resp.status_code == 200
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert pdf_resp.content.startswith(b"%PDF-")

    # 4. Download Job ZIP archive
    zip_resp = client.get(f"/api/certificates/jobs/{job_id}/download-zip")
    assert zip_resp.status_code == 200
    assert zip_resp.headers["content-type"] == "application/zip"
    assert len(zip_resp.content) > 100

    # 5. Verify Certificate by valid code
    verify_resp = client.get(f"/api/certificates/verify/{cert_code}")
    assert verify_resp.status_code == 200
    verify_data = verify_resp.json()
    assert verify_data["is_valid"] is True
    assert verify_data["recipient_name"] == "Eva Green"
    assert verify_data["course_name"] == "Cinema and Art History"

    # 6. Verify non-existent code
    verify_fake = client.get("/api/certificates/verify/NON-EXISTENT-CODE")
    assert verify_fake.status_code == 200
    assert verify_fake.json()["is_valid"] is False


def test_get_nonexistent_job_returns_404(client):
    resp = client.get("/api/certificates/jobs/invalid-id-000")
    assert resp.status_code == 404


def test_get_nonexistent_cert_download_returns_404(client):
    resp = client.get("/api/certificates/invalid-cert-000/download")
    assert resp.status_code == 404
