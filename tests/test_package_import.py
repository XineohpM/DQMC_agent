import os
import subprocess
import sys


def test_package_import_is_agent_independent():
    code = """
import sys
import dqmc_tools
assert dqmc_tools.__version__ == "0.1.0"
assert callable(dqmc_tools.require_allowed_path)
assert callable(dqmc_tools.require_output_path)
assert "mcp" not in sys.modules
assert "fastapi" not in sys.modules
"""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stderr
