"""
PDF Report Generator — matches Vee Technologies daily client report format.

Layout: Header → Company News table → Competition News table → Industry News table → Footer
Columns: Article Date | Headline | Publication | Edition
"""

from __future__ import annotations

import io
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Vee Technologies report colors
HEADER_COLOR_HEX = "#FF8C69"
SECTION_COLOR_HEX = "#FFD0C0"
TEXT_COLOR_HEX = "#1a1a1a"
MUTED_COLOR_HEX = "#666666"
ALT_ROW_HEX = "#F9F9F9"


def generate_daily_report_pdf(
    client_name: str,
    date: str,
    company_articles: list,
    competition_articles: list,
    industry_articles: list,
) -> bytes:
    """
    Generate PDF daily media intelligence report in Vee Technologies format.
    Returns PDF as bytes. Requires reportlab.
    """
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle,
            Paragraph, Spacer, HRFlowable,
        )
        from reportlab.lib.enums import TA_CENTER
    except ImportError:
        logger.error("reportlab not installed. Run: pip install reportlab")
        return b""

    HEADER_COLOR = colors.HexColor(HEADER_COLOR_HEX)
    SECTION_COLOR = colors.HexColor(SECTION_COLOR_HEX)
    TEXT_COLOR = colors.HexColor(TEXT_COLOR_HEX)
    MUTED_COLOR = colors.HexColor(MUTED_COLOR_HEX)
    ALT_ROW = colors.HexColor(ALT_ROW_HEX)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=20 * mm, bottomMargin=20 * mm,
    )

    title_style = ParagraphStyle("Title", fontSize=14, fontName="Helvetica-Bold",
                                  alignment=TA_CENTER, textColor=TEXT_COLOR, spaceAfter=4)
    sub_style = ParagraphStyle("Sub", fontSize=10, fontName="Helvetica",
                                alignment=TA_CENTER, textColor=MUTED_COLOR, spaceAfter=12)
    cell_style = ParagraphStyle("Cell", fontSize=8, fontName="Helvetica",
                                 textColor=TEXT_COLOR, leading=11)
    head_style = ParagraphStyle("Head", fontSize=9, fontName="Helvetica-Bold",
                                 textColor=TEXT_COLOR)

    story = []

    # ── Document Header ────────────────────────────────────────
    story.append(Paragraph("Daily Media Intelligence Report", title_style))
    story.append(Paragraph(f"{client_name}  ·  {date}", sub_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 6 * mm))

    col_widths = [28 * mm, 90 * mm, 40 * mm, 22 * mm]

    def _make_section(title: str, articles: list) -> list:
        if not articles:
            return []
        elements = []

        # Section header (salmon background)
        t_header = Table([[Paragraph(title, ParagraphStyle(
            "SH", fontSize=9, fontName="Helvetica-Bold", textColor=TEXT_COLOR,
        )), "", "", ""]], colWidths=[180 * mm])
        t_header.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), SECTION_COLOR),
            ("SPAN", (0, 0), (-1, -1)),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t_header)

        # Column headers + data rows
        data = [[
            Paragraph("Article Date", head_style),
            Paragraph("Headline", head_style),
            Paragraph("Publication", head_style),
            Paragraph("Edition", head_style),
        ]]
        for article in articles:
            raw_date = article.get("published_at", article.get("publishedAt", ""))
            try:
                if "T" in str(raw_date):
                    d = datetime.fromisoformat(str(raw_date).replace("Z", ""))
                else:
                    d = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d")
                date_str = d.strftime("%d/%m/%Y")
            except Exception:
                date_str = str(raw_date)[:10] if raw_date else ""

            headline = article.get("title", article.get("headline", ""))
            source = article.get("source", "")
            edition = article.get("edition", "Online Web")

            data.append([
                Paragraph(date_str, cell_style),
                Paragraph(str(headline)[:200], cell_style),
                Paragraph(str(source), cell_style),
                Paragraph(str(edition), cell_style),
            ])

        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEEEEE")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#DDDDDD")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ALT_ROW]),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 6 * mm))
        return elements

    story.extend(_make_section("Company Specific News", company_articles))
    story.extend(_make_section("Competition News", competition_articles))
    story.extend(_make_section("Industry News", industry_articles))

    # ── Footer ─────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc")))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph(
        f"Generated by VeeTrack · Vee Technologies · "
        f"{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC",
        ParagraphStyle("Footer", fontSize=7, textColor=MUTED_COLOR, alignment=TA_CENTER),
    ))

    doc.build(story)
    return buffer.getvalue()


def send_report_email(
    to_email: str,
    client_name: str,
    date: str,
    pdf_bytes: bytes,
    from_email: str = "reports@veetechnologies.com",
) -> bool:
    """Send the PDF report as email attachment via SMTP."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.base import MIMEBase
    from email.mime.text import MIMEText
    from email import encoders

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")

    if not smtp_user or not smtp_password:
        logger.info(f"SMTP not configured — skipping email to {to_email}")
        return False

    msg = MIMEMultipart()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = f"VeeTrack Daily Report — {client_name} — {date}"

    body = (
        f"Dear {client_name} Team,\n\n"
        f"Please find attached your VeeTrack Daily Media Intelligence Report for {date}.\n\n"
        f"This report covers:\n"
        f"• Company-specific news coverage\n"
        f"• Competitor media activity\n"
        f"• Industry news and trends\n\n"
        f"Generated automatically by VeeTrack — AI-Powered Media Intelligence Platform\n"
        f"Vee Technologies, Salem, Tamil Nadu\n"
    )
    msg.attach(MIMEText(body, "plain"))

    attachment = MIMEBase("application", "octet-stream")
    attachment.set_payload(pdf_bytes)
    encoders.encode_base64(attachment)
    attachment.add_header(
        "Content-Disposition",
        f"attachment; filename=VeeTrack_{client_name.replace(' ', '_')}_{date}.pdf",
    )
    msg.attach(attachment)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(from_email, to_email, msg.as_string())
        logger.info(f"Report emailed to {to_email}")
        return True
    except Exception as e:
        logger.warning(f"Email failed to {to_email}: {e}")
        return False
