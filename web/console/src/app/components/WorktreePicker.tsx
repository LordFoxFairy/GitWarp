import type { ChangeEvent } from "react";
import { Select } from "@primer/react";
import type { WorktreeRow } from "../types";

interface WorktreePickerProps {
  worktrees: WorktreeRow[];
  selected: WorktreeRow | null;
  onSelectWorktree: (worktree: WorktreeRow) => void;
}

export function WorktreePicker({ worktrees, selected, onSelectWorktree }: WorktreePickerProps) {
  const bases = baseWorktrees(worktrees);
  const selectedBase = baseForSelection(worktrees, selected);
  const tasks = taskWorktreesForBase(worktrees, selectedBase);
  const taskValue = selected && isTaskWorktree(selected) ? selected.path : "__base__";

  const changeBase = (event: ChangeEvent<HTMLSelectElement>) => {
    const next = worktrees.find((worktree) => worktree.path === event.currentTarget.value);
    if (next) {
      onSelectWorktree(next);
    }
  };

  const changeTask = (event: ChangeEvent<HTMLSelectElement>) => {
    if (event.currentTarget.value === "__base__") {
      if (selectedBase) {
        onSelectWorktree(selectedBase);
      }
      return;
    }
    const next = tasks.find((worktree) => worktree.path === event.currentTarget.value);
    if (next) {
      onSelectWorktree(next);
    }
  };

  return (
    <div className="workspace-switcher">
      <label className="worktree-picker">
        Base branch
        <Select value={selectedBase?.path ?? ""} onChange={changeBase} disabled={bases.length === 0} block>
          {bases.map((worktree) => (
            <Select.Option key={worktree.path} value={worktree.path}>
              {formatBaseOption(worktree)}
            </Select.Option>
          ))}
        </Select>
      </label>
      <label className="worktree-picker">
        Task worktree
        <Select value={taskValue} onChange={changeTask} disabled={!selectedBase || tasks.length === 0} block>
          <Select.Option value="__base__">Base checkout only</Select.Option>
          {tasks.map((worktree) => (
            <Select.Option key={worktree.path} value={worktree.path}>
              {formatTaskOption(worktree)}
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
