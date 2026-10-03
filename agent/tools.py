import os
import pypdf
from typing import Dict, Any, List, Optional, Callable
from agent.browser import BrowserManager

class ToolContext:
    def __init__(self, run_dir: str, auto_approve: bool = False, ask_user_fn: Optional[Callable[[str], str]] = None, request_approval_fn: Optional[Callable[[str], bool]] = None):
        self.run_dir = run_dir
        self.downloads_dir = os.path.join(run_dir, "downloads")
        os.makedirs(self.downloads_dir, exist_ok=True)
        self.auto_approve = auto_approve
        self.approval_granted = False
        self.ask_user_fn = ask_user_fn
        self.request_approval_fn = request_approval_fn
        self.facts: List[str] = []
        self.browser = BrowserManager(headless=True)
        self.step_counter = 0

    async def close(self):
        await self.browser.close()

# OpenAI tool definitions format for Groq API
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "browser_goto",
            "description": "Navigate to a given web URL in the browser.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The target URL to visit."}
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an interactive element by its number ID from the page snapshot. Refuses form submit buttons unless request_approval has been called and approved.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer", "description": "The numbered element ID [1, 2, ...] from the page observation."}
                },
                "required": ["element_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_fill",
            "description": "Type text into an input field or textarea element by its numbered element ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer", "description": "The numbered element ID of the input field."},
                    "value": {"type": "string", "description": "The text string to enter into the field."}
                },
                "required": ["element_id", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_select",
            "description": "Select an option from a dropdown element by its numbered element ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer", "description": "The numbered element ID of the select element."},
                    "value": {"type": "string", "description": "The option value to select."}
                },
                "required": ["element_id", "value"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_read_page",
            "description": "Read the current page state, visible text, and interactive elements.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "browser_download",
            "description": "Click a link/button by its numbered element ID to download a PDF file to local disk.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_id": {"type": "integer", "description": "The numbered element ID of the download link."}
                },
                "required": ["element_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read text content from a file on the local filesystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Absolute or relative file path to read."}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "extract_pdf_text",
            "description": "Extract raw text content from a PDF document.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Local path to the downloaded PDF file."}
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store an important fact or observation into scratchpad memory so it persists across steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "fact": {"type": "string", "description": "The key fact to remember (e.g. invoice date, amount, vendor name)."}
                },
                "required": ["fact"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the human user for clarification when facing ambiguity or unstated decisions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Clear question to present to the user."}
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "request_approval",
            "description": "Request human approval before performing an impactful action (e.g., submitting an invoice to the finance database).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_description": {"type": "string", "description": "Detailed summary of the action requested for approval."}
                },
                "required": ["action_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Signal that the overall task is complete and provide final summary and extracted data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Detailed explanation of actions completed and outcomes."},
                    "result_data": {
                        "type": "object",
                        "description": "Structured metadata (e.g., vendor, invoice_number, amount, due_date)."
                    }
                },
                "required": ["summary", "result_data"]
            }
        }
    }
]

class ToolExecutor:
    def __init__(self, ctx: ToolContext):
        self.ctx = ctx

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        self.ctx.step_counter += 1
        
        try:
            if name == "browser_goto":
                res = await self.ctx.browser.goto(args["url"])
                snap = await self.ctx.browser.get_snapshot(self.ctx.run_dir, self.ctx.step_counter)
                return {
                    "ok": res["ok"],
                    "error_type": res.get("error_type"),
                    "message": res["message"],
                    "observation": snap["observation"],
                    "screenshot_path": snap["screenshot_path"]
                }

            elif name == "browser_click":
                element_id = int(args["element_id"])
                
                # Check approval gate for finance system database submissions
                if not self.ctx.approval_granted and not self.ctx.auto_approve:
                    snap_temp = await self.ctx.browser.get_snapshot()
                    if "/invoices/new" in snap_temp["url"]:
                        matched_el = next((e for e in snap_temp["elements"] if e["id"] == element_id), None)
                        if matched_el:
                            desc_str = matched_el.get("description", "").lower()
                            text_str = matched_el.get("text", "").lower()
                            is_submit = "type=\"submit\"" in desc_str or "submit" in text_str or "confirm" in text_str
                            if is_submit:
                                return {
                                    "ok": False,
                                    "error_type": "ApprovalRequired",
                                    "message": f"ACTION REFUSED BY SAFETY GATE: Click on element [{element_id}] is a finance database form submission. You must call `request_approval` tool first and receive user approval before submitting.",
                                    "observation": snap_temp["observation"]
                                }

                res = await self.ctx.browser.click(element_id, save_dir=self.ctx.downloads_dir)
                snap = await self.ctx.browser.get_snapshot(self.ctx.run_dir, self.ctx.step_counter)
                return {
                    "ok": res["ok"],
                    "error_type": res.get("error_type"),
                    "message": res["message"],
                    "observation": snap["observation"],
                    "screenshot_path": snap["screenshot_path"]
                }

            elif name == "browser_fill":
                res = await self.ctx.browser.fill(int(args["element_id"]), str(args["value"]))
                snap = await self.ctx.browser.get_snapshot(self.ctx.run_dir, self.ctx.step_counter)
                return {
                    "ok": res["ok"],
                    "error_type": res.get("error_type"),
                    "message": res["message"],
                    "observation": snap["observation"],
                    "screenshot_path": snap["screenshot_path"]
                }

            elif name == "browser_select":
                res = await self.ctx.browser.select_option(int(args["element_id"]), str(args["value"]))
                snap = await self.ctx.browser.get_snapshot(self.ctx.run_dir, self.ctx.step_counter)
                return {
                    "ok": res["ok"],
                    "error_type": res.get("error_type"),
                    "message": res["message"],
                    "observation": snap["observation"],
                    "screenshot_path": snap["screenshot_path"]
                }

            elif name == "browser_read_page":
                snap = await self.ctx.browser.get_snapshot(self.ctx.run_dir, self.ctx.step_counter)
                return {
                    "ok": True,
                    "error_type": None,
                    "message": "Current page state captured.",
                    "observation": snap["observation"],
                    "screenshot_path": snap["screenshot_path"]
                }

            elif name == "browser_download":
                res = await self.ctx.browser.download_file(int(args["element_id"]), self.ctx.downloads_dir)
                snap = await self.ctx.browser.get_snapshot(self.ctx.run_dir, self.ctx.step_counter)
                return {
                    "ok": res["ok"],
                    "error_type": res.get("error_type"),
                    "message": res["message"],
                    "observation": f"{res['message']}\n\nCurrent Page State:\n{snap['observation']}",
                    "file_path": res.get("file_path"),
                    "screenshot_path": snap["screenshot_path"]
                }

            elif name == "read_file":
                file_path = args["file_path"]
                if not os.path.exists(file_path):
                    return {"ok": False, "error_type": "FileNotFound", "message": f"File '{file_path}' does not exist.", "observation": f"Error: File '{file_path}' not found."}
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                return {"ok": True, "error_type": None, "message": f"Read {len(content)} characters from {file_path}", "observation": f"File Content ({file_path}):\n{content[:4000]}"}

            elif name == "extract_pdf_text":
                file_path = args["file_path"]
                if not os.path.exists(file_path):
                    return {"ok": False, "error_type": "FileNotFound", "message": f"PDF file '{file_path}' not found.", "observation": f"Error: PDF file '{file_path}' not found."}
                reader = pypdf.PdfReader(file_path)
                pages_text = [page.extract_text() for page in reader.pages]
                extracted = "\n".join(pages_text)
                return {
                    "ok": True,
                    "error_type": None,
                    "message": f"Extracted text from PDF {file_path} ({len(reader.pages)} pages).",
                    "observation": f"PDF Content ({os.path.basename(file_path)}):\n{extracted}"
                }

            elif name == "remember":
                fact = args["fact"]
                self.ctx.facts.append(fact)
                return {"ok": True, "error_type": None, "message": f"Remembered fact: '{fact}'", "observation": f"Fact stored in scratchpad memory: '{fact}'"}

            elif name == "ask_user":
                question = args["question"]
                if self.ctx.ask_user_fn:
                    user_answer = self.ctx.ask_user_fn(question)
                else:
                    user_answer = "User response not provided (interactive mode off)."
                return {"ok": True, "error_type": None, "message": f"Asked user question. Answer: {user_answer}", "observation": f"User answered: '{user_answer}'"}

            elif name == "request_approval":
                action_desc = args["action_description"]
                if self.ctx.auto_approve:
                    approved = True
                elif self.ctx.request_approval_fn:
                    approved = self.ctx.request_approval_fn(action_desc)
                else:
                    approved = True # default fallback if no interactive fn provided

                if approved:
                    self.ctx.approval_granted = True
                    return {"ok": True, "error_type": None, "message": "Approval granted by user.", "observation": "APPROVAL GRANTED: You are now authorized to perform the requested submit action."}
                else:
                    return {"ok": False, "error_type": "ApprovalDenied", "message": "Approval denied by user.", "observation": "APPROVAL DENIED: User rejected the proposed action. Do not submit."}

            elif name == "finish":
                return {
                    "ok": True,
                    "error_type": None,
                    "message": "Task completion signaled by agent.",
                    "observation": f"Task Finished. Summary: {args.get('summary')}",
                    "result_data": args.get("result_data", {})
                }

            else:
                return {"ok": False, "error_type": "UnknownTool", "message": f"Tool '{name}' is not recognized.", "observation": f"Error: Unknown tool '{name}'."}

        except Exception as e:
            return {"ok": False, "error_type": "ToolExecutionException", "message": f"Exception executing {name}: {str(e)}", "observation": f"Exception during tool execution: {str(e)}"}
