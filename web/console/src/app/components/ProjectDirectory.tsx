import { useState, type FormEvent } from "react";
import { Button, Label, TextInput } from "@primer/react";
import { GitBranchIcon, PlusIcon, RepoIcon, TrashIcon } from "@primer/octicons-react";
import type { ProjectSummary } from "../types";

interface ProjectDirectoryProps {
  projects: ProjectSummary[];
  loading: boolean;
  onOpenProject: (project: ProjectSummary) => void;
  onAddCurrentRepository: () => Promise<void>;
  onAddRepositoryPath: (path: string) => Promise<void>;
  onForgetProject: (repoRoot: string) => Promise<void>;
  onPruneMissing: () => Promise<void>;
}

export function ProjectDirectory({ projects, loading, onOpenProject, onAddCurrentRepository, onAddRepositoryPath, onForgetProject, onPruneMissing }: ProjectDirectoryProps) {
  const [pathValue, setPathValue] = useState("");
  const [showPathForm, setShowPathForm] = useState(false);
  const missingCount = projects.filter((project) => project.exists === false).length;

  const submitPath = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = pathValue.trim();
    if (!value) {
      return;
    }
    await onAddRepositoryPath(value);
    setPathValue("");
    setShowPathForm(false);
  };
  return (
    <section className="project-directory" aria-label="Project Directory">
      <div className="section-heading">
        <div>
          <p className="kicker">Project Directory</p>
          <h2>Managed Projects</h2>
        </div>
        <div className="section-actions">
          <Button type="button" leadingVisual={PlusIcon} onClick={() => void onAddCurrentRepository()} disabled={loading}>
            Add current repository
          </Button>
          <Button type="button" onClick={() => setShowPathForm((current) => !current)} disabled={loading}>
            Add repository path
          </Button>
          {missingCount > 0 ? (
            <Button type="button" variant="danger" leadingVisual={TrashIcon} onClick={() => void onPruneMissing()} disabled={loading}>
              Remove missing ({missingCount})
            </Button>
          ) : null}
        </div>
      </div>
      <span className="muted-hint">Open a project to manage its worktrees and Git state.</span>
      {showPathForm ? (
        <form className="form-stack action-form" onSubmit={(event) => void submitPath(event)}>
          <label>
            Repository path
            <TextInput value={pathValue} onChange={(event) => setPathValue(event.currentTarget.value)} placeholder="/absolute/path/to/repo" block />
          </label>
          <div className="form-actions">
            <Button type="submit" disabled={loading || !pathValue.trim()}>
              Add repository path
            </Button>
            <Button type="button" onClick={() => setShowPathForm(false)} disabled={loading}>
              Cancel
            </Button>
          </div>
        </form>
      ) : null}

      <div className="repo-list" role="table" aria-label="Managed repositories">
        {projects.length === 0 ? (
          <article className="panel project-card empty">
            <h3>{loading ? "Loading projects" : "No repositories found"}</h3>
            <p>{loading ? "Reading GitWarp state..." : "Add current repository or add a repository path to start managing it with GitWarp."}</p>
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
            {projects.map((project) => (
              <ProjectCard key={project.id} project={project} onOpenProject={onOpenProject} onForgetProject={onForgetProject} loading={loading} />
            ))}
          </>
        )}
      </div>
    </section>
  );
}

function ProjectCard({
  project,
  onOpenProject,
  onForgetProject,
  loading,
}: {
  project: ProjectSummary;
  onOpenProject: (project: ProjectSummary) => void;
  onForgetProject: (repoRoot: string) => Promise<void>;
  loading: boolean;
}) {
  const findings = project.doctor_finding_count + project.reconcile_finding_count;
  const nextActions = project.next_action_count ?? findings;
  const destructive = project.destructive_action_count ?? 0;
  const missing = project.exists === false;
  return (
    <article className={`repo-list-row${missing ? " missing" : ""}`} role="row">
      <div className="repo-list-main">
        <div>
          <h3>
            <RepoIcon size={20} />
            <span>{project.name}</span>
          </h3>
          <p className="project-path">{project.repo_root}</p>
        </div>
        {missing ? (
          <Label variant="danger">missing</Label>
        ) : (
          <Label variant={project.readonly ? "secondary" : "success"}>{project.readonly ? "read-only" : "writable"}</Label>
        )}
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

      {missing ? (
        <Button variant="danger" type="button" leadingVisual={TrashIcon} onClick={() => void onForgetProject(project.repo_root)} disabled={loading}>
          Remove
        </Button>
      ) : (
        <Button variant="primary" type="button" leadingVisual={GitBranchIcon} onClick={() => onOpenProject(project)}>
          Open Project
        </Button>
      )}
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
