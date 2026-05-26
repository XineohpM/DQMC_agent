#!/usr/bin/env python3
"""Audit built-in DQMC script adapter metadata."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dqmc_tools.scripts import audit_script_adapters  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit DQMC script adapter metadata.")
    parser.add_argument("--json", action="store_true", help="Print full JSON audit result.")
    parser.add_argument(
        "--no-fingerprints",
        action="store_true",
        help="Skip script SHA-256 fingerprints.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = audit_script_adapters(include_fingerprints=not args.no_fingerprints)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        summary = result["summary"]
        print(
            "Adapter audit: "
            f"{result['adapter_count']} adapters, "
            f"{summary['errors']} with errors, "
            f"{summary['warnings']} with warnings"
        )
        for adapter in result["adapters"]:
            if adapter["ok"] and adapter["warning_count"] == 0:
                continue
            print(f"- {adapter['script_id']}: {adapter['error_count']} errors, {adapter['warning_count']} warnings")
            for check in adapter["checks"]:
                if check["status"] == "ok":
                    continue
                print(f"  [{check['status']}] {check['name']}: {check['message']}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
