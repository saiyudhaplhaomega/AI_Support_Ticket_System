"""Create a synthetic disputed-invoice fixture for NOAVIA attachment tests.

Unlike ``create_dummy_invoice_pdf.py``, the problem here is stated only inside
the PDF. The ticket body that carries it stays deliberately neutral, so this
fixture proves the classifier actually reads attachment text when it judges
urgency instead of scoring the covering message alone.
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


OUTPUT = Path(__file__).resolve().parents[1] / "output/pdf/noavia-disputed-invoice.pdf"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=A4)
    _, height = A4
    pdf.setTitle("NOAVIA Disputed Invoice - Test Fixture")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(20 * mm, height - 28 * mm, "NOAVIA DEMO INVOICE")
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#5B6472"))
    pdf.drawString(20 * mm, height - 35 * mm, "Synthetic test document - not a real bill or payment request")
    pdf.setFillColor(colors.black)

    details = [
        ("Invoice number", "DEMO-2026-014"),
        ("Invoice date", "18 August 2026"),
        ("Bill to", "NOAVIA Test Customer"),
        ("Payment terms", "Charged on issue"),
        ("Status", "CHARGED - DEMO ONLY"),
    ]
    y = height - 55 * mm
    for label, value in details:
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(20 * mm, y, label)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(65 * mm, y, value)
        y -= 8 * mm

    table_top = y - 5 * mm
    rows = [
        ("Description", "Qty", "Unit price", "Amount"),
        ("Support subscription - demo", "1", "EUR 19.00", "EUR 19.00"),
        ("Support subscription - demo (repeat)", "1", "EUR 19.00", "EUR 19.00"),
    ]
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
    pdf.drawRightString(190 * mm, table_top - 40 * mm, "Subtotal: EUR 38.00")
    pdf.drawRightString(190 * mm, table_top - 48 * mm, "Amount due: EUR 38.00")

    note = [
        "Customer note attached to this invoice:",
        "",
        "This invoice charges the same monthly subscription twice on the same date.",
        "The duplicate line was taken from my payment method and my account balance",
        "is now negative, so a further scheduled payment will fail this week.",
        "Please reverse the duplicate charge and confirm the corrected amount.",
    ]
    text = pdf.beginText(20 * mm, table_top - 62 * mm)
    text.setFont("Helvetica", 11)
    text.setLeading(7 * mm)
    for line in note:
        text.textLine(line)
    pdf.drawText(text)

    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#5B6472"))
    pdf.drawString(20 * mm, 25 * mm, "This document is intentionally benign and contains no payment instructions, links, or embedded files.")
    pdf.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()
