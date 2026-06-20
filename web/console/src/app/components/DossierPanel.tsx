import type { FormEvent } from "react";
import { Button, TextInput } from "@primer/react";
import { CheckCircleIcon } from "@primer/octicons-react";
import type { HandoffInput } from "../gitwarp-api";
import type { DossierKind, WorktreeRow } from "../types";

interface DossierPanelProps {
  readonly: boolean;
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
  selected,
  dossierKind,
  dossierContent,
  onDossierKindChange,
  onHandoff,
  onFinish,
}: DossierPanelProps) {
  const finish = () => {
    if (!selected) {
      return;
    }
    const progress = window.prompt(`Final progress for ${selected.branch}:`, "Verified and ready to collapse");
    if (progress) {
      onFinish(selected, progress);
    }
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
        <WorktreeActions readonly={readonly} worktree={selected} onHandoff={onHandoff} onFinish={finish} />
      ) : null}

      {(!selected || selected.is_main) ? (
        <p className="empty-state">Select a non-main sandbox to record handoff notes or finish it.</p>
      ) : null}
    </aside>
  );
}

function WorktreeActions({
  readonly,
  worktree,
  onHandoff,
  onFinish,
}: {
  readonly: boolean;
  worktree: WorktreeRow;
  onHandoff: (input: HandoffInput) => void;
  onFinish: () => void;
}) {
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
    <div className="detail-actions">
      <form className="handoff-form" onSubmit={submitHandoff}>
        <label>
          Status
          <TextInput name="status" defaultValue={worktree.status || "implementing"} disabled={readonly} block />
        </label>
        <label>
          Progress
          <TextInput name="progress" placeholder="Short milestone" required disabled={readonly} block />
        </label>
        <label>
          Lesson
          <TextInput name="lesson" placeholder="Optional lesson" disabled={readonly} block />
        </label>
        <Button variant="primary" leadingVisual={CheckCircleIcon} type="submit" disabled={readonly}>
          Record Handoff
        </Button>
      </form>

      <Button variant="danger" type="button" onClick={onFinish} disabled={readonly}>
        Finish + Collapse
      </Button>
    </div>
  );
}
