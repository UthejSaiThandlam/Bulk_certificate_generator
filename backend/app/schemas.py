from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.validators import (
    validate_course_name,
    validate_date_string,
    validate_email_address,
    validate_recipient_name,
)


class RecipientCreate(BaseModel):
    recipient_name: str = Field(..., description="Full name of the certificate recipient", examples=["Alice Johnson"])
    recipient_email: str = Field(..., description="Email address of the recipient", examples=["alice@example.com"])
    course_name: str = Field(..., description="Course or program completed", examples=["Advanced Data Science Bootcamp"])
    issue_date: Optional[str] = Field(default=None, description="Date of issuance (YYYY-MM-DD or readable)", examples=["2025-05-15"])
    issuer_name: Optional[str] = Field(default=None, description="Optional custom issuer name override", examples=["Apex Institute of Technology"])

    @field_validator("recipient_name")
    @classmethod
    def check_name(cls, v: str) -> str:
        return validate_recipient_name(v)

    @field_validator("recipient_email")
    @classmethod
    def check_email(cls, v: str) -> str:
        return validate_email_address(v)

    @field_validator("course_name")
    @classmethod
    def check_course(cls, v: str) -> str:
        return validate_course_name(v)

    @field_validator("issue_date")
    @classmethod
    def check_date(cls, v: Optional[str]) -> str:
        return validate_date_string(v)


class GenerateCertificatesRequest(BaseModel):
    template_name: Optional[str] = Field(default="classic", description="Certificate design template (classic, modern, elegant)")
    issuer_name: Optional[str] = Field(default="Academic Certification Authority", description="Name of the issuing organization")
    recipients: List[RecipientCreate] = Field(..., min_length=1, description="List of recipient details for certificate generation")


class CertificateResponse(BaseModel):
    id: str
    job_id: str
    certificate_code: str
    recipient_name: str
    recipient_email: str
    course_name: str
    issue_date: str
    issuer_name: str
    status: str
    download_url: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: str
    template_name: str
    status: str
    total_count: int
    processed_count: int
    failed_count: int
    progress_percentage: float = 0.0
    download_zip_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobDetailResponse(JobResponse):
    certificates: List[CertificateResponse] = []


class VerificationResponse(BaseModel):
    is_valid: bool
    certificate_code: str
    recipient_name: Optional[str] = None
    course_name: Optional[str] = None
    issuer_name: Optional[str] = None
    issue_date: Optional[str] = None
    verification_timestamp: datetime
    download_url: Optional[str] = None
    error_message: Optional[str] = None
