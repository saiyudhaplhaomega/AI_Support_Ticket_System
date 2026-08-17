"""Create a harmless, synthetic invoice fixture for NOAVIA workflow tests."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


OUTPUT = Path(__file__).resolve().parents[1] / "output/pdf/noavia-dummy-invoice.pdf"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=A4)
    width, height = A4
    pdf.setTitle("NOAVIA Dummy Invoice - Test Fixture")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(20 * mm, height - 28 * mm, "NOAVIA DEMO INVOICE")
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#5B6472"))
    pdf.drawString(20 * mm, height - 35 * mm, "Synthetic test document - not a real bill or payment request")
    pdf.setFillColor(colors.black)

    details = [
        ("Invoice number", "DEMO-2026-001"),
        ("Invoice date", "17 August 2026"),
        ("Customer", "NOAVIA Test Customer"),
        ("Status", "PAID - DEMO ONLY"),
    ]
    y = height - 55 * mm
    for label, value in details:
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(20 * mm, y, label)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(65 * mm, y, value)
        y -= 8 * mm

    table_top = y - 5 * mm
    rows = [("Description", "Qty", "Unit price", "Amount"), ("Support subscription - demo", "1", "EUR 19.00", "EUR 19.00")]
    columns = [20 * mm, 112 * mm, 142 * mm, 172 * mm]
    for index, row in enumerate(rows):
        row_y = table_top - index * 10 * mm
        pdf.setFillColor(colors.HexColor("#EAF0F7") if index == 0 else colors.white)
        pdf.rect(20 * mm, row_y - 7 * mm, 170 * mm, 10 * mm, fill=1, stroke=0)
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold" if index == 0 else "Helvetica", 9)
        for x, text in zip(columns, row):
            pdf.drawString(x, row_y - 3 * mm, text)

    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawRightString(190 * mm, table_top - 30 * mm, "Total: EUR 19.00")
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#5B6472"))
    pdf.drawString(20 * mm, 25 * mm, "This document is intentionally benign and contains no payment instructions, links, or embedded files.")
    pdf.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()
