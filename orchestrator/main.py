from fastapi import FastAPI
from pydantic import BaseModel
from orchestrator.graph import run_triage_workflow

app = FastAPI(title="Autonomous SRE Triage Orchestrator")

class IncidentAlert(BaseModel):
    trace_id: str
    service_name: str = "orders-service"

@app.post("/incidents/triage")
async def triage_incident(alert: IncidentAlert):
    result = await run_triage_workflow(alert.trace_id, alert.service_name)
    return {
        "status": "staged" if result["sandbox_passed"] else "verification_failed",
        "root_cause": result["proposal"].get("root_cause"),
        "sandbox_passed": result["sandbox_passed"],
        "sandbox_output": result["sandbox_output"],
        "git_result": result["git_result"],
    }