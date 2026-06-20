import type { WebState } from "../types";

interface SummaryStripProps {
  state: WebState | null;
}

export function SummaryStrip({ state }: SummaryStripProps) {
  const project = state?.projects[0];
  const findings = (project?.doctor_finding_count ?? 0) + (project?.reconcile_finding_count ?? 0);
  return (
    <section className="summary-strip" aria-label="Repository summary">
      <article className="summary-card wide">
        <span>Statusline</span>
        <strong>{state?.statusline ?? "Loading"}</strong>
      </article>
      <article className="summary-card">
        <span>Worktrees</span>
        <strong>{project?.worktree_count ?? state?.worktrees.length ?? 0}</strong>
      </article>
      <article className="summary-card">
        <span>Active</span>
        <strong>{project?.active_worktree_count ?? 0}</strong>
      </article>
      <article className="summary-card">
        <span>Findings</span>
        <strong>{findings}</strong>
      </article>
    </section>
  );
}
