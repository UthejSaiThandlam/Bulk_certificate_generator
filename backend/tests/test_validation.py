import pytest
from pydantic import ValidationError
from app.utils.validators import (
    validate_email_address,
    validate_recipient_name,
    validate_course_name,
    validate_date_string,
)
from app.schemas import RecipientCreate, GenerateCertificatesRequest, MAX_RECIPIENTS_LIMIT


def test_validate_email_success():
    assert validate_email_address("test@example.com") == "test@example.com"
    assert validate_email_address(" User.Name+Tag@Domain.Org ") == "user.name+tag@domain.org"


def test_validate_email_failure():
    with pytest.raises(ValueError, match="Invalid email"):
        validate_email_address("not-an-email")
    with pytest.raises(ValueError, match="Invalid email"):
        validate_email_address("user@")
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_email_address("")


def test_validate_recipient_name():
    assert validate_recipient_name("Jane Doe") == "Jane Doe"
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_recipient_name("   ")
    with pytest.raises(ValueError, match="at least 2 characters"):
        validate_recipient_name("A")


def test_validate_course_name():
    assert validate_course_name("Python Mastery") == "Python Mastery"
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_course_name("")
    with pytest.raises(ValueError, match="at least 2 characters"):
        validate_course_name("X")


def test_validate_date_string():
    assert validate_date_string("2025-04-12") == "2025-04-12"
    assert validate_date_string("15-08-2024") == "2024-08-15"
    assert validate_date_string("12/31/2024") == "2024-12-31"

    # Default fallback to today's date if empty
    today_date = validate_date_string(None)
    assert len(today_date.split("-")) == 3

    with pytest.raises(ValueError, match="Invalid date format"):
        validate_date_string("invalid-date-string")


def test_recipient_schema_valid():
    recipient = RecipientCreate(
        recipient_name="John Smith",
        recipient_email="john@example.com",
        course_name="Machine Learning Operations",
        issue_date="2025-01-15",
    )
    assert recipient.recipient_name == "John Smith"
    assert recipient.recipient_email == "john@example.com"
    assert recipient.issue_date == "2025-01-15"


def test_recipient_schema_invalid():
    with pytest.raises(ValidationError):
        RecipientCreate(
            recipient_name="",
            recipient_email="invalid",
            course_name="",
        )


def test_generate_request_empty_recipients():
    with pytest.raises(ValidationError):
        GenerateCertificatesRequest(recipients=[])


def test_generate_request_exceeds_max_limit():
    dummy = RecipientCreate(
        recipient_name="Test User",
        recipient_email="test@example.com",
        course_name="Test Course",
    )
    oversized_list = [dummy] * (MAX_RECIPIENTS_LIMIT + 1)
    with pytest.raises(ValidationError, match="Exceeded maximum recipient limit"):
        GenerateCertificatesRequest(recipients=oversized_list)
