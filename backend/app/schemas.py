from datetime import datetime
from typing import List, Optional, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.validators import (
    validate_course_name,
    validate_date_string,
    validate_email_address,
    validate_recipient_name,
)

MAX_RECIPIENTS_LIMIT = 5000


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
    template_name: str = Field(default="classic", description="Certificate design template (classic, midnight_dark, vintage_crest, minimal_gold)")
    issuer_name: Optional[str] = Field(default="TECH INSTITUTE", description="Name of the issuing organization")
    idempotency_key: Optional[str] = Field(default=None, max_length=100, description="Optional client idempotency key to prevent duplicate jobs")
    deduplicate_by_email: bool = Field(default=True, description="Whether to automatically deduplicate recipients with identical emails within the job")
    deduplicate: Optional[bool] = Field(default=None, description="Alias for deduplicate_by_email")
    recipients: List[Any] = Field(
        ...,
        min_length=1,
        max_length=MAX_RECIPIENTS_LIMIT,
        description="List of raw recipient records to be validated individually during job ingestion",
    )


class CertificateResponse(BaseModel):
    id: str
    job_id: str
    row_index: int = 0
    certificate_code: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_email: Optional[str] = None
    course_name: Optional[str] = None
    issue_date: Optional[str] = None
    issuer_name: Optional[str] = None
    status: str
    download_url: Optional[str] = None
    error_message: Optional[str] = None
    raw_input: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class JobResponse(BaseModel):
    id: str
    idempotency_key: Optional[str] = None
    template_name: str
    status: str
    total: int
    completed: int
    successful: int
    failed: int
    progress_percentage: float = 0.0
    recommended_polling_interval_seconds: int = 2
    download_zip_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class JobDetailResponse(JobResponse):
    certificates: List[CertificateResponse] = []


class JobCertificatesPageResponse(BaseModel):
    total: int
    limit: int
    offset: int
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
