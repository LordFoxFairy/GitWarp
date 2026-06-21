import { Button, Label } from "@primer/react";
import { MarkGithubIcon, RepoIcon, SyncIcon } from "@primer/octicons-react";
import type { ProjectSummary } from "../types";

interface RepositoryHeaderProps {
  project: ProjectSummary;
  loading: boolean;
  onBack: () => void;
  onRefresh: () => void;
}

interface RepositoryTitleBarProps {
  project: ProjectSummary;
  readonly: boolean;
}

export function RepositoryHeader({ project, loading, onBack, onRefresh }: RepositoryHeaderProps) {
  const owner = repositoryOwner(project.repo_root);

  return (
    <header className="repo-chrome" aria-label="Project Detail">
      <div className="repo-chrome-left">
        <MarkGithubIcon size={32} />
        <div className="repo-chrome-crumb">
          <span>GitWarp</span>
          <span>/</span>
          <span>{owner}</span>
          <span>/</span>
          <strong>{project.name}</strong>
        </div>
      </div>
      <div className="repo-chrome-actions">
        <Button type="button" onClick={onBack}>
          Projects
        </Button>
        <Button type="button" leadingVisual={SyncIcon} onClick={onRefresh} disabled={loading}>
          {loading ? "Refreshing" : "Refresh"}
        </Button>
      </div>
    </header>
  );
}

export function RepositoryTitleBar({ project, readonly }: RepositoryTitleBarProps) {
  const findings = project.doctor_finding_count + project.reconcile_finding_count;

  return (
    <section className="workspace-summary" aria-label="Repository title">
      <div className="repo-title">
        <RepoIcon size={22} />
        <h1>{project.name}</h1>
        <Label variant={readonly ? "secondary" : "success"}>{readonly ? "Public" : "Writable"}</Label>
      </div>
      <div className="repo-facts">
        <SummaryItem label="Git refs" value={project.branch_ref_count} />
        <SummaryItem label="Live worktrees" value={project.worktree_count} />
        <SummaryItem label="Non-main" value={project.active_worktree_count} />
        <SummaryItem label="Agents" value={project.assigned_agent_count} />
        <SummaryItem label="Findings" value={findings} tone={findings > 0 ? "warning" : "ok"} />
      </div>
      <span className="workspace-statusline">{project.statusline}</span>
    </section>
  );
}

function SummaryItem({ label, value, tone }: { label: string; value: number; tone?: "ok" | "warning" }) {
  return (
    <span className={`summary-pill ${tone ?? ""}`}>
      {label}: <strong>{value}</strong>
    </span>
  );
}

function repositoryOwner(repoRoot: string): string {
  const parts = repoRoot.split("/").filter(Boolean);
  return parts.at(-2) ?? "local";
}
