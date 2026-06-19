from __future__ import annotations

import http.client
import importlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
ENTRYPOINT_MODULE = "gitwarp.adapters.cli.entrypoint"


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def gitwarp_command() -> list[str]:
    return ["python3", "-m", ENTRYPOINT_MODULE]


def gitwarp_env() -> dict[str, str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_DIR) + (os.pathsep + existing if existing else "")
    return env


def run_gitwarp(repo: Path, *args: str, expect_ok: bool = True) -> dict[str, object]:
    result = subprocess.run(
        [*gitwarp_command(), *args],
        cwd=str(repo),
        env=gitwarp_env(),
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(result.stdout.strip())
    if expect_ok:
        assert result.returncode == 0, result.stdout or result.stderr
        assert payload["ok"] is True, payload
    else:
        assert result.returncode != 0, payload
        assert payload["ok"] is False, payload
    return payload


def run_gitwarp_text(repo: Path, *args: str) -> str:
    result = subprocess.run(
        [*gitwarp_command(), *args],
        cwd=str(repo),
        env=gitwarp_env(),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def findings_with_code(payload: dict[str, object], code: str) -> list[dict[str, object]]:
    return [
        finding
        for finding in payload["findings"]  # type: ignore[index]
        if finding["code"] == code
    ]


def ensure_src_path() -> None:
    src_dir = str(SRC_DIR)
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)


def load_gitwarp_services() -> object:
    ensure_src_path()
    return importlib.import_module("gitwarp.application.services")


def load_gitwarp_ledger() -> object:
    ensure_src_path()
    return importlib.import_module("gitwarp.infrastructure.ledger")


def load_gitwarp_web() -> object:
    ensure_src_path()
    return importlib.import_module("gitwarp.webapp.security")


def read_json_response(response: object) -> dict[str, object]:
    body = response.read().decode("utf-8")  # type: ignore[attr-defined]
    return json.loads(body)


class GitWarpTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        run_git(self.repo, "init", "-b", "main")
        run_git(self.repo, "config", "user.name", "Test User")
        run_git(self.repo, "config", "user.email", "test@example.com")
        (self.repo / "README.md").write_text("hello\n", encoding="utf-8")
        run_git(self.repo, "add", "README.md")
        run_git(self.repo, "commit", "-m", "init")

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def make_repo(self) -> Path:
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        repo = Path(tempdir.name)
        run_git(repo, "init", "-b", "main")
        run_git(repo, "config", "user.name", "Test User")
        run_git(repo, "config", "user.email", "test@example.com")
        (repo / "README.md").write_text("hello\n", encoding="utf-8")
        run_git(repo, "add", "README.md")
        run_git(repo, "commit", "-m", "init")
        return repo

    def stop_process(self, proc: subprocess.Popen[str]) -> None:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
        if proc.stdout is not None:
            proc.stdout.close()
        if proc.stderr is not None:
            proc.stderr.close()

    def start_web_server(self, repo: Path, *args: str) -> tuple[subprocess.Popen[str], dict[str, object]]:
        proc = subprocess.Popen(
            [*gitwarp_command(), *args],
            cwd=str(repo),
            env=gitwarp_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        assert proc.stdout is not None
        line = proc.stdout.readline()
        if not line:
            stderr = proc.stderr.read() if proc.stderr else ""
            self.fail(f"web server did not emit readiness JSON; stderr={stderr}")
        payload = json.loads(line)
        self.addCleanup(self.stop_process, proc)
        self.assertEqual(payload["ok"], True)
        return proc, payload

    def fetch_web_json(
        self,
        url: str,
        path: str,
        *,
        method: str = "GET",
        token: str | None = None,
        data: dict[str, object] | None = None,
    ) -> tuple[int, dict[str, object]]:
        body = None
        headers: dict[str, str] = {}
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["X-GitWarp-Token"] = token
        request = urllib.request.Request(f"{url}{path}", data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, read_json_response(response)
        except urllib.error.HTTPError as exc:
            return exc.code, read_json_response(exc)

    def post_web_raw(
        self,
        url: str,
        path: str,
        *,
        token: str | None = None,
        body: bytes = b"{}",
        content_type: str | None = None,
    ) -> tuple[int, dict[str, object]]:
        headers: dict[str, str] = {}
        if token:
            headers["X-GitWarp-Token"] = token
        if content_type:
            headers["Content-Type"] = content_type
        request = urllib.request.Request(f"{url}{path}", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, read_json_response(response)
        except urllib.error.HTTPError as exc:
            return exc.code, read_json_response(exc)

    def fetch_web_text(self, url: str, path: str) -> tuple[int, str, str]:
        request = urllib.request.Request(f"{url}{path}", method="GET")
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8"), response.headers.get("Content-Type", "")
