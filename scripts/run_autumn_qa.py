"""Reproduce pytest evidence and offline benchmarks without model API calls.

Run: python -m scripts.run_autumn_qa
Use --skip-tests only after generating final-tests.xml and coverage.json.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from everstory.eval.agent_models import (
    CaseResult, ExchangeResult, RoleModelResult, build_report, rescore_role_results,
)
from everstory.eval.runner import run_eval, run_long_eval, to_markdown, to_long_markdown
from everstory.eval.team import TeamEvalResult, run_team_eval, to_team_markdown
from everstory.llm.client import LLMClient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "autumn-qa"


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def junit_counts(path):
    root = ElementTree.parse(path).getroot()
    cases = root.findall(".//testcase")
    failed = sum(c.find("failure") is not None or c.find("error") is not None for c in cases)
    skipped = sum(c.find("skipped") is not None for c in cases)
    return {"total": len(cases), "passed": len(cases) - failed - skipped, "failed": failed, "skipped": skipped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    os.environ["LLM_MODE"] = "stub"
    if not args.skip_tests:
        command = [
            sys.executable, "-m", "pytest", "tests", "-q", "--tb=short",
            "--junitxml=reports/autumn-qa/final-tests.xml", "--cov=everstory", "--cov-branch",
            "--cov-report=html:reports/autumn-qa/coverage",
            "--cov-report=json:reports/autumn-qa/coverage.json",
        ]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
        (OUT / "final-tests.log").write_text(result.stdout + result.stderr, encoding="utf-8")
        print(result.stdout[-3000:])
        if result.returncode:
            return result.returncode

    print("Running deterministic architecture/long-horizon/team benchmarks...")
    architecture_client = LLMClient(mode="stub")
    architecture = run_eval(architecture_client, provider="offline-stub")
    long_client = LLMClient(mode="stub")
    long_results = run_long_eval(long_client, horizon=60, provider="offline-stub")
    teams = []
    for repeat in range(1, 4):
        client = LLMClient(mode="stub")
        teams.append(run_team_eval(client, provider=f"offline-stub-repeat-{repeat}"))
    assert not architecture_client.call_history and not long_client.call_history
    assert all(row.calls == 0 for row in teams)
    offline = {
        "mode": "stub", "real_model_calls": 0, "real_model_tokens": 0,
        "architecture": [asdict(row) for row in architecture],
        "long_horizon": long_results,
        "team_repeats": [row.to_dict() for row in teams],
    }
    write_json(OUT / "offline-evaluation.json", offline)
    offline_md = to_markdown(architecture, "stub") + "\n" + to_long_markdown(long_results)
    offline_md += "\n" + "\n\n".join(to_team_markdown(row) for row in teams)
    (OUT / "offline-evaluation.md").write_text(offline_md, encoding="utf-8")

    print("Rescoring archived outputs; no real provider requests...")
    archived = json.loads((ROOT / "reports/agent-routing-evaluation.json").read_text(encoding="utf-8"))
    roles = [RoleModelResult(
        **{k: v for k, v in row.items() if k != "case_results"},
        case_results=[CaseResult(**case) for case in row["case_results"]],
    ) for row in archived["role_results"]]
    stored_scores = {(r.role, r.connection_id, c.case_id): c.overall_score for r in roles for c in r.case_results}
    rescore_role_results(roles)
    mismatches = [
        {"role": r.role, "connection_id": r.connection_id, "case": c.case_id,
         "stored": stored_scores[(r.role, r.connection_id, c.case_id)], "rescored": c.overall_score}
        for r in roles for c in r.case_results
        if abs(stored_scores[(r.role, r.connection_id, c.case_id)] - c.overall_score) > 1e-9
    ]
    exchanges = [ExchangeResult(**row) for row in archived["exchange_results"]]
    historic_teams = [TeamEvalResult(**row) for row in archived["team_results"]]
    history_md, rescored = build_report(roles, exchanges, historic_teams)
    audit = {
        "source_generated_at": archived["generated_at"],
        "new_model_calls": 0, "candidate_combinations": len(roles),
        "unique_cases": len({c.case_id for r in roles for c in r.case_results}),
        "scored_cases": sum(len(r.case_results) for r in roles),
        "role_failures": sum(bool(c.error) for r in roles for c in r.case_results),
        "rescored_case_mismatches": mismatches,
        "stored_summary": archived["summary"], "recomputed_summary": rescored["summary"],
        "exchange_chains": len(exchanges), "full_cases": len(historic_teams),
    }
    write_json(OUT / "historical-score-audit.json", audit)
    (OUT / "historical-rescored.md").write_text(
        "> Historical raw outputs rescored offline. No provider calls were rerun.\n\n" + history_md,
        encoding="utf-8",
    )

    final_counts = junit_counts(OUT / "final-tests.xml")
    baseline = junit_counts(OUT / "baseline.xml") if (OUT / "baseline.xml").exists() else None
    before_fix = junit_counts(OUT / "before-fix.xml") if (OUT / "before-fix.xml").exists() else None
    coverage = json.loads((OUT / "coverage.json").read_text(encoding="utf-8"))
    totals = coverage["totals"]
    api_file = next(row for name, row in coverage["files"].items() if name.replace("\\", "/").endswith("api/main.py"))
    api_totals = api_file["summary"]
    cov = {
        "project_lines": totals["covered_lines"] / totals["num_statements"],
        "project_branches": totals["covered_branches"] / totals["num_branches"],
        "api_lines": api_totals["covered_lines"] / api_totals["num_statements"],
        "api_branches": api_totals["covered_branches"] / api_totals["num_branches"],
        "project_statement_count": totals["num_statements"],
        "project_executed_statements": totals["covered_lines"],
    }
    versions = {name: importlib.metadata.version(name) for name in (
        "everstory", "pytest", "pytest-cov", "fastapi", "starlette", "httpx", "SQLAlchemy", "coverage",
    )}
    deps = subprocess.run([sys.executable, "-m", "pip", "freeze"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (OUT / "environment-freeze.txt").write_text(deps.stdout, encoding="utf-8")
    # Record the source commit without requiring Git on the report reader's PATH.
    head = (ROOT / ".git/HEAD").read_text().strip()
    if head.startswith("ref: "):
        ref = ROOT / ".git" / head[5:]
        head = ref.read_text().strip() if ref.exists() else head
    final_cases = ElementTree.parse(OUT / "final-tests.xml").findall(".//testcase")
    new_api_cases = sum(c.attrib.get("classname", "").split(".")[-1] == "test_contracts" for c in final_cases)
    metadata = {
        "generated_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "source_commit": head, "local_changes": True, "python": sys.version,
        "platform": platform.platform(), "versions": versions, "baseline": baseline,
        "before_fix": before_fix, "final": final_counts, "coverage": cov,
        "new_api_cases": new_api_cases, "new_real_model_calls": 0,
        "historical_score_audit": audit,
    }
    write_json(OUT / "experiment-summary.json", metadata)
    print(json.dumps({"final": final_counts, "coverage": cov,
        "historical_recommended_score": audit["recomputed_summary"]["recommended_role_average"],
        "score_mismatches": len(mismatches), "new_model_calls": 0}, ensure_ascii=False, indent=2))
    assert not mismatches, "Archived scores differ from current rubric; review audit."
    assert final_counts["failed"] == 0
    assert all(t.case_solved and t.stale_task_blocked and t.unauthorized_mutations == 0 for t in teams)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
