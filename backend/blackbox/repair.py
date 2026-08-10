"""Repair engine: applies LLM-planned fixes as real file changes, verifies them by
re-executing the pipeline + invariant suite, and produces a real git artifact
(optionally published as a real GitHub pull request).

The LLM proposes the full new content of a transform; the diff is computed
deterministically here (difflib), so the displayed patch is always the patch
that actually ran. Likewise the PR body is rendered from the recorded
IncidentState only — every number in it is a number some tool actually produced.
"""

from __future__ import annotations

import difflib
import subprocess
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from .config import REPO_ROOT, settings
from .models import GitArtifact, IncidentState, MetricSnapshot, ProposedPatch, TestReport
from . import warehouse


def _resolve_transform(file_rel: str) -> Path:
    import os

    path = (REPO_ROOT / file_rel).resolve()
    transforms = settings.transforms_dir.resolve()
    if not str(path).startswith(str(transforms) + os.sep) or path.suffix != ".sql":
        raise ValueError(f"repairs may only modify pipeline transforms, got {file_rel!r}")
    if not path.exists():
        raise FileNotFoundError(file_rel)
    return path


def propose_patch(file_rel: str, new_content: str, reasoning: str) -> ProposedPatch:
    path = _resolve_transform(file_rel)
    old = path.read_text()
    if not new_content.endswith("\n"):
        new_content += "\n"
    diff = "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{file_rel}",
            tofile=f"b/{file_rel}",
        )
    )
    if not diff:
        raise ValueError("proposed content is identical to the current file")
    return ProposedPatch(file=file_rel, diff=diff, reasoning=reasoning, status="proposed")


def apply_patch(patch: ProposedPatch, new_content: str) -> None:
    path = _resolve_transform(patch.file)
    backup = path.with_suffix(".sql.orig")
    if not backup.exists():
        backup.write_text(path.read_text())
    if not new_content.endswith("\n"):
        new_content += "\n"
    path.write_text(new_content)
    patch.status = "applied"


def revert_patch(patch: ProposedPatch) -> None:
    path = _resolve_transform(patch.file)
    backup = path.with_suffix(".sql.orig")
    if backup.exists():
        path.write_text(backup.read_text())
        backup.unlink()
    else:
        subprocess.run(["git", "checkout", "--", patch.file], cwd=REPO_ROOT, check=False)
    patch.status = "rejected"


def cleanup_backups() -> None:
    for p in settings.transforms_dir.glob("*.sql.orig"):
        p.unlink()


def verify_repair() -> tuple[TestReport, MetricSnapshot, bool]:
    """Rebuild the warehouse with the patched transform, run the full invariant
    suite, and recompute the KPI. Success = all tests pass AND KPI back in range."""
    build = warehouse.rebuild_warehouse()
    if not build["ok"]:
        report = TestReport(total=0, passed=0, failed=1, failures=[])
        snapshot = warehouse.get_metric_snapshot()
        return report, snapshot, False
    report = warehouse.run_invariants()
    snapshot = warehouse.get_metric_snapshot()
    metric_ok = 0.8 <= snapshot.anomaly_ratio <= 1.3
    return report, snapshot, report.failed == 0 and report.total > 0 and metric_ok


def make_git_artifact(patch: ProposedPatch, incident_id: str, summary: str) -> GitArtifact:
    """Commit the verified fix on a dedicated branch via a temporary worktree so the
    main working tree (and any concurrent work) is never disturbed."""
    branch = f"blackbox/fix-{incident_id}"
    subprocess.run(["git", "branch", "-D", branch], cwd=REPO_ROOT, capture_output=True)
    with tempfile.TemporaryDirectory(prefix="blackbox-fix-") as wt:
        subprocess.run(
            ["git", "worktree", "add", "-b", branch, wt, "HEAD"],
            cwd=REPO_ROOT, check=True, capture_output=True,
        )
        try:
            src = REPO_ROOT / patch.file
            dst = Path(wt) / patch.file
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(src.read_text())
            subprocess.run(["git", "add", patch.file], cwd=wt, check=True, capture_output=True)
            msg = (
                f"fix: {summary}\n\n"
                f"Automated repair by BlackBox for incident {incident_id}.\n"
                f"Verified: pipeline invariant suite green, KPI restored to baseline range.\n"
            )
            subprocess.run(["git", "commit", "-m", msg], cwd=wt, check=True, capture_output=True)
            sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=wt, check=True, capture_output=True, text=True
            ).stdout.strip()
            stat = subprocess.run(
                ["git", "show", "--stat", "--oneline", "HEAD"],
                cwd=wt, check=True, capture_output=True, text=True,
            ).stdout.strip()
        finally:
            subprocess.run(
                ["git", "worktree", "remove", "--force", wt], cwd=REPO_ROOT, capture_output=True
            )
    return GitArtifact(branch=branch, commit=sha, diff_stat=stat)


# ---------------------------------------------------------------------------
# Autonomous pull request
#
# Hard safety rules (see tests/test_repair_pr.py):
#   * OFF by default — settings.blackbox_create_pr / BLACKBOX_CREATE_PR.
#   * Only ever runs AFTER verification succeeded; it can never gate or change it.
#   * Only branches named blackbox/fix-* may be pushed, and only to `origin`.
#   * Every failure is swallowed and reported, never raised.
# ---------------------------------------------------------------------------

FIX_BRANCH_PREFIX = "blackbox/fix-"
PR_TITLE_PREFIX = "fix(pipeline): "
PR_TITLE_MAX = 72


def _run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout)


def _stderr(proc: subprocess.CompletedProcess) -> str:
    return " ".join(((proc.stderr or "") + " " + (proc.stdout or "")).split())[:400]


def _num(v: Any, nd: int = 2) -> str:
    if isinstance(v, bool) or v is None:
        return "n/a"
    if isinstance(v, (int, float)):
        return f"{v:,.{nd}f}"
    return str(v)


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def build_pr_title(state: IncidentState) -> str:
    """`fix(pipeline): <root cause>` truncated on a word boundary to <= 72 chars."""
    summary = " ".join((state.root_cause.summary if state.root_cause else "").split())
    if not summary:
        summary = f"verified repair for incident {state.id}"
    budget = PR_TITLE_MAX - len(PR_TITLE_PREFIX)
    if len(summary) > budget:
        cut = summary[: budget - 3]
        if " " in cut[1:]:
            cut = cut[: cut.rfind(" ")]
        summary = cut.rstrip(" ,.;:-—") + "..."
    return PR_TITLE_PREFIX + summary


def _cited_evidence(state: IncidentState) -> list:
    ids = state.root_cause.evidence_ids if state.root_cause else []
    items = [state.evidence_by_id(i) for i in ids]
    return [e for e in items if e is not None]


def _quantitative_block(ev) -> str | None:
    """Render one cited profile / baseline_comparison evidence item as real numbers.

    Reads only `ev.data` — the raw payload the deterministic tool produced.
    """
    data = ev.data
    if not isinstance(data, dict):
        return None
    head = f"**{ev.title}** (`{ev.id}`)"

    if isinstance(data.get("comparisons"), list) and data["comparisons"]:
        rows = []
        for c in data["comparisons"][:8]:
            rows.append(
                [
                    str(c.get("day", "")),
                    _num(c.get("revenue_usd")),
                    _num(c.get("baseline_revenue_usd")),
                    _num(c.get("revenue_ratio"), 3) + "x",
                    _num(c.get("aov_median_usd")),
                    _num(c.get("baseline_aov_median_usd")),
                    f"{c.get('order_count')} / {c.get('baseline_order_count')}",
                ]
            )
        table = _md_table(
            ["day", "revenue", "baseline revenue", "ratio", "AOV median", "baseline AOV",
             "orders / baseline"],
            rows,
        )
        src = data.get("baseline_source")
        tail = f"\n\nBaseline source: `{src}`" if src else ""
        return f"{head}\n\n{table}{tail}"

    if isinstance(data.get("days"), list) and data["days"]:
        rows = [
            [
                str(d.get("day", "")),
                str(d.get("segment", "")),
                str(d.get("n", "")),
                _num(d.get("mean"), 4),
                _num(d.get("median"), 4),
                _num(d.get("min"), 4),
                _num(d.get("max"), 4),
                _num(d.get("null_rate"), 4),
            ]
            for d in data["days"][:10]
        ]
        table = _md_table(
            ["day", "segment", "rows", "mean", "median", "min", "max", "null rate"], rows
        )
        subject = f"`{data.get('table')}.{data.get('column')}`"
        seg = data.get("segment_by")
        subject += f" segmented by `{seg}`" if seg else ""
        return f"{head}\n\n{subject}\n\n{table}"

    if "anomaly_ratio" in data:
        return (
            f"{head}\n\n"
            f"KPI day `{data.get('kpi_day')}`: revenue **{_num(data.get('revenue'))}** vs expected "
            f"**{_num(data.get('expected_revenue'))}** → anomaly ratio "
            f"**{_num(data.get('anomaly_ratio'), 4)}x** (`{data.get('status')}`)."
        )
    return None


def build_pr_body(state: IncidentState) -> str:
    """Render the PR description as a genuine review artifact.

    Every figure comes out of the recorded IncidentState (evidence payloads, test
    reports, metric snapshots, the difflib patch). Nothing is invented here: fields
    that were never recorded are reported as missing rather than filled in.
    """
    rc = state.root_cause
    cited = _cited_evidence(state)
    parts: list[str] = []

    # 1 — disclosure -------------------------------------------------------
    parts.append(
        "## Autonomous repair — disclosure\n\n"
        "**BlackBox, an autonomous agent, generated _and_ verified this repair.** No human "
        "wrote the diff below, and no human ran the verification; the agent investigated the "
        "incident, proposed the patch, rebuilt the warehouse and re-ran the full invariant "
        "suite before opening this PR.\n\n"
        "**The scenario is a deterministic synthetic demo fixture** (`pipeline/`, seeded and "
        "pinned so every run is byte-identical). The business data is fabricated on purpose; "
        "the execution is not — every number below is real output of real tooling (DuckDB, "
        "DataHub GraphQL, pytest, difflib, git). Review it as you would any machine-authored "
        "change: the diff is the contract."
    )

    # 2 — root cause -------------------------------------------------------
    if rc is not None:
        parts.append(
            "## Root cause\n\n"
            f"{rc.summary}\n\n"
            + _md_table(
                ["", ""],
                [
                    ["**Blamed asset**", f"`{rc.asset_urn}`"],
                    ["**Blamed field**", f"`{rc.field}`"],
                    ["**Cited evidence**", f"{len(rc.evidence_ids)} item(s)"],
                ],
            )
        )
    else:
        parts.append("## Root cause\n\nNo confirmed root cause was recorded for this incident.")

    # 3 — DataHub evidence summary ----------------------------------------
    counts = Counter(e.source for e in state.evidence)
    by_source = ", ".join(f"`{s}` × {n}" for s, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))
    lines = [
        "## DataHub evidence",
        "",
        f"{len(state.evidence)} evidence item(s) recorded by deterministic tool code — "
        f"{by_source or 'none'}.",
        "",
        "Cited lineage / metadata evidence:",
        "",
    ]
    dh = [e for e in cited if e.kind in ("lineage", "metadata")]
    if dh:
        lines += [f"- `{e.id}` **{e.title}** — {e.detail or e.kind} _(source: {e.source})_" for e in dh]
    else:
        lines.append("- none cited")
    parts.append("\n".join(lines))

    # 4 — quantitative proof ----------------------------------------------
    blocks = [b for b in (_quantitative_block(e) for e in cited
                          if e.kind in ("profile", "baseline_comparison")) if b]
    parts.append(
        "## Quantitative proof\n\n"
        + ("\n\n".join(blocks) if blocks else "No quantitative evidence was cited for this incident.")
    )

    # 5 — the diff ---------------------------------------------------------
    if state.patch is not None:
        parts.append(
            f"## The fix — `{state.patch.file}`\n\n"
            f"{state.patch.reasoning}\n\n"
            "```diff\n" + state.patch.diff.rstrip("\n") + "\n```"
        )
    else:
        parts.append("## The fix\n\nNo patch was recorded for this incident.")

    # 6 — before / after KPI ----------------------------------------------
    def _kpi_row(label: str, m: MetricSnapshot | None) -> list[str]:
        if m is None:
            return [label, "n/a", "n/a", "n/a", "n/a"]
        return [label, m.kpi_day, _num(m.revenue), _num(m.expected_revenue),
                f"**{_num(m.anomaly_ratio, 4)}x** ({m.status})"]

    parts.append(
        "## Verification — KPI before / after\n\n"
        + _md_table(
            ["", "KPI day", "revenue", "expected revenue", "anomaly ratio"],
            [_kpi_row("**before**", state.metric_before), _kpi_row("**after**", state.metric_after)],
        )
        + "\n\nAcceptance band for the anomaly ratio is [0.8, 1.3]; the repair is only marked "
        "verified when the KPI lands inside it."
    )

    # 7 — invariants -------------------------------------------------------
    after, before = state.tests_after, state.tests_before
    inv = ["## Verification — pipeline invariants", ""]
    if after is not None:
        inv.append(f"**{after.passed}/{after.total} passed** after the repair "
                   f"({after.failed} failing).")
    else:
        inv.append("No post-repair invariant run was recorded.")
    if before is not None:
        inv.append("")
        inv.append(f"For comparison, before the repair: {before.passed}/{before.total} passed "
                   f"({before.failed} failing).")
        if before.failures:
            inv.append("")
            inv += [f"- `{f.name}` — {' '.join((f.message or '').split())[:160]}"
                    for f in before.failures[:8]]
    parts.append("\n".join(inv))

    # 8 — provenance footer ------------------------------------------------
    git = state.git_artifact
    stage = getattr(state.stage, "value", state.stage)
    provenance = f"Incident `{state.id}` · stage `{stage}`"
    if git is not None:
        provenance += f" · branch `{git.branch}` · commit `{git.commit[:10]}`"
    parts.append(
        "---\n\n"
        + provenance
        + "\n\nGenerated by BlackBox — autonomous data incident response on DataHub."
    )

    return "\n\n".join(parts) + "\n"


# ------------------------------------------------------------------ publish


def _has_origin() -> bool:
    return "origin" in _run(["git", "remote"], timeout=15).stdout.split()


def _gh_ready() -> bool:
    try:
        return _run(["gh", "auth", "status"], timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def try_create_pr(artifact: GitArtifact, title: str, body: str) -> dict[str, Any]:
    """Push the fix branch to `origin` and open a PR via `gh`.

    Returns {"status": skipped|created|failed, "url": str|None, "detail": str}.
    Refuses outright to push anything that is not a `blackbox/fix-*` branch.
    """
    branch = artifact.branch
    if not branch.startswith(FIX_BRANCH_PREFIX):
        return {"status": "failed", "url": None,
                "detail": f"refusing to push {branch!r}: only {FIX_BRANCH_PREFIX}* branches may be pushed"}
    if not _has_origin():
        return {"status": "skipped", "url": None, "detail": "no `origin` remote configured"}
    if not _gh_ready():
        return {"status": "skipped", "url": None,
                "detail": "`gh auth status` failed (GitHub CLI missing or not authenticated)"}

    refspec = f"refs/heads/{branch}:refs/heads/{branch}"
    push = _run(["git", "push", "origin", refspec], timeout=120)
    if push.returncode != 0:
        # The only permitted retry: a force update of this one fix branch. The
        # refspec is fully qualified and prefix-checked above, so `main` (or any
        # other ref) can never be the target.
        push = _run(["git", "push", "--force", "origin", refspec], timeout=120)
    if push.returncode != 0:
        return {"status": "failed", "url": None, "detail": f"git push failed: {_stderr(push)}"}

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, prefix="blackbox-pr-") as f:
        f.write(body)
        body_file = f.name
    try:
        pr = _run(
            ["gh", "pr", "create", "--head", branch, "--title", title, "--body-file", body_file],
            timeout=90,
        )
    finally:
        Path(body_file).unlink(missing_ok=True)

    if pr.returncode == 0:
        url = next((ln.strip() for ln in reversed(pr.stdout.splitlines()) if ln.strip()), "")
        return {"status": "created", "url": url or None,
                "detail": f"pull request opened for {branch}" if url else "gh reported success but printed no url"}

    # A PR may already exist for this branch (re-run of the same incident id).
    existing = _run(["gh", "pr", "view", branch, "--json", "url", "-q", ".url"], timeout=60)
    url = existing.stdout.strip()
    if existing.returncode == 0 and url:
        return {"status": "created", "url": url,
                "detail": f"branch pushed; a pull request already existed for {branch}"}
    return {"status": "failed", "url": None, "detail": f"gh pr create failed: {_stderr(pr)}"}


def publish_repair_pr(state: IncidentState, artifact: GitArtifact) -> dict[str, Any]:
    """Opt-in, best-effort publication of a VERIFIED repair as a real GitHub PR.

    Never raises, never mutates anything but `artifact.pr_url`, and does no work at
    all (not even a subprocess) unless BLACKBOX_CREATE_PR is true — so the demo and
    the evals behave exactly as they did before this existed.
    """
    if not settings.blackbox_create_pr:
        return {
            "status": "disabled", "url": None, "branch": artifact.branch,
            "title": "PR publication disabled",
            "detail": "BLACKBOX_CREATE_PR is false — the verified fix stays on the local branch.",
        }
    title = build_pr_title(state)
    try:
        body = build_pr_body(state)
    except Exception as e:  # a malformed state must not cost us the verified repair
        return {
            "status": "failed", "url": None, "branch": artifact.branch, "title": "PR body build failed",
            "detail": f"{type(e).__name__}: {e}", "pr_title": title,
        }
    try:
        res = try_create_pr(artifact, title, body)
    except Exception as e:  # subprocess timeout / missing binary / anything else
        res = {"status": "failed", "url": None, "detail": f"{type(e).__name__}: {e}"}

    status = res.get("status", "failed")
    url = res.get("url")
    if status == "created" and url:
        artifact.pr_url = url
    evidence_title = {
        "created": f"Pull request opened: {url}",
        "skipped": "PR publication skipped",
    }.get(status, "PR publication failed")
    return {
        "status": status, "url": url, "branch": artifact.branch, "title": evidence_title,
        "detail": res.get("detail", ""), "pr_title": title, "body_chars": len(body),
        "body_preview": body[:500],
    }
