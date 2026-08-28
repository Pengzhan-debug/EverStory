"""Run the full real-model routing, exchange, and investigation benchmark."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from everstory.config import build_client
from everstory.eval.agent_models import (
    build_report,
    CaseResult,
    ExchangeResult,
    RoleModelResult,
    run_exchange_benchmark,
    run_role_benchmark,
)
from everstory.eval.team import TeamEvalResult, run_team_eval


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_role_results(path: Path) -> list[RoleModelResult]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    return [
        RoleModelResult(
            **{key: value for key, value in row.items() if key != "case_results"},
            case_results=[CaseResult(**case) for case in row["case_results"]],
        )
        for row in rows
    ]


def _load_dataclasses(path: Path, cls):
    return [cls(**row) for row in json.loads(path.read_text(encoding="utf-8"))]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="reports/agent-routing-evaluation-zh.md")
    parser.add_argument("--json-out", default="reports/agent-routing-evaluation.json")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--exchange-repeats", type=int, default=2)
    parser.add_argument("--team-repeats", type=int, default=3)
    parser.add_argument("--fresh", action="store_true", help="Ignore phase checkpoints")
    parser.add_argument(
        "--refresh-team", action="store_true",
        help="Reuse role/exchange checkpoints but rerun final routed cases",
    )
    args = parser.parse_args()

    def client_factory():
        return build_client(mode="api")

    probe = client_factory()
    missing = [
        connection_id for connection_id, connection in probe.connections.items()
        if connection.get("provider") == "volcengine_ark" and not connection.get("api_key")
    ]
    if missing:
        print(f"Missing model credentials: {', '.join(missing)}")
        return 2

    checkpoint_dir = Path(args.json_out).parent / "agent-eval-checkpoints"
    role_checkpoint = checkpoint_dir / "role-results.json"
    exchange_checkpoint = checkpoint_dir / "exchange-results.json"
    team_checkpoint = checkpoint_dir / "team-results.json"

    print("[1/3] role-to-model benchmark")
    if role_checkpoint.exists() and not args.fresh:
        role_results = _load_role_results(role_checkpoint)
        print("      resumed saved role results")
    else:
        role_results = run_role_benchmark(
            client_factory, workers=args.workers,
            progress=lambda item, done, total: print(
                f"      [{done:02}/{total}] {item.role} / {item.model}: "
                f"{item.overall_score:.1%}"
            ),
        )
        _write_json(role_checkpoint, [asdict(item) for item in role_results])
    completed = sum(len(item.case_results) for item in role_results)
    print(f"      completed {completed} scored role cases")

    print("[2/3] cross-agent information exchange")
    if exchange_checkpoint.exists() and not args.fresh:
        exchange_results = _load_dataclasses(exchange_checkpoint, ExchangeResult)
        print("      resumed saved exchange results")
    else:
        exchange_results = run_exchange_benchmark(
            client_factory, repeats=args.exchange_repeats,
            workers=min(args.workers, 3),
            progress=lambda item, done, total: print(
                f"      [{done}/{total}] {item.scenario} #{item.repeat}: "
                f"transfer={item.transfer_accuracy:.0%}"
            ),
        )
        _write_json(exchange_checkpoint, [asdict(item) for item in exchange_results])
    print(f"      completed {len(exchange_results)} exchange chains")

    print("[3/3] repeated end-to-end investigation")
    team_results = (
        _load_dataclasses(team_checkpoint, TeamEvalResult)
        if team_checkpoint.exists() and not args.fresh and not args.refresh_team else []
    )
    if team_results:
        print(f"      resumed {len(team_results)} saved full case(s)")
    for index in range(len(team_results) + 1, args.team_repeats + 1):
        last_error = None
        for attempt in range(1, 4):
            try:
                result = run_team_eval(
                    client_factory(), provider=f"configured-routing-run-{index}"
                )
                team_results.append(result)
                _write_json(team_checkpoint, [item.to_dict() for item in team_results])
                print(f"      case {index}/{args.team_repeats} complete")
                break
            except Exception as exc:
                last_error = exc
                print(f"      case {index} attempt {attempt}/3 failed: {str(exc)[:140]}")
                time.sleep(attempt * 2)
        else:
            raise RuntimeError(f"Full case {index} failed after retries: {last_error}")
    print(f"      completed {len(team_results)} full cases")

    markdown, payload = build_report(role_results, exchange_results, team_results)
    out = Path(args.out)
    json_out = Path(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown, encoding="utf-8")
    _write_json(json_out, payload)
    print(f"Report: {out}")
    print(f"Raw data: {json_out}")
    print(f"Verdict: {payload['verdict']} · {payload['summary']['calls']} calls · {payload['summary']['tokens']} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
