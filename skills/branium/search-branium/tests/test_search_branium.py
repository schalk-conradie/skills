import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "search_branium.py"


class SearchBraniumTests(unittest.TestCase):
    def run_script(self, vault: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--vault", str(vault), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    def write_note(self, vault: Path, relative_path: str, text: str = "# Note\nneedle\n") -> None:
        path = vault / Path(relative_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_registry(self, vault: Path, *, project_folder: str) -> None:
        entry = {
            "client": "SBS",
            "project": "SBS - Application Forms",
            "repoPath": str(vault / "repo"),
            "projectFolder": project_folder,
            "tags": ["client/sbs", "project/sbs-application-forms"],
        }
        registry_path = vault / "99 Meta" / "project-registry.json"
        registry_path.parent.mkdir(parents=True, exist_ok=True)
        registry_path.write_text(json.dumps([entry]), encoding="utf-8")

    def test_default_search_excludes_operational_files_but_keeps_knowledge_areas(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            included = {
                "Brainium Home.md",
                "10 Clients/Client/Projects/Project/Notes/Client Note.md",
                "100 Home/Tasks/Current Todo.md",
                "20 Research/Topic/Research Note.md",
            }
            excluded = {
                "AGENTS.md",
                "10 Clients/Client/Projects/Project/AGENTS.md",
                "99 Meta/Registry Notes.md",
                "90 Templates/Template.md",
                ".obsidian/Config.md",
                "Excalidraw/Drawing.excalidraw.md",
            }
            for path in included | excluded:
                self.write_note(vault, path)

            result = self.run_script(vault, "--scope", "all", "--query", "needle", "--json")

        self.assertEqual(result.returncode, 0, result.stderr)
        paths = {Path(item["relativePath"]).as_posix() for item in json.loads(result.stdout)["results"]}
        self.assertEqual(paths, included)
        self.assertTrue(paths.isdisjoint(excluded))

    def test_missing_registered_project_folder_has_specific_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            missing_folder = "10 Clients/SBS/Projects/SBS - Application Forms"
            self.write_registry(vault, project_folder=missing_folder)
            result = self.run_script(
                vault,
                "--cwd",
                str(vault / "repo"),
                "--scope",
                "project",
                "--query",
                "needle",
            )

        self.assertEqual(result.returncode, 1)
        self.assertIn("SBS / SBS - Application Forms", result.stderr)
        self.assertIn("points to a missing project folder", result.stderr)
        self.assertIn(missing_folder, result.stderr.replace("\\", "/"))

    def test_full_sbs_name_resolves_to_canonical_client_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            vault = Path(temp_dir)
            project_folder = "10 Clients/SBS/Projects/SBS - Application Forms"
            self.write_registry(vault, project_folder=project_folder)
            self.write_note(vault, f"{project_folder}/Notes/Application.md", "# Application\nforms routing\n")
            result = self.run_script(
                vault,
                "--client",
                "Stellenbosch Business School",
                "--scope",
                "client",
                "--query",
                "forms routing",
                "--json",
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        paths = [Path(item["relativePath"]).as_posix() for item in json.loads(result.stdout)["results"]]
        self.assertEqual(paths, [f"{project_folder}/Notes/Application.md"])


if __name__ == "__main__":
    unittest.main()
