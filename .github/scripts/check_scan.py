"""Read the output of ``hermes plugins validate <path> --json`` and fail on a security scan verdict other than safe.

Validation passes with a caution verdict, but an unattended ``hermes plugins install`` from a community source is
blocked on it, so every user who lets Hermes run the install command would be stopped. Each validation warning is
also printed as an annotation, because catalog reviewers read them.

Usage: python .github/scripts/check_scan.py <file with the JSON output>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main(argv: list[str]) -> int:
    text = Path(argv[1]).read_text(encoding="utf-8")
    report = json.loads(text[text.index("{"):])
    for warning in report.get("warnings", []):
        print(f"::warning::hermes plugins validate: {warning}")
    failed = [f"{item['name']}: {item['detail']}" for item in report["checks"] if not item["ok"]]
    verdict = next((item["detail"] for item in report["checks"] if item["name"] == "security scan"), "missing")
    if verdict != "safe":
        failed.append(f"security scan verdict is {verdict}; an unattended install needs safe")
    for item in failed:
        print(f"::error::{item}")
    print(f"security scan verdict: {verdict}, warnings: {len(report.get('warnings', []))}, failed checks: {len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
