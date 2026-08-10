"""Repair engine: applies LLM-planned fixes as real file changes, verifies them by
re-executing the pipeline + invariant suite, and produces a real git artifact.

The LLM proposes the full new content of a transform; the diff is computed
deterministically here (difflib), so the displayed patch is always the patch
that actually ran.
"""

from __future__ import annotations

import difflib
import subprocess
import tempfile
from pathlib import Path

from .config import REPO_ROOT, settings
from .models import GitArtifact, MetricSnapshot, ProposedPatch, TestReport
from . import warehouse


def _resolve_transform(file_rel: str) -> Path:
    path = (REPO_ROOT / file_rel).resolve()
    transforms = settings.transforms_dir.resolve()
    if not str(path).startswith(str(transforms)) or path.suffix != ".sql":
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


def try_create_pr(artifact: GitArtifact, title: str, body: str) -> str | None:
    """Best-effort: push the fix branch and open a PR if a GitHub remote + auth exist."""
    remotes = subprocess.run(
        ["git", "remote"], cwd=REPO_ROOT, capture_output=True, text=True
    ).stdout.split()
    if "origin" not in remotes:
        return None
    push = subprocess.run(
        ["git", "push", "-f", "origin", f"{artifact.branch}:{artifact.branch}"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    if push.returncode != 0:
        return None
    pr = subprocess.run(
        ["gh", "pr", "create", "--head", artifact.branch, "--title", title, "--body", body],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60,
    )
    if pr.returncode != 0:
        existing = subprocess.run(
            ["gh", "pr", "view", artifact.branch, "--json", "url", "-q", ".url"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        return existing.stdout.strip() or None
    return pr.stdout.strip().splitlines()[-1] if pr.stdout.strip() else None
