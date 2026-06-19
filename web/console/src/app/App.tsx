import { useEffect, useMemo, useState } from "react";
import { ActionPanel } from "./components/ActionPanel";
import { Header } from "./components/Header";
import { InspectorPanel } from "./components/InspectorPanel";
import { OutputPanel } from "./components/OutputPanel";
import { SummaryStrip } from "./components/SummaryStrip";
import { WorktreeBoard } from "./components/WorktreeBoard";
import { GitWarpApi } from "./gitwarp-api";
import type { CommandResult, DossierKind, WebState, WorktreeRow } from "./types";

interface AppProps {
  token: string;
}

export function App({ token }: AppProps) {
  const api = useMemo(() => new GitWarpApi(token), [token]);
  const [state, setState] = useState<WebState | null>(null);
  const [selected, setSelected] = useState<WorktreeRow | null>(null);
  const [dossierKind, setDossierKind] = useState<DossierKind>("task");
  const [dossierContent, setDossierContent] = useState("Select a non-main worktree to inspect task.md, progress.md, and lessons.md.");
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

  return (
    <main className="app-shell">
      <Header readonly={Boolean(state?.readonly)} loading={loading} onRefresh={() => void refresh()} />
      <SummaryStrip state={state} />
      <p className="repo-path">{state?.repo_root ?? "Repository state is loading..."}</p>

      <section className="manager-grid">
        <ActionPanel
          readonly={Boolean(state?.readonly)}
          onStart={(input) => runCommand(() => api.start(input))}
          onDispatch={(input) => runCommand(() => api.dispatch(input))}
        />
        <WorktreeBoard
          readonly={Boolean(state?.readonly)}
          worktrees={state?.worktrees ?? []}
          onSelect={selectWorktree}
          onHandoff={(input) => runCommand(() => api.handoff(input))}
          onFinish={(worktree, progress) => runCommand(() => api.finishAndCollapse(worktree.path, progress))}
        />
        <InspectorPanel
          state={state}
          selected={selected}
          dossierKind={dossierKind}
          dossierContent={dossierContent}
          onDossierKindChange={setDossierKind}
        />
      </section>

      <OutputPanel output={output} onClear={() => setOutput("Ready.")} />
    </main>
  );
}
