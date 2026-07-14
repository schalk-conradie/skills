import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_branium_note.py"


class CreateBraniumNoteTests(unittest.TestCase):
    def run_script(self, vault: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", str(vault), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def emitted_type_tags(self, output: str) -> list[str]:
        return [line.strip().removeprefix("- ") for line in output.splitlines() if line.startswith("  - type/")]

    def write_registry(
        self,
        vault: Path,
        *,
        create_project_folder: bool = True,
        include_repo_path: bool = True,
        repo_path: Path | None = None,
    ) -> dict:
        entry = {
            "client": "SBS",
            "project": "SBS - Application Forms",
            "projectFolder": "10 Clients/SBS/Projects/SBS - Application Forms",
            "tags": ["client/sbs", "project/sbs-application-forms"],
        }
        if include_repo_path:
            entry["repoPath"] = str(repo_path or vault / "repo")
        registry_path = vault / "99 Meta" / "project-registry.json"
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(json.dumps([entry]), encoding="utf-8")
        if create_project_folder:
            (vault / Path(entry["projectFolder"])).mkdir(parents=True)
        return entry

    def test_project_dry_run_requires_registry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = self.run_script(
                Path(temp_dir),
                "--area",
                "project",
                "--client",
                "SBS",
                "--project",
                "SBS - Application Forms",
                "--title",
                "Test",
                "--dry-run",
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("Brainium project registry not found", result.stderr)

    def test_explicit_project_must_match_existing_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            self.write_registry(vault)
            result = self.run_script(
                vault,
                "--client",
                "Unknown",
                "--project",
                "Unknown - Project",
                "--title",
                "Test",
                "--dry-run",
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("No Brainium project registry entry matched", result.stderr)

    def test_project_template_defaults_tags_alias_and_status_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            self.write_registry(vault)
            base_args = (
                "--client",
                "Stellenbosch Business School",
                "--project",
                "SBS - Application Forms",
                "--title",
                "Architecture choice",
                "--note-type",
                "adr",
                "--dry-run",
            )
            default_result = self.run_script(vault, *base_args)
            override_result = self.run_script(vault, *base_args, "--status", "accepted")

        self.assertEqual(default_result.returncode, 0, default_result.stderr)
        self.assertIn("client: 'SBS'", default_result.stdout)
        self.assertIn("status: 'proposed'", default_result.stdout)
        self.assertEqual(self.emitted_type_tags(default_result.stdout), ["type/adr"])
        self.assertEqual(override_result.returncode, 0, override_result.stderr)
        self.assertIn("status: 'accepted'", override_result.stdout)
        self.assertNotIn("status: 'proposed'", override_result.stdout)

    def test_home_todo_alias_and_maintenance_link_are_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            todo_result = self.run_script(
                vault,
                "--area",
                "home",
                "--note-type",
                "home-current-todo",
                "--title",
                "Weekend tasks",
                "--dry-run",
            )
            maintenance_result = self.run_script(
                vault,
                "--area",
                "home",
                "--note-type",
                "home-maintenance-log",
                "--title",
                "Geyser service",
                "--dry-run",
            )

        self.assertEqual(todo_result.returncode, 0, todo_result.stderr)
        self.assertIn("type: home-todo", todo_result.stdout)
        self.assertIn("status: 'active'", todo_result.stdout)
        self.assertEqual(self.emitted_type_tags(todo_result.stdout), ["type/home-todo"])
        self.assertIn(str(Path("100 Home") / "Tasks"), todo_result.stdout)
        self.assertEqual(maintenance_result.returncode, 0, maintenance_result.stderr)
        self.assertEqual(
            self.emitted_type_tags(maintenance_result.stdout),
            ["type/home-maintenance-log"],
        )
        self.assertIn(
            "[[100 Home/Maintenance/Maintenance Log|Maintenance Log]]",
            maintenance_result.stdout,
        )

    def test_project_quick_note_uses_template_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            self.write_registry(vault)
            result = self.run_script(
                vault,
                "--cwd",
                str(vault / "repo"),
                "--title",
                "Context",
                "--note-type",
                "note",
                "--dry-run",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("status: 'captured'", result.stdout)

    def test_all_home_types_emit_canonical_tags_and_template_statuses(self) -> None:
        expected_statuses = {
            "home-todo": "active",
            "home-document-register": "active",
            "home-important-information": "active",
            "home-inventory": "active",
            "home-maintenance-log": "active",
            "home-note": "inbox",
            "home-project": "idea",
            "home-quick-note": "inbox",
            "home-routine": "active",
            "home-service-provider": "active",
            "home-shopping-list": "active",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            results = {
                note_type: self.run_script(
                    vault,
                    "--area",
                    "home",
                    "--note-type",
                    note_type,
                    "--title",
                    note_type,
                    "--dry-run",
                )
                for note_type in expected_statuses
            }

        for note_type, expected_status in expected_statuses.items():
            with self.subTest(note_type=note_type):
                result = results[note_type]
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("  - area/home", result.stdout)
                self.assertEqual(self.emitted_type_tags(result.stdout), [f"type/{note_type}"])
                self.assertIn(f"status: '{expected_status}'", result.stdout)

    def test_project_from_vault_uses_registered_repo_as_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault = root / "vault"
            vault.mkdir()
            repo_path = root / "repo"
            self.write_registry(vault, repo_path=repo_path)
            result = self.run_script(
                vault,
                "--cwd",
                str(vault),
                "--client",
                "SBS",
                "--project",
                "SBS - Application Forms",
                "--title",
                "Context",
                "--dry-run",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"source_path: '{repo_path.resolve()}'", result.stdout)
        self.assertIn(f"Source: `{repo_path.resolve()}`", result.stdout)

    def test_project_and_home_from_vault_omit_source_without_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            self.write_registry(vault, include_repo_path=False)
            project_result = self.run_script(
                vault,
                "--cwd",
                str(vault),
                "--client",
                "SBS",
                "--project",
                "SBS - Application Forms",
                "--title",
                "Context",
                "--dry-run",
            )
            home_result = self.run_script(
                vault,
                "--cwd",
                str(vault / "100 Home"),
                "--area",
                "home",
                "--note-type",
                "home-maintenance-log",
                "--title",
                "Maintenance",
                "--dry-run",
            )

        self.assertEqual(project_result.returncode, 0, project_result.stderr)
        self.assertNotIn("source_path:", project_result.stdout)
        self.assertNotIn("\nSource:", project_result.stdout)
        self.assertEqual(home_result.returncode, 0, home_result.stderr)
        self.assertNotIn("source_path:", home_result.stdout)
        self.assertNotIn("\nSource:", home_result.stdout)

    def test_external_cwd_source_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            vault = root / "vault"
            vault.mkdir()
            repo_path = root / "repo"
            self.write_registry(vault, repo_path=repo_path)
            result = self.run_script(
                vault,
                "--cwd",
                str(repo_path),
                "--title",
                "Context",
                "--dry-run",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"source_path: '{repo_path.resolve()}'", result.stdout)
        self.assertIn(f"Source: `{repo_path.resolve()}`", result.stdout)


if __name__ == "__main__":
    unittest.main()
