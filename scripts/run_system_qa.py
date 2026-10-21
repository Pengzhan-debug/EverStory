"""Reproduce real HTTP/browser tests and stepped load; never uses live models."""

import argparse
import csv
from datetime import datetime, timezone
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from qa.runtime import local_server


def run(command, log):
    with log.open("w", encoding="utf-8") as output:
        completed = subprocess.run(command, cwd=ROOT, env=dict(os.environ, PYTHONUTF8="1"),
                                   stdout=output, stderr=subprocess.STDOUT)
    if completed.returncode:
        raise RuntimeError(f"Command failed ({completed.returncode}): see {log}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-functional", action="store_true")
    parser.add_argument("--browsers", nargs="+", default=["chromium"])
    parser.add_argument("--channel", help="Optional installed browser channel, e.g. chrome")
    parser.add_argument("--skip-load", action="store_true")
    parser.add_argument("--seconds", type=int, default=30, help="Seconds per stepped load run")
    parser.add_argument("--soak-seconds", type=int, default=120)
    parser.add_argument("--out", type=Path, default=ROOT / "reports/system-qa/artifacts")
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if not args.skip_functional:
        if (out / "allure-results").exists():
            raise RuntimeError("Choose a fresh --out directory to avoid mixing Allure runs")
        run([sys.executable, "-m", "pytest", "qa/http", "qa/browser",
             *[item for name in args.browsers for item in ("--browser", name)],
             *(["--browser-channel", args.channel] if args.channel else []), "--alluredir", str(out / "allure-results"),
             "--junitxml", str(out / "functional.xml"), "--tracing", "retain-on-failure",
             "--screenshot", "only-on-failure", "--output", str(out / "playwright")], out / "functional.log")
    results = []
    if not args.skip_load:
        # Fresh app and SQLite DB for every measurement; each virtual user owns its cookies.
        plan = [(users, args.seconds, repeat, "step") for users in (5, 15, 30) for repeat in (1, 2)]
        plan.append((15, args.soak_seconds, 1, "soak"))
        for users, seconds, repeat, kind in plan:
            label = f"{kind}-{users}u-r{repeat}"
            print(f"Running {label}: {seconds}s", flush=True)
            prefix = out / label
            with local_server(out / f"{label}-server.log") as url:
                run([sys.executable, "-m", "locust", "-f", "qa/performance/locustfile.py",
                     "--host", url, "--headless", "--users", str(users), "--spawn-rate", str(users),
                     "--run-time", f"{seconds}s", "--stop-timeout", "15", "--only-summary",
                     "--exit-code-on-error", "1", "--csv", str(prefix), "--html", str(prefix) + ".html"],
                    out / f"{label}.log")
            with Path(str(prefix) + "_stats.csv").open(encoding="utf-8") as handle:
                stats = list(csv.DictReader(handle))
            for row in stats:
                observed = float(row["Request Count"]) / float(row["Requests/s"]) if float(row["Requests/s"]) else 0
                results.append({"run": label, "users": users, "duration_seconds": seconds,
                                "observed_request_window_seconds": round(observed, 3), **row})
    versions = {name: importlib.metadata.version(name) for name in
                ("requests", "pytest", "pytest-playwright", "playwright", "allure-pytest", "locust")}
    payload = {"recorded_at": datetime.now(timezone.utc).isoformat(), "python": platform.python_version(),
               "os": platform.platform(), "versions": versions, "backend": "local Stub + SQLite + in-memory coordination",
               "workload": "3:1 weighted GET world / POST wait; 100–300ms think time; auth setup included",
               "ramp": "all target users spawned in approximately one second; ramp included in statistics",
               "results": results}
    (out / "measurements.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved measurements to {out}", flush=True)


if __name__ == "__main__":
    main()
