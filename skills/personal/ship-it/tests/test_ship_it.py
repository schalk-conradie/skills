import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Optional

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "ship-it.sh"


class Repo:
    def __init__(self, root: Path, env: dict):
        self.root = root
        self.env = env

    def git(self, *args: str, cwd: Optional[Path] = None) -> str:
        return subprocess.run(
            ["git", *args], cwd=cwd or self.root, env=self.env, check=True, capture_output=True, text=True
        ).stdout.strip()

    def ship(self, *args: str, stdin: str = "", cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["bash", str(SCRIPT), *args], cwd=cwd or self.root, env=self.env, input=stdin, capture_output=True, text=True
        )

    def ok(self, *args: str, stdin: str = "", cwd: Optional[Path] = None) -> str:
        run = self.ship(*args, stdin=stdin, cwd=cwd)
        if run.returncode != 0:
            raise AssertionError(f"ship-it {' '.join(args)} failed:\n{run.stderr}")
        return run.stdout

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def hook(self, name: str, body: str, hooks_dir: str = ".git/hooks") -> None:
        path = self.root / hooks_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def show(self, rev: str, name: str) -> str:
        return self.git("show", f"{rev}:{name}")


class ShipItTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        config = base / "gitconfig"
        config.write_text("[user]\n\tname = Test\n\temail = test@example.com\n[init]\n\tdefaultBranch = main\n")
        env = {**os.environ, "GIT_CONFIG_GLOBAL": str(config), "GIT_CONFIG_NOSYSTEM": "1", "TMPDIR": str(base)}
        root = base / "repo"
        root.mkdir()
        self.repo = Repo(root, env)
        self.repo.git("init", "-q")
        self.repo.write("f.txt", "one\ntwo\n")
        self.repo.git("add", ".")
        self.repo.git("commit", "-qm", "init")

    def tearDown(self):
        self.tmp.cleanup()

    def two_slices(self):
        r = self.repo
        r.ok("start")
        r.write("a.txt", "a\n")
        r.ok("checkpoint", "1", "-", stdin="feat: add a\n")
        r.write("a.txt", "a\nb\n")
        r.ok("checkpoint", "2", "-", stdin="feat: add b\n")

    def test_commits_one_commit_per_slice_and_leaves_a_clean_tree(self):
        r = self.repo
        self.two_slices()
        r.write("f.txt", "ONE\ntwo\n")
        r.ok("fold", "1")
        r.ok("commit")
        self.assertEqual(r.git("log", "--format=%s"), "feat: add b\nfeat: add a\ninit")
        self.assertEqual(r.show("HEAD~1", "a.txt"), "a")
        self.assertEqual(r.show("HEAD~1", "f.txt"), "ONE\ntwo")
        self.assertEqual(r.git("status", "--porcelain"), "")
        self.assertEqual(r.git("for-each-ref", "refs/ship-it"), "")
        self.assertEqual(r.git("worktree", "list", "--porcelain").count("worktree "), 1)

    def test_sessions_in_two_worktrees_keep_their_own_snapshots(self):
        r = self.repo
        other = r.root.parent / "other"
        r.git("worktree", "add", "-q", str(other), "-b", "other")
        r.ok("start")
        r.write("a.txt", "a\n")
        r.ok("checkpoint", "1", "-", stdin="feat: main work\n")
        r.ok("start", cwd=other)
        (other / "b.txt").write_text("b\n")
        r.ok("checkpoint", "1", "-", stdin="feat: other work\n", cwd=other)
        r.ok("abort", cwd=other)
        refs = r.git("for-each-ref", "--format=%(refname)", "refs/ship-it").splitlines()
        self.assertEqual(len(refs), 2)
        snapshot = [ref for ref in refs if ref.endswith("slice-0001")][0]
        self.assertIn("a.txt", r.git("ls-tree", "--name-only", snapshot))

    def test_hooks_see_only_the_slice_being_committed(self):
        r = self.repo
        seen = r.root.parent / "seen.txt"
        r.hook("pre-commit", f"ls >> '{seen}'\necho --- >> '{seen}'\n")
        r.ok("start")
        r.write("s1.txt", "1\n")
        r.ok("checkpoint", "1", "-", stdin="feat: one\n")
        r.write("s2.txt", "2\n")
        r.ok("checkpoint", "2", "-", stdin="feat: two\n")
        r.ok("commit")
        first, second = seen.read_text().split("---\n")[:2]
        self.assertNotIn("s2.txt", first)
        self.assertIn("s2.txt", second)

    def test_a_hook_that_changes_a_slice_commits_nothing(self):
        r = self.repo
        r.hook("pre-commit", "for f in $(git diff --cached --name-only); do tr a-z A-Z < $f > $f.t && mv $f.t $f; git add $f; done\n")
        r.ok("start")
        r.write("h.txt", "hello\n")
        r.ok("checkpoint", "1", "-", stdin="feat: hello\n")
        r.write("h.txt", "hello\nworld\n")
        r.ok("checkpoint", "2", "-", stdin="feat: world\n")
        head = r.git("rev-parse", "HEAD")
        run = r.ship("commit")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("Nothing was committed", run.stderr)
        self.assertEqual(r.git("rev-parse", "HEAD"), head)
        patch = r.root / ".git" / "ship-it" / "hook-slice-0001.patch"
        self.assertIn("+HELLO", patch.read_text())

    def test_a_hook_change_can_be_folded_in_and_committed(self):
        r = self.repo
        r.hook("pre-commit", "for f in $(git diff --cached --name-only); do tr a-z A-Z < $f > $f.t && mv $f.t $f; git add $f; done\n")
        r.ok("start")
        r.write("h.txt", "hello\n")
        r.ok("checkpoint", "1", "-", stdin="feat: hello\n")
        self.assertNotEqual(r.ship("commit").returncode, 0)
        r.git("apply", str(r.root / ".git" / "ship-it" / "hook-slice-0001.patch"))
        r.ok("fold", "1")
        r.ok("commit")
        self.assertEqual(r.show("HEAD", "h.txt"), "HELLO")

    def test_a_rejecting_hook_leaves_the_branch_where_it_was(self):
        r = self.repo
        r.hook("pre-commit", "exit 1\n")
        r.ok("start")
        r.write("a.txt", "a\n")
        r.ok("checkpoint", "1", "-", stdin="feat: add a\n")
        head = r.git("rev-parse", "HEAD")
        self.assertNotEqual(r.ship("commit").returncode, 0)
        self.assertEqual(r.git("rev-parse", "HEAD"), head)
        self.assertEqual(r.git("worktree", "list", "--porcelain").count("worktree "), 1)

    def test_hooks_in_an_untracked_relative_hooks_path_still_run(self):
        r = self.repo
        r.git("config", "core.hooksPath", ".husky/_")
        r.write(".gitignore", ".husky/_\n")
        r.git("add", ".gitignore")
        r.git("commit", "-qm", "ignore hooks")
        r.hook("pre-commit", "exit 1\n", hooks_dir=".husky/_")
        r.ok("start")
        r.write("a.txt", "a\n")
        r.ok("checkpoint", "1", "-", stdin="feat: add a\n")
        self.assertNotEqual(r.ship("commit").returncode, 0)

    def test_hooks_can_use_installed_node_modules(self):
        r = self.repo
        r.write(".gitignore", "node_modules\n")
        r.git("add", ".gitignore")
        r.git("commit", "-qm", "ignore deps")
        r.write("node_modules/tool.txt", "installed\n")
        r.hook("pre-commit", "test -f node_modules/tool.txt\n")
        r.ok("start")
        r.write("a.txt", "a\n")
        r.ok("checkpoint", "1", "-", stdin="feat: add a\n")
        r.ok("commit")

    def test_fold_refuses_to_empty_a_slice(self):
        r = self.repo
        r.ok("start")
        r.write("f.txt", "one\ntwo\nthree\n")
        r.ok("checkpoint", "1", "-", stdin="feat: add three\n")
        r.write("b.txt", "b\n")
        r.ok("checkpoint", "2", "-", stdin="feat: add b\n")
        r.write("f.txt", "one\ntwo\n")
        run = r.ship("fold", "1")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("no changes of its own", run.stderr)

    def test_checkpoint_refuses_after_a_branch_switch(self):
        r = self.repo
        r.ok("start")
        r.write("a.txt", "a\n")
        r.git("checkout", "-q", "-b", "elsewhere")
        run = r.ship("checkpoint", "1", "-", stdin="feat: add a\n")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("switch back", run.stderr)

    def test_a_relative_message_file_resolves_from_the_callers_folder(self):
        r = self.repo
        outside = r.root.parent / "msgs"
        outside.mkdir()
        (outside / "m.txt").write_text("feat: from a file\n")
        r.ok("start")
        r.write("sub/x.txt", "x\n")
        r.ok("checkpoint", "1", "../../msgs/m.txt", cwd=r.root / "sub")
        self.assertIn("feat: from a file", r.ok("list"))

    def test_plain_style_accepts_a_non_conventional_header(self):
        r = self.repo
        r.ok("start", "--plain")
        r.write("a.txt", "a\n")
        r.ok("checkpoint", "1", "-", stdin="Add the a file\n")

    def test_conventional_style_rejects_a_plain_header(self):
        r = self.repo
        r.ok("start")
        r.write("a.txt", "a\n")
        self.assertNotEqual(r.ship("checkpoint", "1", "-", stdin="Add the a file\n").returncode, 0)

    def test_recall_prints_the_saved_plan_and_decisions(self):
        r = self.repo
        r.ok("start")
        r.ok("plan", "-", stdin="1. add a\n")
        r.ok("decision", "-", stdin="kept the old name\n")
        out = r.ok("recall")
        self.assertIn("1. add a", out)
        self.assertIn("- kept the old name", out)


if __name__ == "__main__":
    unittest.main()
