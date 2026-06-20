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
        Current worktree
        <Select value={selected?.path ?? ""} onChange={changeWorktree} disabled={worktrees.length === 0} block>
          {worktrees.map((worktree) => (
            <Select.Option key={worktree.path} value={worktree.path}>
              {worktree.branch || "unknown"} {worktree.is_main ? "(main)" : `- ${worktree.agent_id || "unassigned"}`}
            </Select.Option>
          ))}
        </Select>
      </label>
    </div>
  );
}

export function defaultWorktree(worktrees: WorktreeRow[]): WorktreeRow | null {
  return worktrees.find((worktree) => !worktree.is_main) ?? worktrees[0] ?? null;
}
