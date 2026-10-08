import csv
import io
import json
import re
from typing import List, Dict, Any, Tuple
from app.schemas import RecipientCreate, MAX_RECIPIENTS_LIMIT

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
    return list(reader)


def parse_excel(content_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse Excel files (.xlsx, .xls) using openpyxl or pandas."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(content_bytes), data_only=True)
        sheet = wb.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows or len(rows) < 2:
            raise ValueError("Excel worksheet contains no data rows")

        headers = [str(cell) if cell is not None else f"col_{idx}" for idx, cell in enumerate(rows[0])]
        records = []
        for r in rows[1:]:
            if not any(r):
                continue
            row_dict = {}
            for idx, val in enumerate(r):
                if idx < len(headers):
                    row_dict[headers[idx]] = str(val) if val is not None else ""
            records.append(row_dict)
        return records
    except Exception as e:
        # Fallback to pandas
        try:
            import pandas as pd
            df = pd.read_excel(io.BytesIO(content_bytes))
            return df.fillna("").astype(str).to_dict(orient="records")
        except Exception:
            raise ValueError(f"Could not read Excel file: {str(e)}")


def parse_docx(content_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse Word document (.docx) by reading tables or key-value paragraphs."""
    import docx
    doc = docx.Document(io.BytesIO(content_bytes))

    records = []
    # 1. Try reading tables in docx
    for table in doc.tables:
        if len(table.rows) >= 2:
            headers = [cell.text.strip() for cell in table.rows[0].cells]
            for row in table.rows[1:]:
                row_vals = [cell.text.strip() for cell in row.cells]
                if not any(row_vals):
                    continue
                row_dict = {headers[i]: row_vals[i] for i in range(min(len(headers), len(row_vals)))}
                records.append(row_dict)

    if records:
        return records

    # 2. Fallback: Parse line-by-line text paragraphs (comma/tab separated)
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    if len(lines) >= 2:
        return parse_csv_or_tsv("\n".join(lines).encode("utf-8"))

    raise ValueError("No table or structured recipient records found in Word document (.docx)")


def parse_pdf(content_bytes: bytes) -> List[Dict[str, Any]]:
    """Extract recipient records from PDF tables or lines using pymupdf or pypdf."""
    import pymupdf
    doc = pymupdf.open(stream=content_bytes, filetype="pdf")

    all_text_lines = []
    for page in doc:
        # Check for built-in tables if available
        try:
            tabs = page.find_tables()
            if tabs and len(tabs.tables) > 0:
                for tab in tabs.tables:
                    df = tab.to_pandas()
                    if not df.empty:
                        return df.fillna("").astype(str).to_dict(orient="records")
        except Exception:
            pass

        # Text extraction fallback
        text = page.get_text("text")
        for line in text.splitlines():
            line_str = line.strip()
            if line_str:
                all_text_lines.append(line_str)

    if len(all_text_lines) >= 2:
        # Attempt to parse lines as CSV / TSV / Delimited
        return parse_csv_or_tsv("\n".join(all_text_lines).encode("utf-8"))

    raise ValueError("No tabular or comma-separated recipient records could be extracted from PDF")


def parse_json(content_bytes: bytes) -> List[Dict[str, Any]]:
    """Parse JSON file containing list of recipients."""
    data = json.loads(content_bytes.decode("utf-8", errors="replace"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ["recipients", "data", "users", "certificates", "rows"]:
            if key in data and isinstance(data[key], list):
                return data[key]
    raise ValueError("JSON file must contain an array of recipient objects")


def extract_recipients_from_any_file(
    filename: str,
    content_bytes: bytes,
    default_issuer: str = "Academic Certification Authority",
    deduplicate: bool = True,
) -> List[RecipientCreate]:
    """
    Universal ingestion engine:
    Accepts CSV, XLSX, XLS, DOCX, PDF, JSON, TSV, TXT.
    Normalizes column headers, sanitizes values, and returns validated RecipientCreate list.
    """
    ext = filename.lower().split(".")[-1]

    if ext in ["csv", "tsv", "txt"]:
        raw_rows = parse_csv_or_tsv(content_bytes)
    elif ext in ["xlsx", "xls"]:
        raw_rows = parse_excel(content_bytes)
    elif ext in ["docx", "doc"]:
        raw_rows = parse_docx(content_bytes)
    elif ext == "pdf":
        raw_rows = parse_pdf(content_bytes)
    elif ext == "json":
        raw_rows = parse_json(content_bytes)
    else:
        # Attempt auto-detection via CSV / text
        try:
            raw_rows = parse_csv_or_tsv(content_bytes)
        except Exception:
            raise ValueError(f"Unsupported file format '.{ext}'. Supported: .csv, .xlsx, .docx, .pdf, .json, .tsv, .txt")

    if not raw_rows:
        raise ValueError(f"No records found in uploaded {ext.upper()} file")

    # Identify column mappings from the first row's keys
    sample_keys = list(raw_rows[0].keys())
    name_col, email_col, course_col, date_col, issuer_col = identify_columns(sample_keys)

    if not (name_col and email_col and course_col):
        raise ValueError(
            f"Uploaded file must contain at minimum columns for Name, Email, and Course.\n"
            f"Detected headers: {sample_keys}.\n"
            f"Matched: name='{name_col}', email='{email_col}', course='{course_col}'"
        )

    recipients: List[RecipientCreate] = []
    seen_emails = set()
    row_errors = []

    for idx, row in enumerate(raw_rows, start=1):
        raw_name = str(row.get(name_col, "") or "").strip()
        raw_email = str(row.get(email_col, "") or "").strip()
        raw_course = str(row.get(course_col, "") or "").strip()
        raw_date = str(row.get(date_col, "") or "").strip() if date_col else None
        raw_issuer = str(row.get(issuer_col, "") or "").strip() if issuer_col else default_issuer

        if not raw_name and not raw_email and not raw_course:
            continue

        if deduplicate:
            clean_email = raw_email.lower()
            if clean_email in seen_emails:
                continue
            seen_emails.add(clean_email)

        try:
            recipients.append(
                RecipientCreate(
                    recipient_name=raw_name,
                    recipient_email=raw_email,
                    course_name=raw_course,
                    issue_date=raw_date,
                    issuer_name=raw_issuer or default_issuer,
                )
            )
        except Exception as err:
            row_errors.append(f"Row {idx}: {str(err)}")

    if row_errors:
        raise ValueError(f"Validation errors in file: {'; '.join(row_errors[:5])}")

    if not recipients:
        raise ValueError("No valid recipient rows found after parsing and validation")

    if len(recipients) > MAX_RECIPIENTS_LIMIT:
        raise ValueError(f"Exceeded maximum recipient limit of {MAX_RECIPIENTS_LIMIT} per job. Found {len(recipients)}.")

    return recipients
