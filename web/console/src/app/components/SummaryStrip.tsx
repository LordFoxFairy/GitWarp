import type { WebState } from "../types";

interface SummaryStripProps {
  state: WebState | null;
}

export function SummaryStrip({ state }: SummaryStripProps) {
  return (
    <section className="summary-strip" aria-label="Repository summary">
      <article className="summary-card wide">
        <span>Statusline</span>
        <strong>{state?.statusline ?? "Loading"}</strong>
      </article>
      <article className="summary-card">
        <span>Worktrees</span>
        <strong>{state?.worktrees.length ?? 0}</strong>
      </article>
      <article className="summary-card">
        <span>Doctor</span>
        <strong>{state?.doctor?.summary?.total ?? 0}</strong>
      </article>
      <article className="summary-card">
        <span>Reconcile</span>
        <strong>{state?.reconcile?.summary?.total ?? 0}</strong>
      </article>
    </section>
  );
}
