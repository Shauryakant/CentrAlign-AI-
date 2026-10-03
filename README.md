# Autonomous AI Task Worker

An autonomous, framework-free AI task worker designed for enterprise business workflows. Given a natural-language task, the worker autonomously navigates web portals, parses documents, extracts key values, enforces safety approval gates, handles transient and structural failures, and verifies recorded database results out-of-band.

Built for the **CentrAlign AI Engineering Internship Take-Home Assignment**.

---

## 🏗️ Architecture Overview

```
                               ┌─────────────────────────────────────────┐
                               │           Natural Language Task         │
                               └────────────────────┬────────────────────┘
                                                    │
                                                    ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                   Hand-Written Agent ReAct Loop                                     │
 │  ┌───────────────────────────┐    ┌───────────────────────────┐    ┌─────────────────────────────┐  │
 │  │    Rolling Context        │    │    Scratchpad Memory      │    │    Error Adaptation        │  │
 │  │ (~Last 6 Raw Steps)       │    │ (Facts, Steps, Questions) │    │ (Dual-Tier Retry Guidance)  │  │
 │  └─────────────┬─────────────┘    └─────────────┬─────────────┘    └─────────────┬───────────────┘  │
 └────────────────┼────────────────────────────────┼────────────────────────────────┼──────────────────┘
                  │                                │                                │
                  ▼                                ▼                                ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                 Groq API (Llama 3.3 70B Versatile)                                  │
 └────────────────────────────────────────────────┬────────────────────────────────────────────────────┘
                                                  │ (Function Call Tool Selection)
                                                  ▼
 ┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                                      Generic Tool Executor                                          │
 │ ┌─────────────┐ ┌───────────────┐ ┌─────────────┐ ┌──────────────┐ ┌─────────────┐ ┌─────────────┐ │
 │ │browser_goto │ │browser_click  │ │browser_fill │ │extract_pdf   │ │remember     │ │ask_user     │ │
 │ ├─────────────┤ ├───────────────┤ ├─────────────┤ ├──────────────┤ ├─────────────┤ ├─────────────┤ │
 │ │browser_select││browser_download││read_file   │ │request_appr. │ │finish       │ │read_page    │ │
 │ └─────────────┘ └───────────────┘ └─────────────┘ └──────────────┘ └─────────────┘ └─────────────┘ │
 └──────────────────────┬──────────────────────────────────┬───────────────────────────────────────────┘
                        │ (DOM Numbering & Snapshots)      │ (HTTP Submit)
                        ▼                                  ▼
 ┌──────────────────────────────────────────┐    ┌─────────────────────────────────────────────────────┐
 │       Mock Vendor Portal (:8001)         │    │           Internal Finance System (:8002)           │
 │ - Login Screen & Invoices                │    │ - Strict Form (YYYY-MM-DD Date, Clean Amount)       │
 │ - PDF File Downloads                     │    │ - SQLite DB Storage & Duplicate Rejection           │
 └──────────────────────────────────────────┘    └──────────────────────────┬──────────────────────────┘
                                                                            │ (Out-of-Band API Query)
                                                                            ▼
                                                 ┌─────────────────────────────────────────────────────┐
                                                 │             Independent Verifier Engine             │
                                                 │ Compares DB Record vs Claimed Result vs PDF Truth   │
                                                 └─────────────────────────────────────────────────────┘
```

---

## ⚡ Quick Start & Running Instructions

### Prerequisites
- Python 3.11+
- Playwright Chromium browser installed (`playwright install chromium`)
- Groq API Key (get a free key at [console.groq.com](https://console.groq.com))

### 1. Installation & Environment Setup

```bash
# Clone repository
git clone https://github.com/<your-username>/ai-task-worker.git
cd ai-task-worker

# Install dependencies
pip install fastapi uvicorn python-multipart jinja2 pydantic reportlab pypdf rich playwright openai python-dotenv pytest

# Install Playwright Chromium browser
playwright install chromium

# Copy environment example and add your Groq API key
cp .env.example .env
```

Open `.env` and set your key:
```env
GROQ_API_KEY=gsk_your_actual_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
```

### 2. Start Local Mock Services & Web Control Dashboard

In Terminal 1, launch the mock application servers and Web Control Panel:

```bash
python -m mock_apps.run_servers
```

Access the interfaces in your browser:
- 🚀 **Control Dashboard**: `http://127.0.0.1:8000` (Run tasks via Web UI)
- 🏢 **Vendor Portal (Mock)**: `http://127.0.0.1:8001` (`admin` / `password123`)
- 💼 **Internal Finance System**: `http://127.0.0.1:8002`

---

## 🐳 Deployment (Docker & Cloud)

### Option A: 1-Command Local Container Deployment

```bash
docker-compose up --build
```
Open `http://localhost:8000` to interact with the Task Worker Web UI.

### Option B: Cloud Deployment (Render / Railway / Fly.io / AWS EC2)

1. Connect your GitHub repository `https://github.com/Shauryakant/CentrAlign-AI-.git` to **Render** or **Railway**.
2. Select **Docker Runtime** (uses the included `Dockerfile`).
3. Set environment variable `GROQ_API_KEY` in your Cloud Service dashboard.
4. Deploy! Render/Railway will host the Web Control Dashboard, Vendor Portal, and Finance System live.

### 3. Run Task Worker via CLI

In Terminal 2, execute the autonomous agent:

#### Happy Path Run (Interactive Approval & Disambiguation)
```bash
python cli.py --task "Find the latest invoice from Acme Supplies in the vendor portal (http://127.0.0.1:8001), download the PDF, extract the amount and due date, and record it into our internal finance system at http://127.0.0.1:8002."
```

#### Automated Evaluation Run (--auto-approve)
```bash
python cli.py --task "Find invoice INV-2026-881 for Acme Supplies from http://127.0.0.1:8001, extract data, and record it into http://127.0.0.1:8002." --auto-approve
```

### 4. Run Complete Benchmark Evaluation Suite

```bash
python evals/run_evals.py
```

---

## 🔑 Key Design Decisions

1. **Framework-Free Core Loop**: No LangChain, LangGraph, or CrewAI. Built completely by hand using standard Python and the official `openai` SDK pointing to Groq's endpoint (`https://api.groq.com/openai/v1`).
2. **DOM-Element Numbering**: Rather than feeding token-expensive raw HTML into the context window, a custom JS script is injected into Playwright. It numbers all visible interactive elements (`[1] <input id="username">`, `[2] <button id="login">`) and trims visible text to ~3000 characters.
3. **Dual-Tier Error Adaptation**:
   - *Tier 1 (Transient)*: Exponential backoff with `Retry-After` header handling on HTTP 429 rate limits.
   - *Tier 2 (Structural)*: If a tool call fails 2 consecutive times (e.g. date validation rejection), the loop injects an explicit adaptation instruction forcing the model to fix its input formatting.
4. **Code-Enforced Safety Gate**: The `browser_click` tool inspects DOM element attributes and refuses submit buttons unless `request_approval` has been called and approved by the human supervisor.
5. **Out-of-Band Independent Verifier**: After the agent claims completion, a separate verifier queries the SQLite database via a private JSON API (port 8002) and verifies recorded values against ground truth parsed directly from the source PDF document.

---

## 📽️ Demo Script (Commands for Video Recording)

1. **Show Seed & Mock Server Startup**:
   ```bash
   python -m mock_apps.seed
   python -m mock_apps.run_servers
   ```
2. **Show Happy Path Run with Interactive Prompts**:
   ```bash
   python cli.py --task "Find the latest invoice from Acme Supplies in the vendor portal (http://127.0.0.1:8001), download the PDF, extract the amount and due date, and record it into our internal finance system at http://127.0.0.1:8002."
   ```
3. **Show Full Evals Suite**:
   ```bash
   python evals/run_evals.py
   ```

---

## 📌 Known Limitations & Assumptions

- **Localhost Scope**: Mock applications run on localhost (`:8001` and `:8002`) with synthetic data.
- **Context Window**: Rolling context preserves the last 6 raw step messages plus scratchpad memory to stay within Groq free-tier rate limits.
- **Form Submissions**: Form inputs rely on standard HTML forms or basic single-page web applications.

---

## 🛠️ Models, APIs, and Libraries Used

- **LLM Endpoint**: Groq OpenAI-compatible API (`llama-3.3-70b-versatile`)
- **Browser Automation**: Playwright (Chromium)
- **Web Applications**: FastAPI, Uvicorn, Jinja2, SQLite3
- **Document Processing**: ReportLab (PDF generation), PyPDF (text extraction)
- **CLI & UI**: Rich (terminal tables, panels, status spinners)
- **Data Validation**: Pydantic v2
