import { Label } from "@primer/react";
import type { DispatchInput, HandoffInput, StartWorktreeInput, TaskCreateInput } from "../gitwarp-api";
import type { CommandResult, DossierKind, MatrixRow, WebState, WorktreeRow } from "../types";
import { ActionQueuePanel } from "./ActionQueuePanel";
import { ActionPanel } from "./ActionPanel";
import { DossierPanel } from "./DossierPanel";
import { WorktreePicker, baseForSelection, defaultWorktree } from "./WorktreePicker";

interface PendingTaskCandidate {
  baseBranch: string;
  branch: string;
}

interface MetadataPanelProps {
  state: WebState | null;
  readonly: boolean;
  busy: boolean;
  selected: WorktreeRow | null;
  dossierKind: DossierKind;
  dossierContent: string;
  pendingTaskBranch: PendingTaskCandidate | null;
  onSelectWorktree: (worktree: WorktreeRow) => void;
  onSelectTaskCandidate: (branch: string, baseBranch: string) => void;
  onCreateBaseCheckout: (branch: string) => Promise<void>;
  onDossierKindChange: (kind: DossierKind) => void;
  onRunTaskCreate: (input: TaskCreateInput) => Promise<CommandResult>;
  onRunStart: (input: StartWorktreeInput) => Promise<CommandResult>;
  onRunDispatch: (input: DispatchInput) => Promise<CommandResult>;
  onRunHandoff: (input: HandoffInput) => Promise<CommandResult>;
  onRunFinish: (worktree: WorktreeRow, status: string, progress: string) => Promise<CommandResult>;
  onRunRemove: (worktree: WorktreeRow) => Promise<CommandResult>;
}

export function MetadataPanel({
  state,
  readonly,
  busy,
  selected,
  dossierKind,
  dossierContent,
  pendingTaskBranch,
  onSelectWorktree,
  onSelectTaskCandidate,
  onCreateBaseCheckout,
  onDossierKindChange,
  onRunTaskCreate,
  onRunStart,
  onRunDispatch,
  onRunHandoff,
  onRunFinish,
  onRunRemove,
}: MetadataPanelProps) {
  const worktrees = state?.worktrees ?? [];
  const matrixRows = state?.matrix?.rows ?? [];
  const selectedWorktree = selected && worktrees.some((worktree) => worktree.path === selected.path) ? selected : defaultWorktree(worktrees);
  const selectedBase = baseForSelection(worktrees, selectedWorktree);
  const matrixRowsByBranch = new Map(matrixRows.map((row) => [row.branch, row] as const));
  const selectedMatrixRow = selectedWorktree?.branch ? matrixRowsByBranch.get(selectedWorktree.branch) ?? null : null;

  return (
    <section className="tab-panel workspace-console" aria-label="Sandbox management console">
      <WorktreePicker
        worktrees={worktrees}
        matrixRows={matrixRows}
        selected={selectedWorktree}
        onSelectWorktree={onSelectWorktree}
        onSelectTaskCandidate={onSelectTaskCandidate}
        onCreateBaseCheckout={onCreateBaseCheckout}
      />

      <div className="workspace-grid">
        <div className="workspace-main">
          <DossierPanel
            readonly={readonly}
            busy={busy}
            selected={selectedWorktree}
            selectedMatrixRow={selectedMatrixRow}
            dossierKind={dossierKind}
            dossierContent={dossierContent}
            onDossierKindChange={onDossierKindChange}
            onHandoff={onRunHandoff}
            onFinish={onRunFinish}
            onRunRemove={onRunRemove}
          />
        </div>

        <aside className="workspace-side" aria-label="Agent management">
          <SelectedWorktreeSummary worktree={selectedWorktree} />
          <ActionQueuePanel actions={state?.next_actions ?? []} fallback={state?.recommended_next ?? []} />
          <ActionPanel
            readonly={readonly}
            busy={busy}
            cwd={state?.repo_root}
            baseBranch={selectedBase?.branch}
            pendingTaskBranch={pendingTaskBranch}
            onTaskCreate={onRunTaskCreate}
            onStart={onRunStart}
            onDispatch={onRunDispatch}
          />
        </aside>
      </div>
    </section>
  );
}

function SelectedWorktreeSummary({ worktree }: { worktree: WorktreeRow | null }) {
  if (!worktree) {
    return (
      <article className="panel selected-worktree">
        <h2>No worktree selected</h2>
        <p className="empty-state">Create a sandbox or select an existing worktree.</p>
      </article>
    );
  }

  return (
    <article className="panel selected-worktree">
      <div className="panel-title row">
        <div>
          <span>Selected Worktree</span>
          <h2>{worktree.branch || "unknown"}</h2>
        </div>
        <Label variant={worktree.is_main ? "secondary" : "accent"}>{worktree.is_main ? "main" : worktree.status || "active"}</Label>
      </div>
      <dl className="workspace-meta compact">
        <div>
          <dt>Role</dt>
          <dd>{worktree.branch_role || (worktree.is_main ? "base" : "task")}</dd>
        </div>
        <div>
          <dt>Parent Base</dt>
          <dd>{worktree.base_branch || (worktree.is_main || worktree.branch_role === "base" ? "none" : "main")}</dd>
        </div>
        <div>
          <dt>Agent</dt>
          <dd>{worktree.agent_id || "unassigned"}</dd>
        </div>
        <div>
          <dt>Purpose</dt>
          <dd>{worktree.purpose || (worktree.is_main ? "Public main repository" : "No purpose recorded")}</dd>
        </div>
        <div>
          <dt>Progress</dt>
          <dd>{worktree.latest_progress || "No progress recorded."}</dd>
        </div>
        <div>
          <dt>Path</dt>
          <dd>{worktree.path}</dd>
        </div>
      </dl>
    </article>
  );
}
