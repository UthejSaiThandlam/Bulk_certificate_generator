import logging
import os
import zipfile
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import GenerationJob, CertificateRecord, JobStatus, CertificateStatus
from app.services.certificate_generator import CertificateGenerator

logger = logging.getLogger(__name__)


def process_bulk_generation_job(
    job_id: str,
    db_override: Session | None = None,
    generated_dir_override: str | None = None,
) -> None:
    """
    Background worker task to generate all certificates for a job.
    Includes:
    - Per-recipient fault isolation: one failure does not halt or fail the remaining certificates.
    - Batch commit strategy (every 25 items or at completion) to eliminate I/O overhead.
    - Clean rollback and safe client-facing error messages on unexpected exceptions.
    - ZIP archive bundling.
    """
    db = db_override or SessionLocal()
    should_close = db_override is None
    job: GenerationJob | None = None

    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if not job:
            return

        job.status = JobStatus.PROCESSING
        db.commit()

        # Target directory for this job
        base_dir = generated_dir_override or str(settings.GENERATED_DIR)
        job_dir = os.path.abspath(os.path.join(base_dir, job_id))
        os.makedirs(job_dir, exist_ok=True)

        certificates = (
            db.query(CertificateRecord)
            .filter(CertificateRecord.job_id == job_id)
            .order_by(CertificateRecord.row_index)
            .all()
        )

        generated_files = []
        successful_count = 0
        failed_count = 0
        uncommitted_count = 0

        for cert in certificates:
            # If already failed during ingestion/validation, maintain status
            if cert.status == CertificateStatus.FAILED:
                failed_count += 1
                continue

            # If already succeeded in a prior resumed run, retain file
            if cert.status == CertificateStatus.SUCCESS and cert.file_path and os.path.exists(cert.file_path):
                successful_count += 1
                generated_files.append(cert.file_path)
                continue

            # Generate unique filename for PDF
            clean_name = "".join(c for c in (cert.recipient_name or "recipient") if c.isalnum() or c in ("-", "_")).strip()[:40]
            cert_code = cert.certificate_code or CertificateGenerator.generate_verification_code()
            filename = f"{job_id[:8]}_{clean_name}_{cert_code}.pdf"
            output_path = os.path.join(job_dir, filename)

            try:
                CertificateGenerator.generate_certificate_pdf(
                    output_path=output_path,
                    recipient_name=cert.recipient_name or "",
                    course_name=cert.course_name or "",
                    issue_date=cert.issue_date or "",
                    certificate_code=cert_code,
                    issuer_name=cert.issuer_name or "Academic Certification Authority",
                    template_name=job.template_name,
                )
                cert.file_path = output_path
                cert.certificate_code = cert_code
                cert.status = CertificateStatus.SUCCESS
                cert.error_message = None
                successful_count += 1
                generated_files.append(output_path)
            except Exception as e:
                # Isolate failure to this single certificate
                cert.status = CertificateStatus.FAILED
                cert.error_message = str(e)
                failed_count += 1

            uncommitted_count += 1
            # Batch commit every 25 items to avoid transaction bottlenecks
            if uncommitted_count >= 25:
                job.successful = successful_count
                job.failed = failed_count
                db.commit()
                uncommitted_count = 0

        # Bundle generated certificates into a zip file if any succeeded
        if generated_files:
            zip_filename = f"certificates_{job_id[:8]}.zip"
            zip_path = os.path.join(job_dir, zip_filename)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in generated_files:
                    if os.path.exists(file_path):
                        zipf.write(file_path, arcname=os.path.basename(file_path))
            job.zip_file_path = zip_path

        # Determine final job status
        if failed_count == 0:
            job.status = JobStatus.COMPLETED
        elif successful_count > 0 and failed_count > 0:
            job.status = JobStatus.COMPLETED_WITH_ERRORS
        else:
            job.status = JobStatus.FAILED

        job.successful = successful_count
        job.failed = failed_count
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        logger.exception("Unexpected error while executing bulk generation job %s", job_id)
        db.rollback()
        if job:
            try:
                job.status = JobStatus.FAILED
                job.error_message = f"Job processing error: {str(e)}"
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                db.rollback()
    finally:
        if should_close:
            db.close()


def resume_interrupted_jobs(db_override: Session | None = None) -> int:
    """
    Crash Recovery Routine:
    Finds jobs left in 'PROCESSING' or 'PENDING' status after an unexpected server restart,
    and resumes processing for them.
    """
    db = db_override or SessionLocal()
    should_close = db_override is None
    resumed_count = 0
    try:
        stuck_jobs = (
            db.query(GenerationJob)
            .filter(GenerationJob.status.in_([JobStatus.PROCESSING, JobStatus.PENDING]))
            .all()
        )
        for job in stuck_jobs:
            process_bulk_generation_job(job.id, db_override=db)
            resumed_count += 1
        return resumed_count
    finally:
        if should_close:
            db.close()
