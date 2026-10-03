import os
import sqlite3
from mock_apps.pdf_generator import generate_invoice_pdf
from mock_apps.finance_system import DB_PATH, init_db
from mock_apps.failure_state import reset_failure_config

STATIC_PDF_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static", "invoices"))

def seed_database_and_pdfs():
    print("Seeding synthetic PDF invoices...")
    os.makedirs(STATIC_PDF_DIR, exist_ok=True)

    # Generate sample PDFs with varied date and amount formats to test PDF parsing & normalization
    generate_invoice_pdf(
        os.path.join(STATIC_PDF_DIR, "INV-2026-881.pdf"),
        invoice_num="INV-2026-881",
        vendor="Acme Supplies",
        amount_str="$4,500.50",
        due_date_str="2026-11-01",
        items=[("Ergonomic Chairs (x5)", "$2,500.00"), ("Standing Desks (x2)", "$2,000.50")]
    )

    generate_invoice_pdf(
        os.path.join(STATIC_PDF_DIR, "INV-2026-992.pdf"),
        invoice_num="INV-2026-992",
        vendor="Acme Supply Co",
        amount_str="$1,800.00",
        due_date_str="2026-10-25",
        items=[("Industrial Cleaning Supplies", "$1,800.00")]
    )

    generate_invoice_pdf(
        os.path.join(STATIC_PDF_DIR, "INV-2026-104.pdf"),
        invoice_num="INV-2026-104",
        vendor="Global Tech Solutions",
        amount_str="EUR 3,200.00",
        due_date_str="December 15, 2026", # Non-standard date format in source PDF to test agent normalization!
        items=[("Enterprise Cloud Hosting Q4", "EUR 3,200.00")]
    )

    generate_invoice_pdf(
        os.path.join(STATIC_PDF_DIR, "INV-2026-440.pdf"),
        invoice_num="INV-2026-440",
        vendor="Apex Logistics",
        amount_str="$890.00",
        due_date_str="2026-10-05",
        items=[("Freight Shipping - Cargo Hub", "$890.00")]
    )

    print("Initializing SQLite Database...")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS invoices")
    conn.commit()
    conn.close()
    
    init_db()

    # Reset failure configuration
    reset_failure_config()
    print("Seed complete successfully.")

if __name__ == "__main__":
    seed_database_and_pdfs()
