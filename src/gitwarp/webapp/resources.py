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
    :root { color-scheme: light; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }
    body { margin: 0; background: #f4efe5; color: #1f2421; }
    main { max-width: 1120px; margin: 0 auto; padding: 32px 20px; }
    h1 { font-size: 30px; margin: 0 0 8px; }
    .card { background: #fffaf0; border: 2px solid #1f2421; border-radius: 14px; padding: 16px; box-shadow: 5px 5px 0 #1f2421; }
    button { border: 2px solid #1f2421; background: #d96c4a; color: #fffaf0; border-radius: 10px; padding: 9px 12px; font-weight: 700; }
    table { width: 100%; border-collapse: collapse; margin-top: 14px; }
    th, td { text-align: left; border-bottom: 1px solid #d8c8aa; padding: 9px; vertical-align: top; }
    pre { white-space: pre-wrap; background: #1f2421; color: #fffaf0; padding: 12px; border-radius: 10px; overflow: auto; }
  </style>
</head>
<body>
  <main>
    <section class="card">
      <h1>GitWarp Web Console</h1>
      <p id="summary">Loading /api/state...</p>
      <button id="refresh">Refresh</button>
      <table>
        <thead><tr><th>Branch</th><th>Agent</th><th>Status</th><th>Purpose</th><th>Progress</th></tr></thead>
        <tbody id="worktrees"></tbody>
      </table>
      <pre id="raw"></pre>
    </section>
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
