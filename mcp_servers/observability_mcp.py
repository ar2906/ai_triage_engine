import json
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("Observability-MCP")
TRACE_FILE = Path("logs/traces.jsonl")

def _load_spans() -> list[dict]:
    if not TRACE_FILE.exists():
        return []
    with TRACE_FILE.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]

@mcp.tool()
def get_trace_by_id(trace_id: str) -> list[dict]:
    """Retrieve all OpenTelemetry spans, attributes, and exception events for a specific trace_id."""
    spans = [s for s in _load_spans() if s.get("trace_id") == trace_id]
    if not spans:
        return [{"error": f"No spans found for trace_id={trace_id}"}]
    return spans

@mcp.tool()
def search_recent_errors(limit: int = 10) -> list[dict]:
    """Find the most recent OpenTelemetry spans marked with ERROR status or exception events."""
    errors = [
        s for s in _load_spans()
        if s.get("status") == "ERROR" or any(e.get("name") == "exception" for e in s.get("events", []))
    ]
    return errors[-limit:] if errors else [{"message": "No error spans found in logs."}]

app = mcp.http_app()