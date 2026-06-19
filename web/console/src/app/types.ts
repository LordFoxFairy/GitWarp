export type Severity = "error" | "warning" | "info" | string;

export interface Finding {
  code?: string;
  severity?: Severity;
  message?: string;
  description?: string;
}

export interface FindingSummary {
  total?: number;
  by_code?: Record<string, number>;
}

export interface FindingGroup {
  cached?: boolean;
  cache_age_seconds?: number;
  findings?: Finding[];
  summary?: FindingSummary;
}

export interface DispatchMetadata {
  launch_command?: string;
  launch_preview?: string;
}

export interface WorktreeRow {
  path: string;
  branch: string;
  commit?: string;
  is_main?: boolean;
  agent_id?: string;
  status?: string;
  purpose?: string;
  latest_progress?: string;
  task_md?: string;
  progress_md?: string;
  lessons_md?: string;
  dispatch?: DispatchMetadata;
}

export interface WebState {
  ok: boolean;
  readonly: boolean;
  repo_root: string;
  statusline: string;
  worktrees: WorktreeRow[];
  doctor?: FindingGroup;
  reconcile?: FindingGroup;
}

export interface DossierPayload {
  ok: boolean;
  path: string;
  content: string;
}

export interface CommandResult {
  ok: boolean;
  [key: string]: unknown;
}

export type DossierKind = "task" | "progress" | "lessons";
