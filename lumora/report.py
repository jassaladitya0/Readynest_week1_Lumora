"""
report.py — Lumora
Builds a polished, multi-page PDF report combining dataset stats, insights, and charts.
"""
import base64
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

BRAND_PURPLE = colors.HexColor("#7C3AED")
BRAND_CYAN = colors.HexColor("#22D3EE")
BRAND_DARK = colors.HexColor("#1E1B2E")


def build_pdf_report(filepath: str, dataset_name: str, stats: dict,
                      insights: list, uni_charts: list, bi_charts: list):
    doc = SimpleDocTemplate(filepath, pagesize=A4,
                             topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleBrand", parent=styles["Title"],
                                  textColor=BRAND_PURPLE, fontSize=26, alignment=TA_CENTER)
    sub_style = ParagraphStyle("SubBrand", parent=styles["Normal"],
                                textColor=colors.grey, fontSize=11, alignment=TA_CENTER)
    h2_style = ParagraphStyle("H2Brand", parent=styles["Heading2"], textColor=BRAND_DARK)
    body_style = styles["Normal"]

    story = []

    # Cover
    story.append(Spacer(1, 3 * cm))
    story.append(Paragraph("LUMORA", title_style))
    story.append(Paragraph("Illuminate Your Data", sub_style))
    story.append(Spacer(1, 1 * cm))
    story.append(Paragraph(f"Data Analysis Report — {dataset_name}", styles["Heading2"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(
        f"{stats['row_count']:,} rows &nbsp;|&nbsp; {stats['col_count']} columns",
        body_style))
    story.append(Spacer(1, 6 * cm))
    story.append(Paragraph("Made by Aditya Jassal", ParagraphStyle(
        "Footer", parent=styles["Normal"], alignment=TA_CENTER, textColor=colors.grey)))
    story.append(PageBreak())

    # Key Insights
    story.append(Paragraph("Key Insights", h2_style))
    story.append(Spacer(1, 0.3 * cm))
    for i, insight in enumerate(insights, 1):
        story.append(Paragraph(f"{i}. {insight}", body_style))
        story.append(Spacer(1, 0.15 * cm))
    story.append(Spacer(1, 0.5 * cm))

    # Descriptive Statistics — numeric
    if stats["numeric"]:
        story.append(Paragraph("Descriptive Statistics (Numeric Columns)", h2_style))
        story.append(Spacer(1, 0.2 * cm))
        cols = list(stats["numeric"][0].keys())
        table_data = [cols] + [[str(row.get(c, "")) for c in cols] for row in stats["numeric"]]
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_PURPLE),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F3F0FF")]),
        ]))
        story.append(t)
        story.append(Spacer(1, 0.5 * cm))

    # Categorical summary
    if stats["categorical"]:
        story.append(Paragraph("Categorical Columns Summary", h2_style))
        story.append(Spacer(1, 0.2 * cm))
        table_data = [["Column", "Unique Values", "Top Value", "Frequency"]]
        for row in stats["categorical"]:
            table_data.append([row["column"], str(row["unique"]), row["top"], str(row["freq"])])
        t = Table(table_data, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), BRAND_CYAN),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#E6FBFF")]),
        ]))
        story.append(t)
    story.append(PageBreak())

    # Univariate charts
    story.append(Paragraph("Univariate Analysis", h2_style))
    story.append(Spacer(1, 0.3 * cm))
    for chart in uni_charts:
        story.append(Paragraph(chart["title"], styles["Heading4"]))
        img_data = base64.b64decode(chart["img"])
        img = Image(io.BytesIO(img_data), width=15 * cm, height=15 * cm * 0.45)
        story.append(img)
        story.append(Spacer(1, 0.4 * cm))

    story.append(PageBreak())

    # Bivariate charts
    story.append(Paragraph("Bivariate Analysis", h2_style))
    story.append(Spacer(1, 0.3 * cm))
    for chart in bi_charts:
        story.append(Paragraph(chart["title"], styles["Heading4"]))
        img_data = base64.b64decode(chart["img"])
        img = Image(io.BytesIO(img_data), width=13 * cm, height=13 * cm * 0.8)
        story.append(img)
        story.append(Spacer(1, 0.4 * cm))

    doc.build(story)
    return filepath
