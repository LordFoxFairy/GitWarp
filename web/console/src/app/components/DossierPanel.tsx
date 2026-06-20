import { useEffect, useState, type FormEvent } from "react";
import { Button, TextInput } from "@primer/react";
import { CheckCircleIcon } from "@primer/octicons-react";
import type { HandoffInput } from "../gitwarp-api";
import type { CommandResult, DossierKind, WorktreeRow } from "../types";

interface DossierPanelProps {
  readonly: boolean;
  busy: boolean;
  selected: WorktreeRow | null;
  dossierKind: DossierKind;
  dossierContent: string;
  onDossierKindChange: (kind: DossierKind) => void;
  onHandoff: (input: HandoffInput) => Promise<CommandResult>;
  onFinish: (worktree: WorktreeRow, status: string, progress: string) => Promise<CommandResult>;
}

function value(form: HTMLFormElement, name: string): string {
  return new FormData(form).get(name)?.toString().trim() ?? "";
}

export function DossierPanel({
  readonly,
  busy,
  selected,
  dossierKind,
  dossierContent,
  onDossierKindChange,
  onHandoff,
  onFinish,
}: DossierPanelProps) {
  const isTask = Boolean(selected && !selected.is_main && selected.branch_role !== "base");
  const finish = (status: string, progress: string) => {
    if (!selected) {
      return Promise.resolve({ ok: false });
    }
    return onFinish(selected, status, progress);
  };

  return (
    <aside className="panel dossier-panel" aria-label="Dossier inspection">
      <div className="panel-title row">
        <div>
          <span>Dossier</span>
          <h2>{isTask ? `${dossierKind}.md` : "No task selected"}</h2>
          {isTask ? <p className="subtle">{selected?.branch}</p> : null}
        </div>
      </div>

      <div className="segmented">
        {(["task", "progress", "lessons"] as DossierKind[]).map((kind) => (
          <Button
            className={`dossier-tab ${kind === dossierKind ? "active" : ""}`}
            data-dossier-kind={kind}
            type="button"
            key={kind}
            variant={kind === dossierKind ? "primary" : "default"}
            onClick={() => onDossierKindChange(kind)}
          >
            {kind}
          </Button>
        ))}
      </div>

      <pre className="readout">{dossierContent}</pre>

      {isTask && readonly ? (
        <p className="empty-state">Read-only mode is enabled. Handoff and finish actions are hidden.</p>
      ) : null}

      {isTask && selected && !readonly ? (
        <WorktreeActions readonly={readonly} busy={busy} worktree={selected} onHandoff={onHandoff} onFinish={finish} />
      ) : null}

      {!isTask ? (
        <p className="empty-state">Select a task worktree under the current base to inspect task.md, record handoffs, or finish merged work.</p>
      ) : null}
    </aside>
  );
}

function WorktreeActions({
  readonly,
  busy,
  worktree,
  onHandoff,
  onFinish,
}: {
  readonly: boolean;
  busy: boolean;
  worktree: WorktreeRow;
  onHandoff: (input: HandoffInput) => Promise<CommandResult>;
  onFinish: (status: string, progress: string) => Promise<CommandResult>;
}) {
  const [showFinish, setShowFinish] = useState(false);
  const [finalStatus, setFinalStatus] = useState("merged");
  const [finalProgress, setFinalProgress] = useState("Merged into parent base; ready to collapse task sandbox");
  const [confirmation, setConfirmation] = useState("");
  const expectedConfirmation = worktree.branch || worktree.path;
  const finishAllowed = confirmation === expectedConfirmation && finalStatus.trim().length > 0 && finalProgress.trim().length > 0;

  useEffect(() => {
    setShowFinish(false);
    setFinalStatus("merged");
    setFinalProgress("Merged into parent base; ready to collapse task sandbox");
    setConfirmation("");
  }, [worktree.path]);

  const submitHandoff = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) {
      return;
    }
    const form = event.currentTarget;
    const lesson = value(form, "lesson");
    try {
      await onHandoff({
        cwd: worktree.path,
        status: value(form, "status"),
        progress: value(form, "progress"),
        ...(lesson ? { lesson } : {}),
      });
      form.reset();
    } catch {
      // Keep handoff text available when the command fails.
    }
  };

  const submitFinish = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!finishAllowed || busy) {
      return;
    }
    try {
      await onFinish(finalStatus.trim(), finalProgress.trim());
      setShowFinish(false);
    } catch {
      // Keep destructive confirmation visible when the command fails.
    }
  };

  return (
    <div className="detail-actions">
      <form className="handoff-form" onSubmit={submitHandoff} aria-busy={busy}>
        <label>
          Status
          <TextInput name="status" defaultValue={worktree.status || "implementing"} disabled={readonly || busy} block />
        </label>
        <label>
          Progress
          <TextInput name="progress" placeholder="Short milestone" required disabled={readonly || busy} block />
        </label>
        <label>
          Lesson
          <TextInput name="lesson" placeholder="Optional lesson" disabled={readonly || busy} block />
        </label>
        <Button variant="primary" leadingVisual={CheckCircleIcon} type="submit" disabled={readonly || busy}>
          {busy ? "Working..." : "Record Handoff"}
        </Button>
      </form>

      {!showFinish ? (
        <Button variant="danger" type="button" onClick={() => setShowFinish(true)} disabled={readonly || busy}>
          Finish Merged Task
        </Button>
      ) : (
        <form className="finish-confirm" onSubmit={submitFinish}>
          <div>
            <strong>Collapse this task sandbox</strong>
            <p className="form-hint">
              GitWarp will only collapse this task when Git proves its branch HEAD is already merged into the parent base. It will remove the task worktree, ledger row, and matching dossier. It will not push, merge, or delete the branch.
            </p>
          </div>
          <label>
            Final status
            <TextInput
              value={finalStatus}
              onChange={(event) => setFinalStatus(event.currentTarget.value)}
              disabled={readonly || busy}
              required
              block
            />
          </label>
          <label>
            Final progress
            <TextInput
              value={finalProgress}
              onChange={(event) => setFinalProgress(event.currentTarget.value)}
              disabled={readonly || busy}
              required
              block
            />
          </label>
          <label>
            Type branch to confirm
            <TextInput
              value={confirmation}
              onChange={(event) => setConfirmation(event.currentTarget.value)}
              placeholder={expectedConfirmation}
              disabled={readonly || busy}
              required
              block
            />
          </label>
          <div className="form-actions">
            <Button variant="danger" type="submit" disabled={readonly || busy || !finishAllowed}>
              {busy ? "Collapsing..." : "Collapse Worktree"}
            </Button>
            <Button type="button" onClick={() => setShowFinish(false)} disabled={busy}>
              Cancel
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}
