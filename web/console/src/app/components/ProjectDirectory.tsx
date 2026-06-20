import { Button, Label } from "@primer/react";
import { GitBranchIcon, RepoIcon } from "@primer/octicons-react";
import type { ProjectSummary } from "../types";

interface ProjectDirectoryProps {
  projects: ProjectSummary[];
  loading: boolean;
  onOpenProject: (project: ProjectSummary) => void;
}

export function ProjectDirectory({ projects, loading, onOpenProject }: ProjectDirectoryProps) {
  return (
    <section className="project-directory" aria-label="Project Directory">
      <div className="section-heading">
        <div>
          <p className="kicker">Project Directory</p>
          <h2>Managed Projects</h2>
        </div>
        <span className="muted-hint">Open a project to manage its worktrees and Git state.</span>
      </div>

      <div className="repo-list">
        {projects.length === 0 ? (
          <article className="panel project-card empty">
            <h3>{loading ? "Loading projects" : "No repositories found"}</h3>
            <p>{loading ? "Reading GitWarp state..." : "Start GitWarp from a repository to manage its worktrees."}</p>
          </article>
        ) : (
          projects.map((project) => <ProjectCard key={project.id} project={project} onOpenProject={onOpenProject} />)
        )}
      </div>
    </section>
  );
}

function ProjectCard({ project, onOpenProject }: { project: ProjectSummary; onOpenProject: (project: ProjectSummary) => void }) {
  const findings = project.doctor_finding_count + project.reconcile_finding_count;
  return (
    <article className="repo-list-row">
      <div className="repo-list-main">
        <div>
          <h3>
            <RepoIcon size={20} />
            <span>{project.name}</span>
          </h3>
          <p className="project-path">{project.repo_root}</p>
        </div>
        <Label variant={project.readonly ? "secondary" : "success"}>{project.readonly ? "read-only" : "writable"}</Label>
      </div>

      <div className="repo-list-meta" aria-label={`${project.name} summary`}>
        <span className="statusline-banner">{project.statusline}</span>
        <Metric label="Worktrees" value={project.worktree_count} />
        <Metric label="Active" value={project.active_worktree_count} />
        <Metric label="Agents" value={project.assigned_agent_count} />
        <Metric label="Findings" value={findings} tone={findings > 0 ? "warning" : "ok"} />
      </div>

      <Button variant="primary" type="button" leadingVisual={GitBranchIcon} onClick={() => onOpenProject(project)}>
        Open Project
      </Button>
    </article>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone?: "ok" | "warning" }) {
  return (
    <div className={tone ? `metric ${tone}` : "metric"}>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
