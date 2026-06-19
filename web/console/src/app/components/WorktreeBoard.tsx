import type { FormEvent } from "react";
import type { HandoffInput } from "../gitwarp-api";
import type { WorktreeRow } from "../types";

interface WorktreeBoardProps {
  readonly: boolean;
  worktrees: WorktreeRow[];
  onSelect: (worktree: WorktreeRow) => void;
  onHandoff: (input: HandoffInput) => void;
  onFinish: (worktree: WorktreeRow, progress: string) => void;
}

function value(form: HTMLFormElement, name: string): string {
  return new FormData(form).get(name)?.toString().trim() ?? "";
}

export function WorktreeBoard({ readonly, worktrees, onSelect, onHandoff, onFinish }: WorktreeBoardProps) {
  return (
    <section className="panel board-panel" aria-label="Active worktrees">
      <div className="panel-title row">
        <div>
          <span>Board</span>
          <h2>Active Worktrees</h2>
        </div>
        <span className="muted-hint">Select a row to inspect dossier files.</span>
      </div>
      <div className="workspace-list">
        {worktrees.length === 0 ? (
          <p className="empty-state">No worktrees found.</p>
        ) : (
          worktrees.map((worktree) => (
            <WorktreeCard
              key={worktree.path}
              readonly={readonly}
              worktree={worktree}
              onSelect={onSelect}
              onHandoff={onHandoff}
              onFinish={onFinish}
            />
          ))
        )}
      </div>
    </section>
  );
}

interface WorktreeCardProps {
  readonly: boolean;
  worktree: WorktreeRow;
  onSelect: (worktree: WorktreeRow) => void;
  onHandoff: (input: HandoffInput) => void;
  onFinish: (worktree: WorktreeRow, progress: string) => void;
}

function WorktreeCard({ readonly, worktree, onSelect, onHandoff, onFinish }: WorktreeCardProps) {
  const finish = () => {
    const progress = window.prompt(`Final progress for ${worktree.branch}:`, "Verified and ready to collapse");
    if (progress) {
      onFinish(worktree, progress);
    }
  };

  return (
    <article className="workspace-card">
      <div className="workspace-card-head">
        <div>
          <p className="branch">{worktree.branch || "unknown"}</p>
          <p className="subtle">{worktree.is_main ? "main checkout" : worktree.path || ""}</p>
        </div>
        <span className="status-chip">{worktree.is_main ? "main" : worktree.status || "active"}</span>
      </div>

      <dl className="workspace-meta">
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
          <dt>Instructions</dt>
          <dd>{worktree.instructions?.length ? `${worktree.instructions.length} mounted` : "None"}</dd>
        </div>
      </dl>

      <div className="workspace-actions">
        <div className="row-actions">
          <button className="button ghost" type="button" onClick={() => onSelect(worktree)} disabled={Boolean(worktree.is_main)}>
            Open Dossier
          </button>
          <button className="button danger" type="button" onClick={finish} disabled={Boolean(worktree.is_main || readonly)}>
            Finish + Collapse
          </button>
        </div>
      </div>

      {!worktree.is_main ? <WorktreeHandoffForm readonly={readonly} worktree={worktree} onHandoff={onHandoff} /> : null}
    </article>
  );
}

function WorktreeHandoffForm({ readonly, worktree, onHandoff }: { readonly: boolean; worktree: WorktreeRow; onHandoff: (input: HandoffInput) => void }) {
  const submitHandoff = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const lesson = value(form, "lesson");
    onHandoff({
      cwd: worktree.path,
      status: value(form, "status"),
      progress: value(form, "progress"),
      ...(lesson ? { lesson } : {}),
    });
    form.reset();
  };

  return (
    <form className="inline-form" onSubmit={submitHandoff}>
      <label>
        Status
        <input name="status" defaultValue={worktree.status || "implementing"} disabled={readonly} />
      </label>
      <label className="progress-field">
        Progress
        <input name="progress" placeholder="Short milestone" required disabled={readonly} />
      </label>
      <label>
        Lesson
        <input name="lesson" placeholder="Optional" disabled={readonly} />
      </label>
      <button className="button secondary" type="submit" disabled={readonly}>
        Record Handoff
      </button>
    </form>
  );
}
