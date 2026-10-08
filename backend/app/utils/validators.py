import re
from datetime import datetime

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_email_address(email: str) -> str:
    """Validate email format and return stripped lowercase email."""
    if not email or not isinstance(email, str):
        raise ValueError("Email cannot be empty")
    cleaned = email.strip().lower()
    if not EMAIL_REGEX.match(cleaned):
        raise ValueError(f"Invalid email address format: '{email}'")
    return cleaned


def validate_recipient_name(name: str) -> str:
    """Validate recipient name has content and realistic length."""
    if not name or not isinstance(name, str):
        raise ValueError("Recipient name cannot be empty")
    cleaned = name.strip()
    if not cleaned:
        raise ValueError("Recipient name cannot be empty")
    if len(cleaned) < 2:
        raise ValueError("Recipient name must be at least 2 characters long")
    if len(cleaned) > 150:
        raise ValueError("Recipient name cannot exceed 150 characters")
    return cleaned


def validate_course_name(course: str) -> str:
    """Validate course name."""
    if not course or not isinstance(course, str):
        raise ValueError("Course name cannot be empty")
    cleaned = course.strip()
    if not cleaned:
        raise ValueError("Course name cannot be empty")
    if len(cleaned) < 2:
        raise ValueError("Course name must be at least 2 characters long")
    if len(cleaned) > 200:
        raise ValueError("Course name cannot exceed 200 characters")
    return cleaned


def validate_date_string(date_str: str | None) -> str:
    """
    Validate date string in common formats (YYYY-MM-DD, DD-MM-YYYY, etc.)
    Defaults to current date if not provided.
    """
    if not date_str or not str(date_str).strip():
        return datetime.now().strftime("%Y-%m-%d")

    date_str = str(date_str).strip()
    formats = ["%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%B %d, %Y", "%d %B %Y"]
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise ValueError(
        f"Invalid date format: '{date_str}'. Expected formats: YYYY-MM-DD, DD-MM-YYYY, or MM/DD/YYYY"
    )
