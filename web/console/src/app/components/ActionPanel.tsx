import { useState, type FormEvent } from "react";
import { Button, Select, Textarea, TextInput } from "@primer/react";
import { RepoForkedIcon, RocketIcon } from "@primer/octicons-react";
import type { DispatchInput, StartWorktreeInput } from "../gitwarp-api";
import type { CommandResult } from "../types";

interface ActionPanelProps {
  readonly: boolean;
  busy: boolean;
  baseBranch?: string;
  onStart: (input: StartWorktreeInput) => Promise<CommandResult>;
  onDispatch: (input: DispatchInput) => Promise<CommandResult>;
}

type ActionMode = "create" | "launch" | null;

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

export function ActionPanel({ readonly, busy, baseBranch, onStart, onDispatch }: ActionPanelProps) {
  const [mode, setMode] = useState<ActionMode>(null);

  const submitStart = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await onStart({
        agent_id: value(form, "agent_id"),
        branch: value(form, "branch"),
        ...(baseBranch ? { base_branch: baseBranch } : {}),
        purpose: value(form, "purpose"),
        ...instructionOptions(form),
      });
      form.reset();
      setMode(null);
    } catch {
      // Keep the form open so branch collisions or validation errors can be corrected.
    }
  };

  const submitDispatch = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const agent = value(form, "agent") === "claude" ? "claude" : "codex";
    try {
      await onDispatch({
        agent,
        branch: value(form, "branch"),
        ...(baseBranch ? { base_branch: baseBranch } : {}),
        purpose: value(form, "purpose"),
        ...instructionOptions(form),
      });
      form.reset();
      setMode(null);
    } catch {
      // Keep the form open so branch collisions or validation errors can be corrected.
    }
  };

  return (
    <section className="panel agent-tools" aria-label="Agent tools">
      <div className="panel-title">
        <span>Agent Tools</span>
        <h2>Start or launch work</h2>
      </div>

      {readonly ? (
        <p className="empty-state">Read-only mode is enabled. Start GitWarp Web without `--readonly` to create sandboxes or launch agents.</p>
      ) : (
        <>
          <div className="agent-tool-buttons">
            <Button
              variant="primary"
              leadingVisual={RepoForkedIcon}
              type="button"
              onClick={() => setMode(mode === "create" ? null : "create")}
              disabled={busy}
            >
              Create Sandbox
            </Button>
            <Button leadingVisual={RocketIcon} type="button" onClick={() => setMode(mode === "launch" ? null : "launch")} disabled={busy}>
              Prepare Agent Launch
            </Button>
          </div>

          {mode === "create" ? <CreateSandboxForm busy={busy} baseBranch={baseBranch} onSubmit={submitStart} onCancel={() => setMode(null)} /> : null}
          {mode === "launch" ? <PrepareLaunchForm busy={busy} baseBranch={baseBranch} onSubmit={submitDispatch} onCancel={() => setMode(null)} /> : null}
        </>
      )}
    </section>
  );
}

function CreateSandboxForm({
  busy,
  baseBranch,
  onSubmit,
  onCancel,
}: {
  busy: boolean;
  baseBranch?: string;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
}) {
  return (
    <form className="form-stack action-form" onSubmit={onSubmit} aria-busy={busy}>
      <label>
        Agent ID
        <TextInput name="agent_id" placeholder="codex-ui-fix" required disabled={busy} block />
      </label>
      <label>
        Branch
        <TextInput name="branch" placeholder="feature/my-task" required disabled={busy} block />
      </label>
      <p className="form-hint">Parent base: {baseBranch || "main"}</p>
      <label>
        Purpose
        <Textarea name="purpose" rows={3} placeholder="Short task description" required disabled={busy} block resize="vertical" />
      </label>
      <InstructionFields busy={busy} />
      <div className="form-actions">
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? "Creating..." : "Create Sandbox"}
        </Button>
        <Button type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function PrepareLaunchForm({
  busy,
  baseBranch,
  onSubmit,
  onCancel,
}: {
  busy: boolean;
  baseBranch?: string;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
}) {
  return (
    <form className="form-stack action-form" onSubmit={onSubmit} aria-busy={busy}>
      <label>
        Agent
        <Select name="agent" defaultValue="codex" disabled={busy} block>
          <Select.Option value="codex">codex</Select.Option>
          <Select.Option value="claude">claude</Select.Option>
        </Select>
      </label>
      <label>
        Branch
        <TextInput name="branch" placeholder="feature/parallel-task" required disabled={busy} block />
      </label>
      <p className="form-hint">Parent base: {baseBranch || "main"}</p>
      <label>
        Purpose
        <Textarea name="purpose" rows={3} placeholder="Create workspace and launch command" required disabled={busy} block resize="vertical" />
      </label>
      <InstructionFields busy={busy} />
      <div className="form-actions">
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? "Preparing..." : "Prepare Agent Launch"}
        </Button>
        <Button type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </form>
  );
}

function InstructionFields({ busy }: { busy: boolean }) {
  return (
    <fieldset className="instruction-fields">
      <legend>Instruction Mounts</legend>
      <label>
        Files
        <Textarea name="instructions" rows={3} placeholder={"AGENTS.md\nCLAUDE.md=docs/claude-code.md"} disabled={busy} block resize="vertical" />
      </label>
      <label>
        Profile
        <TextInput name="instruction_profile" placeholder="claude-code" disabled={busy} block />
      </label>
      <label>
        Mode
        <Select name="instruction_mode" defaultValue="copy" disabled={busy} block>
          <Select.Option value="copy">copy snapshot</Select.Option>
          <Select.Option value="symlink">symlink live file</Select.Option>
        </Select>
      </label>
    </fieldset>
  );
}
