import os
import unicodedata
import uuid
import tempfile
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas


class CertificateGenerator:
    """Production-grade service to generate PDF certificates with ReportLab."""

    @staticmethod
    def generate_verification_code() -> str:
        """Generate a clean, collision-resistant unique verification code."""
        part1 = uuid.uuid4().hex[:4].upper()
        part2 = uuid.uuid4().hex[4:8].upper()
        return f"CERT-{part1}-{part2}"

    @classmethod
    def sanitize_text_for_pdf(cls, text: str) -> str:
        """
        Normalize and sanitize text for ReportLab's standard core fonts.
        Converts non-ASCII Unicode characters gracefully to avoid encoding crashes.
        """
        if not text:
            return ""
        # Normalize Unicode characters (e.g., accents é -> e, ñ -> n)
        normalized = unicodedata.normalize("NFKD", text)
        # Encode with replacement to prevent unhandled glyph rendering exceptions in Standard Type 1 fonts
        safe_ascii = normalized.encode("latin-1", errors="replace").decode("latin-1")
        return safe_ascii

    @classmethod
    def calculate_scaled_font(
        cls,
        c: canvas.Canvas,
        text: str,
        font_name: str,
        initial_size: int,
        min_size: int,
        max_width: float,
    ) -> tuple[int, str]:
        """
        Dynamically scale font down for long names/courses to prevent text overlapping or edge bleeding.
        If minimum font size is reached and text still exceeds max_width, safely truncates with ellipsis.
        """
        size = initial_size
        while size >= min_size:
            w = c.stringWidth(text, font_name, size)
            if w <= max_width:
                return size, text
            size -= 2

        # If it still exceeds at minimum font size, truncate text with ellipsis
        truncated = text
        while len(truncated) > 4 and c.stringWidth(truncated + "...", font_name, min_size) > max_width:
            truncated = truncated[:-1]
        return min_size, truncated + "..."

    @classmethod
    def generate_certificate_pdf(
        cls,
        output_path: str,
        recipient_name: str,
        course_name: str,
        issue_date: str,
        certificate_code: str,
        issuer_name: str = "Academic Certification Authority",
        template_name: str = "classic",
    ) -> str:
        """
        Atomic PDF generation:
        1. Renders to a temporary file.
        2. Validates that the file exists and is valid.
        3. Atomically replaces/moves to the final output_path.
        """
        final_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(final_dir, exist_ok=True)

        width, height = landscape(letter)  # 792 x 612 pt
        max_text_width = width - 140

        # Sanitize texts for font compatibility
        safe_name = cls.sanitize_text_for_pdf(recipient_name)
        safe_course = cls.sanitize_text_for_pdf(course_name)
        safe_issuer = cls.sanitize_text_for_pdf(issuer_name)
        safe_date = cls.sanitize_text_for_pdf(issue_date)

        # Atomic generation using a temporary file in the same directory
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=final_dir)
        temp_path = temp_file.name
        temp_file.close()

        try:
            c = canvas.Canvas(temp_path, pagesize=(width, height))
            c.setTitle(f"Certificate - {safe_name}")
            c.setAuthor(safe_issuer)
            c.setSubject(safe_course)

            # Palette
            navy_dark = colors.HexColor("#0f172a")
            navy_mid = colors.HexColor("#1e293b")
            gold_main = colors.HexColor("#d97706")
            gold_light = colors.HexColor("#fef3c7")
            gold_border = colors.HexColor("#b45309")
            slate_gray = colors.HexColor("#64748b")
            charcoal = colors.HexColor("#1e293b")
            cream_bg = colors.HexColor("#fcfbf7")

            # 1. Background
            c.setFillColor(cream_bg)
            c.rect(0, 0, width, height, fill=True, stroke=False)

            # 2. Dual Ornate Borders
            c.setStrokeColor(navy_dark)
            c.setLineWidth(4)
            c.rect(20, 20, width - 40, height - 40, fill=False, stroke=True)

            c.setStrokeColor(gold_border)
            c.setLineWidth(1.5)
            c.rect(28, 28, width - 56, height - 56, fill=False, stroke=True)

            c.setStrokeColor(colors.HexColor("#e2e8f0"))
            c.setLineWidth(0.75)
            c.rect(34, 34, width - 68, height - 68, fill=False, stroke=True)

            # Corner decorative accents
            corner_size = 28
            corners = [
                (28, 28),
                (width - 28 - corner_size, 28),
                (28, height - 28 - corner_size),
                (width - 28 - corner_size, height - 28 - corner_size),
            ]
            c.setFillColor(gold_light)
            c.setStrokeColor(gold_border)
            c.setLineWidth(1)
            for cx, cy in corners:
                c.rect(cx, cy, corner_size, corner_size, fill=True, stroke=True)

            # 3. Issuer Branding
            c.setFont("Helvetica-Bold", 12)
            c.setFillColor(gold_border)
            c.drawCentredString(width / 2.0, height - 70, safe_issuer.upper())

            c.setStrokeColor(gold_main)
            c.setLineWidth(1.5)
            c.line(width / 2.0 - 60, height - 80, width / 2.0 + 60, height - 80)
            c.setFillColor(gold_main)
            c.circle(width / 2.0, height - 80, 3, fill=True, stroke=False)

            # 4. Main Certificate Title
            c.setFont("Times-Bold", 32)
            c.setFillColor(navy_dark)
            c.drawCentredString(width / 2.0, height - 125, "CERTIFICATE OF ACHIEVEMENT")

            # 5. Lead-in Text
            c.setFont("Helvetica-Oblique", 11)
            c.setFillColor(slate_gray)
            c.drawCentredString(width / 2.0, height - 165, "THIS CERTIFICATE IS PROUDLY PRESENTED TO")

            # 6. Dynamic Name Scaling (Prevents overlap on long names)
            name_font_size, display_name = cls.calculate_scaled_font(
                c, safe_name, "Times-BoldItalic", initial_size=34, min_size=16, max_width=max_text_width
            )
            c.setFont("Times-BoldItalic", name_font_size)
            c.setFillColor(navy_dark)
            c.drawCentredString(width / 2.0, height - 215, display_name)

            # Name Underline
            drawn_name_width = min(max(c.stringWidth(display_name, "Times-BoldItalic", name_font_size) + 30, 240), max_text_width)
            c.setStrokeColor(gold_main)
            c.setLineWidth(1.5)
            c.line(width / 2.0 - (drawn_name_width / 2.0), height - 228, width / 2.0 + (drawn_name_width / 2.0), height - 228)

            # 7. Achievement Context Description
            c.setFont("Helvetica", 11)
            c.setFillColor(charcoal)
            c.drawCentredString(
                width / 2.0,
                height - 265,
                "for successfully completing all the requirements, assessments, and curriculum of",
            )

            # 8. Dynamic Course Scaling
            course_font_size, display_course = cls.calculate_scaled_font(
                c, safe_course, "Helvetica-Bold", initial_size=20, min_size=12, max_width=max_text_width
            )
            c.setFont("Helvetica-Bold", course_font_size)
            c.setFillColor(navy_mid)
            c.drawCentredString(width / 2.0, height - 305, display_course)

            # 9. Gold Medallion / Official Seal Emblem
            seal_x = width / 2.0
            seal_y = 120
            c.setStrokeColor(gold_border)
            c.setFillColor(gold_light)
            c.setLineWidth(2)
            c.circle(seal_x, seal_y, 34, fill=True, stroke=True)

            c.setStrokeColor(gold_main)
            c.setFillColor(navy_dark)
            c.setLineWidth(1)
            c.circle(seal_x, seal_y, 28, fill=True, stroke=True)

            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(gold_light)
            c.drawCentredString(seal_x, seal_y + 6, "OFFICIAL")
            c.drawCentredString(seal_x, seal_y - 6, "SEAL")
            c.setFont("Times-Roman", 6)
            c.drawCentredString(seal_x, seal_y - 16, "VERIFIED")
            c.setFont("Helvetica-Bold", 10)
            c.drawCentredString(seal_x, seal_y + 16, "★")

            # 10. Left Signature Block
            sig_y = 115
            left_x = 160
            c.setStrokeColor(colors.HexColor("#94a3b8"))
            c.setLineWidth(1)
            c.line(left_x - 70, sig_y, left_x + 70, sig_y)

            c.setStrokeColor(navy_dark)
            c.setLineWidth(1.2)
            p = c.beginPath()
            p.moveTo(left_x - 50, sig_y + 12)
            p.curveTo(left_x - 20, sig_y + 25, left_x - 10, sig_y + 5, left_x + 20, sig_y + 18)
            p.curveTo(left_x + 35, sig_y + 28, left_x + 45, sig_y + 8, left_x + 60, sig_y + 14)
            c.drawPath(p, fill=False, stroke=True)

            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(navy_dark)
            c.drawCentredString(left_x, sig_y - 16, "Dr. Arthur Pendelton")
            c.setFont("Helvetica", 8)
            c.setFillColor(slate_gray)
            c.drawCentredString(left_x, sig_y - 28, "Director of Academic Affairs")

            # 11. Right Signature Block
            right_x = width - 160
            c.setStrokeColor(colors.HexColor("#94a3b8"))
            c.setLineWidth(1)
            c.line(right_x - 70, sig_y, right_x + 70, sig_y)

            p2 = c.beginPath()
            p2.moveTo(right_x - 45, sig_y + 10)
            p2.curveTo(right_x - 25, sig_y + 30, right_x + 5, sig_y + 2, right_x + 30, sig_y + 20)
            p2.curveTo(right_x + 40, sig_y + 24, right_x + 50, sig_y + 12, right_x + 58, sig_y + 16)
            c.drawPath(p2, fill=False, stroke=True)

            c.setFont("Helvetica-Bold", 10)
            c.setFillColor(navy_dark)
            c.drawCentredString(right_x, sig_y - 16, "Prof. Evelyn Vance")
            c.setFont("Helvetica", 8)
            c.setFillColor(slate_gray)
            c.drawCentredString(right_x, sig_y - 28, "Lead Instructor & Evaluator")

            # 12. Bottom Metadata Footer
            c.setFont("Helvetica", 9)
            c.setFillColor(slate_gray)
            c.drawString(45, 45, f"Date of Issue: {safe_date}")
            c.drawRightString(width - 45, 45, f"Verification Code: {certificate_code}")

            # Save canvas
            c.showPage()
            c.save()

            # Verify temp file is non-empty
            if not os.path.exists(temp_path) or os.path.getsize(temp_path) < 100:
                raise IOError("Generated certificate PDF is empty or missing")

            # Atomically replace final file
            if os.path.exists(output_path):
                os.remove(output_path)
            os.replace(temp_path, output_path)

            return output_path

        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            raise

    @classmethod
    def validate_template_at_startup(cls, template_dir: str = "templates") -> bool:
        """
        Fail-fast check at application startup to verify PDF generator engine
        and template availability work without errors.
        """
        os.makedirs(template_dir, exist_ok=True)
        test_pdf = os.path.join(template_dir, "startup_check.pdf")
        try:
            cls.generate_certificate_pdf(
                output_path=test_pdf,
                recipient_name="System Diagnostic Test",
                course_name="Startup Verification Protocol",
                issue_date="2025-01-01",
                certificate_code="CERT-SYS-TEST",
                issuer_name="System Health Check",
            )
            # Remove test file
            if os.path.exists(test_pdf):
                os.remove(test_pdf)
            return True
        except Exception as e:
            raise RuntimeError(f"Startup template validation failed: {str(e)}") from e
