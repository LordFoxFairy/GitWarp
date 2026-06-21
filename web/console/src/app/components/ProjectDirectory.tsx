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

      <div className="repo-list" role="table" aria-label="Managed repositories">
        {projects.length === 0 ? (
          <article className="panel project-card empty">
            <h3>{loading ? "Loading projects" : "No repositories found"}</h3>
            <p>{loading ? "Reading GitWarp state..." : "Start GitWarp from a repository to manage its worktrees."}</p>
          </article>
        ) : (
          <>
            <div className="repo-list-header" role="row">
              <span role="columnheader">Repository</span>
              <span role="columnheader">Git refs</span>
              <span role="columnheader">Live worktrees</span>
              <span role="columnheader">Agents</span>
              <span role="columnheader">Next</span>
              <span role="columnheader" aria-label="Actions" />
            </div>
            {projects.map((project) => <ProjectCard key={project.id} project={project} onOpenProject={onOpenProject} />)}
          </>
        )}
      </div>
    </section>
  );
}

function ProjectCard({ project, onOpenProject }: { project: ProjectSummary; onOpenProject: (project: ProjectSummary) => void }) {
  const findings = project.doctor_finding_count + project.reconcile_finding_count;
  const nextActions = project.next_action_count ?? findings;
  const destructive = project.destructive_action_count ?? 0;
  return (
    <article className="repo-list-row" role="row">
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

      <Metric label="Git refs" value={project.branch_ref_count} detail="local branches" />
      <Metric label="Live worktrees" value={project.worktree_count} detail={`${project.active_worktree_count} non-main`} />
      <Metric label="Agents" value={project.assigned_agent_count} detail="assigned" />
      <Metric
        label="Next"
        value={nextActions}
        detail={destructive > 0 ? `${destructive} confirm` : nextActions > 0 ? "review" : "clear"}
        tone={nextActions > 0 ? "warning" : "ok"}
      />

      <Button variant="primary" type="button" leadingVisual={GitBranchIcon} onClick={() => onOpenProject(project)}>
        Open Project
      </Button>
    </article>
  );
}

function Metric({ label, value, detail, tone }: { label: string; value: number; detail: string; tone?: "ok" | "warning" }) {
  return (
    <div className={tone ? `metric ${tone}` : "metric"}>
      <dt>{label}</dt>
      <dd>{value}</dd>
      <span>{detail}</span>
    </div>
  );
}
