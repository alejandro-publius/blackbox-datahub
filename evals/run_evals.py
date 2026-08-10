"""Orchestrator CLI for the BlackBox eval suite.

Runs scenarios SEQUENTIALLY (they share the warehouse + pipeline/transforms on
disk — never parallelize), each in its own ``uv run python -m evals.run_one``
subprocess so env/state isolation is guaranteed. Aggregates to
evals/results/run_<seq>.json + evals/results/latest.md and prints the table.

Usage:
    uv run python -m evals.run_evals [--scenarios a,b,c] [--trials N] [--timeout SECONDS]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = Path(__file__).resolve().parent / "results"
TRANSFORMS_DIR = REPO_ROOT / "pipeline" / "transforms"

DEFAULT_SCENARIOS = [
    "bad_repair_rejected",
    "positive_incident",
    "control_no_incident",
    "datahub_ablation",
    "positive_incident_repeat",
]


def _next_run_number() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    seq = 0
    for p in RESULTS_DIR.glob("run_*.json"):
        m = re.fullmatch(r"run_(\d+)", p.stem)
        if m:
            seq = max(seq, int(m.group(1)))
    return seq + 1


def _run_one(name: str, trial: int, disable_datahub: bool, out_path: Path, timeout: int) -> dict:
    """Spawn one scenario subprocess and read back its JSON result."""
    cmd = [
        "uv", "run", "python", "-m", "evals.run_one",
        name, "--out", str(out_path), "--trial", str(trial),
    ]
    env = os.environ.copy()
    if disable_datahub:
        # run_one also sets this itself before importing blackbox; injecting it
        # into the subprocess env as well is defense in depth.
        cmd.append("--disable-datahub")
        env["BLACKBOX_DISABLE_DATAHUB"] = "true"

    def synthetic(status: str) -> dict:
        return {
            "scenario": name,
            "status": status,
            "checks": {},
            "metrics": {},
            "notes": [],
            "details": {},
            "incident_id": None,
            "wall_time_s": None,
            "trial": trial,
            "disable_datahub": disable_datahub,
        }

    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, timeout=timeout)
    except subprocess.TimeoutExpired:
        return synthetic(f"error: timeout after {timeout}s")
    if not out_path.exists():
        return synthetic(f"error: run_one exited rc={proc.returncode} without a result file")
    try:
        return json.loads(out_path.read_text())
    finally:
        out_path.unlink(missing_ok=True)


def _final_safety_restore() -> None:
    """If a killed subprocess left the transforms dirty, restore + rebuild.
    (Each run_one restores after itself; this only covers hard kills.)"""
    dirty = (
        subprocess.run(
            ["git", "diff", "--quiet", "--", "pipeline/transforms/"], cwd=REPO_ROOT
        ).returncode
        != 0
    )
    origs = list(TRANSFORMS_DIR.glob("*.sql.orig"))
    if not dirty and not origs:
        return
    print("post-run safety restore: cleaning pipeline/transforms/ and rebuilding ...")
    subprocess.run(["git", "checkout", "--", "pipeline/transforms/"], cwd=REPO_ROOT, check=False)
    for p in origs:
        p.unlink()
    subprocess.run(["uv", "run", "python", "pipeline/run.py"], cwd=REPO_ROOT, check=False)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def _checks_cell(checks: dict[str, bool]) -> str:
    if not checks:
        return "—"
    return " ".join(f"{k} {'✓' if v else '✗'}" for k, v in checks.items())


def _notes_cell(result: dict) -> str:
    notes = list(result.get("notes") or [])
    if result.get("wall_time_s") is not None:
        notes.append(f"{result['wall_time_s']}s")
    text = "; ".join(notes)
    return (text[:220] + "…") if len(text) > 220 else (text or "—")


def _row_name(result: dict, trials: int) -> str:
    name = result["scenario"]
    if trials > 1 and name == "positive_incident_repeat":
        name = f"{name} #{result.get('trial', 1)}"
    return name


def _render_table(results: list[dict], trials: int) -> str:
    header = "| scenario | status | key checks | notes |\n|---|---|---|---|"
    rows = [
        f"| {_row_name(r, trials)} | {r['status']} | {_checks_cell(r.get('checks') or {})} "
        f"| {_notes_cell(r)} |"
        for r in results
    ]
    return "\n".join([header, *rows])


def _render_markdown(run_seq: int, results: list[dict], trials: int, started: str, finished: str) -> str:
    lines = [
        f"# BlackBox eval run {run_seq}",
        "",
        f"- started: {started}",
        f"- finished: {finished}",
        f"- full results: `evals/results/run_{run_seq:04d}.json`",
        "",
        _render_table(results, trials),
        "",
    ]
    # Per-scenario details worth human eyes (diffs, failing invariants).
    for r in results:
        details = r.get("details") or {}
        interesting = {
            k: details.get(k)
            for k in ("failing_tests", "immutability_failures", "root_cause", "final_summary")
            if details.get(k)
        }
        if not interesting and not details.get("patch_diff"):
            continue
        lines.append(f"## {_row_name(r, trials)} — {r['status']}")
        for k, v in interesting.items():
            lines.append(f"- **{k}**: `{json.dumps(v, default=str)[:600]}`")
        if details.get("patch_diff"):
            lines += ["", "```diff", str(details["patch_diff"]).rstrip(), "```", ""]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.run_evals")
    parser.add_argument(
        "--scenarios",
        default=",".join(DEFAULT_SCENARIOS),
        help=f"comma-separated scenario names (default: {','.join(DEFAULT_SCENARIOS)})",
    )
    parser.add_argument(
        "--trials", type=int, default=1,
        help="number of trials for positive_incident_repeat (default: 1)",
    )
    parser.add_argument(
        "--timeout", type=int, default=3600,
        help="per-scenario subprocess timeout in seconds (default: 3600)",
    )
    args = parser.parse_args(argv)

    # scenarios.py defers all blackbox imports, so this is safe pre-env-setup
    # and also outside `uv run` (metadata only).
    from evals.scenarios import SCENARIOS

    names = [n.strip() for n in args.scenarios.split(",") if n.strip()]
    unknown = [n for n in names if n not in SCENARIOS]
    if unknown:
        print(f"unknown scenario(s): {unknown}; known: {sorted(SCENARIOS)}", file=sys.stderr)
        return 2

    run_seq = _next_run_number()
    started = datetime.now(timezone.utc).isoformat()
    results: list[dict] = []

    for name in names:  # SEQUENTIAL by design — scenarios share warehouse/transforms
        scenario = SCENARIOS[name]
        trials = args.trials if name == "positive_incident_repeat" else 1
        for trial in range(1, trials + 1):
            label = f"{name}" + (f" (trial {trial}/{trials})" if trials > 1 else "")
            print(f"=== running {label} ===", flush=True)
            tmp = RESULTS_DIR / f".tmp_run{run_seq:04d}_{name}_t{trial}.json"
            result = _run_one(name, trial, scenario.disable_datahub, tmp, args.timeout)
            results.append(result)
            print(f"=== {label}: {result['status']} ===\n", flush=True)

    _final_safety_restore()
    finished = datetime.now(timezone.utc).isoformat()

    # Consistency aggregate for repeated trials
    repeat = [r for r in results if r["scenario"] == "positive_incident_repeat"]
    consistency = None
    if repeat:
        passed = sum(1 for r in repeat if r["status"] == "passed")
        consistency = {"trials": len(repeat), "passed": passed, "pass_rate": passed / len(repeat)}

    payload = {
        "run": run_seq,
        "started_at": started,
        "finished_at": finished,
        "scenarios_requested": names,
        "trials": args.trials,
        "consistency": consistency,
        "results": results,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RESULTS_DIR / f"run_{run_seq:04d}.json"
    run_path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    (RESULTS_DIR / "latest.md").write_text(
        _render_markdown(run_seq, results, args.trials, started, finished)
    )

    print(_render_table(results, args.trials))
    if consistency:
        print(f"\npositive_incident_repeat consistency: {consistency['passed']}/{consistency['trials']} passed")
    print(f"\nwrote {run_path} and {RESULTS_DIR / 'latest.md'}")

    bad = [r for r in results if r["status"].startswith(("failed", "error"))]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
