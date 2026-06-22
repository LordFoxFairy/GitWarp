import { useEffect, useRef, useState } from "react";
import { Button, Label } from "@primer/react";
import { FileDirectoryIcon, FileIcon, GitBranchIcon, RepoIcon } from "@primer/octicons-react";
import type { GitWarpApi } from "../gitwarp-api";
import type { RepositoryFilePayload, RepositoryTreeEntry, RepositoryTreePayload, WebState, WorktreeRow } from "../types";
import { WorktreePicker, defaultWorktree } from "./WorktreePicker";

interface CodePanelProps {
  api: GitWarpApi;
  state: WebState | null;
  selected: WorktreeRow | null;
  onSelectWorktree: (worktree: WorktreeRow) => void;
  onSelectTaskCandidate: (branch: string, baseBranch: string) => void;
  onCreateBaseCheckout: (branch: string) => Promise<void>;
  onViewMetadata: () => void;
}

export function CodePanel({ api, state, selected, onSelectWorktree, onSelectTaskCandidate, onCreateBaseCheckout, onViewMetadata }: CodePanelProps) {
  const worktrees = state?.worktrees ?? [];
  const selectedWorktree = selected && worktrees.some((worktree) => worktree.path === selected.path) ? selected : defaultWorktree(worktrees);
  const [currentPath, setCurrentPath] = useState("");
  const [tree, setTree] = useState<RepositoryTreePayload | null>(null);
  const [file, setFile] = useState<RepositoryFilePayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const fileRequestId = useRef(0);

  useEffect(() => {
    fileRequestId.current += 1;
    setCurrentPath("");
    setFile(null);
  }, [selectedWorktree?.path]);

  useEffect(() => {
    if (!selectedWorktree) {
      setTree(null);
      setFile(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    void api
      .getRepositoryTree(selectedWorktree.path, currentPath)
      .then((payload) => {
        if (!cancelled) {
          setTree(payload);
        }
      })
      .catch((caught) => {
        if (!cancelled) {
          setTree(null);
          setError(String(caught));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [api, selectedWorktree, currentPath]);

  const openDirectory = (path: string) => {
    setCurrentPath(path);
    setFile(null);
  };

  const openFile = async (entry: RepositoryTreeEntry) => {
    if (!selectedWorktree) {
      return;
    }
    const requestId = fileRequestId.current + 1;
    fileRequestId.current = requestId;
    setLoading(true);
    setError("");
    try {
      const payload = await api.getRepositoryFile(selectedWorktree.path, entry.path);
      if (fileRequestId.current === requestId) {
        setFile(payload);
      }
    } catch (caught) {
      if (fileRequestId.current === requestId) {
        setFile(null);
        setError(String(caught));
      }
    } finally {
      if (fileRequestId.current === requestId) {
        setLoading(false);
      }
    }
  };

  return (
    <section className="tab-panel code-console" aria-label="Repository code browser" aria-busy={loading}>
      <div className="repository-content-grid">
        {!selectedWorktree ? (
          <p className="status-note">Select or create a base checkout before browsing repository files.</p>
        ) : null}
        <div className="repository-main-column">
          <div className="repo-toolbar" aria-label="Worktree selection">
            <WorktreePicker
              worktrees={worktrees}
              matrixRows={state?.matrix?.rows ?? []}
              selected={selectedWorktree}
              onSelectWorktree={onSelectWorktree}
              onSelectTaskCandidate={onSelectTaskCandidate}
              onCreateBaseCheckout={onCreateBaseCheckout}
            />
            <div className="repo-toolbar-status">
              <Label variant={selectedWorktree?.is_main ? "secondary" : "accent"}>
                {selectedWorktree?.is_main ? "main checkout" : selectedWorktree?.status || "active"}
              </Label>
              <span>{selectedWorktree?.agent_id || "unassigned agent"}</span>
            </div>
          </div>

          <div className="panel code-browser">
            <div className="code-browser-head">
              <div className="commit-strip">
                <RepoIcon size={16} />
                <strong>{selectedWorktree?.branch || "Repository files"}</strong>
                <span>{tree?.commit ? `HEAD ${tree.commit.slice(0, 7)}` : "Tracked files at selected HEAD"}</span>
              </div>
              <Label variant="secondary">{loading ? "loading" : formatLineCount(tree?.entries.length ?? 0, "item")}</Label>
            </div>

            {loading ? <p className="status-note" role="status">Loading repository contents...</p> : null}
            {error ? <p className="inline-error" role="alert">{error}</p> : null}
            {file ? (
              <FileViewer file={file} tree={tree} onBackToDirectory={() => setFile(null)} onOpenPath={openDirectory} />
            ) : (
              <>
                <Breadcrumbs tree={tree} onOpenPath={openDirectory} />
                <FileList entries={tree?.entries ?? []} loading={loading} onOpenDirectory={openDirectory} onOpenFile={openFile} />
              </>
            )}
          </div>
        </div>

        <WorktreeAbout worktree={selectedWorktree} tree={tree} onViewMetadata={onViewMetadata} />
      </div>
    </section>
  );
}

function WorktreeAbout({
  worktree,
  tree,
  onViewMetadata,
}: {
  worktree: WorktreeRow | null;
  tree: RepositoryTreePayload | null;
  onViewMetadata: () => void;
}) {
  if (!worktree) {
    return (
      <aside className="repo-about panel" aria-label="Worktree about">
        <div className="panel-title">
          <span>About</span>
          <h2>No worktree selected</h2>
        </div>
        <p className="empty-state">Create or select a worktree to view its agent, purpose, and progress.</p>
      </aside>
    );
  }

  return (
    <aside className="repo-about panel" aria-label="Worktree about">
      <div className="panel-title">
        <span>About</span>
        <h2>{worktree.is_main ? "Main repository" : "Isolated sandbox"}</h2>
      </div>
      <p className="about-purpose">{worktree.purpose || (worktree.is_main ? "Public checkout for coordination and review." : "No purpose recorded.")}</p>
      <dl className="about-list">
        <div>
          <dt>
            <GitBranchIcon size={14} /> Worktree
          </dt>
          <dd>{worktree.branch || "unknown"}</dd>
        </div>
        <div>
          <dt>Role</dt>
          <dd>{worktree.branch_role || (worktree.is_main ? "base" : "task")}</dd>
        </div>
        <div>
          <dt>Parent Base</dt>
          <dd>{worktree.base_branch || (worktree.is_main || worktree.branch_role === "base" ? "none" : "main")}</dd>
        </div>
        <div>
          <dt>Agent</dt>
          <dd>{worktree.agent_id || "unassigned"}</dd>
        </div>
        <div>
          <dt>Progress</dt>
          <dd>{worktree.latest_progress || "No progress recorded."}</dd>
        </div>
        <div>
          <dt>Commit</dt>
          <dd>{tree?.commit ? tree.commit.slice(0, 12) : worktree.commit?.slice(0, 12) || "unknown"}</dd>
        </div>
        <div>
          <dt>Path</dt>
          <dd>{worktree.path}</dd>
        </div>
      </dl>
      {!worktree.is_main ? (
        <p className="form-hint">Use the Metadata tab for task.md, progress.md, lessons.md, handoff, and finish actions.</p>
      ) : (
        <p className="form-hint">Use Create Sandbox from Metadata before making isolated or concurrent edits.</p>
      )}
      <Button type="button" onClick={onViewMetadata}>
        View metadata
      </Button>
    </aside>
  );
}

function Breadcrumbs({ tree, onOpenPath }: { tree: RepositoryTreePayload | null; onOpenPath: (path: string) => void }) {
  const breadcrumbs = tree?.breadcrumbs ?? [{ name: "root", path: "" }];
  return (
    <nav className="repo-breadcrumbs" aria-label="Repository path">
      {breadcrumbs.map((crumb, index) => (
        <span key={`${crumb.path}:${index}`}>
          {index > 0 ? <span className="breadcrumb-separator">/</span> : null}
          <button type="button" onClick={() => onOpenPath(crumb.path)}>
            {crumb.name}
          </button>
        </span>
      ))}
    </nav>
  );
}

function FileBreadcrumbs({
  file,
  tree,
  onOpenPath,
}: {
  file: RepositoryFilePayload;
  tree: RepositoryTreePayload | null;
  onOpenPath: (path: string) => void;
}) {
  const breadcrumbs = [...(tree?.breadcrumbs ?? [{ name: "root", path: "" }]), { name: file.name, path: file.path }];
  return (
    <nav className="repo-breadcrumbs" aria-label="Repository file path">
      {breadcrumbs.map((crumb, index) => {
        const isFile = index === breadcrumbs.length - 1;
        return (
          <span key={`${crumb.path}:${index}`}>
            {index > 0 ? <span className="breadcrumb-separator">/</span> : null}
            {isFile ? (
              <strong>{crumb.name}</strong>
            ) : (
              <button type="button" onClick={() => onOpenPath(crumb.path)}>
                {crumb.name}
              </button>
            )}
          </span>
        );
      })}
    </nav>
  );
}

function FileList({
  entries,
  loading,
  onOpenDirectory,
  onOpenFile,
}: {
  entries: RepositoryTreeEntry[];
  loading: boolean;
  onOpenDirectory: (path: string) => void;
  onOpenFile: (entry: RepositoryTreeEntry) => void;
}) {
  if (entries.length === 0) {
    return <p className="empty-state">{loading ? "Loading repository tree..." : "This directory has no tracked files."}</p>;
  }
  return (
    <div className="file-list" aria-label="Tracked repository files">
      {entries.map((entry) => {
        const isDirectory = entry.type === "directory";
        return (
          <button
            className="file-row"
            type="button"
            key={entry.path}
            onClick={() => (isDirectory ? onOpenDirectory(entry.path) : onOpenFile(entry))}
          >
            <span className="file-row-main">
              {isDirectory ? <FileDirectoryIcon size={16} /> : <FileIcon size={16} />}
              <span>{entry.name}</span>
            </span>
            <span className="file-row-type">{isDirectory ? "dir" : "file"}</span>
          </button>
        );
      })}
    </div>
  );
}

function FileViewer({
  file,
  tree,
  onBackToDirectory,
  onOpenPath,
}: {
  file: RepositoryFilePayload;
  tree: RepositoryTreePayload | null;
  onBackToDirectory: () => void;
  onOpenPath: (path: string) => void;
}) {
  const lines = splitFileLines(file.content);
  return (
    <article className="file-viewer" aria-label="Repository file viewer">
      <div className="file-viewer-head">
        <div>
          <FileBreadcrumbs file={file} tree={tree} onOpenPath={onOpenPath} />
          <p className="form-hint">
            {file.encoding === "utf-8" ? `${file.size} bytes · contents with line numbers` : `${file.size} bytes · ${file.encoding} encoded preview`}
          </p>
        </div>
        <Button type="button" onClick={onBackToDirectory}>
          Back to directory
        </Button>
      </div>
      {file.encoding === "utf-8" ? (
        <ol className="code-lines">
          {lines.map((line, index) => (
            <li key={`${index}:${line}`}>
              <span className="line-number">{index + 1}</span>
              <code>{line || " "}</code>
            </li>
          ))}
        </ol>
      ) : (
        <pre className="readout">{file.content}</pre>
      )}
    </article>
  );
}

function splitFileLines(content: string): string[] {
  return content.replace(/\r\n/g, "\n").split("\n");
}

function formatLineCount(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? "" : "s"}`;
}
