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


def sync_existing_generated_folders(base_dir: str | None = None) -> int:
    """
    Scans the 'generated/' directory for existing generated certificates
    and ensures they are indexed in SQLite so users can see, download, and verify them.
    """
    if not base_dir:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    generated_dir = os.path.join(base_dir, "generated")
    if not os.path.exists(generated_dir):
        return 0

    import re
    import pymupdf

    db = SessionLocal()
    imported_jobs = 0

    try:
        for entry in os.listdir(generated_dir):
            folder_path = os.path.join(generated_dir, entry)
            if not os.path.isdir(folder_path):
                continue

            job_id = entry
            existing_job = db.query(GenerationJob).filter(GenerationJob.id == job_id).first()
            if existing_job:
                continue

            # Find PDFs in this folder
            pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".pdf") and not f.startswith("startup_check")]
            if not pdf_files:
                continue

            # Find ZIP if present
            zip_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".zip")]
            zip_path = os.path.abspath(os.path.join(folder_path, zip_files[0])) if zip_files else None

            # Create GenerationJob record
            job = GenerationJob(
                id=job_id,
                template_name="classic",
                status=JobStatus.COMPLETED,
                total=len(pdf_files),
                successful=len(pdf_files),
                failed=0,
                zip_file_path=zip_path,
                created_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db.add(job)
            db.flush()

            for pdf_name in pdf_files:
                pdf_path = os.path.abspath(os.path.join(folder_path, pdf_name))
                cert_code_match = re.search(r"CERT-[A-Z0-9]+-[A-Z0-9]+", pdf_name)
                cert_code = cert_code_match.group(0) if cert_code_match else f"CERT-{job_id[:4].upper()}-{pdf_name[:4].upper()}"

                recipient_name = "Certificate Recipient"
                course_name = "Professional Certification"
                issuer_name = "Academic Certification Authority"

                try:
                    doc = pymupdf.open(pdf_path)
                    meta = doc.metadata or {}
                    if meta.get("title") and "Certificate -" in meta["title"]:
                        recipient_name = meta["title"].replace("Certificate -", "").strip()
                    if meta.get("subject"):
                        course_name = meta["subject"].strip()
                    if meta.get("author"):
                        issuer_name = meta["author"].strip()
                    doc.close()
                except Exception:
                    parts = pdf_name.replace(".pdf", "").split("_")
                    if len(parts) >= 2:
                        recipient_name = parts[1]

                existing_cert = db.query(CertificateRecord).filter(CertificateRecord.certificate_code == cert_code).first()
                if not existing_cert:
                    cert_rec = CertificateRecord(
                        job_id=job.id,
                        certificate_code=cert_code,
                        recipient_name=recipient_name,
                        recipient_email=f"{''.join(c for c in recipient_name if c.isalnum()).lower()}@example.com",
                        course_name=course_name,
                        issue_date="2026-10-08",
                        issuer_name=issuer_name,
                        status=CertificateStatus.SUCCESS,
                        file_path=pdf_path,
                    )
                    db.add(cert_rec)

            db.commit()
            imported_jobs += 1

        return imported_jobs
    finally:
        db.close()

