interface HeaderProps {
  readonly: boolean;
  loading: boolean;
  onRefresh: () => void;
}

export function Header({ readonly, loading, onRefresh }: HeaderProps) {
  return (
    <header className="topbar">
      <div>
        <p className="kicker">GitWarp Manager</p>
        <h1>Worktree Control</h1>
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
