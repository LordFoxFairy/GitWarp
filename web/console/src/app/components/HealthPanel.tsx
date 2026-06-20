import type { Finding, FindingGroup, WebState } from "../types";

interface HealthPanelProps {
  state: WebState | null;
}

export function HealthPanel({ state }: HealthPanelProps) {
  return (
    <section className="panel health-panel" aria-label="Repository health">
      <div className="panel-title row">
        <div>
          <span>Health</span>
          <h2>Doctor / Reconcile</h2>
        </div>
        <span className="muted-hint">Shows actionable checks first; ok checks remain available for context.</span>
      </div>
      <HealthList doctor={state?.doctor} reconcile={state?.reconcile} />
    </section>
  );
}

interface HealthListProps {
  doctor?: FindingGroup;
  reconcile?: FindingGroup;
}

function HealthList({ doctor, reconcile }: HealthListProps) {
  const findings = [
    ...summarize("reconcile", reconcile),
    ...summarize("doctor", doctor),
  ];

  if (findings.length === 0) {
    return (
      <div className="health-list">
        <article className="health-item">
          <strong>All clear</strong>
          <p>Doctor and reconcile returned no findings.</p>
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
  const findings = group?.findings ?? [];
  const actionable = findings.filter((finding) => finding.severity !== "ok");
  const fallback = findings.filter((finding) => finding.severity === "ok").slice(0, 6);
  return (actionable.length > 0 ? actionable : fallback).map((finding) => ({ source, ...finding }));
}
