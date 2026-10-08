import csv
import io
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import GenerationJob, CertificateRecord, JobStatus, CertificateStatus
from app.schemas import (
    GenerateCertificatesRequest,
    RecipientCreate,
    JobResponse,
    JobDetailResponse,
    CertificateResponse,
    VerificationResponse,
)
from app.services.certificate_generator import CertificateGenerator
from app.services.job_processor import process_bulk_generation_job
from app.utils.validators import validate_email_address, validate_recipient_name, validate_course_name, validate_date_string

router = APIRouter(prefix="/api/certificates", tags=["Certificates"])


def _build_job_response(job: GenerationJob) -> JobResponse:
    progress = 0.0
    if job.total_count > 0:
        progress = round((job.processed_count / job.total_count) * 100, 1)

    zip_url = f"/api/certificates/jobs/{job.id}/download-zip" if job.zip_file_path and os.path.exists(job.zip_file_path) else None

    return JobResponse(
        id=job.id,
        template_name=job.template_name,
        status=job.status,
        total_count=job.total_count,
        processed_count=job.processed_count,
        failed_count=job.failed_count,
        progress_percentage=progress,
        download_zip_url=zip_url,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def _build_certificate_response(cert: CertificateRecord) -> CertificateResponse:
    download_url = f"/api/certificates/{cert.id}/download" if cert.file_path and os.path.exists(cert.file_path) else None
    return CertificateResponse(
        id=cert.id,
        job_id=cert.job_id,
        certificate_code=cert.certificate_code,
        recipient_name=cert.recipient_name,
        recipient_email=cert.recipient_email,
        course_name=cert.course_name,
        issue_date=cert.issue_date,
        issuer_name=cert.issuer_name,
        status=cert.status,
        download_url=download_url,
        created_at=cert.created_at,
    )


@router.post(
    "/generate",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a bulk certificate generation job via JSON",
)
def create_bulk_generation_job(
    request: GenerateCertificatesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Submits a batch of recipients for certificate generation.
    Returns 202 Accepted and processes the certificate generation asynchronously.
    """
    if not request.recipients:
        raise HTTPException(status_code=400, detail="Recipients list cannot be empty")

    job = GenerationJob(
        template_name=request.template_name or "classic",
        status=JobStatus.PENDING,
        total_count=len(request.recipients),
        processed_count=0,
        failed_count=0,
    )
    db.add(job)
    db.flush()

    for item in request.recipients:
        cert_code = CertificateGenerator.generate_verification_code()
        cert_record = CertificateRecord(
            job_id=job.id,
            certificate_code=cert_code,
            recipient_name=item.recipient_name,
            recipient_email=item.recipient_email,
            course_name=item.course_name,
            issue_date=item.issue_date or validate_date_string(None),
            issuer_name=item.issuer_name or request.issuer_name,
            status=CertificateStatus.SUCCESS,
        )
        db.add(cert_record)

    db.commit()
    db.refresh(job)

    # Queue background task
    background_tasks.add_task(process_bulk_generation_job, job.id)

    return _build_job_response(job)


@router.post(
    "/upload-csv",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload CSV file for bulk certificate generation",
)
async def upload_csv_and_generate(
    file: UploadFile = File(..., description="CSV file with recipient records"),
    template_name: str = Form("classic"),
    issuer_name: str = Form("Academic Certification Authority"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """
    Upload a CSV file containing recipient headers:
    `recipient_name`, `recipient_email`, `course_name`, `issue_date`
    (or `name`, `email`, `course`, `date`).
    """
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files (.csv) are supported")

    content = await file.read()
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            decoded = content.decode("latin-1")
        except Exception:
            raise HTTPException(status_code=400, detail="Could not decode CSV file. Please ensure UTF-8 encoding.")

    reader = csv.DictReader(io.StringIO(decoded))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV file is empty or headers are missing")

    # Normalize headers
    header_map = {}
    for h in reader.fieldnames:
        clean = h.strip().lower().replace(" ", "_")
        header_map[clean] = h

    name_key = header_map.get("recipient_name") or header_map.get("name") or header_map.get("full_name")
    email_key = header_map.get("recipient_email") or header_map.get("email")
    course_key = header_map.get("course_name") or header_map.get("course") or header_map.get("program")
    date_key = header_map.get("issue_date") or header_map.get("date")

    if not (name_key and email_key and course_key):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain at least name, email, and course columns. Found columns: {list(reader.fieldnames)}",
        )

    recipients: List[RecipientCreate] = []
    row_errors = []

    for idx, row in enumerate(reader, start=1):
        raw_name = row.get(name_key, "").strip()
        raw_email = row.get(email_key, "").strip()
        raw_course = row.get(course_key, "").strip()
        raw_date = row.get(date_key, "").strip() if date_key else None

        if not raw_name and not raw_email and not raw_course:
            continue  # skip completely blank rows

        try:
            recipients.append(
                RecipientCreate(
                    recipient_name=raw_name,
                    recipient_email=raw_email,
                    course_name=raw_course,
                    issue_date=raw_date,
                    issuer_name=issuer_name,
                )
            )
        except Exception as err:
            row_errors.append(f"Row {idx}: {str(err)}")

    if row_errors:
        raise HTTPException(
            status_code=422,
            detail={"message": "Validation errors found in CSV rows", "errors": row_errors[:10]},
        )

    if not recipients:
        raise HTTPException(status_code=400, detail="No valid recipient rows found in CSV")

    # Create Job
    job = GenerationJob(
        template_name=template_name,
        status=JobStatus.PENDING,
        total_count=len(recipients),
        processed_count=0,
        failed_count=0,
    )
    db.add(job)
    db.flush()

    for item in recipients:
        cert_code = CertificateGenerator.generate_verification_code()
        cert_record = CertificateRecord(
            job_id=job.id,
            certificate_code=cert_code,
            recipient_name=item.recipient_name,
            recipient_email=item.recipient_email,
            course_name=item.course_name,
            issue_date=item.issue_date,
            issuer_name=item.issuer_name or issuer_name,
            status=CertificateStatus.SUCCESS,
        )
        db.add(cert_record)

    db.commit()
    db.refresh(job)

    if background_tasks:
        background_tasks.add_task(process_bulk_generation_job, job.id)
    else:
        # Fallback sync execution if no background tasks instance
        process_bulk_generation_job(job.id)

    return _build_job_response(job)


@router.get(
    "/jobs",
    response_model=List[JobResponse],
    summary="List all certificate generation jobs",
)
def list_jobs(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retrieve list of generation jobs with recent status."""
    jobs = db.query(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(limit).all()
    return [_build_job_response(j) for j in jobs]


@router.get(
    "/jobs/{job_id}",
    response_model=JobDetailResponse,
    summary="Get generation job status and certificates",
)
def get_job_status(job_id: str, db: Session = Depends(get_db)):
    """Check the real-time status and progress of a bulk generation job."""
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")

    base = _build_job_response(job)
    certs = [_build_certificate_response(c) for c in job.certificates]

    return JobDetailResponse(
        **base.model_dump(),
        certificates=certs,
    )


@router.get(
    "/jobs/{job_id}/download-zip",
    summary="Download bundled zip file containing all generated certificates",
)
def download_job_zip(job_id: str, db: Session = Depends(get_db)):
    """Download the ZIP archive of all successfully generated certificates."""
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(status_code=409, detail="Job is still processing. Please try again shortly.")

    if not job.zip_file_path or not os.path.exists(job.zip_file_path):
        raise HTTPException(status_code=404, detail="ZIP archive not found or no certificates were generated")

    filename = os.path.basename(job.zip_file_path)
    return FileResponse(
        path=job.zip_file_path,
        media_type="application/zip",
        filename=filename,
    )


@router.get(
    "/{certificate_id}/download",
    summary="Download single certificate PDF",
)
def download_single_certificate(certificate_id: str, db: Session = Depends(get_db)):
    """Download an individual certificate PDF."""
    cert = db.query(CertificateRecord).filter(CertificateRecord.id == certificate_id).first()
    if not cert:
        raise HTTPException(status_code=404, detail="Certificate not found")

    if not cert.file_path or not os.path.exists(cert.file_path):
        raise HTTPException(status_code=404, detail="Certificate file has not been generated yet or was removed")

    safe_name = "".join(c for c in cert.recipient_name if c.isalnum() or c in ("-", "_")).strip()
    download_filename = f"Certificate_{cert.certificate_code}_{safe_name}.pdf"
    return FileResponse(
        path=cert.file_path,
        media_type="application/pdf",
        filename=download_filename,
    )


@router.get(
    "/verify/{certificate_code}",
    response_model=VerificationResponse,
    summary="Verify authenticity of a certificate by verification code",
)
def verify_certificate(certificate_code: str, db: Session = Depends(get_db)):
    """
    Public verification endpoint to authenticate a certificate code.
    Used by employers or third parties to check credential validity.
    """
    cleaned_code = certificate_code.strip().upper()
    cert = db.query(CertificateRecord).filter(CertificateRecord.certificate_code == cleaned_code).first()

    from datetime import datetime, timezone

    if not cert:
        return VerificationResponse(
            is_valid=False,
            certificate_code=cleaned_code,
            verification_timestamp=datetime.now(timezone.utc),
            error_message="Certificate code not found in registry",
        )

    download_url = f"/api/certificates/{cert.id}/download" if cert.file_path and os.path.exists(cert.file_path) else None

    return VerificationResponse(
        is_valid=True,
        certificate_code=cert.certificate_code,
        recipient_name=cert.recipient_name,
        course_name=cert.course_name,
        issuer_name=cert.issuer_name,
        issue_date=cert.issue_date,
        verification_timestamp=datetime.now(timezone.utc),
        download_url=download_url,
    )
