import os
import math
import uuid
from typing import Optional
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch


class CertificateGenerator:
    """Service to generate professional PDF certificates using ReportLab."""

    @staticmethod
    def generate_verification_code() -> str:
        """Generate a clean, professional unique verification code."""
        part1 = uuid.uuid4().hex[:4].upper()
        part2 = uuid.uuid4().hex[4:8].upper()
        return f"CERT-{part1}-{part2}"

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
        Generate an elegant vector-quality PDF certificate and save it to output_path.
        Returns the absolute output path.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        width, height = landscape(letter)  # 792 x 612 pt
        c = canvas.Canvas(output_path, pagesize=(width, height))
        c.setTitle(f"Certificate - {recipient_name}")
        c.setAuthor(issuer_name)
        c.setSubject(course_name)

        # Color Palette
        navy_dark = colors.HexColor("#0f172a")
        navy_mid = colors.HexColor("#1e293b")
        gold_main = colors.HexColor("#d97706")
        gold_light = colors.HexColor("#fef3c7")
        gold_border = colors.HexColor("#b45309")
        slate_gray = colors.HexColor("#64748b")
        charcoal = colors.HexColor("#1e293b")
        cream_bg = colors.HexColor("#fcfbf7")

        # 1. Subtle warm background
        c.setFillColor(cream_bg)
        c.rect(0, 0, width, height, fill=True, stroke=False)

        # 2. Dual Ornate Borders
        # Outer Border
        c.setStrokeColor(navy_dark)
        c.setLineWidth(4)
        c.rect(20, 20, width - 40, height - 40, fill=False, stroke=True)

        # Inner Thin Gold Border
        c.setStrokeColor(gold_border)
        c.setLineWidth(1.5)
        c.rect(28, 28, width - 56, height - 56, fill=False, stroke=True)

        # Fine accent inner border
        c.setStrokeColor(colors.HexColor("#e2e8f0"))
        c.setLineWidth(0.75)
        c.rect(34, 34, width - 68, height - 68, fill=False, stroke=True)

        # Corner geometric decorative accents
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

        # 3. Top Organization / Issuer Branding
        c.setFont("Helvetica-Bold", 12)
        c.setFillColor(gold_border)
        c.drawCentredString(width / 2.0, height - 70, issuer_name.upper())

        # Sub-header emblem accent
        c.setStrokeColor(gold_main)
        c.setLineWidth(1.5)
        c.line(width / 2.0 - 60, height - 80, width / 2.0 + 60, height - 80)
        c.setFillColor(gold_main)
        c.circle(width / 2.0, height - 80, 3, fill=True, stroke=False)

        # 4. Main Certificate Title
        c.setFont("Times-Bold", 32)
        c.setFillColor(navy_dark)
        c.drawCentredString(width / 2.0, height - 125, "CERTIFICATE OF ACHIEVEMENT")

        # 5. Presentation Lead-in
        c.setFont("Helvetica-Oblique", 11)
        c.setFillColor(slate_gray)
        c.drawCentredString(width / 2.0, height - 165, "THIS CERTIFICATE IS PROUDLY PRESENTED TO")

        # 6. Recipient Name
        c.setFont("Times-BoldItalic", 34)
        c.setFillColor(navy_dark)
        c.drawCentredString(width / 2.0, height - 215, recipient_name)

        # Underline for name
        name_width = min(max(c.stringWidth(recipient_name, "Times-BoldItalic", 34) + 40, 260), width - 160)
        c.setStrokeColor(gold_main)
        c.setLineWidth(1.5)
        c.line(width / 2.0 - (name_width / 2.0), height - 228, width / 2.0 + (name_width / 2.0), height - 228)

        # 7. Achievement Context Description
        c.setFont("Helvetica", 11)
        c.setFillColor(charcoal)
        c.drawCentredString(
            width / 2.0,
            height - 265,
            "for successfully completing all the requirements, assessments, and curriculum of",
        )

        # 8. Course / Program Name
        c.setFont("Helvetica-Bold", 20)
        c.setFillColor(navy_mid)
        c.drawCentredString(width / 2.0, height - 305, course_name)

        # 9. Gold Medallion / Official Seal Emblem (Center Bottom)
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

        # Star accents on seal
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(seal_x, seal_y + 16, "★")

        # 10. Left Signature Block (Authorized Director)
        sig_y = 115
        left_x = 160
        c.setStrokeColor(colors.HexColor("#94a3b8"))
        c.setLineWidth(1)
        c.line(left_x - 70, sig_y, left_x + 70, sig_y)

        # Simulated elegant signature curve
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

        # 11. Right Signature Block (Instructor / Dean)
        right_x = width - 160
        c.setStrokeColor(colors.HexColor("#94a3b8"))
        c.setLineWidth(1)
        c.line(right_x - 70, sig_y, right_x + 70, sig_y)

        # Simulated elegant signature curve
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

        # 12. Bottom Metadata Footer (Date & Certificate Verification ID)
        c.setFont("Helvetica", 9)
        c.setFillColor(slate_gray)
        c.drawString(45, 45, f"Date of Issue: {issue_date}")

        c.drawRightString(width - 45, 45, f"Verification Code: {certificate_code}")

        # Finish and save
        c.showPage()
        c.save()

        return output_path
