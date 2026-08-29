import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


GB = Path(__file__).parents[1] / "stow/scripts/gb"


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(name, None)
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )


class GbTest(unittest.TestCase):
    def test_prunes_only_local_merged_branches(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            home = root / "home"
            remote = root / "remote.git"
            repo = root / "repo"
            locked_worktree = root / "locked-worktree"
            stale_worktree = root / "stale-worktree"
            home.mkdir()

            isolated_git = {
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_SYSTEM": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
                "HOME": str(home),
            }
            with mock.patch.dict(os.environ, isolated_git):
                self.assert_pruning_behavior(
                    root,
                    remote,
                    repo,
                    locked_worktree,
                    stale_worktree,
                )

    def assert_pruning_behavior(
        self,
        root: Path,
        remote: Path,
        repo: Path,
        locked_worktree: Path,
        stale_worktree: Path,
    ) -> None:
        run(
            "git",
            "init",
            "--bare",
            "--initial-branch=main",
            str(remote),
            cwd=root,
        )
        run("git", "clone", str(remote), str(repo), cwd=root)
        run("git", "config", "user.name", "GB Test", cwd=repo)
        run("git", "config", "user.email", "gb@example.test", cwd=repo)

        (repo / "README.md").write_text("initial\n")
        run("git", "add", "README.md", cwd=repo)
        run("git", "commit", "-m", "initial", cwd=repo)
        run("git", "push", "-u", "origin", "main", cwd=repo)
        run("git", "branch", "keep", cwd=repo)
        run("git", "push", "-u", "origin", "keep", cwd=repo)

        run("git", "switch", "-c", "merged", cwd=repo)
        (repo / "merged.txt").write_text("merged\n")
        run("git", "add", "merged.txt", cwd=repo)
        run("git", "commit", "-m", "merged change", cwd=repo)
        run("git", "push", "-u", "origin", "merged", cwd=repo)
        run("git", "switch", "main", cwd=repo)
        run("git", "merge", "--no-ff", "merged", "-m", "merge branch", cwd=repo)
        run("git", "push", "origin", "main", cwd=repo)
        run("git", "push", "origin", "--delete", "merged", cwd=repo)

        run("git", "branch", "locked", cwd=repo)
        run("git", "push", "-u", "origin", "locked", cwd=repo)
        run("git", "push", "origin", "--delete", "locked", cwd=repo)

        run("git", "switch", "-c", "unmerged", cwd=repo)
        (repo / "unmerged.txt").write_text("unmerged\n")
        run("git", "add", "unmerged.txt", cwd=repo)
        run("git", "commit", "-m", "unmerged change", cwd=repo)
        run("git", "push", "-u", "origin", "unmerged", cwd=repo)
        run("git", "switch", "main", cwd=repo)
        run("git", "push", "origin", "--delete", "unmerged", cwd=repo)

        run(
            "git",
            "worktree",
            "add",
            str(stale_worktree),
            "merged",
            cwd=repo,
        )
        shutil.rmtree(stale_worktree)
        run(
            "git",
            "worktree",
            "add",
            str(locked_worktree),
            "locked",
            cwd=repo,
        )
        run("git", "worktree", "lock", str(locked_worktree), cwd=repo)
        shutil.rmtree(locked_worktree)

        remote_refs_before = run(
            "git", "for-each-ref", "--format=%(refname) %(objectname)", cwd=remote
        ).stdout
        result = run(sys.executable, str(GB), cwd=repo)
        remote_refs_after = run(
            "git", "for-each-ref", "--format=%(refname) %(objectname)", cwd=remote
        ).stdout

        self.assertEqual(remote_refs_after, remote_refs_before)
        self.assertIn("refs/heads/keep", remote_refs_after)
        self.assertNotIn(
            "refs/heads/merged",
            run("git", "show-ref", cwd=repo).stdout,
        )
        self.assertIn(
            "refs/heads/unmerged",
            run("git", "show-ref", cwd=repo).stdout,
        )
        self.assertIn(
            "refs/heads/locked",
            run("git", "show-ref", cwd=repo).stdout,
        )
        self.assertNotIn(
            str(stale_worktree),
            run("git", "worktree", "list", "--porcelain", cwd=repo).stdout,
        )
        self.assertIn(
            str(locked_worktree),
            run("git", "worktree", "list", "--porcelain", cwd=repo).stdout,
        )
        self.assertIn(
            "gb: skipped local branch unmerged "
            "(unmerged commits; upstream gone)",
            result.stderr,
        )
        self.assertIn(
            f"gb: skipped local branch locked "
            f"(missing registered worktree: {locked_worktree.resolve()}; "
            "unlock it if needed, then run git worktree prune)",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
