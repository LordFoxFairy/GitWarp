import { useEffect, useMemo, useState } from "react";
import { HealthPanel } from "./components/HealthPanel";
import { Header } from "./components/Header";
import { OverviewPanel } from "./components/OverviewPanel";
import { OutputPanel } from "./components/OutputPanel";
import { ProjectDirectory } from "./components/ProjectDirectory";
import { RepositoryHeader, RepositoryTitleBar } from "./components/RepositoryHeader";
import { RepositoryTabs } from "./components/RepositoryTabs";
import { GitWarpApi, type DispatchInput, type HandoffInput, type StartWorktreeInput } from "./gitwarp-api";
import type { CommandResult, DossierKind, ProjectSummary, RepositoryTab, WebState, WorktreeRow } from "./types";

interface AppProps {
  token: string;
}

type OperationStatus = "idle" | "running" | "success" | "error";

interface OperationState {
  status: OperationStatus;
  message: string;
}

export function App({ token }: AppProps) {
  const api = useMemo(() => new GitWarpApi(token), [token]);
  const [state, setState] = useState<WebState | null>(null);
  const [selectedProject, setSelectedProject] = useState<ProjectSummary | null>(null);
  const [selectedWorktreePath, setSelectedWorktreePath] = useState<string | null>(null);
  const [dossierKind, setDossierKind] = useState<DossierKind>("task");
  const [dossierContent, setDossierContent] = useState("Select a non-main worktree to inspect task.md, progress.md, and lessons.md.");
  const [activeTab, setActiveTab] = useState<RepositoryTab>("workspace");
  const [output, setOutput] = useState("Ready.");
  const [loading, setLoading] = useState(false);
  const [operation, setOperation] = useState<OperationState>({ status: "idle", message: "" });

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
    return worktrees.find((worktree) => !worktree.is_main) ?? worktrees[0] ?? null;
  }, [selectedProject, selectedWorktreePath, state]);

  const refresh = async () => {
    setLoading(true);
    try {
      const nextState = await api.getState();
      setState(nextState);
      if (selectedProject) {
        setSelectedProject(nextState.projects.find((project) => project.id === selectedProject.id) ?? null);
      }
    } catch (error) {
      writeOutput(String(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void refresh();
  }, [api]);

  useEffect(() => {
    const path = selected?.[`${dossierKind}_md` as keyof WorktreeRow];
    if (!selected) {
      setDossierContent("Select a worktree to inspect task.md, progress.md, and lessons.md.");
      return;
    }
    if (selected.is_main || typeof path !== "string") {
      setDossierContent("The main checkout has no GitWarp dossier. Select an isolated sandbox to inspect task.md, progress.md, and lessons.md.");
      return;
    }
    let cancelled = false;
    void api
      .readDossier(path)
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
  }, [api, selected, dossierKind]);

  useEffect(() => {
    if (!selectedProject || !state) {
      return;
    }
    if (selectedWorktreePath && state.worktrees.some((worktree) => worktree.path === selectedWorktreePath)) {
      return;
    }
    const nextSelected = state.worktrees.find((worktree) => !worktree.is_main) ?? state.worktrees[0] ?? null;
    if (nextSelected) {
      setSelectedWorktreePath(nextSelected.path);
      setDossierKind("task");
    }
  }, [selectedProject, selectedWorktreePath, state]);

  const selectWorktree = (worktree: WorktreeRow) => {
    setSelectedWorktreePath(worktree.path);
    setDossierKind("task");
    setActiveTab("workspace");
  };

  const openProject = (project: ProjectSummary) => {
    setSelectedProject(project);
    setSelectedWorktreePath(null);
    setDossierKind("task");
    setActiveTab("workspace");
    setDossierContent("Select a sandbox to inspect task.md, progress.md, and lessons.md.");
  };

  const closeProject = () => {
    setSelectedProject(null);
    setSelectedWorktreePath(null);
    setDossierKind("task");
    setActiveTab("workspace");
    setDossierContent("Select a sandbox to inspect task.md, progress.md, and lessons.md.");
  };

  const runCommand = async (label: string, command: () => Promise<CommandResult>) => {
    setOperation({ status: "running", message: `${label} is running...` });
    writeOutput(`${label} is running...`);
    try {
      const result = await command();
      writeOutput(result);
      setOperation({ status: "success", message: `${label} completed.` });
      await refresh();
    } catch (error) {
      const message = String(error);
      writeOutput(message);
      setOperation({ status: "error", message });
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
        activeTab={activeTab}
        state={state}
        readonly={Boolean(state?.readonly)}
        busy={operationBusy}
        selected={selected}
        dossierKind={dossierKind}
        dossierContent={dossierContent}
        onDossierKindChange={setDossierKind}
        onSelectWorktree={selectWorktree}
        onRunStart={(input) => runCommand("Create sandbox", () => api.start(input))}
        onRunDispatch={(input) => runCommand("Prepare agent launch", () => api.dispatch(input))}
        onRunHandoff={(input) => runCommand("Record handoff", () => api.handoff(input))}
        onRunFinish={(worktree, progress) => runCommand("Finish and collapse", () => api.finishAndCollapse(worktree.path, progress))}
      />

      {output !== "Ready." ? <OutputPanel output={output} onClear={() => setOutput("Ready.")} /> : null}
    </main>
  );
}

interface RepositorySectionProps {
  activeTab: RepositoryTab;
  state: WebState | null;
  readonly: boolean;
  busy: boolean;
  selected: WorktreeRow | null;
  dossierKind: DossierKind;
  dossierContent: string;
  onDossierKindChange: (kind: DossierKind) => void;
  onSelectWorktree: (worktree: WorktreeRow) => void;
  onRunStart: (input: StartWorktreeInput) => void;
  onRunDispatch: (input: DispatchInput) => void;
  onRunHandoff: (input: HandoffInput) => void;
  onRunFinish: (worktree: WorktreeRow, progress: string) => void;
}

function RepositorySection({
  activeTab,
  state,
  readonly,
  busy,
  selected,
  dossierKind,
  dossierContent,
  onDossierKindChange,
  onSelectWorktree,
  onRunStart,
  onRunDispatch,
  onRunHandoff,
  onRunFinish,
}: RepositorySectionProps) {
  if (activeTab === "health") {
    return (
      <section className="tab-panel">
        <HealthPanel state={state} />
      </section>
    );
  }

  return (
    <OverviewPanel
      state={state}
      readonly={readonly}
      busy={busy}
      selected={selected}
      dossierKind={dossierKind}
      dossierContent={dossierContent}
      onSelectWorktree={onSelectWorktree}
      onDossierKindChange={onDossierKindChange}
      onRunStart={onRunStart}
      onRunDispatch={onRunDispatch}
      onRunHandoff={onRunHandoff}
      onRunFinish={onRunFinish}
    />
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
