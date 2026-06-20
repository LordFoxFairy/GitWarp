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

export interface MountedInstruction {
  source: string;
  target: string;
  path: string;
  mode: "copy" | "symlink" | string;
  status: "copied" | "linked" | "existing" | string;
  sha256?: string;
  bytes?: number;
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
  instructions?: MountedInstruction[];
  instruction_profile?: string;
  instruction_mode?: "copy" | "symlink" | string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  repo_root: string;
  ledger_path: string;
  readonly: boolean;
  statusline: string;
  worktree_count: number;
  active_worktree_count: number;
  assigned_agent_count: number;
  doctor_finding_count: number;
  reconcile_finding_count: number;
}

export interface WebState {
  ok: boolean;
  readonly: boolean;
  repo_root: string;
  statusline: string;
  projects: ProjectSummary[];
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
export type RepositoryTab = "workspace" | "health";
