import { Button, Label } from "@primer/react";
import { SyncIcon } from "@primer/octicons-react";

interface HeaderProps {
  readonly: boolean;
  loading: boolean;
  title: string;
  eyebrow?: string;
  description?: string;
  onRefresh: () => void;
}

export function Header({ readonly, loading, title, eyebrow = "GitWarp Manager", description, onRefresh }: HeaderProps) {
  return (
    <header className="topbar">
      <div>
        <p className="kicker">{eyebrow}</p>
        <h1>{title}</h1>
        {description ? <p className="topbar-description">{description}</p> : null}
      </div>
      <div className="topbar-actions">
        <Label variant={readonly ? "secondary" : "success"}>{readonly ? "Read-only" : "Mutation enabled"}</Label>
        <Button variant="primary" type="button" leadingVisual={SyncIcon} onClick={onRefresh} disabled={loading}>
          {loading ? "Refreshing" : "Refresh"}
        </Button>
      </div>
    </header>
  );
}
