import { Button, Flash, Label, TextInput } from "@primer/react";
import { GitBranchIcon, TrashIcon } from "@primer/octicons-react";
import { useEffect, useMemo, useState } from "react";
import { GitWarpApi } from "../gitwarp-api";
import type { CommandResult, MatrixPayload, MatrixRow } from "../types";

interface BranchesPanelProps {
  api: GitWarpApi;
  cwd: string;
  active: boolean;
  refreshKey: number;
  readonly: boolean;
  busy: boolean;
  onRunPrune: (branch: string, confirmBranch: string, baseBranch?: string) => Promise<CommandResult>;
}

export function BranchesPanel({ api, cwd, active, refreshKey, readonly, busy, onRunPrune }: BranchesPanelProps) {
  const [payload, setPayload] = useState<MatrixPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [baseBranch, setBaseBranch] = useState<string | undefined>();
  const [expandedRowId, setExpandedRowId] = useState<string | null>(null);
  const [confirmByRow, setConfirmByRow] = useState<Record<string, string>>({});

  const loadMatrix = async () => {
    setLoading(true);
    setError("");
    try {
      setPayload(await api.getMatrix(cwd, baseBranch));
    } catch (loadError) {
      setError(String(loadError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!active) {
      return;
    }
    void loadMatrix();
  }, [active, api, cwd, refreshKey, baseBranch]);

  const baseOptions = useMemo(() => {
    const rows = payload?.rows ?? [];
    return rows
      .filter((row) => row.git.branch_ref)
      .map((row) => row.branch)
      .filter((branch, index, branches) => branches.indexOf(branch) === index)
      .sort((left, right) => left.localeCompare(right));
  }, [payload]);

  const prune = async (row: MatrixRow) => {
    try {
      await onRunPrune(row.branch, confirmByRow[row.row_id] || "", payload?.merge_base);
      setConfirmByRow((current) => ({ ...current, [row.row_id]: "" }));
      setExpandedRowId(null);
    } catch (pruneError) {
      setError(String(pruneError));
    } finally {
      await loadMatrix();
    }
  };

  return (
    <section className="panel branches-panel" aria-label="Git control plane matrix">
      <div className="panel-title row">
        <div>
          <span>Control Plane</span>
          <h2>Refs &amp; worktrees</h2>
        </div>
        <Button type="button" onClick={() => void loadMatrix()} disabled={loading || busy}>
          Refresh
        </Button>
      </div>

      {error ? <Flash variant="danger">{error}</Flash> : null}
      {payload ? <MatrixSummary payload={payload} baseOptions={baseOptions} selectedBase={baseBranch} busy={busy || loading} onBaseChange={setBaseBranch} /> : null}

      <div className="branch-list matrix-list" role="table" aria-label="Git and GitWarp matrix">
        <div className="branch-list-header" role="row">
          <span>Record</span>
          <span>Sources</span>
          <span>Meaning</span>
          <span>Action</span>
        </div>
        {(payload?.rows ?? []).map((row) => (
          <MatrixRowView
            key={row.row_id}
            row={row}
            readonly={readonly}
            busy={busy}
            expanded={expandedRowId === row.row_id}
            confirmValue={confirmByRow[row.row_id] || ""}
            onExpand={() => setExpandedRowId(expandedRowId === row.row_id ? null : row.row_id)}
            onConfirmChange={(value) => setConfirmByRow((current) => ({ ...current, [row.row_id]: value }))}
            onPrune={() => void prune(row)}
          />
        ))}
      </div>

      {!payload && !loading ? <p className="empty-state">Control-plane matrix is unavailable. Refresh to retry.</p> : null}
      {loading ? <p className="empty-state">Loading Git control plane...</p> : null}
    </section>
  );
}

interface MatrixSummaryProps {
  payload: MatrixPayload;
  baseOptions: string[];
  selectedBase?: string;
  busy: boolean;
  onBaseChange: (base?: string) => void;
}

function MatrixSummary({ payload, baseOptions, selectedBase, busy, onBaseChange }: MatrixSummaryProps) {
  return (
    <div className="matrix-summary">
      <p className="muted-hint">
        Default branch is <strong>{payload.default_branch}</strong>; cleanup merge base is <strong>{payload.merge_base}</strong>. This is a read-only matrix of Git refs, live Git worktrees, GitWarp ledger rows, and dossiers.
      </p>
      <label className="matrix-base-picker">
        Cleanup base
        <select value={selectedBase || ""} onChange={(event) => onBaseChange(event.currentTarget.value || undefined)} disabled={busy}>
          <option value="">Default ({payload.default_branch})</option>
          {baseOptions.map((branch) => (
            <option key={branch} value={branch}>
              {branch}
            </option>
          ))}
        </select>
      </label>
      <div className="matrix-metrics" aria-label="Matrix summary">
        <Metric label="Git refs" value={payload.sources.git_branch_refs} />
        <Metric label="Live Git worktrees" value={payload.sources.git_worktrees} />
        <Metric label="Ledger rows" value={payload.sources.ledger_entries} />
        <Metric label="Dossier dirs" value={payload.sources.dossier_dirs} />
        <Metric label="Prunable local refs" value={payload.summary.prunable_branch_refs} tone="warning" />
        <Metric label="Merged GitWarp tasks" value={payload.summary.merged_gitwarp_tasks} tone="warning" />
      </div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone?: "warning" }) {
  return (
    <span className={`matrix-metric ${tone || ""}`}>
      <strong>{value}</strong>
      {label}
    </span>
  );
}

interface MatrixRowViewProps {
  row: MatrixRow;
  readonly: boolean;
  busy: boolean;
  expanded: boolean;
  confirmValue: string;
  onExpand: () => void;
  onConfirmChange: (value: string) => void;
  onPrune: () => void;
}

function MatrixRowView({ row, readonly, busy, expanded, confirmValue, onExpand, onConfirmChange, onPrune }: MatrixRowViewProps) {
  const canSubmitPrune = row.recommended_action === "prune_branch" && confirmValue === row.branch && !readonly && !busy;
  return (
    <article className={`branch-list-row matrix-row ${row.legacy_state}`} role="row">
      <div className="branch-name-cell" role="cell">
        <strong>
          <GitBranchIcon size={16} />
          {row.branch}
        </strong>
        <span>{row.head ? row.head.slice(0, 12) : "no HEAD"}</span>
        <code className="record-id">{row.row_id}</code>
      </div>
      <div className="source-cell" role="cell">
        <SourceChips row={row} />
        <Label variant={labelVariant(row)}>{statusLabel(row)}</Label>
        <p>{stateLine(row)}</p>
      </div>
      <div role="cell">
        <p className={row.legacy_state === "deprecated" ? "safe-prune" : ""}>{meaningText(row)}</p>
        {row.next_command ? <code className="branch-command">{row.next_command}</code> : null}
      </div>
      <div className="branch-action-cell matrix-action-cell" role="cell">
        {row.recommended_action === "prune_branch" ? (
          <PruneConfirmation
            row={row}
            readonly={readonly}
            busy={busy}
            expanded={expanded}
            confirmValue={confirmValue}
            canSubmit={canSubmitPrune}
            onExpand={onExpand}
            onConfirmChange={onConfirmChange}
            onPrune={onPrune}
          />
        ) : (
          <span className="branch-action-note">{actionText(row)}</span>
        )}
      </div>
    </article>
  );
}

interface PruneConfirmationProps {
  row: MatrixRow;
  readonly: boolean;
  busy: boolean;
  expanded: boolean;
  confirmValue: string;
  canSubmit: boolean;
  onExpand: () => void;
  onConfirmChange: (value: string) => void;
  onPrune: () => void;
}

function PruneConfirmation({ row, readonly, busy, expanded, confirmValue, canSubmit, onExpand, onConfirmChange, onPrune }: PruneConfirmationProps) {
  if (!expanded) {
    return (
      <Button variant="danger" type="button" leadingVisual={TrashIcon} onClick={onExpand} disabled={readonly || busy}>
        Review prune
      </Button>
    );
  }
  return (
    <div className="branch-confirm">
      <p>
        Delete local branch ref <strong>{row.branch}</strong>. Live worktrees, ledger rows, and dossiers are not removed.
      </p>
      <TextInput
        aria-label={`Type ${row.branch} to confirm branch prune`}
        placeholder={row.branch}
        value={confirmValue}
        onChange={(event) => onConfirmChange(event.currentTarget.value)}
        disabled={readonly || busy}
      />
      <div className="branch-confirm-actions">
        <Button type="button" onClick={onExpand} disabled={busy}>
          Cancel
        </Button>
        <Button variant="danger" type="button" leadingVisual={TrashIcon} onClick={onPrune} disabled={!canSubmit}>
          Delete local branch ref
        </Button>
      </div>
    </div>
  );
}

type LabelVariant = "success" | "attention" | "accent" | "secondary";

function SourceChips({ row }: { row: MatrixRow }) {
  const chips = [
    row.git.branch_ref ? { key: "branch", label: "branch ref" } : null,
    row.git.worktree ? { key: "worktree", label: "live worktree" } : null,
    row.gitwarp.ledger ? { key: "ledger", label: "ledger row" } : null,
    row.gitwarp.dossier_state !== "none" ? { key: "dossier", label: `dossier: ${row.gitwarp.dossier_state}` } : null,
  ].filter((chip): chip is { key: string; label: string } => chip !== null);

  if (chips.length === 0) {
    chips.push({ key: "metadata", label: "metadata only" });
  }

  return (
    <div className="source-chip-row" aria-label={`Sources for ${row.row_id}`}>
      {chips.map((chip) => (
        <span key={chip.key} className={`source-chip ${chip.key}`}>
          {chip.label}
        </span>
      ))}
    </div>
  );
}

function labelVariant(row: MatrixRow): LabelVariant {
  if (row.category === "merged_ref" || row.category === "merged_task") {
    return "success";
  }
  if (row.legacy_state === "legacy" || row.category === "untracked_worktree") {
    return "attention";
  }
  if (row.category === "active_task" || row.category === "base") {
    return "accent";
  }
  return "secondary";
}

function statusLabel(row: MatrixRow) {
  if (row.category === "merged_ref") {
    return "deprecated ref";
  }
  if (row.category === "merged_task") {
    return "merged task";
  }
  if (row.category === "untracked_worktree") {
    return "untracked";
  }
  if (row.category === "stale_ledger") {
    return "stale ledger";
  }
  if (row.category === "orphan_dossier") {
    return "orphan dossier";
  }
  return row.category.replaceAll("_", " ");
}

function stateLine(row: MatrixRow) {
  const role = row.role || "unknown";
  const owner = row.agent_id ? ` · ${row.agent_id}` : "";
  const base = row.category === "main" ? "" : row.git.merged_to_base ? " · merged" : "";
  return `${role}${base}${owner}`;
}

function meaningText(row: MatrixRow) {
  if (row.category === "merged_ref") {
    return "Merged local ref with no worktree and no GitWarp ledger row.";
  }
  if (row.category === "merged_task") {
    return "Live GitWarp task worktree is merged; finish/collapse removes the worktree, ledger row, and dossier, not the branch ref.";
  }
  if (row.category === "untracked_worktree") {
    return "Git worktree exists, but GitWarp has not adopted it.";
  }
  if (row.category === "stale_ledger") {
    return "GitWarp metadata points to a worktree Git no longer reports.";
  }
  if (row.category === "orphan_dossier") {
    return "Dossier directory is not referenced by the ledger.";
  }
  if (row.category === "orphan_ref") {
    return "Local branch is not merged into the cleanup base.";
  }
  if (row.category === "main") {
    return "Public root checkout for coordination and review.";
  }
  return row.purpose || "No cleanup action is recommended.";
}

function actionText(row: MatrixRow) {
  if (row.recommended_action === "adopt") {
    return "Adopt only when the user wants GitWarp to manage it.";
  }
  if (row.recommended_action === "repair_metadata") {
    return "Repair metadata with gitwarp init after review.";
  }
  if (row.recommended_action === "finish_collapse_merged") {
    return "Collapse from Metadata after confirming the task is complete.";
  }
  if (row.recommended_action === "create_base_worktree") {
    return "Create a base worktree before assigning agents.";
  }
  return "No destructive action.";
}
