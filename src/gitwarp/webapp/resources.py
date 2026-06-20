from __future__ import annotations

from pathlib import Path

from ..domain.errors import GitWarpError


FALLBACK_WEB_CONSOLE_HTML = """<!doctype html>
<html lang="en" data-gitwarp-token="__TOKEN__">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>GitWarp Web Console</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f8fa;
      --surface: #ffffff;
      --line: #d0d7de;
      --ink: #24292f;
      --muted: #57606a;
      --accent: #0969da;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans", Helvetica, Arial, sans-serif;
    }
    body { margin: 0; background: var(--bg); color: var(--ink); }
    header { display: flex; align-items: center; justify-content: space-between; gap: 16px; border-bottom: 1px solid var(--line); padding: 16px 24px; background: var(--surface); }
    main { max-width: 1280px; margin: 0 auto; padding: 24px; }
    h1 { margin: 0; font-size: 24px; }
    .muted { color: var(--muted); font-size: 13px; }
    .panel { overflow: hidden; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); }
    button { border: 1px solid rgba(31, 35, 40, 0.15); border-radius: 6px; background: #1f883d; color: white; padding: 7px 12px; font-weight: 600; }
    table { width: 100%; border-collapse: collapse; }
    th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 10px 12px; vertical-align: top; }
    th { background: var(--bg); color: var(--muted); font-size: 12px; }
    td:first-child { color: var(--accent); font-weight: 600; }
    tr:last-child td { border-bottom: 0; }
    pre { max-height: 320px; margin: 16px 0 0; overflow: auto; border: 1px solid #30363d; border-radius: 8px; padding: 12px; background: #0d1117; color: #f0f6fc; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>GitWarp Web Console</h1>
      <div class="muted" id="summary">Loading /api/state...</div>
    </div>
    <button id="refresh">Refresh</button>
  </header>
  <main>
    <section class="panel">
      <table>
        <thead><tr><th>Branch</th><th>Agent</th><th>Status</th><th>Purpose</th><th>Progress</th></tr></thead>
        <tbody id="worktrees"></tbody>
      </table>
    </section>
    <pre id="raw"></pre>
  </main>
  <script>
    const token = document.documentElement.dataset.gitwarpToken;
    function appendCell(row, value) {
      const cell = document.createElement('td');
      cell.textContent = value || '';
      row.appendChild(cell);
    }
    async function refresh() {
      const response = await fetch('/api/state', {headers: {'X-GitWarp-Token': token}});
      const state = await response.json();
      document.querySelector('#summary').textContent =
        `${state.statusline} | doctor=${state.doctor.summary.total} reconcile=${state.reconcile.summary.total}`;
      const body = document.querySelector('#worktrees');
      body.replaceChildren();
      for (const item of state.worktrees) {
        const row = document.createElement('tr');
        appendCell(row, item.branch);
        appendCell(row, item.agent_id);
        appendCell(row, item.status);
        appendCell(row, item.purpose);
        appendCell(row, item.latest_progress);
        body.appendChild(row);
      }
      document.querySelector('#raw').textContent = JSON.stringify(state, null, 2);
    }
    document.querySelector('#refresh').addEventListener('click', refresh);
    refresh().catch((error) => { document.querySelector('#summary').textContent = String(error); });
  </script>
</body>
</html>
"""

WEB_CONSOLE_HTML = FALLBACK_WEB_CONSOLE_HTML


def web_console_dist_dir() -> Path | None:
    package_root = Path(__file__).resolve().parents[1]
    source_root = Path(__file__).resolve().parents[3]
    candidates = [
        source_root / "web" / "console" / "dist",
        package_root / "assets" / "web_console",
        Path.cwd().resolve() / "web" / "console" / "dist",
    ]
    for candidate in candidates:
        if (candidate / "index.html").is_file() and (candidate / "app.css").is_file() and (candidate / "app.js").is_file():
            return candidate
    return None


def render_console_html(token: str) -> str:
    dist_dir = web_console_dist_dir()
    if dist_dir is None:
        return FALLBACK_WEB_CONSOLE_HTML.replace("__TOKEN__", token)

    html = (dist_dir / "index.html").read_text(encoding="utf-8")
    css = (dist_dir / "app.css").read_text(encoding="utf-8")
    js = (dist_dir / "app.js").read_text(encoding="utf-8")
    return html.replace("__TOKEN__", token).replace("__CSS__", css).replace("__JS__", js)


def read_dossier_file(raw_path: str | None, dossier_root: Path) -> dict[str, str | bool]:
    if not raw_path:
        raise GitWarpError("missing dossier path")
    target = Path(raw_path).expanduser().resolve()
    try:
        target.relative_to(dossier_root.resolve())
    except ValueError as exc:
        raise PermissionError("path is outside GitWarp dossier root") from exc
    if not target.is_file():
        raise FileNotFoundError(str(target))
    return {"ok": True, "path": str(target), "content": target.read_text(encoding="utf-8", errors="replace")}
