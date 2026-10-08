import json
import os
from datetime import datetime, timezone
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, UploadFile, File, Form, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.config import settings
from app.database import get_db
from app.models import GenerationJob, CertificateRecord, JobStatus, CertificateStatus
from app.schemas import (
    GenerateCertificatesRequest,
    RecipientCreate,
    JobResponse,
    JobDetailResponse,
    JobCertificatesPageResponse,
    CertificateResponse,
    VerificationResponse,
)
from app.services.certificate_generator import CertificateGenerator
from app.services.job_processor import process_bulk_generation_job
from app.utils.file_parser import extract_raw_recipients_from_file
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
        recommended_polling_interval_seconds=settings.RECOMMENDED_POLLING_INTERVAL_SECONDS,
        download_zip_url=zip_url,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at,
    )


def _build_certificate_response(cert: CertificateRecord) -> CertificateResponse:
    # Decouple download_url from expensive disk os.path.exists checks during polling
    download_url = f"/api/certificates/{cert.id}/download" if cert.status == CertificateStatus.SUCCESS else None
    return CertificateResponse(
        id=cert.id,
        job_id=cert.job_id,
        row_index=cert.row_index,
        certificate_code=cert.certificate_code,
        recipient_name=cert.recipient_name,
        recipient_email=cert.recipient_email,
        course_name=cert.course_name,
        issue_date=cert.issue_date,
        issuer_name=cert.issuer_name,
        status=cert.status,
        download_url=download_url,
        error_message=cert.error_message,
        raw_input=cert.raw_input,
        created_at=cert.created_at,
    )


def _ingest_job_from_raw_recipients(
    raw_recipients: List[Any],
    template_name: str,
    issuer_name: str,
    idempotency_key: Optional[str],
    deduplicate_by_email: bool,
    background_tasks: BackgroundTasks,
    db: Session,
) -> JobResponse:
    """
    Unified ingestion pipeline:
    - Checks idempotency.
    - Validates batch bounds.
    - Iterates over each recipient independently:
      * Valid rows become PENDING certificates.
      * Invalid rows become FAILED certificates with error_message and row_index.
    - Prevents 422 whole-batch rejections.
    - Handles concurrent duplicate idempotency keys safely with IntegrityError handling.
    """
    # 1. Idempotency Check
    if idempotency_key:
        existing_job = db.query(GenerationJob).filter(GenerationJob.idempotency_key == idempotency_key).first()
        if existing_job:
            return _build_job_response(existing_job)

    # 2. Batch bounds
    if not raw_recipients:
        raise HTTPException(status_code=400, detail="Recipients list cannot be empty")
    if len(raw_recipients) > settings.MAX_RECIPIENTS_LIMIT:
        raise HTTPException(
            status_code=400,
            detail=f"Exceeded maximum recipient limit of {settings.MAX_RECIPIENTS_LIMIT} per job. Received: {len(raw_recipients)}",
        )

    # 3. Create GenerationJob shell
    job = GenerationJob(
        idempotency_key=idempotency_key,
        template_name=template_name or "classic",
        status=JobStatus.PENDING,
        total=0,
        successful=0,
        failed=0,
    )

    try:
        db.add(job)
        db.flush()
    except IntegrityError:
        db.rollback()
        if idempotency_key:
            existing = db.query(GenerationJob).filter(GenerationJob.idempotency_key == idempotency_key).first()
            if existing:
                return _build_job_response(existing)
        raise HTTPException(status_code=409, detail="A job with this idempotency key was submitted concurrently.")

    pending_records: List[CertificateRecord] = []
    failed_records: List[CertificateRecord] = []
    seen_emails = set()

    for row_idx, item in enumerate(raw_recipients, start=1):
        if isinstance(item, dict):
            data = item
        elif hasattr(item, "model_dump"):
            data = item.model_dump()
        elif hasattr(item, "__dict__"):
            data = item.__dict__
        else:
            data = {"raw": str(item)}

        raw_name = str(data.get("recipient_name") or "").strip()
        raw_email = str(data.get("recipient_email") or "").strip()
        raw_course = str(data.get("course_name") or "").strip()
        raw_date = data.get("issue_date")
        raw_issuer = str(data.get("issuer_name") or issuer_name).strip()

        # Deduplication by email
        clean_email_key = raw_email.lower()
        if deduplicate_by_email and clean_email_key:
            if clean_email_key in seen_emails:
                continue
            seen_emails.add(clean_email_key)

        # Validate individually
        try:
            validated = RecipientCreate(
                recipient_name=raw_name,
                recipient_email=raw_email,
                course_name=raw_course,
                issue_date=raw_date,
                issuer_name=raw_issuer or issuer_name,
            )
            cert_code = CertificateGenerator.generate_verification_code()
            cert_record = CertificateRecord(
                job_id=job.id,
                row_index=row_idx,
                certificate_code=cert_code,
                recipient_name=validated.recipient_name,
                recipient_email=validated.recipient_email,
                course_name=validated.course_name,
                issue_date=validated.issue_date or validate_date_string(None),
                issuer_name=validated.issuer_name or issuer_name,
                status=CertificateStatus.PENDING,
                raw_input=json.dumps(data),
            )
            pending_records.append(cert_record)
        except Exception as val_err:
            # Fault isolation: row-level failure recorded
            fail_record = CertificateRecord(
                job_id=job.id,
                row_index=row_idx,
                certificate_code=None,
                recipient_name=raw_name or None,
                recipient_email=raw_email or None,
                course_name=raw_course or None,
                issue_date=str(raw_date) if raw_date else None,
                issuer_name=raw_issuer or issuer_name,
                status=CertificateStatus.FAILED,
                error_message=f"Validation failed: {str(val_err)}",
                raw_input=json.dumps(data),
            )
            failed_records.append(fail_record)

    all_records = pending_records + failed_records
    if not all_records:
        db.rollback()
        raise HTTPException(status_code=400, detail="No valid or processable recipients found in submission")

    job.total = len(all_records)
    job.failed = len(failed_records)
    job.successful = 0

    for record in all_records:
        db.add(record)

    db.commit()
    db.refresh(job)

    # Queue background task for pending items if any exist
    if pending_records:
        background_tasks.add_task(process_bulk_generation_job, job.id)
    else:
        # All items were invalid
        job.status = JobStatus.FAILED
        job.error_message = f"All {len(failed_records)} recipient rows failed validation."
        db.commit()

    return _build_job_response(job)


@router.post(
    "/generate",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create bulk certificate generation job with row-level validation isolation",
)
def create_bulk_generation_job(
    request: GenerateCertificatesRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Submits a batch of recipients for certificate generation.
    - Idempotency key supported to avoid duplicate processing.
    - Validates each recipient individually in an isolated loop.
    - Valid rows become PENDING certificates. Invalid rows become FAILED certificates.
    - Never rejects the entire batch with 422 if only some rows are invalid.
    """
    dedupe = request.deduplicate if request.deduplicate is not None else request.deduplicate_by_email
    return _ingest_job_from_raw_recipients(
        raw_recipients=request.recipients,
        template_name=request.template_name,
        issuer_name=request.issuer_name or "TECH INSTITUTE",
        idempotency_key=request.idempotency_key,
        deduplicate_by_email=dedupe,
        background_tasks=background_tasks,
        db=db,
    )


def _handle_file_upload(
    file: UploadFile,
    template_name: str,
    issuer_name: str,
    idempotency_key: Optional[str],
    deduplicate: bool,
    background_tasks: BackgroundTasks,
    db: Session,
) -> JobResponse:
    # Enforce bounded file read to protect against memory exhaustion (HTTP 413)
    max_bytes = settings.MAX_UPLOAD_SIZE_BYTES
    content = file.file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded file exceeds maximum limit of {max_bytes // (1024 * 1024)} MB",
        )

    try:
        raw_rows = extract_raw_recipients_from_file(
            filename=file.filename or "recipients.csv",
            content_bytes=content,
            default_issuer=issuer_name,
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err))

    return _ingest_job_from_raw_recipients(
        raw_recipients=raw_rows,
        template_name=template_name,
        issuer_name=issuer_name,
        idempotency_key=idempotency_key,
        deduplicate_by_email=deduplicate,
        background_tasks=background_tasks,
        db=db,
    )


@router.post(
    "/upload-file",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload file (Excel XLSX/XLS, CSV, JSON, TSV, TXT) for bulk certificate generation",
)
def upload_file_and_generate(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Recipient records file (.xlsx, .csv, .json, .tsv, .txt)"),
    template_name: str = Form("classic"),
    issuer_name: str = Form("Academic Certification Authority"),
    idempotency_key: Optional[str] = Form(None),
    deduplicate: bool = Form(True),
    db: Session = Depends(get_db),
):
    return _handle_file_upload(
        file=file,
        template_name=template_name,
        issuer_name=issuer_name,
        idempotency_key=idempotency_key,
        deduplicate=deduplicate,
        background_tasks=background_tasks,
        db=db,
    )


@router.post(
    "/upload-csv",
    response_model=JobResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload CSV file for bulk certificate generation (Alias for upload-file)",
)
def upload_csv_and_generate(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file with recipient records"),
    template_name: str = Form("classic"),
    issuer_name: str = Form("Academic Certification Authority"),
    idempotency_key: Optional[str] = Form(None),
    deduplicate: bool = Form(True),
    db: Session = Depends(get_db),
):
    return _handle_file_upload(
        file=file,
        template_name=template_name,
        issuer_name=issuer_name,
        idempotency_key=idempotency_key,
        deduplicate=deduplicate,
        background_tasks=background_tasks,
        db=db,
    )


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
    summary="Get generation job status, counts, and certificates list",
)
def get_job_status(
    job_id: str,
    limit: int = Query(100, ge=1, le=500, description="Max certificates to include in response"),
    offset: int = Query(0, ge=0, description="Offset for paginating certificates"),
    db: Session = Depends(get_db),
):
    """Check the real-time status and progress of a bulk generation job."""
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")

    base = _build_job_response(job)
    certs_query = (
        db.query(CertificateRecord)
        .filter(CertificateRecord.job_id == job_id)
        .order_by(CertificateRecord.row_index)
        .offset(offset)
        .limit(limit)
        .all()
    )
    certs = [_build_certificate_response(c) for c in certs_query]

    return JobDetailResponse(
        **base.model_dump(),
        certificates=certs,
    )


@router.get(
    "/jobs/{job_id}/certificates",
    response_model=JobCertificatesPageResponse,
    summary="Paginated retrieval of certificates for a generation job",
)
def get_job_certificates_paginated(
    job_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
):
    job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found")

    query = db.query(CertificateRecord).filter(CertificateRecord.job_id == job_id)
    if status_filter:
        query = query.filter(CertificateRecord.status == status_filter.upper())

    total = query.count()
    records = query.order_by(CertificateRecord.row_index).offset(offset).limit(limit).all()

    return JobCertificatesPageResponse(
        total=total,
        limit=limit,
        offset=offset,
        certificates=[_build_certificate_response(c) for c in records],
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

    clean_name = "".join(c for c in (cert.recipient_name or "recipient") if c.isalnum() or c in ("-", "_")).strip()
    download_filename = f"Certificate_{cert.certificate_code or 'ID'}_{clean_name}.pdf"
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
    Single optimised query — no N+1 round-trips.
    """
    cleaned_code = certificate_code.strip().upper()

    # Single query: fetch cert and eagerly load the parent job in one SQL call
    cert = (
        db.query(CertificateRecord)
        .filter(CertificateRecord.certificate_code == cleaned_code)
        .options(joinedload(CertificateRecord.job))
        .first()
    )

    now = datetime.now(timezone.utc)

    if not cert:
        return VerificationResponse(
            is_valid=False,
            certificate_code=cleaned_code,
            verification_timestamp=now,
            error_message="Certificate code not found in registry",
        )

    is_valid = cert.status == CertificateStatus.SUCCESS
    download_url = f"/api/certificates/{cert.id}/download" if is_valid else None

    return VerificationResponse(
        is_valid=is_valid,
        certificate_code=cert.certificate_code or cleaned_code,
        recipient_name=cert.recipient_name,
        course_name=cert.course_name,
        issuer_name=cert.issuer_name,
        issue_date=cert.issue_date,
        verification_timestamp=now,
        download_url=download_url,
        error_message=cert.error_message if not is_valid else None,
    )
