import type { FormEvent } from "react";
import type { DispatchInput, StartWorktreeInput } from "../gitwarp-api";

interface ActionPanelProps {
  readonly: boolean;
  onStart: (input: StartWorktreeInput) => void;
  onDispatch: (input: DispatchInput) => void;
}

function value(form: HTMLFormElement, name: string): string {
  return new FormData(form).get(name)?.toString().trim() ?? "";
}

function instructionOptions(form: HTMLFormElement): Pick<StartWorktreeInput, "instructions" | "instruction_profile" | "instruction_mode"> {
  const rawInstructions = value(form, "instructions");
  const profile = value(form, "instruction_profile");
  const mode = value(form, "instruction_mode") === "symlink" ? "symlink" : "copy";
  const instructions = rawInstructions
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);

  return {
    ...(instructions.length > 0 ? { instructions } : {}),
    ...(profile ? { instruction_profile: profile } : {}),
    instruction_mode: mode,
  };
}

export function ActionPanel({ readonly, onStart, onDispatch }: ActionPanelProps) {
  const submitStart = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    onStart({
      agent_id: value(form, "agent_id"),
      branch: value(form, "branch"),
      purpose: value(form, "purpose"),
      ...instructionOptions(form),
    });
    form.reset();
  };

  const submitDispatch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const agent = value(form, "agent") === "claude" ? "claude" : "codex";
    onDispatch({
      agent,
      branch: value(form, "branch"),
      purpose: value(form, "purpose"),
      ...instructionOptions(form),
    });
    form.reset();
  };

  return (
    <aside className="panel action-panel" aria-label="Create and dispatch workspaces">
      <div className="panel-title">
        <span>Actions</span>
        <h2>Create Worktree</h2>
      </div>
      <form className="form-stack" onSubmit={submitStart}>
        <label>
          Agent ID
          <input name="agent_id" placeholder="codex-ui-fix" required disabled={readonly} />
        </label>
        <label>
          Branch
          <input name="branch" placeholder="feature/my-task" required disabled={readonly} />
        </label>
        <label>
          Purpose
          <textarea name="purpose" rows={3} placeholder="Short task description" required disabled={readonly} />
        </label>
        <InstructionFields readonly={readonly} />
        <button className="button primary full" type="submit" disabled={readonly}>
          Start Worktree
        </button>
      </form>

      <hr />

      <div className="panel-title compact">
        <span>Agent Launch</span>
        <h2>Dispatch</h2>
      </div>
      <form className="form-stack" onSubmit={submitDispatch}>
        <label>
          Agent
          <select name="agent" defaultValue="codex" disabled={readonly}>
            <option value="codex">codex</option>
            <option value="claude">claude</option>
          </select>
        </label>
        <label>
          Branch
          <input name="branch" placeholder="feature/parallel-task" required disabled={readonly} />
        </label>
        <label>
          Purpose
          <textarea name="purpose" rows={3} placeholder="Create workspace and launch command" required disabled={readonly} />
        </label>
        <InstructionFields readonly={readonly} />
        <button className="button secondary full" type="submit" disabled={readonly}>
          Prepare Launch Command
        </button>
      </form>
    </aside>
  );
}

function InstructionFields({ readonly }: { readonly: boolean }) {
  return (
    <fieldset className="instruction-fields">
      <legend>Instruction Mounts</legend>
      <label>
        Files
        <textarea name="instructions" rows={3} placeholder={"AGENTS.md\nCLAUDE.md=docs/claude-code.md"} disabled={readonly} />
      </label>
      <label>
        Profile
        <input name="instruction_profile" placeholder="claude-code" disabled={readonly} />
      </label>
      <label>
        Mode
        <select name="instruction_mode" defaultValue="copy" disabled={readonly}>
          <option value="copy">copy snapshot</option>
          <option value="symlink">symlink live file</option>
        </select>
      </label>
    </fieldset>
  );
}
