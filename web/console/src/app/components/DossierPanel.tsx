import type { DossierKind, WorktreeRow } from "../types";

interface DossierPanelProps {
  selected: WorktreeRow | null;
  dossierKind: DossierKind;
  dossierContent: string;
  onDossierKindChange: (kind: DossierKind) => void;
}

export function DossierPanel({ selected, dossierKind, dossierContent, onDossierKindChange }: DossierPanelProps) {
  return (
    <aside className="panel dossier-panel" aria-label="Dossier inspection">
      <div className="panel-title">
        <span>Dossier</span>
        <h2>{selected ? `${selected.branch} / ${dossierKind}.md` : "No sandbox selected"}</h2>
      </div>
      <div className="segmented">
        {(["task", "progress", "lessons"] as DossierKind[]).map((kind) => (
          <button
            className={`button tab ${kind === dossierKind ? "active" : ""}`}
            data-dossier-kind={kind}
            type="button"
            key={kind}
            onClick={() => onDossierKindChange(kind)}
          >
            {kind}
          </button>
        ))}
      </div>
      <pre className="readout">{dossierContent}</pre>
    </aside>
  );
}
