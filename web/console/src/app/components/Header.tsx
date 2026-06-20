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
        <span className="status-pill">{readonly ? "Read-only" : "Mutation enabled"}</span>
        <button className="button primary" type="button" onClick={onRefresh} disabled={loading}>
          {loading ? "Refreshing" : "Refresh"}
        </button>
      </div>
    </header>
  );
}
