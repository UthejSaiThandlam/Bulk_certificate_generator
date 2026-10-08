import csv
import io
import json
import re
from typing import List, Dict, Any, Tuple

# Candidate column mappings for auto-detection
NAME_HEADERS = {"recipient_name", "name", "full_name", "student_name", "participant_name", "candidate_name", "person_name", "learner"}
EMAIL_HEADERS = {"recipient_email", "email", "e_mail", "email_address", "mail", "contact_email"}
COURSE_HEADERS = {"course_name", "course", "program", "program_name", "training", "subject", "topic", "event", "workshop", "certification"}
DATE_HEADERS = {"issue_date", "date", "completion_date", "award_date", "certification_date", "issued_on"}
ISSUER_HEADERS = {"issuer_name", "issuer", "organization", "institute", "authority", "academy", "company"}


def normalize_header(h: Any) -> str:
    """Normalize any header string to lowercase snake_case."""
    if h is None:
        return ""
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", str(h).strip().lower()).strip("_")
    return clean


def identify_columns(headers: List[str]) -> Tuple[str | None, str | None, str | None, str | None, str | None]:
    """Map arbitrary header names to standardized fields (name, email, course, date, issuer)."""
    norm_map = {normalize_header(h): h for h in headers if h}

    def match_col(candidates):
        for c in candidates:
            if c in norm_map:
                return norm_map[c]
        # Partial match
        for norm, original in norm_map.items():
            if any(cand in norm for cand in candidates):
                return original
        return None

    name_col = match_col(NAME_HEADERS)
    email_col = match_col(EMAIL_HEADERS)
    course_col = match_col(COURSE_HEADERS)
    date_col = match_col(DATE_HEADERS)
    issuer_col = match_col(ISSUER_HEADERS)

    return name_col, email_col, course_col, date_col, issuer_col


def parse_csv_or_tsv(content_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse CSV, TSV, or semicolon/pipe delimited text files."""
    try:
        text = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content_bytes.decode("latin-1", errors="replace")

    # Auto-detect delimiter
    sample = text[:4096]
    delimiter = ","
    for d in [",", "\t", ";", "|"]:
        if d in sample:
            delimiter = d
            break

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("File is empty or contains no readable columns")
    return [row for row in reader if any(v is not None and str(v).strip() for v in row.values())]


def parse_excel(content_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse Excel files (.xlsx, .xls) using openpyxl."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content_bytes), data_only=True)
        sheet = wb.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows or len(rows) < 2:
            raise ValueError("Excel worksheet contains no data rows")

        headers = [str(cell).strip() if cell is not None else f"col_{idx}" for idx, cell in enumerate(rows[0])]
        records = []
        for r in rows[1:]:
            if not any(r):
                continue
            row_dict = {}
            for idx, val in enumerate(r):
                if idx < len(headers):
                    row_dict[headers[idx]] = str(val).strip() if val is not None else ""
            records.append(row_dict)
        return records
    except Exception as e:
        raise ValueError(f"Could not read Excel file: {str(e)}")


def parse_json(content_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse JSON file containing array of recipient objects."""
    data = json.loads(content_bytes.decode("utf-8", errors="replace"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["recipients", "data", "users", "certificates", "rows"]:
            if key in data and isinstance(data[key], list):
                return data[key]
    raise ValueError("JSON file must contain an array of recipient objects")


def extract_raw_recipients_from_file(
    filename: str,
    content_bytes: bytes,
    default_issuer: str = "Academic Certification Authority",
) -> List[Dict[str, Any]]:
    """
    Ingests CSV, TSV, XLSX, or JSON files.
    Returns normalized raw dictionary records without throwing validation errors for bad rows,
    allowing row-by-row isolation during job creation.
    """
    ext = filename.lower().split(".")[-1]

    if ext in ["csv", "tsv", "txt"]:
        raw_rows = parse_csv_or_tsv(content_bytes)
    elif ext in ["xlsx", "xls"]:
        raw_rows = parse_excel(content_bytes)
    elif ext == "json":
        raw_rows = parse_json(content_bytes)
    else:
        try:
            raw_rows = parse_csv_or_tsv(content_bytes)
        except Exception:
            raise ValueError(f"Unsupported file format '.{ext}'. Supported: .csv, .xlsx, .json, .tsv, .txt")

    if not raw_rows:
        raise ValueError(f"No records found in uploaded file '{filename}'")

    sample_keys = list(raw_rows[0].keys())
    name_col, email_col, course_col, date_col, issuer_col = identify_columns(sample_keys)

    # If mandatory column headers cannot be mapped at all
    if not (name_col and email_col and course_col):
        # Check if already standardized
        has_std = all(k in sample_keys for k in ["recipient_name", "recipient_email", "course_name"])
        if not has_std:
            raise ValueError(
                f"Uploaded file must contain at minimum columns for Name, Email, and Course.\n"
                f"Detected headers: {sample_keys}."
            )

    normalized: List[Dict[str, Any]] = []
    for row in raw_rows:
        item = dict(row)
        if name_col and name_col in row:
            item["recipient_name"] = str(row[name_col] or "").strip()
        if email_col and email_col in row:
            item["recipient_email"] = str(row[email_col] or "").strip()
        if course_col and course_col in row:
            item["course_name"] = str(row[course_col] or "").strip()
        if date_col and date_col in row:
            item["issue_date"] = str(row[date_col] or "").strip()
        if issuer_col and issuer_col in row:
            item["issuer_name"] = str(row[issuer_col] or "").strip()
        elif default_issuer:
            item.setdefault("issuer_name", default_issuer)
        normalized.append(item)

    return normalized


def extract_recipients_from_any_file(
    filename: str,
    content_bytes: bytes,
    default_issuer: str = "Academic Certification Authority",
    deduplicate: bool = True,
) -> List[Dict[str, Any]]:
    """Backwards-compatible wrapper returning raw normalized rows."""
    return extract_raw_recipients_from_file(filename, content_bytes, default_issuer)
