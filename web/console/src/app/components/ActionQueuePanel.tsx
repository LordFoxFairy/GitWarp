import { Label } from "@primer/react";
import { AlertIcon, CheckCircleIcon, ShieldCheckIcon } from "@primer/octicons-react";
import type { NextAction } from "../types";

interface ActionQueuePanelProps {
  actions: NextAction[];
  fallback?: string[];
}

function safetyLabel(safety: string): string {
  if (safety === "confirm_destructive") {
    return "confirmation required";
  }
  if (safety === "review") {
    return "review";
  }
  return safety || "safe";
}

function safetyVariant(safety: string): "danger" | "attention" | "success" | "secondary" {
  if (safety === "confirm_destructive") {
    return "danger";
  }
  if (safety === "review") {
    return "attention";
  }
  if (safety === "safe") {
    return "success";
  }
  return "secondary";
}

function actionIcon(action: NextAction) {
  if (action.safety === "confirm_destructive") {
    return AlertIcon;
  }
  if (action.safety === "review") {
    return ShieldCheckIcon;
  }
  return CheckCircleIcon;
}

export function ActionQueuePanel({ actions, fallback = [] }: ActionQueuePanelProps) {
  return (
    <section className="panel action-queue" aria-label="Next actions">
      <div className="panel-title row">
        <div>
          <span>Next actions</span>
          <h2>Recommended queue</h2>
        </div>
        <Label variant={actions.length > 0 ? "attention" : "success"}>{actions.length}</Label>
      </div>

      {actions.length === 0 ? (
        <EmptyQueue fallback={fallback} />
      ) : (
        <ol className="action-queue-list">
          {actions.map((action) => {
            const Icon = actionIcon(action);
            return (
              <li key={action.id} className={`action-queue-item ${action.safety}`}>
                <div className="action-queue-icon" aria-hidden="true">
                  <Icon size={16} />
                </div>
                <div className="action-queue-body">
                  <div className="action-queue-head">
                    <strong>{action.title}</strong>
                    <Label variant={safetyVariant(action.safety)}>{safetyLabel(action.safety)}</Label>
                  </div>
                  <p>{action.description}</p>
                  <dl className="action-queue-meta">
                    {action.branch ? (
                      <div>
                        <dt>Branch</dt>
                        <dd>{action.branch}</dd>
                      </div>
                    ) : null}
                    {action.path ? (
                      <div>
                        <dt>Path</dt>
                        <dd>{action.path}</dd>
                      </div>
                    ) : null}
                  </dl>
                  <div className="recommended-command">
                    <span>Recommended command</span>
                    <code>{action.command}</code>
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

function EmptyQueue({ fallback }: { fallback: string[] }) {
  if (fallback.length > 0) {
    return (
      <div className="queue-fallback">
        <p className="empty-state">No structured queue items. General recommendations:</p>
        <ul>
          {fallback.map((item) => (
            <li key={item}>
              <code>{item}</code>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return <p className="empty-state">No cleanup or adoption actions are pending for this project.</p>;
}
