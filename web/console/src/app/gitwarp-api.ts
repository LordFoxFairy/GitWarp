import type { BranchesPayload, CommandResult, DossierPayload, RepositoryFilePayload, RepositoryTreePayload, WebState } from "./types";

interface ApiErrorPayload {
  ok?: boolean;
  error?: string;
}

export interface StartWorktreeInput {
  agent_id: string;
  branch: string;
  base_branch?: string;
  purpose: string;
  instructions?: string[];
  instruction_profile?: string;
  instruction_mode?: "copy" | "symlink";
}

export interface DispatchInput {
  agent: "codex" | "claude";
  branch: string;
  base_branch?: string;
  purpose: string;
  instructions?: string[];
  instruction_profile?: string;
  instruction_mode?: "copy" | "symlink";
}

export interface HandoffInput {
  cwd: string;
  status: string;
  progress: string;
  lesson?: string;
}

export class GitWarpApi {
  constructor(private readonly token: string) {}

  getState(): Promise<WebState> {
    return this.request<WebState>("/api/state");
  }

  readDossier(path: string): Promise<DossierPayload> {
    return this.request<DossierPayload>(`/api/dossier?${new URLSearchParams({ path }).toString()}`);
  }

  getRepositoryTree(cwd: string, path = ""): Promise<RepositoryTreePayload> {
    return this.request<RepositoryTreePayload>(`/api/repository/tree?${new URLSearchParams({ cwd, path }).toString()}`);
  }

  getRepositoryFile(cwd: string, path: string): Promise<RepositoryFilePayload> {
    return this.request<RepositoryFilePayload>(`/api/repository/file?${new URLSearchParams({ cwd, path }).toString()}`);
  }

  getBranches(cwd: string, base?: string): Promise<BranchesPayload> {
    const params = new URLSearchParams({ cwd });
    if (base) {
      params.set("base", base);
    }
    const query = params.toString();
    return this.request<BranchesPayload>(`/api/branches${query ? `?${query}` : ""}`);
  }

  start(input: StartWorktreeInput): Promise<CommandResult> {
    return this.post("/api/start", input);
  }

  dispatch(input: DispatchInput): Promise<CommandResult> {
    return this.post("/api/dispatch", input);
  }

  handoff(input: HandoffInput): Promise<CommandResult> {
    return this.post("/api/handoff", input);
  }

  async finishAndCollapse(cwd: string, status: string, progress: string): Promise<CommandResult> {
    const challenge = await this.post("/api/confirmation", { action: "finish-collapse", cwd });
    return this.post("/api/finish", {
      cwd,
      status,
      progress,
      collapse: true,
      confirmation: challenge.confirmation,
    });
  }

  finishMergedTask(cwd: string, status: string, progress: string): Promise<CommandResult> {
    return this.post("/api/finish", {
      cwd,
      status,
      progress,
      collapse_merged: true,
    });
  }

  pruneBranch(cwd: string, branch: string, confirmBranch: string, baseBranch?: string): Promise<CommandResult> {
    return this.post("/api/prune-branch", {
      cwd,
      branch,
      confirm_branch: confirmBranch,
      ...(baseBranch ? { base_branch: baseBranch } : {}),
    });
  }

  private post(path: string, body: object): Promise<CommandResult> {
    return this.request<CommandResult>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(path, {
      ...init,
      headers: {
        ...init.headers,
        "X-GitWarp-Token": this.token,
      },
    });
    const payload = (await response.json()) as ApiErrorPayload;
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.error || `HTTP ${response.status}`);
    }
    return payload as T;
  }
}
