import os
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

def generate_invoice_pdf(output_path: str, invoice_num: str, vendor: str, amount_str: str, due_date_str: str, items: list[tuple[str, str]]) -> str:
    """Generate a realistic invoice PDF using reportlab."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter

    # Header
    c.setFont("Helvetica-Bold", 20)
    c.drawString(50, height - 50, f"INVOICE: {invoice_num}")

    c.setFont("Helvetica", 12)
    c.drawString(50, height - 80, f"Vendor: {vendor}")
    c.drawString(50, height - 100, f"Due Date: {due_date_str}")
    c.drawString(50, height - 120, f"Total Amount Due: {amount_str}")

    # Divider line
    c.line(50, height - 135, width - 50, height - 135)

    # Line Items Header
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, height - 160, "Description")
    c.drawString(450, height - 160, "Price")

    y = height - 180
    c.setFont("Helvetica", 10)
    for desc, price in items:
        c.drawString(50, y, desc)
        c.drawString(450, y, price)
        y -= 20

    # Summary
    c.line(50, y - 10, width - 50, y - 10)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y - 30, "Total:")
    c.drawString(450, y - 30, amount_str)

    # Footer
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 40, "Thank you for your business. Please make payments by the due date.")

    c.save()
    return output_path
