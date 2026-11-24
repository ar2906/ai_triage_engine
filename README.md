# Autonomous Production Incident & Regression Triage Engine

An autonomous Site Reliability Engineering (SRE) triage prototype that detects failing production requests via OpenTelemetry traces, correlates stack traces against recent Git commit diffs using Model Context Protocol (MCP) tool servers, verifies candidate fixes in an isolated `pytest` sandbox, and stages verified patches onto dedicated `fix/` Git branches.

---

## Architecture Overview

The system separates reasoning, telemetry access, version control operations, and patch verification across four decoupled local services:

```text
┌─────────────────────────┐       ┌──────────────────────────────────┐
│  Target Microservice    │──────▶│      logs/traces.jsonl           │
│  (FastAPI :8090)        │ OTel  │  (OpenTelemetry Span Export)     │
└─────────────────────────┘       └────────────────┬─────────────────┘
                                                   │
┌─────────────────────────┐                        ▼
│  Incident Webhook       │       ┌──────────────────────────────────┐
│  POST /incidents/triage │──────▶│  Observability MCP Server (:8001)│
│  (Orchestrator :8000)   │       │  • get_trace_by_id               │
└────────────┬────────────┘       │  • search_recent_errors          │
             │                    └──────────────────────────────────┘
             │ LangGraph StateGraph
             ▼
┌─────────────────────────┐       ┌──────────────────────────────────┐
│  Multi-Agent Pipeline   │──────▶│  VCS & Code MCP Server (:8002)   │
│  1. Log Investigator    │       │  • get_recent_commits            │
│  2. Code Archaeologist  │       │  • get_commit_diff               │
│  3. Patch Synthesizer   │       │  • read_source_file              │
│  4. Sandbox Verifier    │       │  • stage_fix_branch (guardrailed)│
│  5. Branch Stager       │       └──────────────────────────────────┘
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│  Isolated Pytest Sandbox│
│  (orchestrator/sandbox) │
└─────────────────────────┘
```

### Core Components

* **Target Microservice (`target_app/main.py` — Port `8090`):** A FastAPI Orders service instrumented with OpenTelemetry (`FastAPIInstrumentor` + custom `JsonlFileSpanExporter`) that records request spans, attributes, and exceptions to `logs/traces.jsonl`.
* **Observability MCP Server (`mcp_servers/observability_mcp.py` — Port `8001`):** A Streamable HTTP `FastMCP` server exposing read-only telemetry lookup tools (`get_trace_by_id`, `search_recent_errors`).
* **VCS & Code MCP Server (`mcp_servers/vcs_mcp.py` — Port `8002`):** A Streamable HTTP `FastMCP` server exposing Git history inspection (`get_recent_commits`, `get_commit_diff`, `read_source_file`) and a guardrailed `stage_fix_branch` tool that enforces `fix/` branch naming prefixes.
* **Isolated Sandbox Verifier (`orchestrator/sandbox.py`):** Copies the candidate code patch and generated regression test into an ephemeral temporary directory and executes `pytest` before allowing any Git commits.
* **LangGraph Orchestrator (`orchestrator/graph.py` & `orchestrator/main.py` — Port `8000`):** Coordinates the stateful triage graph (`TriageState`), connecting Claude (`claude-sonnet-4-5`) to both MCP servers via the official `mcp` Python SDK.

---

## Project Structure

```text
sre-triage-engine/
├── target_app/
│   └── main.py                 # FastAPI Orders microservice with OpenTelemetry tracing
├── mcp_servers/
│   ├── observability_mcp.py    # FastMCP server for trace & error log queries (:8001)
│   └── vcs_mcp.py              # FastMCP server for Git inspection & branch staging (:8002)
├── orchestrator/
│   ├── graph.py                # LangGraph StateGraph & MCP client tool bindings
│   ├── main.py                 # FastAPI incident webhook receiver (:8000)
│   └── sandbox.py              # Isolated temporary workspace pytest runner
├── logs/                       # Runtime OpenTelemetry JSONL trace output (gitignored)
├── .env                        # Environment variables (ANTHROPIC_API_KEY, gitignored)
├── pyproject.toml              # Project dependencies managed with uv
└── README.md
```

---

## Prerequisites & Setup

1. **Python 3.12+** and **[uv](https://docs.astral.sh/uv/)** installed.
2. **Anthropic API Key** configured in a `.env` file at the project root:
   ```env
   ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```
3. **Install dependencies:**
   ```bash
   uv sync
   ```

---

## Running the Services

Start each service in its own terminal tab from the repository root:

1. **Target Orders Microservice (Port `8090`):**
   ```bash
   uv run uvicorn target_app.main:app --port 8090
   ```
2. **Observability MCP Server (Port `8001`):**
   ```bash
   uv run uvicorn mcp_servers.observability_mcp:app --port 8001
   ```
3. **VCS & Code MCP Server (Port `8002`):**
   ```bash
   uv run uvicorn mcp_servers.vcs_mcp:app --port 8002
   ```
4. **SRE Triage Orchestrator (Port `8000`):**
   ```bash
   uv run uvicorn orchestrator.main:app --port 8000
   ```

---

## End-to-End Triage Demo

1. **Trigger a production failure** (e.g., submitting an order without a `coupon` object when null-safety checks are missing):
   ```powershell
   try {
       Invoke-RestMethod -Uri "http://127.0.0.1:8090/orders" -Method Post -ContentType "application/json" -Body '{"order_id": "ORD-999", "amount": 50.0}'
   } catch {
       Write-Host "Triggered 500 error as expected!"
   }
   ```
2. **Extract the failing `trace_id` and dispatch it to the orchestrator:**
   ```powershell
   $failingTrace = (Get-Content logs/traces.jsonl | ConvertFrom-Json | Where-Object { $_.status -eq "ERROR" } | Select-Object -Last 1).trace_id

   Invoke-RestMethod -Uri "http://127.0.0.1:8000/incidents/triage" -Method Post -ContentType "application/json" -Body "{`"trace_id`": `"$failingTrace`", `"service_name`": `"orders-service`"}"
   ```
3. **Inspect the staged patch branch:**
   ```bash
   git branch
   git show --stat
   git diff HEAD~1
   ```

---

## Safety Guardrails

* **Read-Only Telemetry & Code Analysis:** Investigation agents only have access to read-only MCP tools during diagnosis.
* **Mandatory Sandbox Gate:** `stage_branch` is skipped unless `pytest` exits with status `0` inside the isolated sandbox directory.
* **Branch Prefix Enforcement:** `stage_fix_branch` rejects any branch name that does not start with `fix/`, preventing direct commits to `main`.
