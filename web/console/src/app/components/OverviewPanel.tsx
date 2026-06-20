import type { ChangeEvent } from "react";
import { Label, Select } from "@primer/react";
import type { DispatchInput, HandoffInput, StartWorktreeInput } from "../gitwarp-api";
import type { DossierKind, WebState, WorktreeRow } from "../types";
import { ActionPanel } from "./ActionPanel";
import { DossierPanel } from "./DossierPanel";

interface OverviewPanelProps {
  state: WebState | null;
  readonly: boolean;
  selected: WorktreeRow | null;
  dossierKind: DossierKind;
  dossierContent: string;
  onSelectWorktree: (worktree: WorktreeRow) => void;
  onDossierKindChange: (kind: DossierKind) => void;
  onRunStart: (input: StartWorktreeInput) => void;
  onRunDispatch: (input: DispatchInput) => void;
  onRunHandoff: (input: HandoffInput) => void;
  onRunFinish: (worktree: WorktreeRow, progress: string) => void;
}

export function OverviewPanel({
  state,
  readonly,
  selected,
  dossierKind,
  dossierContent,
  onSelectWorktree,
  onDossierKindChange,
  onRunStart,
  onRunDispatch,
  onRunHandoff,
  onRunFinish,
}: OverviewPanelProps) {
  const worktrees = state?.worktrees ?? [];
  const selectedWorktree = selected && worktrees.some((worktree) => worktree.path === selected.path) ? selected : defaultWorktree(worktrees);

  const changeWorktree = (event: ChangeEvent<HTMLSelectElement>) => {
    const next = worktrees.find((worktree) => worktree.path === event.currentTarget.value);
    if (next) {
      onSelectWorktree(next);
    }
  };

  return (
    <section className="tab-panel workspace-console" aria-label="Workspace console">
      <div className="workspace-switcher">
        <label className="worktree-picker">
          Current worktree
          <Select value={selectedWorktree?.path ?? ""} onChange={changeWorktree} disabled={worktrees.length === 0} block>
            {worktrees.map((worktree) => (
              <Select.Option key={worktree.path} value={worktree.path}>
                {worktree.branch || "unknown"} {worktree.is_main ? "(main)" : `- ${worktree.agent_id || "unassigned"}`}
              </Select.Option>
            ))}
          </Select>
        </label>
      </div>

      <div className="workspace-grid">
        <div className="workspace-main">
          <DossierPanel
            readonly={readonly}
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
          <ActionPanel readonly={readonly} onStart={onRunStart} onDispatch={onRunDispatch} />
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

function defaultWorktree(worktrees: WorktreeRow[]): WorktreeRow | null {
  return worktrees.find((worktree) => !worktree.is_main) ?? worktrees[0] ?? null;
}
