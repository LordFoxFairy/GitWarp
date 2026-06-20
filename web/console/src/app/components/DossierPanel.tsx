import { useEffect, useState, type FormEvent } from "react";
import { Button, TextInput } from "@primer/react";
import { CheckCircleIcon } from "@primer/octicons-react";
import type { HandoffInput } from "../gitwarp-api";
import type { DossierKind, WorktreeRow } from "../types";

interface DossierPanelProps {
  readonly: boolean;
  busy: boolean;
  selected: WorktreeRow | null;
  dossierKind: DossierKind;
  dossierContent: string;
  onDossierKindChange: (kind: DossierKind) => void;
  onHandoff: (input: HandoffInput) => void;
  onFinish: (worktree: WorktreeRow, progress: string) => void;
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
  const finish = (progress: string) => {
    if (!selected) {
      return;
    }
    onFinish(selected, progress);
  };

  return (
    <aside className="panel dossier-panel" aria-label="Dossier inspection">
      <div className="panel-title row">
        <div>
          <span>Dossier</span>
          <h2>{selected && !selected.is_main ? `${dossierKind}.md` : "No sandbox selected"}</h2>
          {selected && !selected.is_main ? <p className="subtle">{selected.branch}</p> : null}
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

      {selected && !selected.is_main && readonly ? (
        <p className="empty-state">Read-only mode is enabled. Handoff and finish actions are hidden.</p>
      ) : null}

      {selected && !selected.is_main && !readonly ? (
        <WorktreeActions readonly={readonly} busy={busy} worktree={selected} onHandoff={onHandoff} onFinish={finish} />
      ) : null}

      {(!selected || selected.is_main) ? (
        <p className="empty-state">Select a non-main sandbox to record handoff notes or finish it.</p>
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
  onHandoff: (input: HandoffInput) => void;
  onFinish: (progress: string) => void;
}) {
  const [showFinish, setShowFinish] = useState(false);
  const [finalProgress, setFinalProgress] = useState("Verified and ready to collapse");
  const [confirmation, setConfirmation] = useState("");
  const expectedConfirmation = worktree.branch || worktree.path;
  const finishAllowed = confirmation === expectedConfirmation && finalProgress.trim().length > 0;

  useEffect(() => {
    setShowFinish(false);
    setFinalProgress("Verified and ready to collapse");
    setConfirmation("");
  }, [worktree.path]);

  const submitHandoff = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (busy) {
      return;
    }
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

  const submitFinish = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!finishAllowed || busy) {
      return;
    }
    onFinish(finalProgress.trim());
    setShowFinish(false);
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
          Finish + Collapse
        </Button>
      ) : (
        <form className="finish-confirm" onSubmit={submitFinish}>
          <div>
            <strong>Collapse this sandbox permanently</strong>
            <p className="form-hint">
              GitWarp will record final progress, force-remove the worktree, prune Git worktree metadata, and remove the ledger row.
            </p>
          </div>
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
