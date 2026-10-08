import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from app.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class JobStatus:
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class CertificateStatus:
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    template_name = Column(String(100), default="default", nullable=False)
    status = Column(String(20), default=JobStatus.PENDING, nullable=False, index=True)
    total_count = Column(Integer, default=0, nullable=False)
    processed_count = Column(Integer, default=0, nullable=False)
    failed_count = Column(Integer, default=0, nullable=False)
    zip_file_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at = Column(DateTime, nullable=True)

    certificates = relationship(
        "CertificateRecord",
        back_populates="job",
        cascade="all, delete-orphan",
        order_by="CertificateRecord.created_at",
    )


class CertificateRecord(Base):
    __tablename__ = "certificates"

    id = Column(String(36), primary_key=True, default=generate_uuid, index=True)
    job_id = Column(String(36), ForeignKey("generation_jobs.id"), nullable=False, index=True)
    certificate_code = Column(String(50), unique=True, index=True, nullable=False)
    recipient_name = Column(String(150), nullable=False)
    recipient_email = Column(String(150), nullable=False)
    course_name = Column(String(200), nullable=False)
    issue_date = Column(String(50), nullable=False)
    issuer_name = Column(String(150), default="Academic Certification Authority", nullable=False)
    status = Column(String(20), default=CertificateStatus.SUCCESS, nullable=False)
    file_path = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    job = relationship("GenerationJob", back_populates="certificates")
