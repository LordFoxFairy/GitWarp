import { useEffect, useMemo, useState } from "react";
import { ActionPanel } from "./components/ActionPanel";
import { DossierPanel } from "./components/DossierPanel";
import { HealthPanel } from "./components/HealthPanel";
import { Header } from "./components/Header";
import { OutputPanel } from "./components/OutputPanel";
import { ProjectDirectory } from "./components/ProjectDirectory";
import { RepositoryTabs } from "./components/RepositoryTabs";
import { SummaryStrip } from "./components/SummaryStrip";
import { WorktreeBoard } from "./components/WorktreeBoard";
import { GitWarpApi } from "./gitwarp-api";
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
  const [activeTab, setActiveTab] = useState<RepositoryTab>("overview");
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
    if (!selected || typeof path !== "string") {
      return;
    }
    void api
      .readDossier(path)
      .then((payload) => setDossierContent(payload.content))
      .catch((error) => writeOutput(String(error)));
  }, [api, selected, dossierKind]);

  const selectWorktree = (worktree: WorktreeRow) => {
    setSelected(worktree);
    setDossierKind("task");
    setActiveTab("worktrees");
  };

  const openProject = (project: ProjectSummary) => {
    setSelectedProject(project);
    setSelected(null);
    setDossierKind("task");
    setActiveTab("overview");
    setDossierContent("Select a sandbox to inspect task.md, progress.md, and lessons.md.");
  };

  const closeProject = () => {
    setSelectedProject(null);
    setSelected(null);
    setDossierKind("task");
    setActiveTab("overview");
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
    <main className="app-shell">
      <Header
        readonly={Boolean(state?.readonly)}
        loading={loading}
        title="Project Detail"
        description={selectedProject.repo_root}
        onRefresh={() => void refresh()}
      />
      <button className="button quiet back-button" type="button" onClick={closeProject}>
        Back to Project Directory
      </button>
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
  onRunStart: Parameters<typeof ActionPanel>[0]["onStart"];
  onRunDispatch: Parameters<typeof ActionPanel>[0]["onDispatch"];
  onRunHandoff: Parameters<typeof WorktreeBoard>[0]["onHandoff"];
  onRunFinish: Parameters<typeof WorktreeBoard>[0]["onFinish"];
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
  if (activeTab === "agents") {
    return (
      <section className="tab-panel agent-panel" aria-label="Agent actions">
        <ActionPanel readonly={readonly} onStart={onRunStart} onDispatch={onRunDispatch} />
      </section>
    );
  }

  if (activeTab === "health") {
    return (
      <section className="tab-panel">
        <HealthPanel state={state} />
      </section>
    );
  }

  if (activeTab === "worktrees") {
    return (
      <section className="tab-panel worktree-detail-grid">
        <WorktreeBoard
          readonly={readonly}
          worktrees={state?.worktrees ?? []}
          onSelect={onSelectWorktree}
          onHandoff={onRunHandoff}
          onFinish={onRunFinish}
        />
        <DossierPanel
          selected={selected}
          dossierKind={dossierKind}
          dossierContent={dossierContent}
          onDossierKindChange={onDossierKindChange}
        />
      </section>
    );
  }

  return (
    <section className="tab-panel overview-grid">
      <SummaryStrip state={state} />
      <HealthPanel state={state} />
    </section>
  );
}
