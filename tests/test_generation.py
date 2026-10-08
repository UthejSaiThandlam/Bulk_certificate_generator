import os
import tempfile
from app.services.certificate_generator import CertificateGenerator


def test_verification_code_format():
    code1 = CertificateGenerator.generate_verification_code()
    code2 = CertificateGenerator.generate_verification_code()
    assert code1.startswith("CERT-")
    assert code2.startswith("CERT-")
    assert len(code1.split("-")) == 3
    assert code1 != code2


def test_generate_certificate_pdf_creates_valid_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_certificate.pdf")
        result = CertificateGenerator.generate_certificate_pdf(
            output_path=output_path,
            recipient_name="Alice Wonder",
            course_name="Quantum Computing Fundamentals",
            issue_date="2025-05-20",
            certificate_code="CERT-TEST-1234",
            issuer_name="Global Academy of Science",
        )

        assert os.path.exists(result)
        assert os.path.getsize(result) > 1000

        with open(result, "rb") as f:
            header = f.read(5)
            assert header == b"%PDF-"
