import { useEffect, useState, type FormEvent } from "react";
import { Button, Select, Textarea, TextInput } from "@primer/react";
import { RepoForkedIcon, RocketIcon } from "@primer/octicons-react";
import type { DispatchInput, StartWorktreeInput, TaskCreateInput } from "../gitwarp-api";
import type { CommandResult } from "../types";

interface PendingTaskCandidate {
  baseBranch: string;
  branch: string;
}

interface ActionPanelProps {
  readonly: boolean;
  busy: boolean;
  cwd?: string;
  baseBranch?: string;
  pendingTaskBranch?: PendingTaskCandidate | null;
  onTaskCreate: (input: TaskCreateInput) => Promise<CommandResult>;
  onStart: (input: StartWorktreeInput) => Promise<CommandResult>;
  onDispatch: (input: DispatchInput) => Promise<CommandResult>;
}

type ActionMode = "task" | "create" | "launch" | null;

function value(form: HTMLFormElement, name: string): string {
  return new FormData(form).get(name)?.toString().trim() ?? "";
}

function lines(form: HTMLFormElement, name: string): string[] {
  return value(form, name)
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function instructionOptions(form: HTMLFormElement): Pick<TaskCreateInput, "instructions" | "instruction_profile" | "instruction_mode"> {
  const instructions = lines(form, "instructions");
  const profile = value(form, "instruction_profile");
  const mode = value(form, "instruction_mode") === "symlink" ? "symlink" : "copy";

  return {
    ...(instructions.length > 0 ? { instructions } : {}),
    ...(profile ? { instruction_profile: profile } : {}),
    instruction_mode: mode,
  };
}

export function ActionPanel({ readonly, busy, cwd, baseBranch, pendingTaskBranch, onTaskCreate, onStart, onDispatch }: ActionPanelProps) {
  const [mode, setMode] = useState<ActionMode>(null);
  const [lastShellCommand, setLastShellCommand] = useState("");

  useEffect(() => {
    if (pendingTaskBranch) {
      setMode("task");
    }
  }, [pendingTaskBranch]);

  const submitTaskCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const description = value(form, "description");
    const branch = value(form, "branch") || pendingTaskBranch?.branch || "";
    const targetAgentValue = value(form, "target_agent");
    const targetAgent = targetAgentValue === "codex" || targetAgentValue === "claude" ? targetAgentValue : "generic";
    const acceptanceCriteria = lines(form, "acceptance_criteria");
    const verificationCommands = lines(form, "verification_commands");

    try {
      const result = await onTaskCreate({
        ...(cwd ? { cwd } : {}),
        title: value(form, "title") || `Follow up ${branch}`,
        ...(description ? { description } : {}),
        ...((pendingTaskBranch?.baseBranch || baseBranch) ? { base_branch: pendingTaskBranch?.baseBranch || baseBranch } : {}),
        ...(branch ? { branch } : {}),
        target_agent: targetAgent,
        ...(acceptanceCriteria.length > 0 ? { acceptance_criteria: acceptanceCriteria } : {}),
        ...(verificationCommands.length > 0 ? { verification_commands: verificationCommands } : {}),
        ...instructionOptions(form),
      });
      setLastShellCommand(typeof result.shell_command === "string" ? result.shell_command : "");
      form.reset();
      setMode(null);
    } catch {
      // Keep the form open so validation errors can be corrected.
    }
  };

  const submitStart = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    try {
      await onStart({
        ...(cwd ? { cwd } : {}),
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
        ...(cwd ? { cwd } : {}),
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

  const copyShellCommand = async () => {
    if (!lastShellCommand) {
      return;
    }
    try {
      await navigator.clipboard.writeText(lastShellCommand);
    } catch {
      // The read-only field remains selectable when clipboard access is unavailable.
    }
  };

  return (
    <section className="panel agent-tools" aria-label="Agent tools">
      <div className="panel-title">
        <span>Agent Tools</span>
        <h2>Create task work</h2>
      </div>

      {readonly ? (
        <p className="empty-state">Read-only mode is enabled. Start GitWarp Web without `--readonly` to create tasks, sandboxes, or launch plans.</p>
      ) : (
        <>
          {pendingTaskBranch ? (
            <div className="form-stack action-form" aria-label="Pending task candidate">
              <strong>Pending task candidate</strong>
              <p className="form-hint">
                `{pendingTaskBranch.branch}` is a checkout/create candidate via base `{pendingTaskBranch.baseBranch}`. Review the suggested branch below, then create a real task worktree.
              </p>
            </div>
          ) : null}
          <div className="agent-tool-buttons">
            <Button
              variant="primary"
              leadingVisual={RepoForkedIcon}
              type="button"
              onClick={() => setMode(mode === "task" ? null : "task")}
              disabled={busy}
            >
              Create Task
            </Button>
            <Button type="button" onClick={() => setMode(mode === "create" ? null : "create")} disabled={busy}>
              Create Sandbox
            </Button>
            <Button leadingVisual={RocketIcon} type="button" onClick={() => setMode(mode === "launch" ? null : "launch")} disabled={busy}>
              Prepare Agent Launch
            </Button>
          </div>

          {mode === "task" ? <CreateTaskForm busy={busy} baseBranch={pendingTaskBranch?.baseBranch || baseBranch} pendingTaskBranch={pendingTaskBranch?.branch} onSubmit={submitTaskCreate} onCancel={() => setMode(null)} /> : null}
          {mode === "create" ? <CreateSandboxForm busy={busy} baseBranch={baseBranch} onSubmit={submitStart} onCancel={() => setMode(null)} /> : null}
          {mode === "launch" ? <PrepareLaunchForm busy={busy} baseBranch={baseBranch} onSubmit={submitDispatch} onCancel={() => setMode(null)} /> : null}
          {lastShellCommand ? (
            <div className="form-stack action-form" aria-label="Created task navigation">
              <label>
                cd command
                <TextInput value={lastShellCommand} readOnly block />
              </label>
              <div className="form-actions">
                <Button type="button" onClick={() => void copyShellCommand()} disabled={busy}>
                  Copy cd command
                </Button>
              </div>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}

function CreateTaskForm({
  busy,
  baseBranch,
  pendingTaskBranch,
  onSubmit,
  onCancel,
}: {
  busy: boolean;
  baseBranch?: string;
  pendingTaskBranch?: string;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
}) {
  return (
    <form className="form-stack action-form" onSubmit={onSubmit} aria-busy={busy}>
      <label>
        Title
        <TextInput name="title" placeholder="Polish matrix web UX" defaultValue={pendingTaskBranch ? `Create ${pendingTaskBranch}` : undefined} required disabled={busy} block />
      </label>
      <label>
        Description
        <Textarea name="description" rows={3} placeholder="Full user request or problem statement" disabled={busy} block resize="vertical" />
      </label>
      <p className="form-hint">Parent base from WorktreePicker: {baseBranch || "main"}. Select a different base checkout above to change it.</p>
      <label>
        Target agent
        <Select name="target_agent" defaultValue="generic" disabled={busy} block>
          <Select.Option value="generic">generic</Select.Option>
          <Select.Option value="codex">codex</Select.Option>
          <Select.Option value="claude">claude</Select.Option>
        </Select>
      </label>
      <label>
        Explicit branch
        <TextInput name="branch" placeholder="agent/polish-matrix-web-ux" defaultValue={pendingTaskBranch} disabled={busy} block />
      </label>
      <label>
        Acceptance criteria
        <Textarea name="acceptance_criteria" rows={3} placeholder={"UI creates a task worktree\nReturned worktree is selected"} disabled={busy} block resize="vertical" />
      </label>
      <label>
        Verification commands
        <Textarea name="verification_commands" rows={3} placeholder={"npm run build\npython3 -m unittest discover -s tests -p 'test_*.py' -v"} disabled={busy} block resize="vertical" />
      </label>
      <InstructionFields busy={busy} />
      <div className="form-actions">
        <Button variant="primary" type="submit" disabled={busy}>
          {busy ? "Creating..." : "Create Task"}
        </Button>
        <Button type="button" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </form>
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
