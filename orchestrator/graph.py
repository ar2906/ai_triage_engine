from typing import TypedDict
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from orchestrator.sandbox import verify_patch_in_sandbox

load_dotenv()

llm = ChatAnthropic(model="claude-sonnet-4-5", temperature=0)

class PatchProposal(BaseModel):
    root_cause: str = Field(description="Concise explanation of why the error happened and which commit caused it.")
    target_file: str = Field(description="Relative path to the broken file, e.g. target_app/main.py")
    updated_code: str = Field(description="Complete, valid Python source code fixing the bug.")
    test_file: str = Field(description="Relative path for the regression test, e.g. target_app/tests/test_regression.py")
    test_code: str = Field(description="Complete pytest file using FastAPI TestClient that reproduces the failing payload and verifies the fix.")

class TriageState(TypedDict):
    trace_id: str
    service_name: str
    log_findings: str
    code_findings: str
    proposal: dict
    sandbox_passed: bool
    sandbox_output: str
    git_result: str

async def run_triage_workflow(trace_id: str, service_name: str) -> dict:
    mcp_client = MultiServerMCPClient(
        {
            "observability": {"transport": "streamable_http", "url": "http://127.0.0.1:8001/mcp"},
            "vcs": {"transport": "streamable_http", "url": "http://127.0.0.1:8002/mcp"},
        }
    )
    obs_tools = await mcp_client.get_tools(server_name="observability")
    vcs_tools = await mcp_client.get_tools(server_name="vcs")

    vcs_read_tools = [t for t in vcs_tools if t.name != "stage_fix_branch"]
    stage_tool = next(t for t in vcs_tools if t.name == "stage_fix_branch")

    async def investigate_logs(state: TriageState):
        agent = create_react_agent(llm, obs_tools)
        res = await agent.ainvoke(
            {"messages": [("user", f"Inspect trace_id '{state['trace_id']}' using your observability tools. Extract the exact exception, stack trace, and request payload.")]}
        )
        return {"log_findings": res["messages"][-1].content}

    async def investigate_code(state: TriageState):
        agent = create_react_agent(llm, vcs_read_tools)
        res = await agent.ainvoke(
            {"messages": [("user", "Check recent Git commits, inspect the latest diffs, and read target_app/main.py to identify any recent risky changes.")]}
        )
        return {"code_findings": res["messages"][-1].content}

    async def synthesize_and_verify(state: TriageState):
        structured_llm = llm.with_structured_output(PatchProposal)
        prompt = (
            f"Service: {state['service_name']}\n"
            f"Log Findings:\n{state['log_findings']}\n\n"
            f"Code Findings:\n{state['code_findings']}\n\n"
            "Produce a complete code fix and a pytest regression test using `from fastapi.testclient import TestClient` and `from target_app.main import app`."
        )
        proposal: PatchProposal = await structured_llm.ainvoke(prompt)
        passed, output = verify_patch_in_sandbox(
            proposal.target_file,
            proposal.updated_code,
            proposal.test_file,
            proposal.test_code,
        )
        return {
            "proposal": proposal.model_dump(),
            "sandbox_passed": passed,
            "sandbox_output": output,
        }

    async def stage_branch(state: TriageState):
        if not state["sandbox_passed"]:
            return {"git_result": "Skipped Git staging because sandbox tests failed."}
        p = state["proposal"]
        branch = f"fix/incident-{state['trace_id'][:8]}"
        res = await stage_tool.ainvoke(
            {
                "branch_name": branch,
                "target_file": p["target_file"],
                "updated_code": p["updated_code"],
                "test_file": p["test_file"],
                "test_code": p["test_code"],
            }
        )
        return {"git_result": str(res)}

    builder = StateGraph(TriageState)
    builder.add_node("investigate_logs", investigate_logs)
    builder.add_node("investigate_code", investigate_code)
    builder.add_node("synthesize_and_verify", synthesize_and_verify)
    builder.add_node("stage_branch", stage_branch)

    builder.add_edge(START, "investigate_logs")
    builder.add_edge("investigate_logs", "investigate_code")
    builder.add_edge("investigate_code", "synthesize_and_verify")
    builder.add_edge("synthesize_and_verify", "stage_branch")
    builder.add_edge("stage_branch", END)

    graph = builder.compile()
    return await graph.ainvoke(
        {
            "trace_id": trace_id,
            "service_name": service_name,
            "log_findings": "",
            "code_findings": "",
            "proposal": {},
            "sandbox_passed": False,
            "sandbox_output": "",
            "git_result": "",
        }
    )