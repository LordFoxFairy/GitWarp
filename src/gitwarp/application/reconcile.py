from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..application.diagnostics import build_finding, summarize_findings
from ..application.views import age_seconds
from ..infrastructure.ledger import load_raw_ledger
from ..infrastructure.runtime import RepoContext
from ..infrastructure.worktrees import branch_merged_into_main, parse_worktrees, worktree_dirty


def build_reconcile_payload(ctx: RepoContext, *, stale_hours: float | None = None) -> dict[str, Any]:
    ledger = load_raw_ledger(ctx)
    live_worktrees = parse_worktrees(ctx)
    live_by_path = {item["path"]: item for item in live_worktrees}
    ledger_by_path = {entry.get("path"): entry for entry in ledger["entries"] if entry.get("path")}
    now = datetime.now(timezone.utc)
    findings: list[dict[str, Any]] = []

    for entry in ledger["entries"]:
        entry_path = entry.get("path")
        if entry_path and entry_path not in live_by_path:
            findings.append(
                build_finding(
                    "stale_ledger_entry",
                    "warning",
                    "Ledger entry points to a missing live worktree.",
                    item=entry,
                )
            )
        if entry_path and entry_path in live_by_path:
            last_seen_head = entry.get("last_seen_head")
            current_head = live_by_path[entry_path].get("head")
            if last_seen_head and current_head and last_seen_head != current_head:
                findings.append(
                    build_finding(
                        "head_drift",
                        "warning",
                        "Worktree HEAD differs from the last GitWarp-recorded handoff point.",
                        item=entry,
                    )
                )
        for key in ("task_md", "progress_md", "lessons_md"):
            value = entry.get(key)
            if value and not Path(value).exists():
                findings.append(
                    build_finding(
                        "missing_dossier_file",
                        "warning",
                        f"Tracked dossier file is missing: {key}.",
                        item=entry,
                    )
                )
        status = entry.get("status")
        if status in {"blocked", "dispatch_failed", "merged"}:
            findings.append(
                build_finding(
                    "attention_status",
                    "warning",
                    f"Worktree has attention status: {status}.",
                    item=entry,
                )
            )
        if stale_hours is not None:
            age = age_seconds(entry, now)
            if age is not None and age >= max(0, int(stale_hours * 3600)):
                findings.append(
                    build_finding(
                        "stale_worktree",
                        "warning",
                        f"Worktree ledger has not changed for {age} seconds.",
                        item=entry,
                    )
                )

    for item in live_worktrees:
        if item.get("is_main"):
            continue
        if item["path"] not in ledger_by_path:
            findings.append(
                build_finding(
                    "untracked_worktree",
                    "warning",
                    "Live non-main worktree is missing from the GitWarp ledger.",
                    item=item,
                )
            )
        if worktree_dirty(item["path"]):
            findings.append(
                build_finding(
                    "dirty_worktree",
                    "warning",
                    "Live worktree has uncommitted or untracked changes.",
                    item=ledger_by_path.get(item["path"], item),
                )
            )
        if branch_merged_into_main(ctx, item.get("branch")):
            findings.append(
                build_finding(
                    "merged_head",
                    "warning",
                    "Worktree branch HEAD is already merged into main.",
                    item=ledger_by_path.get(item["path"], item),
                )
            )

    return {
        "ok": True,
        "repo_root": str(ctx.repo_root),
        "ledger_path": str(ctx.ledger_path),
        "findings": findings,
        "summary": summarize_findings(findings),
    }
