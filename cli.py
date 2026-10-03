import argparse
import asyncio
import os
import sys
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from agent.loop import AgentRunner

console = Console()

def cli_ask_user(question: str) -> str:
    console.print(f"\n[bold yellow]?[/bold yellow] [bold white]AGENT QUESTION:[/bold white] {question}")
    return Prompt.ask("[bold cyan]Your Response[/bold cyan]")

def cli_request_approval(action_description: str) -> bool:
    console.print(f"\n[bold red]![/bold red] [bold white]APPROVAL REQUESTED:[/bold white] {action_description}")
    return Confirm.ask("[bold yellow]Do you approve executing this action?[/bold yellow]", default=True)

async def main_async():
    parser = argparse.ArgumentParser(description="Autonomous AI Task Worker CLI")
    parser.add_argument(
        "--task",
        type=str,
        default="Find the latest invoice from Acme Supplies in the vendor portal (http://127.0.0.1:8001), download the PDF, extract the invoice number, amount, and due date, and record it into our internal finance system at http://127.0.0.1:8002.",
        help="Natural language task prompt"
    )
    parser.add_argument("--auto-approve", action="store_true", help="Automatically approve form submission requests")
    parser.add_argument("--max-steps", type=int, default=15, help="Maximum step budget")
    parser.add_argument("--run-id", type=str, default=None, help="Custom run ID")

    args = parser.parse_args()

    console.print(Panel.fit("[bold green]Autonomous AI Task Worker[/bold green]\nCentrAlign AI Hiring Submission Prototype", border_style="green"))
    console.print(f"[bold cyan]Task Prompt:[/bold cyan] {args.task}")
    console.print(f"[bold cyan]Auto Approve:[/bold cyan] {args.auto_approve}")
    console.print(f"[bold cyan]Max Steps:[/bold cyan] {args.max_steps}\n")

    runner = AgentRunner(
        auto_approve=args.auto_approve,
        max_steps=args.max_steps,
        ask_user_fn=cli_ask_user,
        request_approval_fn=cli_request_approval,
        run_id=args.run_id
    )

    with console.status("[bold green]Agent executing task...", spinner="dots"):
        result = await runner.run(args.task)

    # Print Step Execution Summary Table
    table = Table(title=f"Run Execution Summary ({result['run_id']})")
    table.add_column("Step", justify="right", style="cyan")
    table.add_column("Tool", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Duration", justify="right", style="yellow")
    table.add_column("Message", style="white")

    for s in result["steps_trace"]:
        step_num = str(s["step"])
        tool_name = s["tool"]
        ok_str = "[bold green]OK[/bold green]" if s["result"]["ok"] else f"[bold red]FAIL ({s['result'].get('error_type')})[/bold red]"
        dur_str = f"{s['duration_sec']}s"
        msg = s["result"].get("message", "")[:80]
        table.add_row(step_num, tool_name, ok_str, dur_str, msg)

    console.print(table)

    # Print Final Status Panel
    status_color = "green" if result["status"] == "SUCCESS" else "red"
    console.print(Panel(
        f"[bold {status_color}]FINAL STATUS: {result['status']}[/bold {status_color}]\n\n"
        f"[bold white]Summary:[/bold white]\n{result['final_summary']}\n\n"
        f"[bold white]Structured Result Data:[/bold white]\n{json.dumps(result['result_data'], indent=2)}\n\n"
        f"[bold cyan]Trace Folder:[/bold cyan] {runner.run_dir}\n"
        f"[bold cyan]Total Duration:[/bold cyan] {result['total_duration_sec']}s | [bold cyan]Tokens Used:[/bold cyan] Prompt={result['total_prompt_tokens']}, Completion={result['total_completion_tokens']}",
        title="Execution Report",
        border_style=status_color
    ))

if __name__ == "__main__":
    asyncio.run(main_async())
