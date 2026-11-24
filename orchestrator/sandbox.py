import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

def verify_patch_in_sandbox(target_file: str, updated_code: str, test_file: str, test_code: str) -> tuple[bool, str]:
    """Run pytest against the proposed patch in an isolated temporary copy of the project."""
    with tempfile.TemporaryDirectory(prefix="sre_sandbox_") as tmp_dir:
        sandbox_root = Path(tmp_dir)

        shutil.copytree("target_app", sandbox_root / "target_app")
        (sandbox_root / "logs").mkdir(exist_ok=True)

        patched_target = sandbox_root / target_file
        patched_target.write_text(updated_code, encoding="utf-8")

        sandbox_test = sandbox_root / test_file
        sandbox_test.parent.mkdir(parents=True, exist_ok=True)
        sandbox_test.write_text(test_code, encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-v", str(sandbox_test)],
            cwd=sandbox_root,
            capture_output=True,
            text=True,
            timeout=30,
        )
        passed = result.returncode == 0
        output = f"{result.stdout}\n{result.stderr}".strip()
        return passed, output