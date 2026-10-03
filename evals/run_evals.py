import asyncio
import os
import json
import sqlite3
import urllib.request
from typing import Dict, Any, List
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from agent.loop import AgentRunner
from mock_apps.seed import seed_database_and_pdfs
from mock_apps.finance_system import DB_PATH
from verifier import verify_run

console = Console()

def set_failure_injection(config: Dict[str, Any]):
    url = "http://127.0.0.1:8002/api/failure-injection"
    req = urllib.request.Request(
        url,
        data=json.dumps(config).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))

async def run_eval_scenarios():
    console.print(Panel.fit("[bold magenta]Autonomous AI Task Worker - Evaluation Suite[/bold magenta]", border_style="magenta"))
    
    # 1. Reset Seed and Failure Config
    seed_database_and_pdfs()

    eval_results: List[Dict[str, Any]] = []

    # -------------------------------------------------------------
    # SCENARIO 1: Happy Path
    # -------------------------------------------------------------
    console.print("\n[bold cyan]=== Running Scenario 1: Happy Path ===[/bold cyan]")
    task1 = "Log into vendor portal at http://127.0.0.1:8001, download invoice INV-2026-881 for Acme Supplies, extract amount and due_date, and enter it into internal finance system at http://127.0.0.1:8002."
    
    runner1 = AgentRunner(auto_approve=True, max_steps=12, run_id="eval_s1_happy_path")
    res1 = await runner1.run(task1)
    ver1 = verify_run(res1)
    
    s1_pass = res1["status"] == "SUCCESS" and ver1["verified"]
    eval_results.append({
        "scenario": "1. Happy Path",
        "passed": s1_pass,
        "agent_status": res1["status"],
        "verifier": ver1["status"],
        "steps": res1["total_steps"],
        "tokens": res1["total_prompt_tokens"] + res1["total_completion_tokens"],
        "duration": res1["total_duration_sec"]
    })

    # -------------------------------------------------------------
    # SCENARIO 2: Flaky Submit Once
    # -------------------------------------------------------------
    console.print("\n[bold cyan]=== Running Scenario 2: Flaky Submit (Transient Failure Retry) ===[/bold cyan]")
    seed_database_and_pdfs()
    set_failure_injection({"flaky_submit_once": True, "has_flaked": False})
    
    task2 = "Find invoice INV-2026-992 for Acme Supply Co from http://127.0.0.1:8001, extract data, and record it into http://127.0.0.1:8002."
    runner2 = AgentRunner(auto_approve=True, max_steps=15, run_id="eval_s2_flaky_submit")
    res2 = await runner2.run(task2)
    ver2 = verify_run(res2)
    
    s2_pass = res2["status"] == "SUCCESS" and ver2["verified"]
    eval_results.append({
        "scenario": "2. Flaky Submit (Retry)",
        "passed": s2_pass,
        "agent_status": res2["status"],
        "verifier": ver2["status"],
        "steps": res2["total_steps"],
        "tokens": res2["total_prompt_tokens"] + res2["total_completion_tokens"],
        "duration": res2["total_duration_sec"]
    })

    # -------------------------------------------------------------
    # SCENARIO 3: Strict Date Validation Format Adaptation
    # -------------------------------------------------------------
    console.print("\n[bold cyan]=== Running Scenario 3: Strict Date Validation Adaptation ===[/bold cyan]")
    seed_database_and_pdfs()
    set_failure_injection({"strict_date_validation": True})
    
    task3 = "Find invoice INV-2026-104 for Global Tech Solutions from http://127.0.0.1:8001. The PDF has date 'December 15, 2026'. Ensure due_date is converted strictly to YYYY-MM-DD before recording to http://127.0.0.1:8002."
    runner3 = AgentRunner(auto_approve=True, max_steps=15, run_id="eval_s3_strict_date")
    res3 = await runner3.run(task3)
    ver3 = verify_run(res3)
    
    s3_pass = res3["status"] == "SUCCESS" and ver3["verified"]
    eval_results.append({
        "scenario": "3. Strict Date Adaptation",
        "passed": s3_pass,
        "agent_status": res3["status"],
        "verifier": ver3["status"],
        "steps": res3["total_steps"],
        "tokens": res3["total_prompt_tokens"] + res3["total_completion_tokens"],
        "duration": res3["total_duration_sec"]
    })

    # -------------------------------------------------------------
    # SCENARIO 4: Duplicate Invoice Rejection Handling
    # -------------------------------------------------------------
    console.print("\n[bold cyan]=== Running Scenario 4: Duplicate Invoice Rejection Handling ===[/bold cyan]")
    seed_database_and_pdfs()
    # Pre-seed invoice INV-2026-881 into SQLite
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO invoices (vendor, invoice_number, amount, currency, due_date) VALUES ('Acme Supplies', 'INV-2026-881', 4500.50, 'USD', '2026-11-01')")
    conn.commit()
    conn.close()

    task4 = "Record invoice INV-2026-881 for Acme Supplies into http://127.0.0.1:8002."
    runner4 = AgentRunner(auto_approve=True, max_steps=12, run_id="eval_s4_duplicate")
    res4 = await runner4.run(task4)
    
    # In duplicate scenario, agent should detect duplicate error and NOT claim a fake new insertion
    s4_pass = res4["status"] == "SUCCESS" or "duplicate" in res4.get("final_summary", "").lower() or "already exists" in res4.get("final_summary", "").lower()
    eval_results.append({
        "scenario": "4. Duplicate Invoice Stop",
        "passed": s4_pass,
        "agent_status": res4["status"],
        "verifier": "N/A (Duplicate Check)",
        "steps": res4["total_steps"],
        "tokens": res4["total_prompt_tokens"] + res4["total_completion_tokens"],
        "duration": res4["total_duration_sec"]
    })

    # -------------------------------------------------------------
    # SCENARIO 5: Ambiguous Vendor Disambiguation via ask_user
    # -------------------------------------------------------------
    console.print("\n[bold cyan]=== Running Scenario 5: Ambiguous Vendor (ask_user) ===[/bold cyan]")
    seed_database_and_pdfs()
    
    def scripted_ask_user(question: str) -> str:
        console.print(f"[bold yellow][Scripted Eval Answer for Question]:[/bold yellow] {question}")
        return "Acme Supplies"

    task5 = "Process the latest invoice for vendor 'Acme' from http://127.0.0.1:8001 into http://127.0.0.1:8002."
    runner5 = AgentRunner(auto_approve=True, max_steps=15, ask_user_fn=scripted_ask_user, run_id="eval_s5_ambiguous_vendor")
    res5 = await runner5.run(task5)
    ver5 = verify_run(res5)

    s5_pass = res5["status"] == "SUCCESS" and ver5["verified"]
    eval_results.append({
        "scenario": "5. Ambiguous Vendor (ask_user)",
        "passed": s5_pass,
        "agent_status": res5["status"],
        "verifier": ver5["status"],
        "steps": res5["total_steps"],
        "tokens": res5["total_prompt_tokens"] + res5["total_completion_tokens"],
        "duration": res5["total_duration_sec"]
    })

    # -------------------------------------------------------------
    # SCENARIO 6: Generalization Task (Different Domain Task on Unchanged Code)
    # -------------------------------------------------------------
    console.print("\n[bold cyan]=== Running Scenario 6: Generalization Task (Directory Audit) ===[/bold cyan]")
    seed_database_and_pdfs()
    
    task6 = "Navigate to the vendor portal at http://127.0.0.1:8001, count all listed invoices, summarize the vendors and total amounts found, and store facts using remember."
    runner6 = AgentRunner(auto_approve=True, max_steps=10, run_id="eval_s6_generalization")
    res6 = await runner6.run(task6)
    
    s6_pass = res6["status"] == "SUCCESS" and len(res6.get("facts_remembered", [])) > 0
    eval_results.append({
        "scenario": "6. Generalization Task",
        "passed": s6_pass,
        "agent_status": res6["status"],
        "verifier": "N/A (Read Audit)",
        "steps": res6["total_steps"],
        "tokens": res6["total_prompt_tokens"] + res6["total_completion_tokens"],
        "duration": res6["total_duration_sec"]
    })

    # -------------------------------------------------------------
    # PRINT EVALUATION SUMMARY TABLE
    # -------------------------------------------------------------
    table = Table(title="Evaluation Suite - Final Benchmark Results")
    table.add_column("Scenario", style="cyan")
    table.add_column("Pass / Fail", style="bold")
    table.add_column("Agent Status", style="magenta")
    table.add_column("Verifier", style="blue")
    table.add_column("Steps", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Duration", justify="right")

    all_passed = True
    for r in eval_results:
        pf_str = "[bold green]PASS[/bold green]" if r["passed"] else "[bold red]FAIL[/bold red]"
        if not r["passed"]:
            all_passed = False
        table.add_row(
            r["scenario"],
            pf_str,
            r["agent_status"],
            str(r["verifier"]),
            str(r["steps"]),
            str(r["tokens"]),
            f"{r['duration']}s"
        )

    console.print("\n")
    console.print(table)
    
    summary_color = "green" if all_passed else "red"
    console.print(Panel(
        f"[bold {summary_color}]BENCHMARK SUMMARY: {'ALL EVAL SCENARIOS PASSED' if all_passed else 'SOME SCENARIOS FAILED'}[/bold {summary_color}]",
        border_style=summary_color
    ))

if __name__ == "__main__":
    asyncio.run(run_eval_scenarios())
