import json
import os
import re
import urllib.request
import pypdf
from typing import Dict, Any, Optional

def fetch_invoice_from_api(invoice_number: str, port: int = 8002) -> Optional[Dict[str, Any]]:
    url = f"http://127.0.0.1:{port}/api/invoices/{invoice_number}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Verifier/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("ok"):
                    return data.get("invoice")
    except Exception as e:
        print(f"[Verifier] Failed API lookup for {invoice_number}: {e}")
    return None

def extract_pdf_ground_truth(pdf_path: str) -> Dict[str, Any]:
    if not os.path.exists(pdf_path):
        return {}
    
    reader = pypdf.PdfReader(pdf_path)
    text = "\n".join([page.extract_text() for page in reader.pages])

    # Basic regex patterns for ground truth extraction from source PDF
    inv_match = re.search(r"INVOICE:\s*([A-Z0-9-]+)", text, re.IGNORECASE)
    vendor_match = re.search(r"Vendor:\s*([^\n]+)", text, re.IGNORECASE)
    date_match = re.search(r"Due Date:\s*([^\n]+)", text, re.IGNORECASE)
    amt_match = re.search(r"Total Amount Due:\s*([^\n]+)", text, re.IGNORECASE)

    invoice_number = inv_match.group(1).strip() if inv_match else ""
    vendor = vendor_match.group(1).strip() if vendor_match else ""
    raw_date = date_match.group(1).strip() if date_match else ""
    raw_amt = amt_match.group(1).strip() if amt_match else ""

    # Clean amount
    clean_amt_str = re.sub(r"[^\d.]", "", raw_amt)
    parsed_amt = float(clean_amt_str) if clean_amt_str else 0.0

    return {
        "invoice_number": invoice_number,
        "vendor": vendor,
        "raw_due_date": raw_date,
        "amount": parsed_amt,
        "raw_amount": raw_amt,
        "raw_text": text
    }

def verify_run(trace_result: Dict[str, Any], pdf_path: Optional[str] = None) -> Dict[str, Any]:
    """Independent Out-of-Band Verifier.
    Compares database state via API against both agent's claimed values and PDF ground truth.
    """
    claimed_data = trace_result.get("result_data", {})
    inv_number = claimed_data.get("invoice_number", "")

    if not inv_number:
        # Fallback: search facts or steps trace for invoice number
        for step in trace_result.get("steps_trace", []):
            args = step.get("arguments", {})
            if "invoice_number" in args:
                inv_number = args["invoice_number"]
                break

    if not inv_number:
        return {
            "verified": False,
            "status": "FAILED_VERIFICATION",
            "reason": "Agent did not report or record an invoice_number in finish result_data.",
            "mismatches": ["Missing invoice_number"],
            "evidence": {}
        }

    # 1. Fetch DB record from internal finance API
    db_invoice = fetch_invoice_from_api(inv_number)
    if not db_invoice:
        return {
            "verified": False,
            "status": "FAILED_VERIFICATION",
            "reason": f"Invoice '{inv_number}' was not found in finance database via API.",
            "mismatches": [f"Database record missing for {inv_number}"],
            "evidence": {"claimed": claimed_data, "db": None}
        }

    # 2. Extract ground truth from PDF if provided or found in downloads
    pdf_truth = {}
    if pdf_path and os.path.exists(pdf_path):
        pdf_truth = extract_pdf_ground_truth(pdf_path)
    else:
        # Look in run downloads dir
        run_id = trace_result.get("run_id")
        if run_id:
            downloads_dir = os.path.join("runs", run_id, "downloads")
            if os.path.exists(downloads_dir):
                pdf_files = [os.path.join(downloads_dir, f) for f in os.listdir(downloads_dir) if f.endswith(".pdf")]
                if pdf_files:
                    pdf_truth = extract_pdf_ground_truth(pdf_files[0])

    mismatches = []
    
    # Check 1: Vendor name (case-insensitive substring match)
    claimed_vendor = str(claimed_data.get("vendor", "")).strip()
    db_vendor = str(db_invoice.get("vendor", "")).strip()
    if claimed_vendor.lower() != db_vendor.lower():
        mismatches.append(f"Vendor mismatch: Claimed='{claimed_vendor}' vs DB='{db_vendor}'")

    # Check 2: Amount numeric precision
    claimed_amt = float(claimed_data.get("amount", 0.0)) if claimed_data.get("amount") else None
    db_amt = float(db_invoice.get("amount", 0.0))
    if claimed_amt is not None and abs(claimed_amt - db_amt) > 0.01:
        mismatches.append(f"Amount mismatch: Claimed={claimed_amt} vs DB={db_amt}")

    # Check 3: Date YYYY-MM-DD strict format
    db_date = str(db_invoice.get("due_date", "")).strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", db_date):
        mismatches.append(f"Database due_date format invalid (must be YYYY-MM-DD): '{db_date}'")

    # Check 4: Compare DB against PDF ground truth if available
    if pdf_truth:
        if pdf_truth.get("invoice_number") and pdf_truth["invoice_number"].lower() != inv_number.lower():
            mismatches.append(f"PDF Ground Truth Mismatch: PDF invoice={pdf_truth['invoice_number']} vs DB invoice={inv_number}")
        if pdf_truth.get("amount") and abs(pdf_truth["amount"] - db_amt) > 0.01:
            mismatches.append(f"PDF Ground Truth Mismatch: PDF amount={pdf_truth['amount']} vs DB amount={db_amt}")
        pdf_due_date = str(pdf_truth.get("raw_due_date", "")).strip()
        if pdf_due_date and pdf_due_date != db_date:
            mismatches.append(f"PDF Ground Truth Mismatch: PDF due_date='{pdf_due_date}' vs DB due_date='{db_date}'")

    is_verified = len(mismatches) == 0
    verification_status = "VERIFIED_PASS" if is_verified else "FAILED_VERIFICATION"

    return {
        "verified": is_verified,
        "status": verification_status,
        "mismatches": mismatches,
        "evidence": {
            "agent_claimed": claimed_data,
            "database_record": db_invoice,
            "pdf_ground_truth": pdf_truth
        }
    }
