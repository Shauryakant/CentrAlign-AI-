import asyncio
import os
from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from mock_apps.failure_state import failure_config

app = FastAPI(title="Vendor Portal (Mock)")

PDF_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "static", "invoices"))

@app.middleware("http")
async def apply_slow_page(request: Request, call_next):
    if failure_config.slow_page:
        await asyncio.sleep(2.5)
    return await call_next(request)

@app.get("/login", response_class=HTMLResponse)
async def login_page(error: str = ""):
    error_html = f'<div class="error" style="color: red;">{error}</div>' if error else ''
    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Vendor Portal - Login</title></head>
    <body style="font-family: sans-serif; padding: 40px; max-width: 400px; margin: auto;">
        <h2>Vendor Portal Login</h2>
        {error_html}
        <form method="post" action="/login">
            <p><label>Username: <input type="text" name="username" id="username_input"></label></p>
            <p><label>Password: <input type="password" name="password" id="password_input"></label></p>
            <p><button type="submit" id="login_button">Sign In</button></p>
        </form>
    </body>
    </html>
    """

@app.post("/login")
async def login_submit(username: str = Form(...), password: str = Form(...)):
    if username == "admin" and password == "password123":
        res = RedirectResponse(url="/dashboard", status_code=303)
        res.set_cookie("session", "logged_in")
        return res
    return RedirectResponse(url="/login?error=Invalid+credentials", status_code=303)

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, q: str = ""):
    session = request.cookies.get("session")
    if not session:
        return RedirectResponse(url="/login", status_code=303)

    invoices = [
        {"id": "inv_1", "vendor": "Acme Supplies", "number": "INV-2026-881", "amount": "$4,500.50", "date": "2026-11-01", "pdf": "INV-2026-881.pdf"},
        {"id": "inv_2", "vendor": "Acme Supply Co", "number": "INV-2026-992", "amount": "$1,800.00", "date": "2026-10-25", "pdf": "INV-2026-992.pdf"},
        {"id": "inv_3", "vendor": "Global Tech Solutions", "number": "INV-2026-104", "amount": "EUR 3,200.00", "date": "2026-12-15", "pdf": "INV-2026-104.pdf"},
        {"id": "inv_4", "vendor": "Apex Logistics", "number": "INV-2026-440", "amount": "$890.00", "date": "2026-10-05", "pdf": "INV-2026-440.pdf"},
    ]

    if q:
        invoices = [i for i in invoices if q.lower() in i["vendor"].lower() or q.lower() in i["number"].lower()]

    rows = ""
    for inv in invoices:
        rows += f"""
        <tr>
            <td>{inv['vendor']}</td>
            <td>{inv['number']}</td>
            <td>{inv['amount']}</td>
            <td>{inv['date']}</td>
            <td><a href="/download/{inv['pdf']}" id="download_{inv['number']}">Download PDF</a></td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head><title>Vendor Portal - Invoices</title></head>
    <body style="font-family: sans-serif; padding: 20px;">
        <h2>Vendor Portal - Dashboard</h2>
        <form method="get" action="/dashboard" style="margin-bottom: 20px;">
            <input type="text" name="q" placeholder="Search vendor or invoice..." value="{q}" id="search_input">
            <button type="submit" id="search_button">Search</button>
        </form>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr style="background: #f0f0f0;">
                    <th>Vendor Name</th>
                    <th>Invoice Number</th>
                    <th>Amount</th>
                    <th>Due Date</th>
                    <th>Action</th>
                </tr>
            </thead>
            <tbody>
                {rows}
            </tbody>
        </table>
    </body>
    </html>
    """

@app.get("/download/{filename}")
async def download_pdf(filename: str):
    file_path = os.path.join(PDF_DIR, filename)
    if not os.path.exists(file_path):
        return Response(content="File not found", status_code=404)
    return FileResponse(file_path, media_type="application/pdf", filename=filename)
