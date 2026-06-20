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

export function App({ token }: AppProps) {
  const api = useMemo(() => new GitWarpApi(token), [token]);
  const [state, setState] = useState<WebState | null>(null);
  const [selectedProject, setSelectedProject] = useState<ProjectSummary | null>(null);
  const [selected, setSelected] = useState<WorktreeRow | null>(null);
  const [dossierKind, setDossierKind] = useState<DossierKind>("task");
  const [dossierContent, setDossierContent] = useState("Select a non-main worktree to inspect task.md, progress.md, and lessons.md.");
  const [activeTab, setActiveTab] = useState<RepositoryTab>("workspace");
  const [output, setOutput] = useState("Ready.");
  const [loading, setLoading] = useState(false);

  const writeOutput = (payload: CommandResult | string) => {
    setOutput(typeof payload === "string" ? payload : JSON.stringify(payload, null, 2));
  };

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
    void api
      .readDossier(path)
      .then((payload) => setDossierContent(payload.content))
      .catch((error) => writeOutput(String(error)));
  }, [api, selected, dossierKind]);

  useEffect(() => {
    if (!selectedProject || !state) {
      return;
    }
    if (selected && state.worktrees.some((worktree) => worktree.path === selected.path)) {
      return;
    }
    const nextSelected = state.worktrees.find((worktree) => !worktree.is_main) ?? state.worktrees[0] ?? null;
    if (nextSelected) {
      setSelected(nextSelected);
      setDossierKind("task");
    }
  }, [selected, selectedProject, state]);

  const selectWorktree = (worktree: WorktreeRow) => {
    setSelected(worktree);
    setDossierKind("task");
    setActiveTab("workspace");
  };

  const openProject = (project: ProjectSummary) => {
    setSelectedProject(project);
    setSelected(null);
    setDossierKind("task");
    setActiveTab("workspace");
    setDossierContent("Select a sandbox to inspect task.md, progress.md, and lessons.md.");
  };

  const closeProject = () => {
    setSelectedProject(null);
    setSelected(null);
    setDossierKind("task");
    setActiveTab("workspace");
    setDossierContent("Select a sandbox to inspect task.md, progress.md, and lessons.md.");
  };

  const runCommand = async (operation: () => Promise<CommandResult>) => {
    try {
      const result = await operation();
      writeOutput(result);
      await refresh();
    } catch (error) {
      writeOutput(String(error));
    }
  };

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
      <RepositorySection
        activeTab={activeTab}
        state={state}
        readonly={Boolean(state?.readonly)}
        selected={selected}
        dossierKind={dossierKind}
        dossierContent={dossierContent}
        onDossierKindChange={setDossierKind}
        onSelectWorktree={selectWorktree}
        onRunStart={(input) => runCommand(() => api.start(input))}
        onRunDispatch={(input) => runCommand(() => api.dispatch(input))}
        onRunHandoff={(input) => runCommand(() => api.handoff(input))}
        onRunFinish={(worktree, progress) => runCommand(() => api.finishAndCollapse(worktree.path, progress))}
      />

      {output !== "Ready." ? <OutputPanel output={output} onClear={() => setOutput("Ready.")} /> : null}
    </main>
  );
}

interface RepositorySectionProps {
  activeTab: RepositoryTab;
  state: WebState | null;
  readonly: boolean;
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
