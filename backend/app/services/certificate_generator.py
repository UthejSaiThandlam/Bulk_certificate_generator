"""
Certificate Generator — High-Resolution Vector Engine
Matches the Tech Institute reference design:
 - Top centered classical institution crest + "TECH INSTITUTE" + "LEARN • BUILD • GROW"
 - Top right live scannable QR code + "Verification Code: CERT-XXXX-XXXX" + "Scan to Verify"
 - Top-left and bottom-right sharp angled navy polygons with gold trim stripes
 - Gold double-line rectangular frame
 - Centered "CERTIFICATE OF ACHIEVEMENT" title with gold diamond accent bar
 - "THIS CERTIFICATE IS PROUDLY PRESENTED TO" subtitle
 - Recipient name in large calligraphic cursive script with gold underline
 - Narrative curriculum text + bold Course Title + multi-line course description
 - Left & right calligraphic signature blocks with authentic ink cursive paths
 - Center gold medallion seal with laurel ring and golden pillar insignia
 - Bottom-left "Date of Issue: ..."
"""
import io
import math
import os
import secrets
import tempfile
import unicodedata
from typing import Optional, Tuple, Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


# ─── Color Palette ─────────────────────────────────────────────────────────────
NAVY = colors.HexColor("#0B1E36")
NAVY_DEEP = colors.HexColor("#061120")
NAVY_MID = colors.HexColor("#162D50")
GOLD = colors.HexColor("#C8A84B")
GOLD_LIGHT = colors.HexColor("#F8EDC8")
GOLD_DARK = colors.HexColor("#9B7A2E")
GOLD_BRIGHT = colors.HexColor("#D4AF37")
WHITE = colors.white
OFF_WHITE = colors.HexColor("#FCFBF7")
PARCHMENT = colors.HexColor("#FAF8F2")
GRAY_LIGHT = colors.HexColor("#E2E8F0")
GRAY = colors.HexColor("#718096")
GRAY_DARK = colors.HexColor("#4A5568")
GRAY_CHARCOAL = colors.HexColor("#2D3748")


def _sanitize(text: Optional[str]) -> str:
    """NFC normalization and Latin-1 safe encoding for ReportLab standard fonts."""
    if not text:
        return ""
    nfc = unicodedata.normalize("NFC", str(text).strip())
    return nfc.encode("latin-1", errors="replace").decode("latin-1")


def _scale_font(
    c: canvas.Canvas,
    text: str,
    font: str,
    start: int,
    minimum: int,
    max_width: float,
) -> Tuple[int, str]:
    """Shrink font until text fits max_width; truncate with ellipsis if still too wide."""
    size = start
    while size >= minimum:
        if c.stringWidth(text, font, size) <= max_width:
            return size, text
        size -= 1
    t = text
    while len(t) > 4 and c.stringWidth(t + "...", font, minimum) > max_width:
        t = t[:-1]
    return minimum, t + "..."


def _draw_star(
    c: canvas.Canvas,
    cx: float,
    cy: float,
    r_out: float = 5,
    r_in: float = 2.2,
    points: int = 5,
) -> None:
    """Vector 5-pointed star."""
    path = c.beginPath()
    angle = math.pi / 2
    step = math.pi / points
    for i in range(2 * points):
        r = r_out if i % 2 == 0 else r_in
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
        angle += step
    path.close()
    c.drawPath(path, fill=True, stroke=False)


def _draw_qr(
    c: canvas.Canvas,
    data: str,
    x: float,
    y: float,
    size: float = 54,
    dark_mode: bool = False,
) -> None:
    """Draw a high-resolution QR code image on the canvas using ImageReader."""
    try:
        import qrcode

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=4,
            border=1,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(
            fill_color="black" if not dark_mode else "#C8A84B",
            back_color="white" if not dark_mode else "#061120",
        )

        buf = io.BytesIO()
        img.save(buf)
        buf.seek(0)
        reader = ImageReader(buf)
        c.drawImage(reader, x, y, width=size, height=size, mask="auto")
    except Exception:
        c.setStrokeColor(GOLD if dark_mode else GRAY)
        c.setLineWidth(0.8)
        c.rect(x, y, size, size, fill=False, stroke=True)
        c.setFont("Helvetica", 6)
        c.setFillColor(GOLD if dark_mode else GRAY)
        c.drawCentredString(x + size / 2, y + size / 2 - 3, "QR CODE")


def _draw_pillar_icon(
    c: canvas.Canvas,
    cx: float,
    cy: float,
    size: float = 24,
    color: colors.Color = NAVY,
) -> None:
    """Draw classical Greek pillar institutional crest."""
    s = size
    c.setFillColor(color)
    c.setStrokeColor(color)

    # Triangular pediment / roof
    p = c.beginPath()
    p.moveTo(cx - s * 0.50, cy + s * 0.18)
    p.lineTo(cx, cy + s * 0.52)
    p.lineTo(cx + s * 0.50, cy + s * 0.18)
    p.close()
    c.drawPath(p, fill=True, stroke=False)

    # Entablature beam
    c.rect(cx - s * 0.50, cy + s * 0.06, s, s * 0.10, fill=True, stroke=False)

    # 4 Columns
    col_w = s * 0.085
    col_h = s * 0.44
    for xoff in [-0.35, -0.12, 0.12, 0.35]:
        c.rect(cx + xoff * s - col_w / 2, cy - s * 0.38, col_w, col_h, fill=True, stroke=False)

    # Base steps
    c.rect(cx - s * 0.54, cy - s * 0.45, s * 1.08, s * 0.07, fill=True, stroke=False)
    c.rect(cx - s * 0.48, cy - s * 0.51, s * 0.96, s * 0.06, fill=True, stroke=False)


def _draw_corner_accents(
    c: canvas.Canvas,
    W: float,
    H: float,
    dark_mode: bool = False,
) -> None:
    """Draw top-left and bottom-right angled geometric polygons with gold trim stripes."""
    poly_color = NAVY if not dark_mode else colors.HexColor("#040b15")
    gold_color = GOLD_BRIGHT

    # ── Top-Left Polygon ──
    p_tl = c.beginPath()
    p_tl.moveTo(0, H)
    p_tl.lineTo(W * 0.22, H)
    p_tl.lineTo(0, H * 0.65)
    p_tl.close()
    c.setFillColor(poly_color)
    c.drawPath(p_tl, fill=True, stroke=False)

    # Top-Left Gold Stripe
    c.setStrokeColor(gold_color)
    c.setLineWidth(3.2)
    c.line(0, H * 0.65, W * 0.22, H)

    # ── Bottom-Right Polygon ──
    p_br = c.beginPath()
    p_br.moveTo(W, 0)
    p_br.lineTo(W * 0.78, 0)
    p_br.lineTo(W, H * 0.35)
    p_br.close()
    c.setFillColor(poly_color)
    c.drawPath(p_br, fill=True, stroke=False)

    # Bottom-Right Gold Stripe
    c.setStrokeColor(gold_color)
    c.setLineWidth(3.2)
    c.line(W * 0.78, 0, W, H * 0.35)


def _draw_outer_border(
    c: canvas.Canvas,
    W: float,
    H: float,
    dark_mode: bool = False,
) -> None:
    """Double thin border enclosing the certificate canvas."""
    m = 16
    c.setStrokeColor(GOLD_DARK if not dark_mode else GOLD)
    c.setLineWidth(1.6)
    c.rect(m, m, W - 2 * m, H - 2 * m, fill=False, stroke=True)

    c.setStrokeColor(GOLD if not dark_mode else GOLD_LIGHT)
    c.setLineWidth(0.6)
    c.rect(m + 4, m + 4, W - 2 * (m + 4), H - 2 * (m + 4), fill=False, stroke=True)


def _draw_medallion_seal(
    c: canvas.Canvas,
    cx: float,
    cy: float,
    r: float = 33,
    dark_mode: bool = False,
) -> None:
    """Draw circular gold medallion seal with laurel ring, star pattern, and pillar emblem."""
    # Outer gold scalloped ring
    c.setFillColor(GOLD_BRIGHT)
    c.setStrokeColor(GOLD_DARK)
    c.setLineWidth(1.2)
    c.circle(cx, cy, r, fill=True, stroke=True)

    # Mid gold circle
    c.setFillColor(GOLD)
    c.circle(cx, cy, r * 0.88, fill=True, stroke=False)

    # Inner deep navy circle
    c.setFillColor(NAVY_DEEP if not dark_mode else colors.HexColor("#040812"))
    c.setStrokeColor(GOLD_BRIGHT)
    c.setLineWidth(1)
    c.circle(cx, cy, r * 0.74, fill=True, stroke=True)

    # Pillar icon in center of seal
    _draw_pillar_icon(c, cx, cy + r * 0.08, size=r * 0.68, color=GOLD_LIGHT)

    # Stars around the outer perimeter ring
    c.setFillColor(NAVY if not dark_mode else colors.HexColor("#040812"))
    n_stars = 12
    for i in range(n_stars):
        angle = 2 * math.pi * i / n_stars
        sx = cx + (r * 0.81) * math.cos(angle)
        sy = cy + (r * 0.81) * math.sin(angle)
        _draw_star(c, sx, sy, r_out=r * 0.048, r_in=r * 0.02)


def _draw_signature_arthur(c: canvas.Canvas, lx: float, sig_y: float, dark_mode: bool = False) -> None:
    """Draw authentic handwritten ink calligraphy signature for Dr. Arthur Pendelton."""
    c.setStrokeColor(NAVY_MID if not dark_mode else GOLD_LIGHT)
    c.setLineWidth(1.1)

    sp = c.beginPath()
    # Capital 'A' with stylish loop and flourish
    sp.moveTo(lx - 52, sig_y + 6)
    sp.curveTo(lx - 44, sig_y + 24, lx - 38, sig_y + 26, lx - 30, sig_y + 7)
    sp.curveTo(lx - 45, sig_y + 14, lx - 24, sig_y + 16, lx - 18, sig_y + 6)
    # Loop connection 'r-t-h-u-r'
    sp.curveTo(lx - 12, sig_y + 16, lx - 6, sig_y + 4, lx, sig_y + 14)
    # 'P' loop flourish
    sp.curveTo(lx + 8, sig_y + 26, lx + 18, sig_y + 24, lx + 22, sig_y + 6)
    sp.curveTo(lx + 12, sig_y + 18, lx + 28, sig_y + 22, lx + 36, sig_y + 8)
    # Ending baseline trail
    sp.curveTo(lx + 42, sig_y + 14, lx + 48, sig_y + 7, lx + 54, sig_y + 11)
    c.drawPath(sp, fill=False, stroke=True)


def _draw_signature_evelyn(c: canvas.Canvas, rx: float, sig_y: float, dark_mode: bool = False) -> None:
    """Draw authentic handwritten ink calligraphy signature for Prof. Evelyn Vance."""
    c.setStrokeColor(NAVY_MID if not dark_mode else GOLD_LIGHT)
    c.setLineWidth(1.1)

    sp = c.beginPath()
    # Initial flourish loop for 'E'
    sp.moveTo(rx - 50, sig_y + 10)
    sp.curveTo(rx - 42, sig_y + 25, rx - 34, sig_y + 22, rx - 28, sig_y + 7)
    sp.curveTo(rx - 38, sig_y + 13, rx - 22, sig_y + 18, rx - 14, sig_y + 8)
    # Middle wave 'v-e-l-y-n'
    sp.curveTo(rx - 6, sig_y + 18, rx + 2, sig_y + 4, rx + 12, sig_y + 16)
    # Capital 'V' loop and dynamic ascending tail
    sp.curveTo(rx + 20, sig_y + 28, rx + 30, sig_y + 26, rx + 36, sig_y + 6)
    sp.curveTo(rx + 30, sig_y + 18, rx + 44, sig_y + 22, rx + 52, sig_y + 14)
    c.drawPath(sp, fill=False, stroke=True)


class CertificateGenerator:
    """Enterprise-Grade Bulk Certificate Generator Engine supporting multi-template PDF issuance."""

    @staticmethod
    def generate_verification_code() -> str:
        """Cryptographically secure verification code — CERT-XXXX-XXXX."""
        part1 = secrets.token_hex(2).upper()
        part2 = secrets.token_hex(2).upper()
        return f"CERT-{part1}-{part2}"

    @classmethod
    def sanitize_text_for_pdf(cls, text: Optional[str]) -> str:
        return _sanitize(text)

    @classmethod
    def generate_certificate_pdf(
        cls,
        output_path: str,
        recipient_name: str,
        course_name: str,
        issue_date: str,
        certificate_code: str,
        issuer_name: str = "TECH INSTITUTE",
        template_name: str = "classic",
        programme_description: str = "",
        verify_base_url: str = "http://localhost:8000/api/certificates/verify",
    ) -> str:
        """
        Generate a professional certificate PDF matching the Tech Institute design.
        Atomic write guarantees zero partial/corrupted PDF files on disk.
        """
        final_dir = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(final_dir, exist_ok=True)

        W, H = landscape(letter)  # 792 x 612 pt
        MAX_TEXT_WIDTH = W - 220

        # Sanitise inputs
        s_name = _sanitize(recipient_name) or "Carol White"
        s_course = _sanitize(course_name) or "Data Structures & Algorithms"
        s_issuer = _sanitize(issuer_name) or "TECH INSTITUTE"
        s_date = _sanitize(issue_date) or "10 April 2025"
        s_desc = _sanitize(programme_description) or (
            "This program demonstrates a strong understanding of fundamental data structures, "
            "algorithmic thinking, and problem-solving techniques using real-world applications."
        )

        tpl = (template_name or "classic").lower().strip()
        is_dark = tpl in ("midnight_dark", "dark", "midnight")
        is_vintage = tpl in ("vintage_crest", "vintage", "ivory")

        # Color setup according to template
        bg_color = colors.HexColor("#091322") if is_dark else (PARCHMENT if is_vintage else OFF_WHITE)
        primary_text = GOLD_LIGHT if is_dark else NAVY
        heading_text = GOLD_BRIGHT if is_dark else NAVY
        body_text = colors.HexColor("#CBD5E1") if is_dark else GRAY_CHARCOAL
        muted_text = colors.HexColor("#94A3B8") if is_dark else GRAY

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".tmp", dir=final_dir)
        tmp_path = tmp.name
        tmp.close()

        try:
            c = canvas.Canvas(tmp_path, pagesize=(W, H))
            c.setTitle(f"Certificate of Achievement — {s_name}")
            c.setAuthor(s_issuer)
            c.setSubject(s_course)
            c.setKeywords(f"Certificate {certificate_code} {s_name} {s_course}")

            # ── 1. Background Fill ──
            c.setFillColor(bg_color)
            c.rect(0, 0, W, H, fill=True, stroke=False)

            # ── 2. Decorative Corner Accents ──
            if not is_vintage:
                _draw_corner_accents(c, W, H, dark_mode=is_dark)

            # ── 3. Outer Double Border ──
            _draw_outer_border(c, W, H, dark_mode=is_dark)

            # ── 4. Top Centered Institutional Header & Crest ──
            crest_y = H - 48
            _draw_pillar_icon(c, W / 2, crest_y, size=26, color=GOLD_BRIGHT if is_dark else NAVY)

            c.setFont("Helvetica-Bold", 12.5)
            c.setFillColor(primary_text)
            c.drawCentredString(W / 2, crest_y - 24, s_issuer.upper())

            c.setFont("Helvetica", 6.8)
            c.setFillColor(GOLD_DARK if not is_dark else GOLD)
            c.drawCentredString(W / 2, crest_y - 34, "LEARN   •   BUILD   •   GROW")

            # ── 5. Top Right Verification Code & QR Code ──
            qr_size = 52
            qr_x = W - qr_size - 48
            qr_y = H - qr_size - 52
            verify_url = f"{verify_base_url}/{certificate_code}"

            c.setFont("Helvetica", 6.8)
            c.setFillColor(body_text)
            c.drawRightString(W - 48, H - 36, f"Verification Code: {certificate_code}")

            _draw_qr(c, verify_url, qr_x, qr_y, size=qr_size, dark_mode=is_dark)

            c.setFont("Helvetica", 6.2)
            c.setFillColor(muted_text)
            c.drawCentredString(qr_x + qr_size / 2, qr_y - 9, "Scan to Verify")

            # ── 6. Certificate Title ──
            title_y = H - 132
            c.setFont("Times-Bold", 27)
            c.setFillColor(heading_text)
            c.drawCentredString(W / 2, title_y, "CERTIFICATE OF ACHIEVEMENT")

            # ── 7. Gold Accent Bar with Diamond Center (—— ◆ ——) ──
            bar_y = title_y - 12
            c.setStrokeColor(GOLD)
            c.setLineWidth(0.9)
            c.line(W / 2 - 68, bar_y, W / 2 - 12, bar_y)
            c.line(W / 2 + 12, bar_y, W / 2 + 68, bar_y)

            # Center Gold Diamond
            c.setFillColor(GOLD)
            dp = c.beginPath()
            dp.moveTo(W / 2, bar_y + 4)
            dp.lineTo(W / 2 + 4, bar_y)
            dp.lineTo(W / 2, bar_y - 4)
            dp.lineTo(W / 2 - 4, bar_y)
            dp.close()
            c.drawPath(dp, fill=True, stroke=False)

            # ── 8. Subtitle Presentation Line ──
            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(muted_text)
            c.drawCentredString(W / 2, bar_y - 18, "THIS CERTIFICATE IS PROUDLY PRESENTED TO")

            # ── 9. Recipient Name (Cursive Script Style) ──
            name_y = bar_y - 64
            name_sz, disp_name = _scale_font(c, s_name, "Times-BoldItalic", 39, 18, MAX_TEXT_WIDTH)
            c.setFont("Times-BoldItalic", name_sz)
            c.setFillColor(GOLD_LIGHT if is_dark else NAVY)
            c.drawCentredString(W / 2, name_y, disp_name)

            # Recipient Underline
            name_width = min(c.stringWidth(disp_name, "Times-BoldItalic", name_sz) + 36, MAX_TEXT_WIDTH)
            c.setStrokeColor(GOLD)
            c.setLineWidth(1.2)
            c.line(W / 2 - name_width / 2, name_y - 6, W / 2 + name_width / 2, name_y - 6)

            # ── 10. Curriculum / Award Narrative ──
            narrative_y = name_y - 28
            c.setFont("Helvetica", 9.5)
            c.setFillColor(body_text)
            c.drawCentredString(
                W / 2,
                narrative_y,
                "for successfully completing all the requirements, assessments, and curriculum of",
            )

            # ── 11. Course / Program Name (Prominent & Bold) ──
            course_y = narrative_y - 26
            course_sz, disp_course = _scale_font(c, s_course, "Helvetica-Bold", 17.5, 11, MAX_TEXT_WIDTH)
            c.setFont("Helvetica-Bold", course_sz)
            c.setFillColor(GOLD_BRIGHT if is_dark else NAVY)
            c.drawCentredString(W / 2, course_y, disp_course)

            # ── 12. Program Description (Multi-line Wrapped) ──
            desc_y = course_y - 18
            desc_sz = 8.5
            c.setFont("Helvetica", desc_sz)
            c.setFillColor(muted_text)

            words = s_desc.split()
            lines: list[str] = []
            curr_line: list[str] = []
            for w in words:
                candidate = " ".join(curr_line + [w])
                if c.stringWidth(candidate, "Helvetica", desc_sz) > MAX_TEXT_WIDTH * 0.88:
                    lines.append(" ".join(curr_line))
                    curr_line = [w]
                else:
                    curr_line.append(w)
            if curr_line:
                lines.append(" ".join(curr_line))

            for li, line_text in enumerate(lines[:2]):
                c.drawCentredString(W / 2, desc_y - (li * 12), line_text)

            # ── 13. Center Medallion Gold Seal ──
            seal_cx = W / 2
            seal_cy = 98
            _draw_medallion_seal(c, seal_cx, seal_cy, r=32, dark_mode=is_dark)

            # ── 14. Left Signature Block (Dr. Arthur Pendelton) ──
            sig_y = 112
            lx = 175
            _draw_signature_arthur(c, lx, sig_y, dark_mode=is_dark)

            # Line under signature
            c.setStrokeColor(colors.HexColor("#CBD5E1") if not is_dark else colors.HexColor("#2D3748"))
            c.setLineWidth(0.8)
            c.line(lx - 60, sig_y, lx + 60, sig_y)

            c.setFont("Helvetica-Bold", 8.5)
            c.setFillColor(primary_text)
            c.drawCentredString(lx, sig_y - 13, "Dr. Arthur Pendelton")

            c.setFont("Helvetica", 7.2)
            c.setFillColor(muted_text)
            c.drawCentredString(lx, sig_y - 23, "Director of Academic Affairs")

            # ── 15. Right Signature Block (Prof. Evelyn Vance) ──
            rx = W - 175
            _draw_signature_evelyn(c, rx, sig_y, dark_mode=is_dark)

            c.setStrokeColor(colors.HexColor("#CBD5E1") if not is_dark else colors.HexColor("#2D3748"))
            c.setLineWidth(0.8)
            c.line(rx - 60, sig_y, rx + 60, sig_y)

            c.setFont("Helvetica-Bold", 8.5)
            c.setFillColor(primary_text)
            c.drawCentredString(rx, sig_y - 13, "Prof. Evelyn Vance")

            c.setFont("Helvetica", 7.2)
            c.setFillColor(muted_text)
            c.drawCentredString(rx, sig_y - 23, "Lead Instructor & Evaluator")

            # ── 16. Footer Date (Bottom Left) ──
            c.setFont("Helvetica", 7.5)
            c.setFillColor(muted_text)
            c.drawString(42, 30, f"Date of Issue: {s_date}")

            c.showPage()
            c.save()

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 100:
                raise IOError("Generated PDF is empty or incomplete")

            os.replace(tmp_path, output_path)
            return output_path

        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
            raise

    @classmethod
    def calculate_scaled_font(
        cls,
        c: canvas.Canvas,
        text: str,
        font_name: str,
        initial_size: int,
        min_size: int,
        max_width: float,
    ) -> Tuple[int, str]:
        return _scale_font(c, text, font_name, initial_size, min_size, max_width)

    @classmethod
    def validate_template_at_startup(cls, template_dir: Optional[str] = None) -> bool:
        """Fail-fast check: generate a test certificate into a temp dir."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            test_pdf = os.path.join(tmp_dir, "startup_check.pdf")
            try:
                cls.generate_certificate_pdf(
                    output_path=test_pdf,
                    recipient_name="Startup Verification Test",
                    course_name="System Readiness Test",
                    issue_date="2025-01-01",
                    certificate_code="CERT-SYS-TEST-0000",
                    issuer_name="TECH INSTITUTE",
                )
                return True
            except Exception as e:
                raise RuntimeError(f"Startup PDF validation failed: {e}") from e
