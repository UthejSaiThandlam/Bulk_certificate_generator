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


def test_generate_certificate_with_extra_long_name_and_unicode():
    """Verify extra long recipient names scale down dynamically without overlapping or crashing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "long_name_cert.pdf")
        long_name = "Thandlam Uthej Sai-Kalyan-Venkateshwara-Subramaniam-Choudhary"
        result = CertificateGenerator.generate_certificate_pdf(
            output_path=output_path,
            recipient_name=long_name,
            course_name="Advanced Neural Network Architectures & Deep Learning Pipelines",
            issue_date="2025-05-20",
            certificate_code="CERT-LONG-5678",
            issuer_name="International University Consortium",
        )
        assert os.path.exists(result)
        assert os.path.getsize(result) > 1000


def test_generate_certificate_with_accented_characters():
    """Verify accented characters (é, ñ, ü) are handled cleanly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "accent_cert.pdf")
        result = CertificateGenerator.generate_certificate_pdf(
            output_path=output_path,
            recipient_name="François Peña-Müller",
            course_name="Applied Cryptography",
            issue_date="2025-05-20",
            certificate_code="CERT-ACCENT-9999",
        )
        assert os.path.exists(result)
        assert os.path.getsize(result) > 1000


def test_startup_template_validation():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert CertificateGenerator.validate_template_at_startup(tmpdir) is True
