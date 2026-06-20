import { useEffect, useRef, useState } from "react";
import { Button, Label } from "@primer/react";
import { FileDirectoryIcon, FileIcon } from "@primer/octicons-react";
import type { GitWarpApi } from "../gitwarp-api";
import type { RepositoryFilePayload, RepositoryTreeEntry, RepositoryTreePayload, WebState, WorktreeRow } from "../types";
import { WorktreePicker, defaultWorktree } from "./WorktreePicker";

interface CodePanelProps {
  api: GitWarpApi;
  state: WebState | null;
  selected: WorktreeRow | null;
  onSelectWorktree: (worktree: WorktreeRow) => void;
}

export function CodePanel({ api, state, selected, onSelectWorktree }: CodePanelProps) {
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
      <WorktreePicker worktrees={worktrees} selected={selectedWorktree} onSelectWorktree={onSelectWorktree} />

      <div className="code-browser-grid">
        <div className="panel code-browser">
          <div className="panel-title row">
            <div>
              <span>Code</span>
              <h2>{selectedWorktree?.branch || "Repository files"}</h2>
              <p className="subtle">{tree?.commit ? `HEAD ${tree.commit.slice(0, 7)}` : "Browse tracked files at the selected worktree HEAD."}</p>
            </div>
            <Label variant="secondary">{loading ? "loading" : `${tree?.entries.length ?? 0} items`}</Label>
          </div>

          <Breadcrumbs tree={tree} onOpenPath={openDirectory} />

          {loading ? <p className="status-note" role="status">Loading repository contents...</p> : null}
          {error ? <p className="inline-error" role="alert">{error}</p> : null}
          <FileList entries={tree?.entries ?? []} loading={loading} onOpenDirectory={openDirectory} onOpenFile={openFile} />
        </div>

        <FilePreview file={file} />
      </div>
    </section>
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
            <span className="file-name">
              {isDirectory ? <FileDirectoryIcon size={16} /> : <FileIcon size={16} />}
              {entry.name}
            </span>
            <span className="file-kind">{isDirectory ? "Directory" : "File"}</span>
            <span className="file-sha">{entry.object.slice(0, 7)}</span>
          </button>
        );
      })}
    </div>
  );
}

function FilePreview({ file }: { file: RepositoryFilePayload | null }) {
  if (!file) {
    return (
      <aside className="panel file-preview" aria-label="File preview">
        <div className="panel-title">
          <span>Preview</span>
          <h2>Select a file</h2>
        </div>
        <p className="empty-state">Open a file from the Code tab to inspect its committed contents.</p>
      </aside>
    );
  }

  const isText = file.encoding === "utf-8";
  return (
    <aside className="panel file-preview" aria-label="File preview">
      <div className="panel-title row">
        <div>
          <span>Preview</span>
          <h2>{file.name}</h2>
          <p className="subtle">
            {formatBytes(file.size)} {file.truncated ? "· truncated" : ""}
          </p>
        </div>
        <Label variant={isText ? "success" : "attention"}>{file.encoding}</Label>
      </div>
      {isText ? (
        <pre className="file-readout">
          <code>{file.content}</code>
        </pre>
      ) : (
        <p className="empty-state">Binary content is not rendered inline. The API returns a base64 preview for automation.</p>
      )}
    </aside>
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
