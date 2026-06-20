import { Label } from "@primer/react";
import type { DispatchInput, HandoffInput, StartWorktreeInput } from "../gitwarp-api";
import type { CommandResult, DossierKind, WebState, WorktreeRow } from "../types";
import { ActionPanel } from "./ActionPanel";
import { DossierPanel } from "./DossierPanel";
import { WorktreePicker, defaultWorktree } from "./WorktreePicker";

interface MetadataPanelProps {
  state: WebState | null;
  readonly: boolean;
  busy: boolean;
  selected: WorktreeRow | null;
  dossierKind: DossierKind;
  dossierContent: string;
  onSelectWorktree: (worktree: WorktreeRow) => void;
  onDossierKindChange: (kind: DossierKind) => void;
  onRunStart: (input: StartWorktreeInput) => Promise<CommandResult>;
  onRunDispatch: (input: DispatchInput) => Promise<CommandResult>;
  onRunHandoff: (input: HandoffInput) => Promise<CommandResult>;
  onRunFinish: (worktree: WorktreeRow, status: string, progress: string) => Promise<CommandResult>;
}

export function MetadataPanel({
  state,
  readonly,
  busy,
  selected,
  dossierKind,
  dossierContent,
  onSelectWorktree,
  onDossierKindChange,
  onRunStart,
  onRunDispatch,
  onRunHandoff,
  onRunFinish,
}: MetadataPanelProps) {
  const worktrees = state?.worktrees ?? [];
  const selectedWorktree = selected && worktrees.some((worktree) => worktree.path === selected.path) ? selected : defaultWorktree(worktrees);

  return (
    <section className="tab-panel workspace-console" aria-label="Agent metadata console">
      <WorktreePicker worktrees={worktrees} selected={selectedWorktree} onSelectWorktree={onSelectWorktree} />

      <div className="workspace-grid">
        <div className="workspace-main">
          <DossierPanel
            readonly={readonly}
            busy={busy}
            selected={selectedWorktree}
            dossierKind={dossierKind}
            dossierContent={dossierContent}
            onDossierKindChange={onDossierKindChange}
            onHandoff={onRunHandoff}
            onFinish={onRunFinish}
          />
        </div>

        <aside className="workspace-side" aria-label="Agent management">
          <SelectedWorktreeSummary worktree={selectedWorktree} />
          <ActionPanel readonly={readonly} busy={busy} onStart={onRunStart} onDispatch={onRunDispatch} />
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
