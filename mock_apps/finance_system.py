import asyncio
import datetime
import os
import re
import sqlite3
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from mock_apps.failure_state import failure_config

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "finance.db"))

app = FastAPI(title="Internal Finance System (Mock)")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS invoices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vendor TEXT NOT NULL,
            invoice_number TEXT UNIQUE NOT NULL,
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            due_date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.middleware("http")
async def apply_slow_page(request: Request, call_next):
    if failure_config.slow_page:
        await asyncio.sleep(2.5)
    return await call_next(request)

@app.get("/", response_class=HTMLResponse)
@app.get("/invoices", response_class=HTMLResponse)
async def list_invoices(msg: str = "", error: str = ""):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT vendor, invoice_number, amount, currency, due_date, created_at FROM invoices ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    table_rows = ""
    for r in rows:
        table_rows += f"""
        <tr>
            <td>{r[0]}</td>
            <td>{r[1]}</td>
            <td>{r[3]} {r[2]:.2f}</td>
            <td>{r[4]}</td>
            <td>{r[5]}</td>
        </tr>
        """

    msg_html = f'<div class="msg" style="color: green; padding: 10px; background: #e6ffe6; border: 1px solid green; margin-bottom: 15px;">{msg}</div>' if msg else ''
    error_html = f'<div class="error" style="color: red; padding: 10px; background: #ffe6e6; border: 1px solid red; margin-bottom: 15px;">{error}</div>' if error else ''

    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Internal Finance System</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h2>Internal Finance System - Accounts Payable</h2>
        {msg_html}
        {error_html}
        
        <p><a href="/invoices/new" id="new_invoice_link" style="padding: 8px 16px; background: #0066cc; color: white; text-decoration: none; border-radius: 4px;">+ Enter New Invoice</a></p>

        <h3>Registered Invoices</h3>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr style="background: #f0f0f0;">
                    <th>Vendor</th>
                    <th>Invoice Number</th>
                    <th>Amount</th>
                    <th>Due Date</th>
                    <th>Recorded At</th>
                </tr>
            </thead>
            <tbody>
                {table_rows if table_rows else '<tr><td colspan="5">No invoices recorded yet.</td></tr>'}
            </tbody>
        </table>
    </body>
    </html>
    """

@app.get("/invoices/new", response_class=HTMLResponse)
async def new_invoice_form(error: str = ""):
    error_html = f'<div class="error" id="form_error" style="color: red; padding: 10px; background: #ffe6e6; border: 1px solid red; margin-bottom: 15px;">{error}</div>' if error else ''
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Finance System - New Invoice</title></head>
    <body style="font-family: sans-serif; padding: 20px; max-width: 500px;">
        <h2>Record New Invoice</h2>
        {error_html}
        <form method="post" action="/invoices/new" id="invoice_form">
            <p><label>Vendor Name:<br><input type="text" name="vendor" id="vendor_input" style="width: 100%; padding: 6px;" required></label></p>
            <p><label>Invoice Number:<br><input type="text" name="invoice_number" id="invoice_number_input" style="width: 100%; padding: 6px;" required></label></p>
            <p><label>Amount (Numeric):<br><input type="text" name="amount" id="amount_input" style="width: 100%; padding: 6px;" required></label></p>
            <p><label>Currency (e.g. USD, EUR):<br><input type="text" name="currency" id="currency_input" style="width: 100%; padding: 6px;" value="USD" required></label></p>
            <p><label>Due Date (YYYY-MM-DD):<br><input type="text" name="due_date" id="due_date_input" placeholder="2026-10-15" style="width: 100%; padding: 6px;" required></label></p>
            <p><button type="submit" id="submit_invoice_button" style="padding: 10px 20px; background: #28a745; color: white; border: none; border-radius: 4px; cursor: pointer;">Submit Invoice</button></p>
        </form>
        <p><a href="/invoices">Cancel</a></p>
    </body>
    </html>
    """

@app.post("/invoices/new")
async def submit_invoice(
    vendor: str = Form(...),
    invoice_number: str = Form(...),
    amount: str = Form(...),
    currency: str = Form(...),
    due_date: str = Form(...)
):
    # Failure Injection: Flaky submit once
    if failure_config.flaky_submit_once and not failure_config.has_flaked:
        failure_config.has_flaked = True
        return Response(content="<html><body><h1>500 Internal Server Error</h1><p>Database lock timeout. Please retry submission.</p></body></html>", status_code=500)

    # Validation: Amount
    clean_amount_str = amount.replace("$", "").replace("€", "").replace("EUR", "").replace("USD", "").replace(",", "").strip()
    try:
        parsed_amount = float(clean_amount_str)
    except ValueError:
        return RedirectResponse(url=f"/invoices/new?error=Invalid+amount+format:+{amount}", status_code=303)

    # Validation: Date
    due_date = due_date.strip()
    if failure_config.strict_date_validation:
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", due_date):
            return RedirectResponse(url=f"/invoices/new?error=Invalid+date+format.+due_date+must+be+strictly+YYYY-MM-DD+(e.g.+2026-10-15),+got:+{due_date}", status_code=303)
        try:
            datetime.datetime.strptime(due_date, "%Y-%m-%d")
        except ValueError:
            return RedirectResponse(url=f"/invoices/new?error=Invalid+calendar+date:+{due_date}", status_code=303)

    # Database insertion & duplicate rejection
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO invoices (vendor, invoice_number, amount, currency, due_date) VALUES (?, ?, ?, ?, ?)",
            (vendor.strip(), invoice_number.strip(), parsed_amount, currency.strip().upper(), due_date)
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return RedirectResponse(url=f"/invoices/new?error=Duplicate+Invoice:+Invoice+{invoice_number}+already+exists+in+system.", status_code=303)
    conn.close()

    return RedirectResponse(url=f"/invoices?msg=Invoice+{invoice_number}+successfully+recorded.", status_code=303)

# JSON API for post-run independent verifier ONLY (never exposed to agent toolset)
@app.get("/api/invoices")
async def api_get_invoices():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, vendor, invoice_number, amount, currency, due_date, created_at FROM invoices")
    rows = cursor.fetchall()
    conn.close()

    invoices = [
        {
            "id": r[0],
            "vendor": r[1],
            "invoice_number": r[2],
            "amount": r[3],
            "currency": r[4],
            "due_date": r[5],
            "created_at": r[6]
        }
        for r in rows
    ]
    return JSONResponse(content={"ok": True, "invoices": invoices})

@app.get("/api/invoices/{invoice_number}")
async def api_get_invoice_by_number(invoice_number: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, vendor, invoice_number, amount, currency, due_date, created_at FROM invoices WHERE invoice_number = ?", (invoice_number,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return JSONResponse(content={"ok": False, "error": "Invoice not found"}, status_code=404)

    return JSONResponse(content={
        "ok": True,
        "invoice": {
            "id": row[0],
            "vendor": row[1],
            "invoice_number": row[2],
            "amount": row[3],
            "currency": row[4],
            "due_date": row[5],
            "created_at": row[6]
        }
    })

# Failure injection control API
@app.post("/api/failure-injection")
async def set_failure_injection(config: dict):
    if "flaky_submit_once" in config:
        failure_config.flaky_submit_once = config["flaky_submit_once"]
    if "strict_date_validation" in config:
        failure_config.strict_date_validation = config["strict_date_validation"]
    if "slow_page" in config:
        failure_config.slow_page = config["slow_page"]
    if "has_flaked" in config:
        failure_config.has_flaked = config["has_flaked"]
    return JSONResponse(content={"ok": True, "config": failure_config.model_dump()})

@app.get("/api/failure-injection")
async def get_failure_injection():
    return JSONResponse(content={"ok": True, "config": failure_config.model_dump()})
