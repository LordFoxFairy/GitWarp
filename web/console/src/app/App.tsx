import { useEffect, useMemo, useState } from "react";
import { BranchesPanel } from "./components/BranchesPanel";
import { CodePanel } from "./components/CodePanel";
import { HealthPanel } from "./components/HealthPanel";
import { Header } from "./components/Header";
import { MetadataPanel } from "./components/MetadataPanel";
import { OutputPanel } from "./components/OutputPanel";
import { ProjectDirectory } from "./components/ProjectDirectory";
import { RepositoryHeader, RepositoryTitleBar } from "./components/RepositoryHeader";
import { RepositoryTabs } from "./components/RepositoryTabs";
import { GitWarpApi, type DispatchInput, type HandoffInput, type StartWorktreeInput, type TaskCreateInput } from "./gitwarp-api";
import type { CommandResult, DossierKind, ProjectSummary, RepositoryTab, WebState, WorktreeRow } from "./types";

interface AppProps {
  token: string;
}

type OperationStatus = "idle" | "running" | "success" | "error";

interface OperationState {
  status: OperationStatus;
  message: string;
}

interface PendingTaskCandidate {
  baseBranch: string;
  branch: string;
}

export function App({ token }: AppProps) {
  const api = useMemo(() => new GitWarpApi(token), [token]);
  const [state, setState] = useState<WebState | null>(null);
  const [selectedProject, setSelectedProject] = useState<ProjectSummary | null>(null);
  const [selectedWorktreePath, setSelectedWorktreePath] = useState<string | null>(null);
  const [pendingTaskBranch, setPendingTaskBranch] = useState<PendingTaskCandidate | null>(null);
  const [dossierKind, setDossierKind] = useState<DossierKind>("task");
  const [dossierContent, setDossierContent] = useState("Select a non-main worktree to inspect task.md, progress.md, and lessons.md.");
  const [activeTab, setActiveTab] = useState<RepositoryTab>("code");
  const [output, setOutput] = useState("Ready.");
  const [loading, setLoading] = useState(false);
  const [operation, setOperation] = useState<OperationState>({ status: "idle", message: "" });
  const [stateRevision, setStateRevision] = useState(0);

  const writeOutput = (payload: CommandResult | string) => {
    setOutput(typeof payload === "string" ? payload : JSON.stringify(payload, null, 2));
  };

  const selected = useMemo(() => {
    if (!selectedProject || !state) {
      return null;
    }
    const worktrees = state.worktrees;
    if (selectedWorktreePath) {
      const current = worktrees.find((worktree) => worktree.path === selectedWorktreePath);
      if (current) {
        return current;
      }
    }
    return worktrees.find((worktree) => worktree.is_main) ?? worktrees[0] ?? null;
  }, [selectedProject, selectedWorktreePath, state]);

  const refresh = async (projectRoot?: string | null) => {
    setLoading(true);
    try {
      const nextState = projectRoot
        ? await api.getState(projectRoot)
        : await api.getState(selectedProject?.repo_root);
      setState(nextState);
      setStateRevision((current) => current + 1);
      setSelectedProject((current) => {
        if (current) {
          return nextState.projects.find((project) => project.repo_root === (projectRoot ?? current.repo_root)) ?? null;
        }
        return current;
      });
      return nextState;
    } catch (error) {
      writeOutput(String(error));
      return null;
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [api]);

  useEffect(() => {
    if (activeTab !== "metadata") {
      return;
    }
    const path = selected?.[`${dossierKind}_md` as keyof WorktreeRow];
    if (!selected) {
      setDossierContent("Select a worktree to inspect task.md, progress.md, and lessons.md.");
      return;
    }
    if (selected.is_main || selected.branch_role === "base" || typeof path !== "string") {
      setDossierContent("Base checkouts do not have task dossiers. Select a task worktree to inspect task.md, progress.md, and lessons.md.");
      return;
    }
    let cancelled = false;
    void api
      .readDossier(path, selectedProject?.repo_root)
      .then((payload) => {
        if (!cancelled) {
          setDossierContent(payload.content);
        }
      })
      .catch((error) => {
        if (!cancelled) {
          writeOutput(String(error));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeTab, api, selected, dossierKind]);

  useEffect(() => {
    if (!selectedProject || !state) {
      return;
    }
    if (selectedWorktreePath && state.worktrees.some((worktree) => worktree.path === selectedWorktreePath)) {
      return;
    }
    const nextSelected = state.worktrees.find((worktree) => worktree.is_main) ?? state.worktrees[0] ?? null;
    if (nextSelected) {
      setSelectedWorktreePath(nextSelected.path);
      setDossierKind("task");
    }
  }, [selectedProject, selectedWorktreePath, state]);

  const selectWorktree = (worktree: WorktreeRow) => {
    setPendingTaskBranch(null);
    setSelectedWorktreePath(worktree.path);
    setDossierKind("task");
  };

  const selectTaskCandidate = (branch: string, baseBranch: string) => {
    setPendingTaskBranch({ branch, baseBranch });
    setActiveTab("metadata");
  };

  const createBaseCheckout = async (branch: string) => {
    const result = await runCommand("Create base checkout", () => api.createBaseCheckout(branch, `Base checkout for ${branch}`, selectedProject?.repo_root));
    if (typeof result.path === "string") {
      setSelectedWorktreePath(String(result.path));
    }
  };

  const openProject = (project: ProjectSummary) => {
    setSelectedProject(project);
    setSelectedWorktreePath(null);
    setPendingTaskBranch(null);
    setDossierKind("task");
    setActiveTab("code");
    setDossierContent("Select a sandbox to inspect task.md, progress.md, and lessons.md.");
    void refresh(project.repo_root);
  };

  const closeProject = () => {
    setSelectedProject(null);
    setSelectedWorktreePath(null);
    setPendingTaskBranch(null);
    setDossierKind("task");
    setActiveTab("code");
    setDossierContent("Select a sandbox to inspect task.md, progress.md, and lessons.md.");
  };

  const runCommand = async (label: string, command: () => Promise<CommandResult>): Promise<CommandResult> => {
    setOperation({ status: "running", message: `${label} is running...` });
    writeOutput(`${label} is running...`);
    try {
      const result = await command();
      writeOutput(result);
      setOperation({ status: "success", message: `${label} completed.` });
      await refresh();
      if (typeof result.path === "string") {
        setSelectedWorktreePath(String(result.path));
      }
      return result;
    } catch (error) {
      const message = String(error);
      writeOutput(message);
      setOperation({ status: "error", message });
      throw error;
    }
  };

  const operationBusy = operation.status === "running";

  if (!selectedProject) {
    return (
      <main className="app-shell">
        <Header
          readonly={Boolean(state?.readonly)}
          loading={loading}
          title="Project Directory"
          description="Choose a repository first; worktrees, dossiers, and Git health stay inside project detail."
          onRefresh={() => void refresh()}
        />
        <ProjectDirectory projects={state?.projects ?? []} loading={loading} onOpenProject={openProject} />
        {output !== "Ready." ? <OutputPanel output={output} onClear={() => setOutput("Ready.")} /> : null}
      </main>
    );
  }

  return (
    <main className="app-shell repo-mode">
      <RepositoryHeader
        project={selectedProject}
        loading={loading}
        onBack={closeProject}
        onRefresh={() => void refresh()}
      />
      <RepositoryTitleBar project={selectedProject} readonly={Boolean(state?.readonly)} />
      <RepositoryTabs activeTab={activeTab} onTabChange={setActiveTab} />
      {operation.status !== "idle" ? <CommandStatus operation={operation} /> : null}
      <RepositorySection
        api={api}
        activeTab={activeTab}
        state={state}
        repoRoot={selectedProject.repo_root}
        stateRevision={stateRevision}
        readonly={Boolean(state?.readonly)}
        busy={operationBusy}
        selected={selected}
        pendingTaskBranch={pendingTaskBranch}
        dossierKind={dossierKind}
        dossierContent={dossierContent}
        onDossierKindChange={setDossierKind}
        onSelectWorktree={selectWorktree}
        onSelectTaskCandidate={selectTaskCandidate}
        onCreateBaseCheckout={createBaseCheckout}
        onRunTaskCreate={(input) => runCommand("Create task", () => api.createTask(input)).then((result) => {
          setPendingTaskBranch(null);
          return result;
        })}
        onRunStart={(input) => runCommand("Create sandbox", () => api.start(input))}
        onRunDispatch={(input) => runCommand("Prepare agent launch", () => api.dispatch(input))}
        onRunHandoff={(input) => runCommand("Record handoff", () => api.handoff(input))}
        onRunFinish={(worktree, status, progress) =>
          runCommand("Finish task", () =>
            worktree.branch_role === "task"
              ? api.finishMergedTask(worktree.path, status, progress)
              : api.finishAndCollapse(worktree.path, status, progress),
          ).then((result) => {
            setSelectedWorktreePath(null);
            return result;
          })
        }
        onRunRemove={(worktree) =>
          runCommand("Remove worktree", () => api.removeWorktree(worktree.path, worktree.branch, worktree.path)).then((result) => {
            setSelectedWorktreePath(null);
            return result;
          })
        }
        onRunPruneBranch={(branch, confirmBranch, baseBranch) =>
          runCommand("Prune branch", () => api.pruneBranch(selectedProject.repo_root, branch, confirmBranch, baseBranch))
        }
        onViewMetadata={() => setActiveTab("metadata")}
      />

      {output !== "Ready." ? <OutputPanel output={output} onClear={() => setOutput("Ready.")} /> : null}
    </main>
  );
}

interface RepositorySectionProps {
  api: GitWarpApi;
  activeTab: RepositoryTab;
  state: WebState | null;
  repoRoot: string;
  stateRevision: number;
  readonly: boolean;
  busy: boolean;
  selected: WorktreeRow | null;
  pendingTaskBranch: PendingTaskCandidate | null;
  dossierKind: DossierKind;
  dossierContent: string;
  onDossierKindChange: (kind: DossierKind) => void;
  onSelectWorktree: (worktree: WorktreeRow) => void;
  onSelectTaskCandidate: (branch: string, baseBranch: string) => void;
  onCreateBaseCheckout: (branch: string) => Promise<void>;
  onRunTaskCreate: (input: TaskCreateInput) => Promise<CommandResult>;
  onRunStart: (input: StartWorktreeInput) => Promise<CommandResult>;
  onRunDispatch: (input: DispatchInput) => Promise<CommandResult>;
  onRunHandoff: (input: HandoffInput) => Promise<CommandResult>;
  onRunFinish: (worktree: WorktreeRow, status: string, progress: string) => Promise<CommandResult>;
  onRunRemove: (worktree: WorktreeRow) => Promise<CommandResult>;
  onRunPruneBranch: (branch: string, confirmBranch: string, baseBranch?: string) => Promise<CommandResult>;
  onViewMetadata: () => void;
}

function RepositorySection({
  api,
  activeTab,
  state,
  repoRoot,
  stateRevision,
  readonly,
  busy,
  selected,
  pendingTaskBranch,
  dossierKind,
  dossierContent,
  onDossierKindChange,
  onSelectWorktree,
  onSelectTaskCandidate,
  onCreateBaseCheckout,
  onRunTaskCreate,
  onRunStart,
  onRunDispatch,
  onRunHandoff,
  onRunFinish,
  onRunRemove,
  onRunPruneBranch,
  onViewMetadata,
}: RepositorySectionProps) {
  return (
    <div className="repository-tab-stack">
      <div hidden={activeTab !== "code"}>
        <CodePanel
          api={api}
          state={state}
          selected={selected}
          onSelectWorktree={onSelectWorktree}
          onSelectTaskCandidate={onSelectTaskCandidate}
          onCreateBaseCheckout={onCreateBaseCheckout}
          onViewMetadata={onViewMetadata}
        />
      </div>
      <div hidden={activeTab !== "metadata"}>
        <MetadataPanel
          state={state}
          readonly={readonly}
          busy={busy}
          selected={selected}
          pendingTaskBranch={pendingTaskBranch}
          dossierKind={dossierKind}
          dossierContent={dossierContent}
          onSelectWorktree={onSelectWorktree}
          onSelectTaskCandidate={onSelectTaskCandidate}
          onCreateBaseCheckout={onCreateBaseCheckout}
          onDossierKindChange={onDossierKindChange}
          onRunTaskCreate={onRunTaskCreate}
          onRunStart={onRunStart}
          onRunDispatch={onRunDispatch}
          onRunHandoff={onRunHandoff}
          onRunFinish={onRunFinish}
          onRunRemove={onRunRemove}
        />
      </div>
      <div hidden={activeTab !== "branches"}>
        <section className="tab-panel">
          <BranchesPanel
            api={api}
            cwd={repoRoot}
            active={activeTab === "branches"}
            refreshKey={stateRevision}
            readonly={readonly}
            busy={busy}
            onRunPrune={onRunPruneBranch}
          />
        </section>
      </div>
      <div hidden={activeTab !== "health"}>
        <section className="tab-panel">
          <HealthPanel state={state} />
        </section>
      </div>
    </div>
  );
}

function CommandStatus({ operation }: { operation: OperationState }) {
  return (
    <section className={`command-status ${operation.status}`} role={operation.status === "error" ? "alert" : "status"}>
      <strong>{operation.status === "running" ? "Running" : operation.status === "success" ? "Complete" : "Attention"}</strong>
      <span>{operation.message}</span>
    </section>
  );
}
