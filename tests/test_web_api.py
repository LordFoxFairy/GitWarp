from __future__ import annotations

from helpers import *


class WebApiTests(GitWarpTestCase):
    def test_web_state_does_not_create_or_rewrite_ledger(self) -> None:
        services = load_gitwarp_services()
        ledger_path = self.repo / ".gitwarp" / "ledger.json"

        payload = services.build_web_state_payload(self.repo, readonly=True)

        self.assertTrue(payload["ok"])
        self.assertTrue(payload["readonly"])
        self.assertEqual(payload["repo_root"], str(self.repo.resolve()))
        self.assertFalse(ledger_path.exists())

        ledger_path.parent.mkdir()
        ledger_path.write_text("{not-json", encoding="utf-8")
        before = ledger_path.read_bytes()
        invalid_payload = services.build_web_state_payload(self.repo, readonly=True)
        after = ledger_path.read_bytes()

        self.assertEqual(before, after)
        self.assertEqual(invalid_payload["doctor"]["summary"]["by_code"]["ledger_schema"], 1)
        ledger_schema = findings_with_code(invalid_payload["doctor"], "ledger_schema")[0]  # type: ignore[arg-type]
        self.assertEqual(ledger_schema["severity"], "error")

    def test_web_state_includes_dispatch_metadata(self) -> None:
        services = load_gitwarp_services()
        dispatch = run_gitwarp(
            self.repo,
            "dispatch",
            "--cwd",
            str(self.repo),
            "--agent",
            "codex",
            "--branch",
            "feature/web-dispatch-metadata",
            "--purpose",
            "Verify web dispatch metadata",
        )

        payload = services.build_web_state_payload(self.repo, readonly=True)
        row = next(item for item in payload["worktrees"] if item["branch"] == "feature/web-dispatch-metadata")

        self.assertEqual(row["dispatch"]["launch_command"], dispatch["launch_command"])
        self.assertEqual(row["dispatch"]["launch_preview"], dispatch["launch_preview"])

    def test_web_doctor_cache_marks_and_reuses_external_checks(self) -> None:
        services = load_gitwarp_services()
        doctor_cache: dict[str, object] = {}

        first = services.build_web_state_payload(self.repo, readonly=True, doctor_cache=doctor_cache)
        second = services.build_web_state_payload(self.repo, readonly=True, doctor_cache=doctor_cache)

        self.assertFalse(first["doctor"]["cached"])
        self.assertTrue(second["doctor"]["cached"])
        self.assertIsInstance(second["doctor"]["cache_age_seconds"], int)

    def test_web_server_readiness_json_and_state_endpoint(self) -> None:
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
            "--readonly",
        )

        self.assertEqual(ready["host"], "127.0.0.1")
        self.assertIsInstance(ready["port"], int)
        self.assertEqual(ready["repo_root"], str(self.repo.resolve()))
        self.assertTrue(ready["readonly"])

        status, state = self.fetch_web_json(str(ready["url"]), "/api/state")

        self.assertEqual(status, 200)
        self.assertTrue(state["ok"])
        self.assertEqual(state["repo_root"], str(self.repo.resolve()))
        self.assertIn("projects", state)
        self.assertEqual(state["projects"][0]["name"], self.repo.name)
        self.assertEqual(state["projects"][0]["repo_root"], str(self.repo.resolve()))
        self.assertEqual(state["projects"][0]["worktree_count"], len(state["worktrees"]))
        self.assertEqual(state["projects"][0]["active_worktree_count"], 0)
        self.assertEqual(
            state["projects"][0]["doctor_finding_count"],
            sum(1 for finding in state["doctor"]["findings"] if finding["severity"] != "ok"),
        )
        self.assertEqual(
            state["projects"][0]["reconcile_finding_count"],
            sum(1 for finding in state["reconcile"]["findings"] if finding["severity"] != "ok"),
        )
        self.assertIn("worktrees", state)
        self.assertIn("doctor", state)
        self.assertIn("reconcile", state)

    def test_web_project_summary_counts_only_actionable_findings(self) -> None:
        services = load_gitwarp_services()
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-dirty-web-summary",
            "--branch",
            "feature/dirty-web-summary",
            "--purpose",
            "Exercise actionable web findings",
        )
        Path(str(start["path"]), "dirty.txt").write_text("dirty\n", encoding="utf-8")

        payload = services.build_web_state_payload(self.repo, readonly=True)
        project = payload["projects"][0]

        self.assertEqual(
            project["doctor_finding_count"],
            sum(1 for finding in payload["doctor"]["findings"] if finding["severity"] != "ok"),
        )
        self.assertGreaterEqual(project["reconcile_finding_count"], 1)

    def test_web_parser_accepts_subcommand_and_global_alias(self) -> None:
        _, subcommand = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
            "--readonly",
        )
        self.assertTrue(str(subcommand["url"]).startswith("http://127.0.0.1:"))

        alias_repo = self.make_repo()
        _, alias = self.start_web_server(
            alias_repo,
            "--web",
            "--cwd",
            str(alias_repo),
            "--port",
            "0",
            "--no-open",
            "--readonly",
        )
        self.assertTrue(str(alias["url"]).startswith("http://127.0.0.1:"))

    def test_web_rejects_bad_host_header(self) -> None:
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
            "--readonly",
        )

        connection = http.client.HTTPConnection("127.0.0.1", int(ready["port"]), timeout=5)
        try:
            connection.request("GET", "/api/session", headers={"Host": "evil.example"})
            response = connection.getresponse()
            body = json.loads(response.read().decode("utf-8"))
        finally:
            connection.close()

        self.assertEqual(response.status, 403)
        self.assertFalse(body["ok"])
        self.assertEqual(body["code"], "bad_host")

    def test_web_host_validation_rejects_non_loopback_without_unsafe(self) -> None:
        result = subprocess.run(
            [
                *gitwarp_command(),
                "web",
                "--cwd",
                str(self.repo),
                "--host",
                "0.0.0.0",
                "--port",
                "0",
                "--no-open",
                "--readonly",
            ],
            cwd=str(self.repo),
            env=gitwarp_env(),
            capture_output=True,
            text=True,
            check=False,
        )

        payload = json.loads(result.stdout.strip())
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(payload["ok"])
        self.assertIn("loopback", str(payload["error"]))

    def test_web_session_schema_and_readonly_mutation_rejection(self) -> None:
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
            "--readonly",
        )

        session_status, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        schema_status, schema = self.fetch_web_json(str(ready["url"]), "/api/schema")
        init_status, init_payload = self.fetch_web_json(
            str(ready["url"]),
            "/api/init",
            method="POST",
            token=str(session["token"]),
            data={"write_gitignore": False},
        )

        self.assertEqual(session_status, 200)
        self.assertIsInstance(session["token"], str)
        self.assertGreater(len(str(session["token"])), 20)
        self.assertEqual(schema_status, 200)
        self.assertIn("/api/state", schema["endpoints"])
        self.assertIn("/api/repository/tree", schema["endpoints"])
        self.assertIn("/api/repository/file", schema["endpoints"])
        self.assertFalse(schema["endpoints"]["/api/repository/tree"]["mutates"])  # type: ignore[index]
        self.assertFalse(schema["endpoints"]["/api/repository/file"]["mutates"])  # type: ignore[index]
        self.assertTrue(schema["endpoints"]["/api/init"]["mutates"])  # type: ignore[index]
        self.assertEqual(init_status, 403)
        self.assertFalse(init_payload["ok"])
        self.assertEqual(init_payload["code"], "readonly")

    def test_web_root_serves_console_html(self) -> None:
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
            "--readonly",
        )

        status, html, content_type = self.fetch_web_text(str(ready["url"]), "/")

        self.assertEqual(status, 200)
        self.assertIn("text/html", content_type)
        self.assertIn("GitWarp Manager", html)
        self.assertIn("Project Directory", html)
        self.assertIn("Project Detail", html)
        self.assertIn("Open Project", html)
        self.assertIn("Create Sandbox", html)
        self.assertIn("Prepare Agent Launch", html)
        self.assertIn("Instruction Mounts", html)
        self.assertIn("copy snapshot", html)
        self.assertIn("symlink live file", html)
        self.assertIn("Worktrees", html)
        self.assertIn("Doctor / Reconcile", html)
        self.assertIn("Finish + Collapse", html)
        self.assertIn("createRoot", html)
        self.assertIn("React", html)
        self.assertIn("data-dossier-kind", html)
        self.assertIn("/api/state", html)
        self.assertIn("data-gitwarp-token", html)
        self.assertIn("X-GitWarp-Token", html)
        self.assertNotIn("__CSS__", html)
        self.assertNotIn("__JS__", html)

    def test_web_dossier_endpoint_allows_only_dossier_root(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-web-dossier",
            "--branch",
            "feature/web-dossier",
            "--purpose",
            "Expose dossier reads",
        )
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
            "--readonly",
        )

        task_query = urllib.parse.urlencode({"path": str(start["task_md"])})
        status, dossier = self.fetch_web_json(str(ready["url"]), f"/api/dossier?{task_query}")
        outside_query = urllib.parse.urlencode({"path": str(self.repo / "README.md")})
        outside_status, outside = self.fetch_web_json(str(ready["url"]), f"/api/dossier?{outside_query}")

        self.assertEqual(status, 200)
        self.assertTrue(dossier["ok"])
        self.assertEqual(dossier["path"], start["task_md"])
        self.assertIn("Expose dossier reads", dossier["content"])
        self.assertEqual(outside_status, 403)
        self.assertFalse(outside["ok"])
        self.assertEqual(outside["code"], "outside_dossier_root")

    def test_web_repository_browser_reads_committed_tree_and_files(self) -> None:
        (self.repo / "src").mkdir()
        (self.repo / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
        (self.repo / "README.md").write_text("# Browser Fixture\n", encoding="utf-8")
        (self.repo / "binary.bin").write_bytes(b"\x00\xff\x00")
        (self.repo / "large.txt").write_text("x" * 513_000, encoding="utf-8")
        run_git(self.repo, "add", "src/app.py", "README.md", "binary.bin", "large.txt")
        run_git(self.repo, "commit", "-m", "add repository browser fixtures")
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
            "--readonly",
        )
        _, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        token = str(session["token"])

        no_token_status, no_token = self.fetch_web_json(str(ready["url"]), "/api/repository/tree")
        tree_status, tree = self.fetch_web_json(str(ready["url"]), "/api/repository/tree", token=token)
        nested_status, nested = self.fetch_web_json(
            str(ready["url"]),
            f"/api/repository/tree?{urllib.parse.urlencode({'path': 'src', 'cwd': str(self.repo)})}",
            token=token,
        )
        file_status, file_payload = self.fetch_web_json(
            str(ready["url"]),
            f"/api/repository/file?{urllib.parse.urlencode({'path': 'src/app.py', 'cwd': str(self.repo)})}",
            token=token,
        )
        binary_status, binary_payload = self.fetch_web_json(
            str(ready["url"]),
            f"/api/repository/file?{urllib.parse.urlencode({'path': 'binary.bin', 'cwd': str(self.repo)})}",
            token=token,
        )
        large_status, large_payload = self.fetch_web_json(
            str(ready["url"]),
            f"/api/repository/file?{urllib.parse.urlencode({'path': 'large.txt', 'cwd': str(self.repo)})}",
            token=token,
        )

        self.assertEqual(no_token_status, 403)
        self.assertEqual(no_token["code"], "bad_token")
        self.assertEqual(tree_status, 200, tree)
        self.assertEqual(tree["path"], "")
        self.assertEqual(tree["breadcrumbs"][0]["name"], "root")
        self.assertIn("src", {entry["name"] for entry in tree["entries"]})
        self.assertEqual(nested_status, 200, nested)
        self.assertEqual(nested["path"], "src")
        self.assertEqual(nested["entries"][0]["name"], "app.py")
        self.assertEqual(file_status, 200, file_payload)
        self.assertEqual(file_payload["path"], "src/app.py")
        self.assertEqual(file_payload["encoding"], "utf-8")
        self.assertFalse(file_payload["truncated"])
        self.assertIn("print('hello')", file_payload["content"])
        self.assertEqual(binary_status, 200, binary_payload)
        self.assertEqual(binary_payload["encoding"], "base64")
        self.assertEqual(binary_payload["content"], "AP8A")
        self.assertFalse(binary_payload["truncated"])
        self.assertEqual(large_status, 200, large_payload)
        self.assertTrue(large_payload["truncated"])
        self.assertLessEqual(len(str(large_payload["content"])), 512_000)

    def test_web_repository_browser_rejects_unsafe_or_wrong_paths(self) -> None:
        (self.repo / "src").mkdir()
        (self.repo / "src" / "inside.txt").write_text("inside\n", encoding="utf-8")
        (self.repo / "visible.txt").write_text("visible\n", encoding="utf-8")
        run_git(self.repo, "add", "src/inside.txt", "visible.txt")
        run_git(self.repo, "commit", "-m", "add visible file")
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
            "--readonly",
        )
        _, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        token = str(session["token"])

        cases = [
            ("/api/repository/tree", {"path": "../README.md"}, "parent"),
            ("/api/repository/tree", {"path": "/README.md"}, "relative POSIX"),
            ("/api/repository/tree", {"path": "nested/.git/config"}, "Git internals"),
            ("/api/repository/tree", {"path": "visible.txt"}, "not a directory"),
            ("/api/repository/file", {"path": ""}, "required"),
            ("/api/repository/file", {"path": "."}, "required"),
            ("/api/repository/file", {"path": "missing.txt"}, "does not exist"),
            ("/api/repository/file", {"path": ".git/config"}, "Git internals"),
            ("/api/repository/file", {"path": "src"}, "not a file"),
        ]

        for route, query, error in cases:
            with self.subTest(route=route, query=query):
                status, payload = self.fetch_web_json(
                    str(ready["url"]),
                    f"{route}?{urllib.parse.urlencode(query)}",
                    token=token,
                )
                self.assertEqual(status, 400)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["code"], "bad_repository_path")
                self.assertIn(error, str(payload["error"]))

    def test_web_mutations_require_csrf_and_json_content_type(self) -> None:
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
        )
        _, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        token = str(session["token"])

        missing_token_status, missing_token = self.fetch_web_json(
            str(ready["url"]),
            "/api/init",
            method="POST",
            data={"write_gitignore": False},
        )
        bad_type_status, bad_type = self.post_web_raw(
            str(ready["url"]),
            "/api/init",
            token=token,
            body=b"{}",
        )
        connection = http.client.HTTPConnection("127.0.0.1", int(ready["port"]), timeout=5)
        try:
            connection.request(
                "POST",
                "/api/init",
                body=b"{}",
                headers={
                    "X-GitWarp-Token": token,
                    "Content-Type": "application/json",
                    "Content-Length": "not-an-int",
                },
            )
            bad_length_response = connection.getresponse()
            bad_length = json.loads(bad_length_response.read().decode("utf-8"))
        finally:
            connection.close()

        self.assertEqual(missing_token_status, 403)
        self.assertEqual(missing_token["code"], "bad_token")
        self.assertEqual(bad_type_status, 415)
        self.assertEqual(bad_type["code"], "bad_content_type")
        self.assertEqual(bad_length_response.status, 400)
        self.assertEqual(bad_length["code"], "bad_content_length")

    def test_web_confirmation_token_expires(self) -> None:
        web = load_gitwarp_web()
        token, _ = web.encode_confirmation(b"secret", {"action": "collapse"}, ttl_seconds=-1)  # type: ignore[attr-defined]

        with self.assertRaises(TimeoutError):
            web.decode_confirmation(b"secret", token)  # type: ignore[attr-defined]

    def test_web_init_dispatch_start_and_handoff_mutations(self) -> None:
        (self.repo / "AGENTS.md").write_text("web agent rules\n", encoding="utf-8")
        run_git(self.repo, "add", "AGENTS.md")
        run_git(self.repo, "commit", "-m", "add web instruction fixture")

        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
        )
        _, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        token = str(session["token"])

        init_status, init_payload = self.fetch_web_json(
            str(ready["url"]),
            "/api/init",
            method="POST",
            token=token,
            data={"write_gitignore": False},
        )
        dispatch_status, dispatch_payload = self.fetch_web_json(
            str(ready["url"]),
            "/api/dispatch",
            method="POST",
            token=token,
            data={
                "agent": "codex",
                "agent_id": None,
                "branch": "feature/web-mutation-dispatch",
                "purpose": "Dispatch through Web API",
                "instructions": ["AGENTS.md"],
            },
        )
        self.assertEqual(dispatch_status, 200, dispatch_payload)
        start_status, start_payload = self.fetch_web_json(
            str(ready["url"]),
            "/api/start",
            method="POST",
            token=token,
            data={
                "agent_id": "codex-web-start",
                "branch": "feature/web-mutation-start",
                "purpose": "Start through Web API",
                "instructions": ["AGENTS.md"],
            },
        )
        self.assertEqual(start_status, 200, start_payload)
        handoff_status, handoff_payload = self.fetch_web_json(
            str(ready["url"]),
            "/api/handoff",
            method="POST",
            token=token,
            data={
                "cwd": dispatch_payload["path"],
                "status": "testing",
                "progress": "Web handoff recorded",
                "lesson": "Mutation endpoints refresh state after success",
            },
        )
        state_status, state = self.fetch_web_json(str(ready["url"]), "/api/state")
        board = run_gitwarp(self.repo, "board", "--cwd", str(self.repo), "--verbose")

        self.assertEqual(init_status, 200)
        self.assertTrue(init_payload["ok"])
        self.assertTrue((self.repo / ".gitwarp" / "ledger.json").exists())
        self.assertTrue(Path(str(dispatch_payload["path"])).exists())
        self.assertIn("launch_command", dispatch_payload)
        self.assertEqual(dispatch_payload["instructions"][0]["target"], "AGENTS.md")  # type: ignore[index]
        self.assertEqual(dispatch_payload["instruction_mode"], "copy")
        self.assertTrue(Path(str(start_payload["path"])).exists())
        self.assertEqual(start_payload["status"], "active")
        self.assertEqual(start_payload["instructions"][0]["target"], "AGENTS.md")  # type: ignore[index]
        self.assertEqual(handoff_status, 200)
        self.assertEqual(handoff_payload["status"], "testing")
        self.assertEqual(state_status, 200)
        state_row = next(item for item in state["worktrees"] if item["branch"] == "feature/web-mutation-dispatch")  # type: ignore[index]
        board_row = next(item for item in board["worktrees"] if item["branch"] == "feature/web-mutation-dispatch")  # type: ignore[index]
        self.assertEqual(state_row["status"], "testing")
        self.assertEqual(state_row["instructions"][0]["target"], "AGENTS.md")  # type: ignore[index]
        self.assertEqual(board_row["latest_progress"], "Web handoff recorded")

    def test_web_instruction_payload_validation_is_strict(self) -> None:
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
        )
        _, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        cases = [
            (
                {
                    "agent_id": "codex-web-bad-instruction-element",
                    "branch": "feature/web-bad-instruction-element",
                    "purpose": "Reject bad instruction element",
                    "instructions": ["AGENTS.md", 42],
                },
                "instructions must be a list of strings",
            ),
            (
                {
                    "agent_id": "codex-web-bad-instructions",
                    "branch": "feature/web-bad-instructions",
                    "purpose": "Reject non-list instructions",
                    "instructions": "AGENTS.md",
                },
                "instructions must be a list of strings",
            ),
            (
                {
                    "agent_id": "codex-web-bad-profile",
                    "branch": "feature/web-bad-profile",
                    "purpose": "Reject bad profile",
                    "instruction_profile": 42,
                },
                "instruction_profile must be a string",
            ),
            (
                {
                    "agent_id": "codex-web-bad-mode",
                    "branch": "feature/web-bad-mode",
                    "purpose": "Reject bad mode",
                    "instruction_mode": "hardlink",
                },
                "instruction_mode must be one of: copy, symlink",
            ),
        ]

        for data, error in cases:
            with self.subTest(error=error):
                status, payload = self.fetch_web_json(
                    str(ready["url"]),
                    "/api/start",
                    method="POST",
                    token=str(session["token"]),
                    data=data,
                )

                self.assertEqual(status, 400)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["code"], "bad_payload")
                self.assertIn(error, str(payload["error"]))

    def test_web_mutation_payload_schema_rejects_wrong_types_and_unknown_fields(self) -> None:
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
        )
        _, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        token = str(session["token"])
        cases = [
            (
                "/api/init",
                {"write_gitignore": "false"},
                "write_gitignore must be a boolean",
            ),
            (
                "/api/start",
                {"agent_id": "codex-web-schema", "branch": 42, "purpose": "Reject non-string branch"},
                "branch must be a string",
            ),
            (
                "/api/start",
                {"agent_id": "codex-web-schema", "branch": "feature/web-schema", "purpose": ""},
                "missing required field(s): purpose",
            ),
            (
                "/api/dispatch",
                {"branch": "feature/web-unknown", "purpose": "Reject unknown fields", "unexpected": True},
                "unknown field(s): unexpected",
            ),
            (
                "/api/confirmation",
                {"action": "delete-everything"},
                "action must be one of: collapse, finish-collapse",
            ),
            (
                "/api/finish",
                {"cwd": str(self.repo), "status": "pushed", "progress": "Reject non-bool collapse", "collapse": "true"},
                "collapse must be a boolean",
            ),
        ]

        for path, data, error in cases:
            with self.subTest(path=path, error=error):
                status, payload = self.fetch_web_json(
                    str(ready["url"]),
                    path,
                    method="POST",
                    token=token,
                    data=data,
                )

                self.assertEqual(status, 400)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["code"], "bad_payload")
                self.assertIn(error, str(payload["error"]))

    def test_web_finish_collapse_requires_fresh_confirmation(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-web-finish",
            "--branch",
            "feature/web-finish-collapse",
            "--purpose",
            "Finish through Web API",
        )
        worktree_path = Path(str(start["path"]))
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
        )
        _, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        token = str(session["token"])

        missing_status, missing = self.fetch_web_json(
            str(ready["url"]),
            "/api/finish",
            method="POST",
            token=token,
            data={
                "cwd": str(worktree_path),
                "status": "pushed",
                "progress": "Ready to collapse",
                "collapse": True,
            },
        )
        confirm_status, confirmation = self.fetch_web_json(
            str(ready["url"]),
            "/api/confirmation",
            method="POST",
            token=token,
            data={"action": "finish-collapse", "cwd": str(worktree_path), "path": None, "branch": None},
        )
        self.assertEqual(confirm_status, 200, confirmation)
        (worktree_path / "new-head.txt").write_text("new head\n", encoding="utf-8")
        run_git(worktree_path, "add", "new-head.txt")
        run_git(worktree_path, "commit", "-m", "change head after confirmation")
        stale_status, stale = self.fetch_web_json(
            str(ready["url"]),
            "/api/finish",
            method="POST",
            token=token,
            data={
                "cwd": str(worktree_path),
                "status": "pushed",
                "progress": "Attempt stale collapse",
                "collapse": True,
                "confirmation": confirmation["confirmation"],
            },
        )
        self.assertEqual(stale_status, 409)
        self.assertEqual(stale["code"], "stale_confirmation")
        self.assertTrue(worktree_path.exists())
        fresh_status, fresh = self.fetch_web_json(
            str(ready["url"]),
            "/api/confirmation",
            method="POST",
            token=token,
            data={"action": "finish-collapse", "cwd": str(worktree_path), "path": None, "branch": None},
        )
        finish_status, finish = self.fetch_web_json(
            str(ready["url"]),
            "/api/finish",
            method="POST",
            token=token,
            data={
                "cwd": str(worktree_path),
                "status": "pushed",
                "progress": "Fresh confirmation accepted",
                "collapse": True,
                "confirmation": fresh["confirmation"],
            },
        )

        self.assertEqual(missing_status, 403)
        self.assertEqual(missing["code"], "confirmation_required")
        self.assertEqual(confirmation["challenge"]["path"], str(worktree_path))
        self.assertEqual(fresh_status, 200)
        self.assertEqual(finish_status, 200)
        self.assertTrue(finish["collapsed"])
        self.assertFalse(worktree_path.exists())

    def test_web_collapse_confirmation_rejects_dirty_summary_changes(self) -> None:
        start = run_gitwarp(
            self.repo,
            "start",
            "--agent-id",
            "codex-web-collapse",
            "--branch",
            "feature/web-collapse-confirmation",
            "--purpose",
            "Collapse through Web API",
        )
        worktree_path = Path(str(start["path"]))
        _, ready = self.start_web_server(
            self.repo,
            "web",
            "--cwd",
            str(self.repo),
            "--port",
            "0",
            "--no-open",
        )
        _, session = self.fetch_web_json(str(ready["url"]), "/api/session")
        token = str(session["token"])

        confirm_status, confirmation = self.fetch_web_json(
            str(ready["url"]),
            "/api/confirmation",
            method="POST",
            token=token,
            data={"action": "collapse", "cwd": str(worktree_path), "path": None, "branch": None},
        )
        self.assertEqual(confirm_status, 200, confirmation)
        (worktree_path / "dirty-after-confirmation.txt").write_text("dirty\n", encoding="utf-8")
        stale_status, stale = self.fetch_web_json(
            str(ready["url"]),
            "/api/collapse",
            method="POST",
            token=token,
            data={"path": str(worktree_path), "branch": None, "confirmation": confirmation["confirmation"]},
        )
        self.assertEqual(stale_status, 409)
        self.assertEqual(stale["code"], "stale_confirmation")
        self.assertTrue(worktree_path.exists())
        fresh_status, fresh = self.fetch_web_json(
            str(ready["url"]),
            "/api/confirmation",
            method="POST",
            token=token,
            data={"action": "collapse", "cwd": str(worktree_path), "path": None, "branch": None},
        )
        collapse_status, collapse = self.fetch_web_json(
            str(ready["url"]),
            "/api/collapse",
            method="POST",
            token=token,
            data={"path": str(worktree_path), "branch": None, "confirmation": fresh["confirmation"]},
        )

        self.assertEqual(fresh_status, 200)
        self.assertEqual(collapse_status, 200)
        self.assertEqual(collapse["removed_path"], str(worktree_path))
        self.assertFalse(worktree_path.exists())
