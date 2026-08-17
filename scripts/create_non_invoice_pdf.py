"""Create a benign non-invoice PDF fixture for NOAVIA attachment tests."""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


OUTPUT = Path(__file__).resolve().parents[1] / "output/pdf/noavia-non-invoice-support-note.pdf"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=A4)
    _, height = A4
    pdf.setTitle("NOAVIA Support Note - Non-Invoice Test Fixture")
    pdf.setFont("Helvetica-Bold", 20)
    pdf.drawString(20 * mm, height - 28 * mm, "NOAVIA SUPPORT NOTE")
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#5B6472"))
    pdf.drawString(20 * mm, height - 35 * mm, "Synthetic test document - general account-access context only")
    pdf.setFillColor(colors.black)

    lines = [
        "Subject: Account access after a password reset",
        "",
        "Hello Support Team,",
        "",
        "After resetting my password, I can sign in but cannot open the project dashboard.",
        "The browser shows an access message after I select the workspace.",
        "Please help me restore access for my test account.",
        "",
        "This attachment contains support context only and no financial account details.",
    ]
    text = pdf.beginText(20 * mm, height - 58 * mm)
    text.setFont("Helvetica", 11)
    text.setLeading(7 * mm)
    for line in lines:
        text.textLine(line)
    pdf.drawText(text)
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(colors.HexColor("#5B6472"))
    pdf.drawString(20 * mm, 25 * mm, "Benign local test fixture for the NOAVIA interview workflow.")
    pdf.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()
