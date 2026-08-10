"""Subprocess entrypoint: run ONE scenario end-to-end and write a JSON result file.

Why a subprocess per scenario? ``blackbox.config.settings`` is a module-level
pydantic-settings singleton, constructed the first time ``blackbox.config`` is
imported. Env-dependent behavior (BLACKBOX_DISABLE_DATAHUB for the ablation)
therefore requires setting the env var BEFORE any blackbox import — which this
module does, from argv, before importing evals.harness / evals.scenarios
(whose blackbox imports are all deferred anyway, as a second line of defense).
Fresh process ⇒ clean singleton, clean anthropic client, clean caches.

Usage:
    uv run python -m evals.run_one <scenario> --out <result.json> [--disable-datahub] [--trial K]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.run_one")
    parser.add_argument("scenario", help="scenario name (see evals.scenarios.SCENARIOS)")
    parser.add_argument("--out", required=True, help="path to write the JSON result")
    parser.add_argument(
        "--disable-datahub",
        action="store_true",
        help="set BLACKBOX_DISABLE_DATAHUB=true before importing blackbox "
        "(implied by the datahub_ablation scenario)",
    )
    parser.add_argument("--trial", type=int, default=1, help="trial index (bookkeeping only)")
    args = parser.parse_args()

    # MUST happen before the first blackbox import (module-level settings singleton).
    if args.disable_datahub or args.scenario == "datahub_ablation":
        os.environ["BLACKBOX_DISABLE_DATAHUB"] = "true"

    from evals import harness, scenarios  # deferred: env is now finalized

    scenario = scenarios.SCENARIOS.get(args.scenario)
    if scenario is None:
        print(
            f"unknown scenario {args.scenario!r}; known: {sorted(scenarios.SCENARIOS)}",
            file=sys.stderr,
        )
        return 2

    started_at = datetime.now(timezone.utc).isoformat()
    result = harness.run_scenario(scenario)

    payload = result.to_dict()
    payload["trial"] = args.trial
    payload["started_at"] = started_at
    payload["disable_datahub"] = bool(args.disable_datahub or scenario.disable_datahub)
    payload["description"] = scenario.description

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    print(f"[{result.scenario}] {result.status} ({result.wall_time_s}s) -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
