import subprocess
from pathlib import Path
from fastmcp import FastMCP

mcp = FastMCP("VCS-Code-MCP")

def _run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return f"Git error: {result.stderr.strip()}"
    return result.stdout.strip()

@mcp.tool()
def get_recent_commits(limit: int = 5) -> str:
    """List recent Git commits with hash, author, timestamp, and commit message."""
    return _run_git(["log", f"-n{limit}", "--oneline", "--stat"])

@mcp.tool()
def get_commit_diff(commit_hash: str) -> str:
    """Inspect the full code diff introduced by a specific Git commit hash."""
    return _run_git(["show", commit_hash])

@mcp.tool()
def read_source_file(file_path: str) -> str:
    """Read the current contents of a source file in the repository."""
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"
    return path.read_text(encoding="utf-8")

@mcp.tool()
def stage_fix_branch(branch_name: str, target_file: str, updated_code: str, test_file: str, test_code: str) -> str:
    """Create a local fix branch, write the patched code and regression test, and commit them."""
    if not branch_name.startswith("fix/"):
        return "Guardrail violation: branch_name must start with 'fix/'."
    
    checkout_out = _run_git(["checkout", "-b", branch_name])
    Path(target_file).write_text(updated_code, encoding="utf-8")
    Path(test_file).parent.mkdir(parents=True, exist_ok=True)
    Path(test_file).write_text(test_code, encoding="utf-8")
    
    _run_git(["add", target_file, test_file])
    commit_out = _run_git(["commit", "-m", f"fix: automated triage patch on {branch_name}"])
    return f"{checkout_out}\n{commit_out}"

app = mcp.http_app()