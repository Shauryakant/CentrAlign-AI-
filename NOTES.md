# Developer Implementation Notes & Honest Log

This living document details the architectural decisions, autonomous capabilities, manual configurations, real testing limitations, and experiment logs of the **Autonomous AI Task Worker**.

---

## 1. Brief Architecture

The system consists of three main decoupled layers:

1. **Mock Enterprise Environment**:
   - **Vendor Portal (:8001)**: FastAPI app providing authentication, vendor directories (including ambiguous names "Acme Supplies" vs "Acme Supply Co"), and invoice PDF downloads.
   - **Internal Finance System (:8002)**: FastAPI app with SQLite backend enforcing strict form validation (numeric amounts, `YYYY-MM-DD` dates, duplicate rejection) and a private JSON API for out-of-band verification.
   - **Failure Injection Engine**: Middleware enabling simulated server flakiness, strict validation toggles, duplicate entries, and page latency.

2. **Hand-Written Agent Runtime (`agent/`)**:
   - **ReAct Execution Loop (`agent/loop.py`)**: Custom ReAct loop using `openai.AsyncOpenAI` pointing to Groq's `llama-3.3-70b-versatile`.
   - **Scratchpad Memory**: Re-injects `facts_found`, `steps_done`, `failed_attempts`, and `open_questions` at every step while trimming raw turn context to ~last 6 steps.
   - **Generic Toolset (`agent/tools.py`)**: 12 domain-agnostic tools (`browser_goto`, `browser_click`, `browser_fill`, `browser_select`, `browser_read_page`, `browser_download`, `read_file`, `extract_pdf_text`, `remember`, `ask_user`, `request_approval`, `finish`).
   - **Browser Manager (`agent/browser.py`)**: Playwright Chromium wrapper with DOM element numbering via JS injection and screenshot capturing.

3. **Independent Out-of-Band Verifier (`verifier.py`)**:
   - Executes after task completion.
   - Queries port `:8002` JSON API to retrieve DB state and cross-references values against both the agent's claimed `result_data` and ground-truth text extracted directly from source PDFs.

---

## 2. What is Genuinely Autonomous

- **Goal Decomposition & Navigation**: Given a prompt like "Find the latest invoice for Acme Supplies...", the agent independently decides to log in, search vendors, identify the matching row, click the download button, parse the PDF text, open the finance portal, fill each form input, and finish.
- **Ambiguity Detection**: When instructed to process an invoice for "Acme", the agent inspects the page, identifies two candidate vendors ("Acme Supplies" and "Acme Supply Co"), recognizes the unstated ambiguity, and calls `ask_user` for human clarification.
- **Error Recovery & Adaptation**:
  - If a form submit returns a 500 transient database error (simulated via `flaky_submit_once`), the agent observes the failure and retries submission.
  - If the finance system rejects a date format like "December 15, 2026", the error counter triggers an adaptation prompt forcing the agent to convert the date into strict `YYYY-MM-DD` format ("2026-12-15").
- **Domain Generalization**: The agent executes non-invoice tasks (e.g. Directory Audit & Vendor Summarization) on the exact same codebase without modifying tool schemas or agent code.

---

## 3. What is Hard-Coded or Manually Configured

- **Target Service URLs**: The default host URLs (`http://127.0.0.1:8001` and `http://127.0.0.1:8002`) are passed in prompt tasks or configuration.
- **DOM Numbering Script**: The JavaScript selector list (`a, button, input, select, textarea, [role="button"], [onclick]`) is predefined in `agent/browser.py` to filter interactive elements.
- **Form Field Mapping Rules**: The LLM infers which element index corresponds to which input field based on the element description attributes (`name="vendor"`, `id="due_date_input"`).

---

## 4. Models, Frameworks, APIs, Libraries & Tools Used

- **LLM Endpoint**: Groq OpenAI-compatible REST API (`https://api.groq.com/openai/v1`)
- **LLM Model**: `llama-3.3-70b-versatile` (specified via `GROQ_MODEL`)
- **SDK**: `openai` Python SDK (version 3.24.0)
- **Browser Automation**: `playwright` (version 1.63.0, Chromium headless)
- **Web Application Stack**: `fastapi` (0.142.2), `uvicorn`, `jinja2`, `python-multipart`, `sqlite3`
- **PDF Generation & Extraction**: `reportlab` (5.0.1), `pypdf` (6.19.0)
- **CLI & Formatting**: `rich` (15.0.0)
- **Data Validation & Typing**: `pydantic` (2.13.5)
- **AI Coding Assistant**: Google Antigravity AI Agent

---

## 5. Biggest Technical Limitation (From Real Testing)

- **Groq Free-Tier Rate Limits (TPM / RPM)**: Groq's free tier imposes strict Requests Per Minute (RPM) and Tokens Per Minute (TPM) limits on `llama-3.3-70b-versatile`. Sending full raw page HTML quickly exceeds token quotas and causes HTTP 429 rate limit errors.
- **Mitigation Implemented**:
  1. DOM element numbering in JS trims body text to ~3000 chars and replaces HTML trees with compact element lists (`[1] <input name="vendor">`).
  2. Rolling context window keeps only the system prompt + initial task + last 6 step messages.
  3. Exponential backoff with `Retry-After` header parsing handles rate limit responses automatically.

---

## 6. What I'd Build in 2 More Weeks

1. **Visual Computer Use Fallback**: Integrate multimodal vision models (e.g. Gemini 2.5 Flash / Claude 3.5 Sonnet Vision) to fall back on coordinate-based clicks when DOM element numbering misses canvas elements or complex custom web components.
2. **Persistent Enterprise Memory (RAG Vector Store)**: Build an embedded ChromaDB/FAISS vector index to store long-term company policies, vendor aliases, standard operating procedures (SOPs), and historical task runs.
3. **Multi-Tab & Multi-Browser Session Orchestration**: Support concurrent multi-tab browser sessions so the agent can cross-reference multiple web apps simultaneously without losing page state.
4. **Interactive Web Dashboard**: Upgrade the Rich CLI into a full FastAPI + React real-time web dashboard with live streaming DOM screenshots, step-by-step trace playback, and human approval modals.

---

## 7. Experiments and Failures Log

| Experiment / Hypothesis | What Happened | What I Changed |
|---|---|---|
| **Sending raw HTML to LLM** | Caused Groq TPM rate limits (HTTP 429) within 2 steps due to 50k+ token pages. | Implemented client-side JS DOM element numbering; extracts only visible interactive elements and trims text to 3,000 chars. |
| **Full conversation context accumulation** | After 8 steps, total prompt tokens reached 15,000+, slowing down responses and risking context limits. | Implemented rolling context window (`raw_steps_history[-6:]`) combined with persistent scratchpad memory re-injection. |
| **Unrestricted agent submit actions** | Agent occasionally submitted forms with incomplete or unvalidated data. | Implemented code-enforced Safety Approval Gate (`request_approval` tool required before clicking submit elements). |
| **Relying solely on LLM self-reporting** | Agent claimed success even when form submission failed server-side validation. | Built independent out-of-band verifier (`verifier.py`) querying the SQLite API directly to cross-check records against source PDF ground truth. |

---

## 8. AI Tools Disclosure Log

- **AI Tools Used**: Google Antigravity AI Agent with Gemini 3.6 Flash model.
- **Usage Scope**: Used for initial scaffold generation, writing modular code, drafting test scenarios, creating documentation, and verifying git commit conventions.
- **Human Guidance & Auditing**: Architecture design, safety gate logic, out-of-band verifier design, error classification rules, and test verification were fully reviewed and directed.
