import asyncio
import json
import os
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from agent.loop import AgentRunner
from verifier import verify_run

app = FastAPI(title="Autonomous AI Task Worker - Control Dashboard")

# Mount runs directory to serve step screenshots
os.makedirs("runs", exist_ok=True)
app.mount("/runs", StaticFiles(directory="runs"), name="runs")

@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>AI Task Worker - Web Control Panel</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 30px; background: #f8f9fa; color: #333; }
            .container { max-width: 900px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
            h1 { color: #1a73e8; margin-top: 0; }
            .badge { background: #e8f0fe; color: #1a73e8; padding: 4px 10px; border-radius: 12px; font-size: 0.85em; font-weight: 600; }
            textarea { width: 100%; height: 100px; padding: 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; box-sizing: border-box; font-family: inherit; }
            .btn { background: #1a73e8; color: white; border: none; padding: 12px 24px; font-size: 15px; font-weight: 600; border-radius: 6px; cursor: pointer; }
            .btn:hover { background: #1557b0; }
            .checkbox-group { margin: 15px 0; }
            .links { margin-top: 20px; font-size: 14px; color: #666; }
            .links a { color: #1a73e8; text-decoration: none; font-weight: 500; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Autonomous AI Task Worker <span class="badge">CentrAlign Prototype</span></h1>
            <p>Enter a natural language enterprise request below to trigger the autonomous browser agent.</p>
            
            <form action="/run" method="post">
                <p><label><strong>Task Instructions:</strong></label></p>
                <textarea name="task_prompt" required>Find the latest invoice from Acme Supplies in the vendor portal (http://127.0.0.1:8001), download the PDF, extract the amount and due date, and record it into our internal finance system at http://127.0.0.1:8002.</textarea>
                
                <div class="checkbox-group">
                    <label><input type="checkbox" name="auto_approve" checked value="true"> Auto-approve form submission requests</label>
                </div>
                
                <p><button type="submit" class="btn">🚀 Execute Task Worker</button></p>
            </form>

            <div class="links">
                <strong>Local Environment Portals:</strong>
                <ul>
                    <li><a href="http://127.0.0.1:8001" target="_blank">Vendor Portal (:8001)</a> - User: <code>admin</code> / Pass: <code>password123</code></li>
                    <li><a href="http://127.0.0.1:8002" target="_blank">Internal Finance System (:8002)</a></li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    """

@app.post("/run", response_class=HTMLResponse)
async def run_task(task_prompt: str = Form(...), auto_approve: str = Form("false")):
    is_auto = auto_approve == "true"
    
    runner = AgentRunner(auto_approve=is_auto, max_steps=15)
    result = await runner.run(task_prompt)
    ver_result = verify_run(result)

    final_status = result["status"]
    if result["status"] == "SUCCESS" and not ver_result["verified"]:
        final_status = "FAILED_VERIFICATION"

    status_color = "#2e7d32" if final_status in ("SUCCESS", "VERIFIED_PASS") and ver_result["verified"] else "#d32f2f"
    ver_badge = '<span style="background: #e8f5e9; color: #2e7d32; padding: 4px 8px; border-radius: 4px;">PASS</span>' if ver_result["verified"] else f'<span style="background: #ffebee; color: #d32f2f; padding: 4px 8px; border-radius: 4px;">{ver_result["status"]}</span>'

    step_rows = ""
    for s in result["steps_trace"]:
        screenshot_html = ""
        screenshot_path = s["result"].get("screenshot_path", "")
        if screenshot_path and os.path.exists(screenshot_path):
            rel_path = os.path.relpath(screenshot_path, start=".")
            rel_path = rel_path.replace("\\", "/")
            screenshot_html = f'<br><a href="/{rel_path}" target="_blank"><img src="/{rel_path}" style="max-width: 300px; border: 1px solid #ddd; margin-top: 5px; border-radius: 4px;"></a>'

        step_rows += f"""
        <tr>
            <td><strong>Step {s['step']}</strong></td>
            <td><code>{s['tool']}</code></td>
            <td>{'OK' if s['result']['ok'] else 'FAIL (' + str(s['result'].get('error_type')) + ')'}</td>
            <td>{s['duration_sec']}s</td>
            <td>{s['result'].get('message', '')} {screenshot_html}</td>
        </tr>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Execution Report - AI Task Worker</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 30px; background: #f8f9fa; color: #333; }}
            .container {{ max-width: 1000px; margin: auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
            h1 {{ color: #1a73e8; margin-top: 0; }}
            .status-banner {{ padding: 15px; border-radius: 6px; background: {status_color}; color: white; font-weight: bold; margin-bottom: 20px; font-size: 18px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            th, td {{ border: 1px solid #e0e0e0; padding: 10px; text-align: left; font-size: 14px; }}
            th {{ background: #f5f5f5; }}
            pre {{ background: #f5f5f5; padding: 10px; border-radius: 4px; overflow-x: auto; }}
            .btn {{ background: #1a73e8; color: white; border: none; padding: 8px 16px; font-size: 14px; border-radius: 4px; cursor: pointer; text-decoration: none; display: inline-block; }}
        </style>
    </head>
    <body>
        <div class="container">
            <p><a href="/" class="btn">← Back to Dashboard</a></p>
            
            <div class="status-banner">
                Final Agent Status: {final_status} | Verifier Status: {ver_result['status']}
            </div>

            <h2>Task Execution Summary</h2>
            <p><strong>Run ID:</strong> <code>{result['run_id']}</code> | <strong>Duration:</strong> {result['total_duration_sec']}s | <strong>Tokens:</strong> Prompt={result['total_prompt_tokens']}, Completion={result['total_completion_tokens']}</p>
            
            <h3>Independent Verification Audit</h3>
            <p><strong>Verification Result:</strong> {ver_badge}</p>
            <p><strong>Database Record via API:</strong></p>
            <pre>{json.dumps(ver_result.get('evidence', {}).get('database_record'), indent=2)}</pre>
            
            <h3>Step-by-Step Execution Timeline</h3>
            <table>
                <thead>
                    <tr>
                        <th>Step</th>
                        <th>Tool</th>
                        <th>Status</th>
                        <th>Duration</th>
                        <th>Details & Screenshots</th>
                    </tr>
                </thead>
                <tbody>
                    {step_rows}
                </tbody>
            </table>

            <h3>Structured Output</h3>
            <pre>{json.dumps(result['result_data'], indent=2)}</pre>
        </div>
    </body>
    </html>
    """
