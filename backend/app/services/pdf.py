"""
PDF report generation via ReportLab (pure Python, no system deps).
"""
from io import BytesIO
from datetime import date
from typing import Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak,
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# Drift brand palette
DARK = colors.HexColor("#0a0b0d")
BG1 = colors.HexColor("#0f1114")
ACCENT = colors.HexColor("#ffaa00")
TEXT = colors.HexColor("#e8eaed")
TEXT2 = colors.HexColor("#a8acb3")
CRIT = colors.HexColor("#ff4a5e")
HIGH = colors.HexColor("#ff8847")
MED = colors.HexColor("#ffc53d")
LOW = colors.HexColor("#4ea8ff")
INFO = colors.HexColor("#7a828f")
OK = colors.HexColor("#34d399")

SEV_COLORS = {
    "critical": CRIT, "high": HIGH, "medium": MED, "low": LOW, "info": INFO,
}


def generate_report_pdf(report: Any, engagement: Any | None) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("Title", parent=styles["Heading1"], fontSize=24,
                                  textColor=colors.white, leading=30)
    h2_style = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=16,
                               textColor=ACCENT, leading=22)
    h3_style = ParagraphStyle("H3", parent=styles["Heading3"], fontSize=12,
                               textColor=TEXT, leading=16)
    body_style = ParagraphStyle("Body", parent=styles["Normal"], fontSize=10,
                                 textColor=TEXT2, leading=14)
    mono_style = ParagraphStyle("Mono", parent=styles["Code"], fontSize=9,
                                 textColor=TEXT2, backColor=BG1, leading=13)
    label_style = ParagraphStyle("Label", parent=styles["Normal"], fontSize=8,
                                  textColor=TEXT2, leading=12, spaceAfter=2)

    story = []

    # ── Cover ──────────────────────────────────────────────────────────────────
    story.append(Paragraph(report.title, title_style))
    story.append(Spacer(1, 4 * mm))
    if engagement:
        meta_data = [
            ["Engagement", engagement.code],
            ["Client", engagement.client],
            ["Period", f"{engagement.start_date} → {engagement.end_date}"],
            ["Version", report.version],
            ["Status", report.status],
        ]
        meta_table = Table(meta_data, colWidths=[40 * mm, 120 * mm])
        meta_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), TEXT2),
            ("TEXTCOLOR", (1, 0), (1, -1), TEXT),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [BG1, DARK]),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#23262d")),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(meta_table)
    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT))
    story.append(PageBreak())

    # ── Blocks ─────────────────────────────────────────────────────────────────
    for block in (report.blocks or []):
        btype = block.get("type", "paragraph")
        content = block.get("content", "")

        if btype == "heading":
            story.append(Paragraph(str(content), h2_style))
            story.append(Spacer(1, 3 * mm))

        elif btype == "paragraph":
            story.append(Paragraph(str(content), body_style))
            story.append(Spacer(1, 2 * mm))

        elif btype == "code":
            story.append(Paragraph(str(content).replace("\n", "<br/>"), mono_style))
            story.append(Spacer(1, 2 * mm))

        elif btype == "finding":
            f = block.get("finding", {})
            sev = f.get("severity", "info")
            sev_color = SEV_COLORS.get(sev, INFO)
            sev_label = sev.upper()
            finding_data = [
                [Paragraph(f"[{sev_label}] {f.get('title', '')}", h3_style), ""],
                [Paragraph(f"{f.get('code', '')} · CVSS {f.get('cvss', 0)}", label_style),
                 Paragraph(f.get('target', ''), label_style)],
                [Paragraph(f.get("summary", ""), body_style), ""],
            ]
            finding_table = Table(finding_data, colWidths=[120 * mm, 50 * mm])
            finding_table.setStyle(TableStyle([
                ("SPAN", (0, 0), (1, 0)),
                ("SPAN", (0, 2), (1, 2)),
                ("BACKGROUND", (0, 0), (-1, -1), BG1),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEAFTER", (0, 0), (0, -1), 3, sev_color),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#23262d")),
            ]))
            story.append(finding_table)
            story.append(Spacer(1, 2 * mm))

        elif btype == "table":
            rows = block.get("rows", [])
            if rows:
                t = Table(rows)
                t.setStyle(TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("TEXTCOLOR", (0, 0), (-1, -1), TEXT2),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#23262d")),
                    ("BACKGROUND", (0, 0), (-1, 0), BG1),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(t)
                story.append(Spacer(1, 2 * mm))

    story.append(Spacer(1, 6 * mm))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#23262d")))
    story.append(Paragraph(f"Generated by Drift · {date.today()}", label_style))

    doc.build(story)
    return buf.getvalue()
