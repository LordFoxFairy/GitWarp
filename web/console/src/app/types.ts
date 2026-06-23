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
  branch_role?: "base" | "task" | string;
  base_branch?: string | null;
  agent_id?: string;
  status?: string;
  purpose?: string;
  task_title?: string;
  task_description?: string | null;
  target_agent?: "codex" | "claude" | "generic" | string;
  acceptance_criteria?: string[];
  verification_commands?: string[];
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
  branch_ref_count: number;
  worktree_count: number;
  active_worktree_count: number;
  assigned_agent_count: number;
  doctor_finding_count: number;
  reconcile_finding_count: number;
  next_action_count?: number;
  destructive_action_count?: number;
}

export interface NextAction {
  id: string;
  priority: number;
  severity: Severity;
  safety: "confirm_destructive" | "review" | "safe" | string;
  category: string;
  title: string;
  description: string;
  command: string;
  branch?: string | null;
  path?: string | null;
  role?: "base" | "task" | string | null;
  source?: {
    kind?: string;
    row_id?: string;
    recommended_action?: string;
    legacy_state?: string;
    managed_state?: string;
    commit_state?: string;
    cleanup_policy?: string;
    classification_basis?: ClassificationBasis;
  };
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
  matrix?: MatrixPayload;
  next_actions?: NextAction[];
  recommended_next?: string[];
}

export interface DossierPayload {
  ok: boolean;
  path: string;
  content: string;
}

export interface RepositoryBreadcrumb {
  name: string;
  path: string;
}

export interface RepositoryTreeEntry {
  name: string;
  path: string;
  type: "directory" | "file";
  mode: string;
  object: string;
}

export interface RepositoryTreePayload {
  ok: boolean;
  repo_root: string;
  checkout_path: string;
  branch?: string;
  commit?: string;
  path: string;
  breadcrumbs: RepositoryBreadcrumb[];
  entries: RepositoryTreeEntry[];
}

export interface RepositoryFilePayload {
  ok: boolean;
  repo_root: string;
  checkout_path: string;
  branch?: string;
  commit?: string;
  path: string;
  name: string;
  size: number;
  encoding: "utf-8" | "base64" | string;
  truncated: boolean;
  content: string;
}

export interface BranchRow {
  name: string;
  head: string;
  upstream?: string | null;
  is_default: boolean;
  base_branch?: string | null;
  branch_role?: "base" | "task" | string;
  has_worktree: boolean;
  worktree_path?: string | null;
  in_ledger: boolean;
  agent_id?: string | null;
  status?: string | null;
  merged_to_base: boolean;
  deletable: boolean;
  delete_blockers: string[];
  category: "base" | "active" | "merged" | "orphan" | string;
  managed_state?: string;
  commit_state?: string;
  cleanup_policy?: string;
  classification_basis?: ClassificationBasis;
}

export interface BranchesPayload {
  ok: boolean;
  repo_root: string;
  default_branch: string;
  merge_base: string;
  branches: BranchRow[];
  summary: {
    total: number;
    deletable: number;
    by_category: Record<string, number>;
  };
}

export interface MatrixGitState {
  branch_ref: boolean;
  worktree: boolean;
  merged_to_base?: boolean | null;
  prunable: boolean;
}

export interface MatrixGitWarpState {
  ledger: boolean;
  ledger_live: boolean;
  dossier_state: "none" | "ok" | "missing" | "stale" | "orphan" | string;
  dossier_path?: string | null;
  task_md?: string | null;
  progress_md?: string | null;
  lessons_md?: string | null;
}

export interface ClassificationBasis {
  base_branch?: string | null;
  head?: string | null;
  merged_to_base?: boolean | null;
  managed_by_gitwarp?: boolean;
  has_worktree?: boolean;
}

export interface MatrixRow {
  row_id: string;
  branch: string;
  category: "main" | "base" | "active_task" | "merged_task" | "merged_ref" | "orphan_ref" | "untracked_worktree" | "stale_ledger" | "orphan_dossier" | "inspect" | string;
  legacy_state: "current" | "deprecated" | "legacy" | string;
  recommended_action: "use_main" | "switch" | "create_base_worktree" | "finish_collapse_merged" | "adopt" | "repair_metadata" | "prune_branch" | "inspect" | string;
  next_command?: string | null;
  path?: string | null;
  head?: string | null;
  role?: "base" | "task" | string | null;
  managed_state?: string;
  commit_state?: string;
  cleanup_policy?: string;
  classification_basis?: ClassificationBasis;
  agent_id?: string | null;
  status?: string | null;
  purpose?: string | null;
  git: MatrixGitState;
  gitwarp: MatrixGitWarpState;
}

export interface MatrixPayload {
  ok: boolean;
  repo_root: string;
  ledger_path: string;
  default_branch: string;
  merge_base: string;
  statusline: string;
  sources: {
    git_branch_refs: number;
    git_worktrees: number;
    ledger_entries: number;
    dossier_dirs: number;
    reconcile_findings: number;
  };
  summary: {
    rows: number;
    active_gitwarp_tasks: number;
    untracked_worktrees: number;
    stale_ledger_entries: number;
    merged_gitwarp_tasks: number;
    prunable_branch_refs: number;
    orphan_branch_refs: number;
    orphan_dossiers: number;
  };
  rows: MatrixRow[];
}

export interface CommandResult {
  ok: boolean;
  [key: string]: unknown;
}

export type DossierKind = "task" | "progress" | "lessons";
export type RepositoryTab = "code" | "metadata" | "branches" | "health";
