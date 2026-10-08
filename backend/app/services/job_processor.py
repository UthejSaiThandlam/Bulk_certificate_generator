import os
import zipfile
import traceback
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import GenerationJob, CertificateRecord, JobStatus, CertificateStatus
from app.services.certificate_generator import CertificateGenerator


def process_bulk_generation_job(job_id: str, db_override: Session | None = None) -> None:
    """
    Background worker task to generate all certificates for a job.
    Includes:
    - Independent per-recipient fault isolation (one failure won't stop others).
    - Status transitions: PENDING -> PROCESSING -> COMPLETED / COMPLETED_WITH_ERRORS / FAILED.
    - Transactional status updates.
    - ZIP archive bundling.
    """
    db = db_override or SessionLocal()
    should_close = db_override is None

    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if not job:
            return

        job.status = JobStatus.PROCESSING
        db.commit()

        # Target directory for this job
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        job_dir = os.path.abspath(os.path.join(base_dir, "generated", job_id))
        os.makedirs(job_dir, exist_ok=True)

        certificates = (
            db.query(CertificateRecord)
            .filter(CertificateRecord.job_id == job_id)
            .order_by(CertificateRecord.created_at)
            .all()
        )

        generated_files = []
        successful_count = 0
        failed_count = 0

        for cert in certificates:
            # Skip already completed items in case of resumed job
            if cert.status == CertificateStatus.SUCCESS and cert.file_path and os.path.exists(cert.file_path):
                successful_count += 1
                generated_files.append(cert.file_path)
                continue

            cert.status = CertificateStatus.PROCESSING
            db.commit()

            # Unique, collision-proof filename: {job_id[:8]}_{recipient_clean}_{certificate_code}.pdf
            clean_name = "".join(c for c in cert.recipient_name if c.isalnum() or c in ("-", "_")).strip()[:40]
            filename = f"{job_id[:8]}_{clean_name}_{cert.certificate_code}.pdf"
            output_path = os.path.join(job_dir, filename)

            try:
                CertificateGenerator.generate_certificate_pdf(
                    output_path=output_path,
                    recipient_name=cert.recipient_name,
                    course_name=cert.course_name,
                    issue_date=cert.issue_date,
                    certificate_code=cert.certificate_code,
                    issuer_name=cert.issuer_name,
                    template_name=job.template_name,
                )
                cert.file_path = output_path
                cert.status = CertificateStatus.SUCCESS
                cert.error_message = None
                successful_count += 1
                generated_files.append(output_path)
            except Exception as e:
                # Isolate failure: mark certificate record FAILED and proceed to remaining
                cert.status = CertificateStatus.FAILED
                cert.error_message = str(e)
                failed_count += 1

            # Update live counter
            job.successful = successful_count
            job.failed = failed_count
            db.commit()

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
        if job:
            job.status = JobStatus.FAILED
            job.error_message = f"{str(e)}\n{traceback.format_exc()}"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        if should_close:
            db.close()


def resume_interrupted_jobs() -> int:
    """
    Crash Recovery Routine:
    Finds jobs left in 'PROCESSING' status after an unexpected server restart,
    and resumes processing for their unfinished items.
    """
    db = SessionLocal()
    resumed_count = 0
    try:
        stuck_jobs = db.query(GenerationJob).filter(GenerationJob.status == JobStatus.PROCESSING).all()
        for job in stuck_jobs:
            process_bulk_generation_job(job.id, db_override=db)
            resumed_count += 1
        return resumed_count
    finally:
        db.close()
