import type { ChangeEvent } from "react";
import { Select } from "@primer/react";
import type { WorktreeRow } from "../types";

interface WorktreePickerProps {
  worktrees: WorktreeRow[];
  selected: WorktreeRow | null;
  onSelectWorktree: (worktree: WorktreeRow) => void;
}

export function WorktreePicker({ worktrees, selected, onSelectWorktree }: WorktreePickerProps) {
  const changeWorktree = (event: ChangeEvent<HTMLSelectElement>) => {
    const next = worktrees.find((worktree) => worktree.path === event.currentTarget.value);
    if (next) {
      onSelectWorktree(next);
    }
  };

  return (
    <div className="workspace-switcher">
      <label className="worktree-picker">
        Worktree
        <Select value={selected?.path ?? ""} onChange={changeWorktree} disabled={worktrees.length === 0} block>
          {worktrees.map((worktree) => (
            <Select.Option key={worktree.path} value={worktree.path}>
              {formatWorktreeOption(worktree)}
            </Select.Option>
          ))}
        </Select>
      </label>
    </div>
  );
}

export function defaultWorktree(worktrees: WorktreeRow[]): WorktreeRow | null {
  return worktrees.find((worktree) => worktree.is_main) ?? worktrees.find((worktree) => !worktree.is_main) ?? worktrees[0] ?? null;
}

function formatWorktreeOption(worktree: WorktreeRow): string {
  const branch = worktree.branch || "unknown";
  if (worktree.is_main) {
    return `${branch} · main checkout`;
  }
  return `${branch} · ${worktree.agent_id || "unassigned"} · ${worktree.status || "active"}`;
}
