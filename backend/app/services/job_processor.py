import os
import zipfile
import traceback
from datetime import datetime, timezone
from app.database import SessionLocal
from app.models import GenerationJob, CertificateRecord, JobStatus, CertificateStatus
from app.services.certificate_generator import CertificateGenerator


def process_bulk_generation_job(job_id: str) -> None:
    """
    Background worker task to generate all certificates for a job,
    update database records, and bundle them into a zip archive.
    """
    db = SessionLocal()
    try:
        job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
        if not job:
            return

        job.status = JobStatus.PROCESSING
        job.processed_count = 0
        job.failed_count = 0
        db.commit()

        # Target directory for this job's certificates
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        job_dir = os.path.abspath(os.path.join(base_dir, "generated", job_id))
        os.makedirs(job_dir, exist_ok=True)

        certificates = db.query(CertificateRecord).filter(CertificateRecord.job_id == job_id).all()
        generated_files = []

        for cert in certificates:
            safe_name = "".join(c for c in cert.recipient_name if c.isalnum() or c in (" ", "-", "_")).strip()
            filename = f"{cert.certificate_code}_{safe_name}.pdf"
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
                generated_files.append(output_path)
            except Exception as e:
                cert.status = CertificateStatus.FAILED
                cert.error_message = str(e)
                job.failed_count += 1

            job.processed_count += 1
            db.commit()

        # Bundle generated certificates into a zip file
        if generated_files:
            zip_filename = f"certificates_{job_id[:8]}.zip"
            zip_path = os.path.join(job_dir, zip_filename)
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path in generated_files:
                    zipf.write(file_path, arcname=os.path.basename(file_path))
            job.zip_file_path = zip_path

        job.status = JobStatus.COMPLETED if job.failed_count < job.total_count else JobStatus.FAILED
        job.completed_at = datetime.now(timezone.utc)
        db.commit()

    except Exception as e:
        if job:
            job.status = JobStatus.FAILED
            job.error_message = f"{str(e)}\n{traceback.format_exc()}"
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
    finally:
        db.close()
