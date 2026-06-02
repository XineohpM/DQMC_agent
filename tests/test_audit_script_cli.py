import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_audit_script_adapters_json_reports_argparse_sync():
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/audit_script_adapters.py",
            "--json",
            "--no-fingerprints",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["argparse_sync"]["parsed"] >= 1
    assert payload["adapter_count"] == 21
    run_maxent = next(item for item in payload["argparse_parsers"] if item["script_id"] == "run_maxent_anneal")
    assert run_maxent["status"] == "parsed"
    assert "schema_diff" in run_maxent
    assert "base" in run_maxent["schema_diff"]["added"]
