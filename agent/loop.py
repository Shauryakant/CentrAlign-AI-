import os
import json
import time
import uuid
import datetime
from typing import Dict, Any, List, Optional
from agent.llm import LLMClient
from agent.tools import ToolContext, ToolExecutor, TOOL_SCHEMAS

SYSTEM_PROMPT_TEMPLATE = """You are an Autonomous AI Task Worker. Your job is to complete natural-language enterprise tasks autonomously by operating browser applications, reading documents, and submitting forms.

GUIDELINES & RULES:
1. Break down the user request into logical steps and execute them using available tools.
2. Observe page snapshots carefully. Interactive elements are numbered as `[N] <tag ...>`.
3. If logging into vendor portal (http://127.0.0.1:8001), use username `admin` and password `password123`.
4. After downloading/extracting PDF text, store key facts (`vendor`, `invoice_number`, `amount`, `due_date`) using `remember(fact="...")`.
5. On the Finance System form (http://127.0.0.1:8002/invoices/new), fill ALL 5 fields (`vendor`, `invoice_number`, `amount`, `currency`, `due_date`), call `request_approval(action_description="Submit invoice INV-xxx")`, click the submit button, and call `finish(summary="...", result_data={{...}})` with structured output.
6. Verify date format is strictly YYYY-MM-DD and amount is clean numeric (e.g. 4500.50). If facing vendor name ambiguity, call `ask_user`.

CURRENT MEMORY SCRATCHPAD:
- Facts Discovered: {facts}
- Steps Completed: {steps_done}
- Failed Attempts / Errors Encountered: {failed_attempts}
- Open Questions / Ambiguities: {open_questions}

ADAPTATION GUIDANCE:
{adaptation_guidance}
"""

class AgentRunner:
    def __init__(
        self,
        auto_approve: bool = False,
        max_steps: int = 20,
        ask_user_fn: Optional[Any] = None,
        request_approval_fn: Optional[Any] = None,
        run_id: Optional[str] = None
    ):
        self.run_id = run_id or f"run_{datetime.datetime.now().strftime('%Y%m%m_%H%M%S')}_{str(uuid.uuid4())[:6]}"
        self.run_dir = os.path.abspath(os.path.join("runs", self.run_id))
        os.makedirs(self.run_dir, exist_ok=True)
        
        self.auto_approve = auto_approve
        self.max_steps = max_steps
        self.ctx = ToolContext(
            run_dir=self.run_dir,
            auto_approve=auto_approve,
            ask_user_fn=ask_user_fn,
            request_approval_fn=request_approval_fn
        )
        self.executor = ToolExecutor(self.ctx)
        self.llm = LLMClient()
        
        # Memory & Trace state
        self.steps_done: List[str] = []
        self.failed_attempts: List[str] = []
        self.open_questions: List[str] = []
        self.trace_steps: List[Dict[str, Any]] = []
        self.consecutive_error_counts: Dict[str, int] = {}
        self.action_history: List[str] = []

    async def run(self, task_prompt: str) -> Dict[str, Any]:
        print(f"[AgentRunner] Starting run {self.run_id} for task: '{task_prompt}'")
        start_time = time.time()
        
        # Initial conversation state
        raw_steps_history: List[Dict[str, Any]] = []
        status = "IN_PROGRESS"
        final_summary = ""
        final_result_data = {}
        
        adaptation_guidance = "Proceed with initial plan."

        for step in range(1, self.max_steps + 1):
            # Check step budget
            if step > self.max_steps:
                status = "BUDGET_EXCEEDED"
                final_summary = f"Exceeded maximum step budget of {self.max_steps} steps."
                break

            # Build System Prompt with current scratchpad memory
            system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                facts=json.dumps(self.ctx.facts) if self.ctx.facts else "None yet",
                steps_done=json.dumps(self.steps_done) if self.steps_done else "None yet",
                failed_attempts=json.dumps(self.failed_attempts) if self.failed_attempts else "None yet",
                open_questions=json.dumps(self.open_questions) if self.open_questions else "None yet",
                adaptation_guidance=adaptation_guidance
            )

            # Rolling context window: Keep System Prompt + Initial Task + last 6 step messages
            messages = [{"role": "system", "content": system_prompt}]
            messages.append({"role": "user", "content": task_prompt})
            
            # Slice last ~6 raw messages to keep token context compact
            recent_raw = raw_steps_history[-6:]
            messages.extend(recent_raw)

            step_start = time.time()
            try:
                # Call LLM
                response_msg = await self.llm.chat_completion(messages=messages, tools=TOOL_SCHEMAS)
            except Exception as e:
                status = "LLM_ERROR"
                final_summary = f"LLM Call failed: {str(e)}"
                break

            # Process LLM response
            tool_calls = getattr(response_msg, "tool_calls", None)
            content_text = getattr(response_msg, "content", None) or ""

            if not tool_calls:
                # If LLM didn't return a tool call, append its message and request tool selection
                raw_steps_history.append({"role": "assistant", "content": content_text})
                raw_steps_history.append({
                    "role": "user",
                    "content": "Please invoke a tool to perform the next action (or call `finish` if completed)."
                })
                continue

            # Handle the first tool call
            tool_call = tool_calls[0]
            func_name = tool_call.function.name
            try:
                func_args = json.loads(tool_call.function.arguments)
            except Exception:
                func_args = {}
                self.failed_attempts.append(f"Step {step}: Malformed tool arguments for {func_name}")

            # Loop detection: detect identical consecutive actions
            action_signature = f"{func_name}:{json.dumps(func_args, sort_keys=True)}"
            self.action_history.append(action_signature)
            if len(self.action_history) >= 3 and self.action_history[-1] == self.action_history[-2] == self.action_history[-3]:
                adaptation_guidance = (
                    f"WARNING: Loop detected! You have executed '{func_name}' with identical arguments {func_args} 3 times in a row. "
                    "Stop repeating this action and try a completely different approach!"
                )
                self.failed_attempts.append(f"Step {step}: Repeated action loop detected for {func_name}")

            # Append assistant's tool call message to rolling history
            raw_steps_history.append({
                "role": "assistant",
                "content": content_text,
                "tool_calls": [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": func_name,
                            "arguments": tool_call.function.arguments
                        }
                    }
                ]
            })

            # Execute tool
            exec_res = await self.executor.execute_tool(func_name, func_args)
            duration = round(time.time() - step_start, 2)

            # Record trace
            trace_entry = {
                "step": step,
                "timestamp": datetime.datetime.now().isoformat(),
                "tool": func_name,
                "arguments": func_args,
                "result": exec_res,
                "duration_sec": duration,
                "prompt_tokens": self.llm.total_prompt_tokens,
                "completion_tokens": self.llm.total_completion_tokens
            }
            self.trace_steps.append(trace_entry)

            # Append tool response message to rolling history
            raw_steps_history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": func_name,
                "content": exec_res["observation"]
            })

            # Evaluate execution outcome
            if exec_res["ok"]:
                self.steps_done.append(f"Step {step}: {func_name} - {exec_res['message']}")
                # Reset error counter for this tool
                self.consecutive_error_counts[func_name] = 0
                
                if func_name == "finish":
                    status = "SUCCESS"
                    final_summary = exec_res.get("observation", "")
                    final_result_data = exec_res.get("result_data", {})
                    break
            else:
                err_type = exec_res.get("error_type", "GeneralError")
                self.failed_attempts.append(f"Step {step}: {func_name} failed ({err_type}) - {exec_res['message']}")
                
                curr_count = self.consecutive_error_counts.get(func_name, 0) + 1
                self.consecutive_error_counts[func_name] = curr_count

                if curr_count >= 2:
                    adaptation_guidance = (
                        f"CRITICAL RELIABILITY ADAPTATION: Tool '{func_name}' has failed {curr_count} times in a row with error '{err_type}'. "
                        f"Previous error details: {exec_res['message']}. DO NOT repeat this exact tool call! "
                        "Re-read the page snapshot, fix input formats (e.g. check date YYYY-MM-DD), or try an alternative tool/workflow."
                    )

        total_duration = round(time.time() - start_time, 2)
        await self.ctx.close()

        # Save trace.json and summary.md
        result_payload = {
            "run_id": self.run_id,
            "status": status,
            "task_prompt": task_prompt,
            "final_summary": final_summary,
            "result_data": final_result_data,
            "total_steps": len(self.trace_steps),
            "total_duration_sec": total_duration,
            "total_prompt_tokens": self.llm.total_prompt_tokens,
            "total_completion_tokens": self.llm.total_completion_tokens,
            "facts_remembered": self.ctx.facts,
            "steps_trace": self.trace_steps
        }

        trace_file = os.path.join(self.run_dir, "trace.json")
        with open(trace_file, "w", encoding="utf-8") as f:
            json.dump(result_payload, f, indent=2)

        summary_md_file = os.path.join(self.run_dir, "summary.md")
        with open(summary_md_file, "w", encoding="utf-8") as f:
            f.write(f"# Run Summary: {self.run_id}\n\n")
            f.write(f"- **Status**: `{status}`\n")
            f.write(f"- **Task**: {task_prompt}\n")
            f.write(f"- **Total Duration**: {total_duration}s\n")
            f.write(f"- **Total Steps**: {len(self.trace_steps)}\n")
            f.write(f"- **Tokens**: Prompt={self.llm.total_prompt_tokens}, Completion={self.llm.total_completion_tokens}\n\n")
            f.write(f"## Final Summary\n{final_summary}\n\n")
            f.write(f"## Result Data\n```json\n{json.dumps(final_result_data, indent=2)}\n```\n")

        print(f"[AgentRunner] Run {self.run_id} completed with status {status} in {total_duration}s")
        return result_payload
