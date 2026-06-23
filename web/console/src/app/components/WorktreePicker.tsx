import type { ChangeEvent } from "react";
import { Select } from "@primer/react";
import type { MatrixRow, WorktreeRow } from "../types";

interface WorktreePickerProps {
  worktrees: WorktreeRow[];
  matrixRows: MatrixRow[];
  selected: WorktreeRow | null;
  onSelectWorktree: (worktree: WorktreeRow) => void;
  onSelectTaskCandidate: (branch: string, baseBranch: string) => void;
  onCreateBaseCheckout: (branch: string) => Promise<void>;
}

export function WorktreePicker({ worktrees, matrixRows, selected, onSelectWorktree, onSelectTaskCandidate, onCreateBaseCheckout }: WorktreePickerProps) {
  const bases = baseWorktrees(worktrees);
  const selectedBase = baseForSelection(worktrees, selected);
  const tasks = taskWorktreesForBase(worktrees, selectedBase);
  const baseCandidates = baseCandidateRows(matrixRows, worktrees);
  const taskCandidates = taskCandidateRows(matrixRows, worktrees, selectedBase);
  const taskValue = selected && isTaskWorktree(selected) ? selected.path : "__base__";

  const changeBase = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = event.currentTarget.value;
    if (value.startsWith("candidate:")) {
      void onCreateBaseCheckout(value.slice("candidate:".length));
      return;
    }
    const next = worktrees.find((worktree) => worktree.path === value);
    if (next) {
      onSelectWorktree(next);
    }
  };

  const changeTask = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = event.currentTarget.value;
    if (value === "__base__") {
      if (selectedBase) {
        onSelectWorktree(selectedBase);
      }
      return;
    }
    if (value.startsWith("candidate:")) {
      const row = taskCandidates.find((candidate) => candidate.branch === value.slice("candidate:".length));
      if (!row) {
        return;
      }
      const baseBranch = row.classification_basis?.base_branch || (row.role === "base" ? row.branch : selectedBase?.branch || "main");
      const resolvedBaseBranch = baseBranch || "main";
      onSelectTaskCandidate(row.branch, resolvedBaseBranch);
      const existingBase = baseWorktrees(worktrees).find((worktree) => worktree.branch === resolvedBaseBranch);
      if (existingBase) {
        onSelectWorktree(existingBase);
        return;
      }
      void onCreateBaseCheckout(resolvedBaseBranch);
      return;
    }
    const next = tasks.find((worktree) => worktree.path === value);
    if (next) {
      onSelectWorktree(next);
    }
  };

  return (
    <div className="workspace-switcher">
      <label className="worktree-picker">
        Base branch
        <Select value={selectedBase?.path ?? ""} onChange={changeBase} disabled={bases.length === 0 && baseCandidates.length === 0} block>
          {bases.map((worktree) => (
            <Select.Option key={worktree.path} value={worktree.path}>
              {formatBaseOption(worktree)}
            </Select.Option>
          ))}
          {baseCandidates.map((row) => (
            <Select.Option key={`candidate:${row.branch}`} value={`candidate:${row.branch}`}>
              {`Create base checkout · ${row.branch}`}
            </Select.Option>
          ))}
        </Select>
      </label>
      <label className="worktree-picker">
        Task worktree
        <Select value={taskValue} onChange={changeTask} disabled={!selectedBase && taskCandidates.length === 0 && tasks.length === 0} block>
          <Select.Option value="__base__">Base checkout only</Select.Option>
          {tasks.map((worktree) => (
            <Select.Option key={worktree.path} value={worktree.path}>
              {formatTaskOption(worktree)}
            </Select.Option>
          ))}
          {taskCandidates.map((row) => (
            <Select.Option key={`candidate:${row.branch}`} value={`candidate:${row.branch}`}>
              {formatTaskCandidateOption(row)}
            </Select.Option>
          ))}
        </Select>
      </label>
    </div>
  );
}

export function defaultWorktree(worktrees: WorktreeRow[]): WorktreeRow | null {
  return baseWorktrees(worktrees)[0] ?? worktrees[0] ?? null;
}

export function isBaseWorktree(worktree: WorktreeRow): boolean {
  return worktree.is_main || worktree.branch_role === "base";
}

export function isTaskWorktree(worktree: WorktreeRow): boolean {
  return !isBaseWorktree(worktree);
}

export function baseWorktrees(worktrees: WorktreeRow[]): WorktreeRow[] {
  return worktrees.filter(isBaseWorktree);
}

export function taskWorktreesForBase(worktrees: WorktreeRow[], base: WorktreeRow | null): WorktreeRow[] {
  if (!base?.branch) {
    return [];
  }
  return worktrees.filter((worktree) => isTaskWorktree(worktree) && (worktree.base_branch || "main") === base.branch);
}

export function baseForSelection(worktrees: WorktreeRow[], selected: WorktreeRow | null): WorktreeRow | null {
  if (selected && isBaseWorktree(selected)) {
    return selected;
  }
  const selectedBaseBranch = selected?.base_branch || "main";
  return baseWorktrees(worktrees).find((worktree) => worktree.branch === selectedBaseBranch) ?? defaultWorktree(worktrees);
}

function baseCandidateRows(matrixRows: MatrixRow[], worktrees: WorktreeRow[]): MatrixRow[] {
  const knownBranches = new Set(baseWorktrees(worktrees).map((worktree) => worktree.branch));
  return matrixRows.filter(
    (row) =>
      row.recommended_action === "create_base_worktree" &&
      Boolean(row.branch) &&
      !knownBranches.has(row.branch),
  );
}

function taskCandidateRows(matrixRows: MatrixRow[], worktrees: WorktreeRow[], selectedBase: WorktreeRow | null): MatrixRow[] {
  const knownBranches = new Set(worktrees.map((worktree) => worktree.branch));
  return matrixRows.filter((row) => {
    if (!row.git.branch_ref || row.git.worktree || !row.branch || knownBranches.has(row.branch)) {
      return false;
    }
    if (row.category === "main" || row.role === "base") {
      return false;
    }
    const baseBranch = row.classification_basis?.base_branch || selectedBase?.branch || "main";
    return baseBranch === (selectedBase?.branch || "main");
  });
}

function formatBaseOption(worktree: WorktreeRow): string {
  const branch = worktree.branch || "unknown";
  if (worktree.is_main) {
    return `${branch} · main checkout`;
  }
  return `${branch} · base`;
}

function formatTaskOption(worktree: WorktreeRow): string {
  const branch = worktree.branch || "unknown";
  return `${branch} · ${worktree.agent_id || "unassigned"} · ${worktree.status || "active"}`;
}

function formatTaskCandidateOption(row: MatrixRow): string {
  const baseBranch = row.classification_basis?.base_branch || "main";
  return `${row.branch} · checkout/create candidate via ${baseBranch}`;
}
