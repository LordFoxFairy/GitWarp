import { Button, Flash, Label, TextInput } from "@primer/react";
import { GitBranchIcon, TrashIcon } from "@primer/octicons-react";
import { useEffect, useState } from "react";
import { GitWarpApi } from "../gitwarp-api";
import type { BranchRow, BranchesPayload, CommandResult } from "../types";

interface BranchesPanelProps {
  api: GitWarpApi;
  cwd: string;
  active: boolean;
  refreshKey: number;
  readonly: boolean;
  busy: boolean;
  onRunPrune: (branch: string, confirmBranch: string) => Promise<CommandResult>;
}

export function BranchesPanel({ api, cwd, active, refreshKey, readonly, busy, onRunPrune }: BranchesPanelProps) {
  const [payload, setPayload] = useState<BranchesPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [confirmByBranch, setConfirmByBranch] = useState<Record<string, string>>({});

  const loadBranches = async () => {
    setLoading(true);
    setError("");
    try {
      setPayload(await api.getBranches(cwd));
    } catch (loadError) {
      setError(String(loadError));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!active) {
      return;
    }
    void loadBranches();
  }, [active, api, cwd, refreshKey]);

  const prune = async (branch: string) => {
    try {
      await onRunPrune(branch, confirmByBranch[branch] || "");
      setConfirmByBranch((current) => ({ ...current, [branch]: "" }));
    } catch (pruneError) {
      setError(String(pruneError));
    } finally {
      await loadBranches();
    }
  };

  return (
    <section className="panel branches-panel" aria-label="Local branch references">
      <div className="panel-title row">
        <div>
          <span>Branches</span>
          <h2>Local branch refs</h2>
        </div>
        <Button type="button" onClick={() => void loadBranches()} disabled={loading || busy}>
          Refresh
        </Button>
      </div>

      {error ? <Flash variant="danger">{error}</Flash> : null}
      {payload ? (
        <p className="muted-hint">
          Default branch is <strong>{payload.default_branch}</strong>; cleanup merge base is <strong>{payload.merge_base}</strong>. Only merged local refs with no worktree and no GitWarp ledger row can be pruned.
        </p>
      ) : null}

      <div className="branch-list" role="table" aria-label="Local branches">
        <div className="branch-list-header" role="row">
          <span>Branch</span>
          <span>Status</span>
          <span>Safety</span>
          <span>Action</span>
        </div>
        {(payload?.branches ?? []).map((branch) => (
          <BranchRowView
            key={branch.name}
            branch={branch}
            readonly={readonly}
            busy={busy}
            confirmValue={confirmByBranch[branch.name] || ""}
            onConfirmChange={(value) => setConfirmByBranch((current) => ({ ...current, [branch.name]: value }))}
            onPrune={() => void prune(branch.name)}
          />
        ))}
      </div>

      {!payload && !loading ? <p className="empty-state">Branch refs are unavailable. Refresh to retry.</p> : null}
      {loading ? <p className="empty-state">Loading branches...</p> : null}
    </section>
  );
}

interface BranchRowViewProps {
  branch: BranchRow;
  readonly: boolean;
  busy: boolean;
  confirmValue: string;
  onConfirmChange: (value: string) => void;
  onPrune: () => void;
}

function BranchRowView({ branch, readonly, busy, confirmValue, onConfirmChange, onPrune }: BranchRowViewProps) {
  const canPrune = branch.deletable && confirmValue === branch.name && !readonly && !busy;
  return (
    <article className="branch-list-row" role="row">
      <div className="branch-name-cell" role="cell">
        <strong>
          <GitBranchIcon size={16} />
          {branch.name}
        </strong>
        <span>{branch.head.slice(0, 12)}</span>
      </div>
      <div role="cell">
        <Label variant={labelVariant(branch.category)}>{branch.category}</Label>
        <p>{branch.branch_role || "unknown"}{branch.base_branch ? ` -> ${branch.base_branch}` : ""}</p>
      </div>
      <div role="cell">
        {branch.deletable ? (
          <p className="safe-prune">Safe to prune</p>
        ) : (
          <p>{branch.delete_blockers.join(", ") || "Protected"}</p>
        )}
      </div>
      <div className="branch-action-cell" role="cell">
        {branch.deletable ? (
          <>
            <TextInput
              aria-label={`Confirm ${branch.name}`}
              placeholder={branch.name}
              value={confirmValue}
              onChange={(event) => onConfirmChange(event.currentTarget.value)}
              disabled={readonly || busy}
            />
            <Button variant="danger" type="button" leadingVisual={TrashIcon} onClick={onPrune} disabled={!canPrune}>
              Prune Branch
            </Button>
          </>
        ) : (
          <Button type="button" disabled>
            Protected
          </Button>
        )}
      </div>
    </article>
  );
}

function labelVariant(category: string) {
  if (category === "merged") {
    return "success";
  }
  if (category === "orphan") {
    return "attention";
  }
  if (category === "active") {
    return "accent";
  }
  return "secondary";
}
