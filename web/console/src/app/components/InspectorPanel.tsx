import type { DossierKind, Finding, FindingGroup, WebState, WorktreeRow } from "../types";

interface InspectorPanelProps {
  state: WebState | null;
  selected: WorktreeRow | null;
  dossierKind: DossierKind;
  dossierContent: string;
  onDossierKindChange: (kind: DossierKind) => void;
}

export function InspectorPanel({ state, selected, dossierKind, dossierContent, onDossierKindChange }: InspectorPanelProps) {
  return (
    <aside className="panel inspect-panel" aria-label="Dossier and health inspection">
      <div className="panel-title">
        <span>Dossier</span>
        <h2>{selected ? `${selected.branch} / ${dossierKind}.md` : "No workspace selected"}</h2>
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

      <div className="panel-title compact">
        <span>Health</span>
        <h2>Doctor / Reconcile</h2>
      </div>
      <HealthList doctor={state?.doctor} reconcile={state?.reconcile} />
    </aside>
  );
}

interface HealthListProps {
  doctor?: FindingGroup;
  reconcile?: FindingGroup;
}

function HealthList({ doctor, reconcile }: HealthListProps) {
  const findings = [
    ...summarize("doctor", doctor),
    ...summarize("reconcile", reconcile),
  ];

  if (findings.length === 0) {
    return (
      <div className="health-list">
        <article className="health-item">
          <strong>All clear</strong>
          <p>Doctor and reconcile returned no actionable findings.</p>
        </article>
      </div>
    );
  }

  return (
    <div className="health-list">
      {findings.map((finding, index) => (
        <article className={`health-item ${finding.severity ?? ""}`} key={`${finding.source}:${finding.code}:${index}`}>
          <strong>
            {finding.source}:{finding.code || "finding"} [{finding.severity || "unknown"}]
          </strong>
          <p>{finding.message || finding.description || "No details provided."}</p>
        </article>
      ))}
    </div>
  );
}

function summarize(source: "doctor" | "reconcile", group?: FindingGroup): Array<Finding & { source: string }> {
  return (group?.findings ?? []).slice(0, 6).map((finding) => ({ source, ...finding }));
}
