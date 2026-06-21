from __future__ import annotations

from helpers import *
from unittest import mock


def write_fake_launcher(
    path: Path,
    *,
    supports_install: bool = True,
    supports_next: bool = False,
    supports_sweep: bool = True,
    supports_upgrade: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    next_case = """
if args[:2] == ["next", "--help"]:
    sys.exit(0)
""" if supports_next else """
if args[:2] == ["next", "--help"]:
    print("usage: gitwarp [-h] {init,scan}", file=sys.stderr)
    sys.exit(2)
"""
    upgrade_case = """
if args[:2] == ["upgrade", "--help"]:
    sys.exit(0)
""" if supports_upgrade else ""
    install_case = """
if args[:2] == ["install", "--help"]:
    sys.exit(0)
""" if supports_install else """
if args[:2] == ["install", "--help"]:
    print("usage: gitwarp [-h] {init,scan}", file=sys.stderr)
    sys.exit(2)
"""
    sweep_case = """
if args[:2] == ["sweep", "--help"]:
    sys.exit(0)
""" if supports_sweep else """
if args[:2] == ["sweep", "--help"]:
    print("usage: gitwarp [-h] {init,scan}", file=sys.stderr)
    sys.exit(2)
"""
    path.write_text(
        f"""#!/usr/bin/env python3
import sys
args = sys.argv[1:]
if args == ["--version"]:
    print("gitwarp 0.1.0")
    sys.exit(0)
if args[:3] == ["task", "create", "--help"]:
    sys.exit(0)
{upgrade_case}
{install_case}
{next_case}
{sweep_case}
sys.exit(2)
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


class RuntimeSyncTests(GitWarpTestCase):
    def test_install_self_dry_run_recommends_pipx_without_mutating(self) -> None:
        payload = run_gitwarp(
            self.repo,
            "install",
            "self",
            "--method",
            "pipx",
            "--source",
            str(REPO_ROOT),
            "--dry-run",
        )

        self.assertTrue(payload["dry_run"])
        self.assertEqual(payload["target"], "self")
        self.assertEqual(payload["method"], "pipx")
        self.assertEqual(payload["command"], ["python3", "-m", "pipx", "install", str(REPO_ROOT)])
        self.assertIn("pipx", payload["shell_command"])

    def test_install_gitwarp_alias_does_not_resolve_package_url_as_path(self) -> None:
        package_source = "git+https://github.com/LordFoxFairy/GitWarp.git"

        payload = run_gitwarp(
            self.repo,
            "install",
            "gitwarp",
            "--method",
            "pipx",
            "--source",
            package_source,
            "--dry-run",
        )

        self.assertEqual(payload["target"], "self")
        self.assertEqual(payload["command"], ["python3", "-m", "pipx", "install", package_source])

    def test_install_self_launcher_writes_current_launcher(self) -> None:
        destination = self.repo / "bin" / "gitwarp"

        payload = run_gitwarp(self.repo, "install", "self", "--method", "launcher", "--dest", str(destination))

        self.assertEqual(payload["target"], "self")
        self.assertEqual(payload["method"], "launcher")
        self.assertFalse(payload["dry_run"])
        self.assertTrue(destination.exists())
        result = payload["result"]  # type: ignore[assignment]
        self.assertEqual(result["status"], "written")  # type: ignore[index]
        self.assertFalse(result["upgrade_required"])  # type: ignore[index]

    def test_install_host_dry_run_targets_native_plugin_scripts(self) -> None:
        codex = run_gitwarp(self.repo, "install", "codex", "--source", str(REPO_ROOT), "--dry-run")
        claude = run_gitwarp(self.repo, "install", "claude", "--source", str(REPO_ROOT), "--dry-run")
        claudecode = run_gitwarp(self.repo, "install", "claudecode", "--source", str(REPO_ROOT), "--dry-run")

        self.assertEqual(codex["target"], "codex")
        self.assertTrue(str(codex["script"]).endswith("scripts/install-codex-plugin.sh"))
        self.assertEqual(claude["target"], "claude-code")
        self.assertEqual(claudecode["target"], "claude-code")
        self.assertTrue(str(claude["script"]).endswith("scripts/install-claude-plugin.sh"))
        self.assertIn("install-claude-plugin.sh", claude["shell_command"])

    def test_upgrade_check_reports_missing_launcher_without_writing(self) -> None:
        destination = self.repo / "bin" / "gitwarp"

        payload = run_gitwarp(self.repo, "upgrade", "--cwd", str(self.repo), "--check", "--dest", str(destination))

        self.assertEqual(payload["status"], "missing")
        self.assertTrue(payload["upgrade_required"])
        self.assertFalse(destination.exists())
        self.assertIn("gitwarp upgrade", " ".join(payload["recommended_next"]))  # type: ignore[arg-type]

    def test_upgrade_check_reports_stale_launcher_without_overwriting(self) -> None:
        destination = self.repo / "bin" / "gitwarp"
        write_fake_launcher(destination, supports_next=False)
        before = destination.read_bytes()

        payload = run_gitwarp(self.repo, "upgrade", "--cwd", str(self.repo), "--check", "--dest", str(destination))

        self.assertEqual(payload["status"], "stale")
        self.assertTrue(payload["upgrade_required"])
        self.assertEqual(destination.read_bytes(), before)
        failed = [probe for probe in payload["probes"] if not probe["ok"]]  # type: ignore[index]
        self.assertEqual(["next"], [probe["name"] for probe in failed])

    def test_upgrade_check_reports_launcher_missing_sweep_command(self) -> None:
        destination = self.repo / "bin" / "gitwarp"
        write_fake_launcher(destination, supports_next=True, supports_sweep=False)

        payload = run_gitwarp(self.repo, "upgrade", "--cwd", str(self.repo), "--check", "--dest", str(destination))

        self.assertEqual(payload["status"], "stale")
        self.assertTrue(payload["upgrade_required"])
        failed = [probe for probe in payload["probes"] if not probe["ok"]]  # type: ignore[index]
        self.assertEqual(["sweep"], [probe["name"] for probe in failed])

    def test_upgrade_check_reports_launcher_missing_install_command(self) -> None:
        destination = self.repo / "bin" / "gitwarp"
        write_fake_launcher(destination, supports_install=False, supports_next=True)

        payload = run_gitwarp(self.repo, "upgrade", "--cwd", str(self.repo), "--check", "--dest", str(destination))

        self.assertEqual(payload["status"], "stale")
        self.assertTrue(payload["upgrade_required"])
        failed = [probe for probe in payload["probes"] if not probe["ok"]]  # type: ignore[index]
        self.assertEqual(["install"], [probe["name"] for probe in failed])

    def test_upgrade_writes_current_launcher_and_validates_capabilities(self) -> None:
        destination = self.repo / "bin" / "gitwarp"

        payload = run_gitwarp(self.repo, "upgrade", "--cwd", str(self.repo), "--dest", str(destination))

        self.assertEqual(payload["status"], "written")
        self.assertFalse(payload["upgrade_required"])
        self.assertTrue(destination.exists())
        self.assertTrue(all(probe["ok"] for probe in payload["probes"]))  # type: ignore[index]
        launcher_text = destination.read_text(encoding="utf-8")
        self.assertIn("PYTHONPATH", launcher_text)
        self.assertIn("gitwarp.adapters.cli.entrypoint", launcher_text)
        version = subprocess.run(
            [str(destination), "--version"],
            cwd=str(self.repo),
            capture_output=True,
            text=True,
            check=True,
        )
        next_help = subprocess.run(
            [str(destination), "next", "--help"],
            cwd=str(self.repo),
            capture_output=True,
            text=True,
            check=False,
        )
        sweep_help = subprocess.run(
            [str(destination), "sweep", "--help"],
            cwd=str(self.repo),
            capture_output=True,
            text=True,
            check=False,
        )
        install_help = subprocess.run(
            [str(destination), "install", "--help"],
            cwd=str(self.repo),
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(version.stdout.strip(), "gitwarp 0.1.0")
        self.assertEqual(next_help.returncode, 0)
        self.assertEqual(sweep_help.returncode, 0)
        self.assertEqual(install_help.returncode, 0)

    def test_doctor_recommends_upgrade_when_launcher_lacks_current_commands(self) -> None:
        fake_bin = self.repo / "fake-bin"
        fake_launcher = fake_bin / "gitwarp"
        write_fake_launcher(fake_launcher, supports_next=False)
        old_path = os.environ.get("PATH", "")
        with mock.patch.dict(os.environ, {"PATH": str(fake_bin) + os.pathsep + old_path}):
            doctor = run_gitwarp(self.repo, "doctor", "--cwd", str(self.repo))

        findings = findings_with_code(doctor, "gitwarp_launcher_capability")
        self.assertEqual(1, len(findings))
        self.assertEqual("warning", findings[0]["severity"])
        self.assertIn("gitwarp upgrade", " ".join(doctor["recommended_next"]))  # type: ignore[arg-type]

    def test_doctor_recommends_module_upgrade_when_launcher_cannot_self_upgrade(self) -> None:
        fake_bin = self.repo / "fake-bin"
        fake_launcher = fake_bin / "gitwarp"
        write_fake_launcher(fake_launcher, supports_next=False, supports_upgrade=False)
        old_path = os.environ.get("PATH", "")
        with mock.patch.dict(os.environ, {"PATH": str(fake_bin) + os.pathsep + old_path}):
            doctor = run_gitwarp(self.repo, "doctor", "--cwd", str(self.repo))

        recommended = " ".join(doctor["recommended_next"])  # type: ignore[arg-type]
        self.assertIn("PYTHONPATH=", recommended)
        self.assertIn(" -m ", recommended)
        self.assertIn("upgrade --dest", recommended)
