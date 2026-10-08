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
    MAX_RECIPIENTS_LIMIT,
)
from app.services.certificate_generator import CertificateGenerator
from app.services.job_processor import process_bulk_generation_job
from app.utils.validators import validate_date_string

router = APIRouter(prefix="/api/certificates", tags=["Certificates"])


def _build_job_response(job: GenerationJob) -> JobResponse:
    completed = job.successful + job.failed
    progress = 0.0
    if job.total > 0:
        progress = round((completed / job.total) * 100, 1)

    zip_url = f"/api/certificates/jobs/{job.id}/download-zip" if job.zip_file_path and os.path.exists(job.zip_file_path) else None

    return JobResponse(
        id=job.id,
        idempotency_key=job.idempotency_key,
        template_name=job.template_name,
        status=job.status,
        total=job.total,
        completed=completed,
        successful=job.successful,
        failed=job.failed,
        progress_percentage=progress,
        recommended_polling_interval_seconds=2,
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
        error_message=cert.error_message,
        created_at=cert.created_at,
    )


@router.post(
    "/generate",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create bulk certificate generation job with deduplication and idempotency",
)
def create_bulk_generation_job(
    request: GenerateCertificatesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Submits a batch of recipients for certificate generation.
    - Idempotency key supported to avoid duplicate processing.
    - Deduplicates recipients by email if enabled.
    - Enforces maximum batch limit (5,000 recipients).
    - Returns HTTP 202 Accepted and processes generation in background.
    """
    # 1. Idempotency Check
    if request.idempotency_key:
        existing_job = db.query(GenerationJob).filter(GenerationJob.idempotency_key == request.idempotency_key).first()
        if existing_job:
            return _build_job_response(existing_job)

    # 2. Deduplication
    recipients_to_process = []
    seen_emails = set()
    for item in request.recipients:
        email_key = item.recipient_email.lower().strip()
        if request.deduplicate_by_email:
            if email_key in seen_emails:
                continue
            seen_emails.add(email_key)
        recipients_to_process.append(item)

    if not recipients_to_process:
        raise HTTPException(status_code=400, detail="No unique recipients found in request")

    # 3. Create Job
    job = GenerationJob(
        idempotency_key=request.idempotency_key,
        template_name=request.template_name or "classic",
        status=JobStatus.PENDING,
        total=len(recipients_to_process),
        successful=0,
        failed=0,
    )
    db.add(job)
    db.flush()

    for item in recipients_to_process:
        cert_code = CertificateGenerator.generate_verification_code()
        cert_record = CertificateRecord(
            job_id=job.id,
            certificate_code=cert_code,
            recipient_name=item.recipient_name,
            recipient_email=item.recipient_email,
            course_name=item.course_name,
            issue_date=item.issue_date or validate_date_string(None),
            issuer_name=item.issuer_name or request.issuer_name,
            status=CertificateStatus.PENDING,
        )
        db.add(cert_record)

    db.commit()
    db.refresh(job)

    # Queue background task
    background_tasks.add_task(process_bulk_generation_job, job.id)

    return _build_job_response(job)


from app.utils.file_parser import extract_recipients_from_any_file


def _create_job_from_recipients(
    recipients: List[RecipientCreate],
    template_name: str,
    issuer_name: str,
    background_tasks: BackgroundTasks,
    db: Session,
) -> JobResponse:
    job = GenerationJob(
        template_name=template_name,
        status=JobStatus.PENDING,
        total=len(recipients),
        successful=0,
        failed=0,
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
            status=CertificateStatus.PENDING,
        )
        db.add(cert_record)

    db.commit()
    db.refresh(job)

    if background_tasks:
        background_tasks.add_task(process_bulk_generation_job, job.id)
    else:
        process_bulk_generation_job(job.id)

    return _build_job_response(job)


@router.post(
    "/upload-file",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload any file (PDF, Word DOCX, Excel XLSX/XLS, CSV, JSON, TSV, TXT) for bulk certificate generation",
)
async def upload_file_and_generate(
    file: UploadFile = File(..., description="Recipient records file (.pdf, .docx, .xlsx, .csv, .json, .txt)"),
    template_name: str = Form("classic"),
    issuer_name: str = Form("Academic Certification Authority"),
    deduplicate: bool = Form(True),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """
    Universal Ingestion Endpoint:
    Accepts Excel (.xlsx, .xls), Word (.docx), PDF (.pdf), CSV (.csv), JSON (.json), or TSV/TXT.
    Automatically identifies recipient name, email, course, and date columns.
    """
    content = await file.read()
    try:
        recipients = extract_recipients_from_any_file(
            filename=file.filename or "unknown.csv",
            content_bytes=content,
            default_issuer=issuer_name,
            deduplicate=deduplicate,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    return _create_job_from_recipients(recipients, template_name, issuer_name, background_tasks, db)


@router.post(
    "/upload-csv",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload CSV file for bulk certificate generation (Backwards compatible)",
)
async def upload_csv_and_generate(
    file: UploadFile = File(..., description="CSV file with recipient records"),
    template_name: str = Form("classic"),
    issuer_name: str = Form("Academic Certification Authority"),
    deduplicate: bool = Form(True),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    content = await file.read()
    try:
        recipients = extract_recipients_from_any_file(
            filename=file.filename or "data.csv",
            content_bytes=content,
            default_issuer=issuer_name,
            deduplicate=deduplicate,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    return _create_job_from_recipients(recipients, template_name, issuer_name, background_tasks, db)


@router.get(
    "/jobs",
    response_model=List[JobResponse],
    summary="List recent certificate generation jobs",
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
    summary="Get generation job status, progress, and individual certificates",
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

    clean_name = "".join(c for c in cert.recipient_name if c.isalnum() or c in ("-", "_")).strip()
    download_filename = f"Certificate_{cert.certificate_code}_{clean_name}.pdf"
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
    from datetime import datetime, timezone

    cleaned_code = certificate_code.strip().upper()
    cert = db.query(CertificateRecord).filter(CertificateRecord.certificate_code == cleaned_code).first()

    if not cert:
        return VerificationResponse(
            is_valid=False,
            certificate_code=cleaned_code,
            verification_timestamp=datetime.now(timezone.utc),
            error_message="Certificate code not found in registry",
        )

    download_url = f"/api/certificates/{cert.id}/download" if cert.file_path and os.path.exists(cert.file_path) else None

    return VerificationResponse(
        is_valid=(cert.status == CertificateStatus.SUCCESS),
        certificate_code=cert.certificate_code,
        recipient_name=cert.recipient_name,
        course_name=cert.course_name,
        issuer_name=cert.issuer_name,
        issue_date=cert.issue_date,
        verification_timestamp=datetime.now(timezone.utc),
        download_url=download_url,
        error_message=cert.error_message if cert.status != CertificateStatus.SUCCESS else None,
    )
