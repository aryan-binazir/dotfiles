import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


GB = Path(__file__).parents[1] / "stow/scripts/gb"


def run(
    *args: str,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
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
        check=check,
    )


class GbTest(unittest.TestCase):
    def test_preserves_clean_worktree_using_target_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            repo = root / "repo"
            main_worktree = root / "main-worktree"

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
            run("git", "commit", "--allow-empty", "-m", "initial", cwd=repo)
            run("git", "push", "-u", "origin", "main", cwd=repo)
            run("git", "switch", "-c", "feature", cwd=repo)
            run("git", "worktree", "add", str(main_worktree), "main", cwd=repo)

            result = run(sys.executable, str(GB), "main", cwd=repo, check=False)

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(
                run("git", "branch", "--show-current", cwd=repo).stdout.strip(),
                "feature",
            )
            self.assertTrue(main_worktree.exists())
            self.assertIn(
                str(main_worktree),
                run("git", "worktree", "list", "--porcelain", cwd=repo).stdout,
            )
            self.assertIn(
                "checked out in another worktree",
                result.stderr,
            )

    def test_preserves_worktree_with_ignored_file_using_target_branch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            remote = root / "remote.git"
            repo = root / "repo"
            main_worktree = root / "main-worktree"

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
            (repo / ".gitignore").write_text("dirty.txt\n")
            run("git", "add", ".gitignore", cwd=repo)
            run("git", "commit", "-m", "initial", cwd=repo)
            run("git", "push", "-u", "origin", "main", cwd=repo)
            run("git", "switch", "-c", "feature", cwd=repo)
            run("git", "worktree", "add", str(main_worktree), "main", cwd=repo)
            (main_worktree / "dirty.txt").write_text("keep me\n")

            result = run(
                sys.executable,
                str(GB),
                "main",
                cwd=repo,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(
                run("git", "branch", "--show-current", cwd=repo).stdout.strip(),
                "feature",
            )
            self.assertTrue((main_worktree / "dirty.txt").exists())
            self.assertIn(
                f"error: branch main is checked out in another worktree: {main_worktree}",
                result.stderr,
            )

    def test_preserves_merged_branches_with_registered_worktrees(self) -> None:
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
        self.assertIn(
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
        self.assertIn(
            str(stale_worktree),
            run("git", "worktree", "list", "--porcelain", cwd=repo).stdout,
        )
        self.assertIn(
            str(locked_worktree),
            run("git", "worktree", "list", "--porcelain", cwd=repo).stdout,
        )
        self.assertIn(
            "1 not proven merged",
            result.stderr,
        )
        self.assertIn(
            "2 in use",
            result.stderr,
        )


class GbCleanupTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="gb-cleanup-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        home = self.root / "home"
        home.mkdir()
        environment = {
            key: value for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        environment.update(
            HOME=str(home), GIT_CONFIG_GLOBAL=os.devnull,
            GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0",
        )
        patcher = mock.patch.dict(os.environ, environment, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.remote = self.root / "remote.git"
        self.repo = self.root / "repo"
        run("git", "init", "--bare", "--initial-branch=main", str(self.remote),
            cwd=self.root)
        run("git", "clone", str(self.remote), str(self.repo), cwd=self.root)
        self.git("config", "user.name", "GB Test")
        self.git("config", "user.email", "gb@example.test")
        self.commit_file("tracked.txt", b"original\n")
        self.git("push", "-u", "origin", "main")

    def git(self, *args: str, check: bool = True):
        return run("git", *args, cwd=self.repo, check=check)

    def commit_file(self, name: str, content: bytes) -> str:
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self.git("add", "--", name)
        self.git("commit", "-m", "update fixture")
        return self.git("rev-parse", "HEAD").stdout.strip()

    def gone_branch(
        self, name: str, *, squash: bool = False,
        contents: tuple[bytes, bytes] = (b"first\n", b"finished\n"),
    ) -> str:
        self.git("switch", "-c", name)
        self.commit_file("feature.txt", contents[0])
        tip = self.commit_file("feature.txt", contents[1])
        self.git("push", "-u", "origin", name)
        self.git("switch", "main")
        if squash:
            self.git("merge", "--squash", name)
            self.git("commit", "-m", "squash feature")
        else:
            self.git("merge", "--no-ff", name, "-m", "merge feature")
        self.git("push", "origin", "main")
        self.git("push", "origin", "--delete", name)
        return tip

    def gb(self, *args: str, check: bool = True):
        return run(sys.executable, str(GB), *args, cwd=self.repo, check=check)

    def install_git_shim(self, body: str) -> None:
        real_git = shutil.which("git")
        bin_dir = self.root / "bin"
        bin_dir.mkdir(exist_ok=True)
        shim = bin_dir / "git"
        shim.write_text(
            f"#!{sys.executable}\nimport os, subprocess, sys\n"
            f"real_git = {real_git!r}\n{body}\n"
            "os.execv(real_git, [real_git, *sys.argv[1:]])\n"
        )
        shim.chmod(0o755)
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]

    def assert_branch_kept(self, name: str, tip: str) -> None:
        branch = self.git("rev-parse", "--verify", name, check=False)
        self.assertEqual(branch.returncode, 0, "the branch must be preserved")
        self.assertEqual(branch.stdout.strip(), tip)
        self.assertEqual(self.git("for-each-ref", f"refs/gb/pruned/{name}").stdout, "")

    def assert_recoverable(self, name: str, tip: str) -> None:
        recovery = f"refs/gb/pruned/{name}/{tip}"
        self.assertNotEqual(
            self.git("show-ref", "--verify", f"refs/heads/{name}", check=False).returncode,
            0,
        )
        saved = self.git("rev-parse", "--verify", recovery, check=False)
        self.assertEqual(saved.returncode, 0, "pruning must retain a recovery ref")
        self.assertEqual(saved.stdout.strip(), tip)
        self.git("reflog", "expire", "--expire=now", "--all")
        self.git("gc", "--prune=now")
        self.git("branch", name, recovery)
        self.assertEqual(self.git("rev-parse", name).stdout.strip(), tip)
        self.assertEqual(self.git("show", f"{name}:feature.txt").stdout, "finished\n")


    def test_normal_sync_does_not_emit_graft_deprecation_advice(self) -> None:
        self.git("config", "advice.graftFileDeprecated", "true")
        result = self.gb()
        self.assertNotIn("hint:", result.stderr)

    def test_restored_and_reused_branch_names_do_not_inherit_deleted_upstreams(self) -> None:
        name = "amb/restore-reuse"
        tip = self.gone_branch(name, squash=True)
        self.gb()
        recovery = f"refs/gb/pruned/{name}/{tip}"
        self.git("branch", name, recovery)
        self.gb()
        self.assertEqual(self.git("rev-parse", name).stdout.strip(), tip)
        self.assertEqual(self.git("for-each-ref", "--format=%(upstream)", f"refs/heads/{name}").stdout.strip(), "")
        self.git("branch", "-D", name)
        self.git("branch", name, "main")
        self.assertEqual(self.git("for-each-ref", "--format=%(upstream)", f"refs/heads/{name}").stdout.strip(), "")

    def test_switch_preserves_ignored_file_collisions(self) -> None:
        base = self.git("rev-parse", "main").stdout.strip()
        target = self.commit_file("generated.bin", b"tracked target bytes")
        self.git("push", "origin", "main")
        self.git("switch", "-c", "working", base)
        working = self.commit_file(".gitignore", b"generated.bin\n")
        ignored = self.repo / "generated.bin"
        ignored.write_bytes(b"precious ignored bytes\0\xff")
        for target_kind in ("local", "remote"):
            with self.subTest(target_kind=target_kind):
                if target_kind == "remote":
                    self.git("branch", "-D", "main")
                result = self.gb(check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(ignored.read_bytes(), b"precious ignored bytes\0\xff")
                self.assertEqual(self.git("symbolic-ref", "--short", "HEAD").stdout.strip(), "working")
                self.assertEqual(self.git("rev-parse", "working").stdout.strip(), working)
                self.assertEqual(self.git("rev-parse", "origin/main").stdout.strip(), target)

    def test_fast_forward_preserves_ignored_file_collisions(self) -> None:
        base = self.commit_file(".gitignore", b"generated.bin\n")
        self.git("push", "origin", "main")
        ignored = self.repo / "generated.bin"
        ignored.write_bytes(b"remote tracked bytes")
        self.git("add", "-f", "generated.bin")
        self.git("commit", "-m", "track previously ignored output")
        remote_tip = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("push", "origin", "main")
        self.git("reset", "--hard", base)
        ignored.write_bytes(b"local ignored bytes\0\xff")
        result = self.gb(check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(ignored.read_bytes(), b"local ignored bytes\0\xff")
        self.assertEqual(self.git("rev-parse", "main").stdout.strip(), base)
        self.assertEqual(self.git("rev-parse", "origin/main").stdout.strip(), remote_tip)

    def test_remote_branch_switch_can_fetch_missing_partial_clone_blobs(self) -> None:
        self.git("switch", "-c", "amb/lazy")
        tip = self.commit_file("lazy.bin", b"lazy blob\0\xff")
        self.git("push", "origin", "amb/lazy")
        self.git("switch", "main")
        run("git", "config", "uploadpack.allowFilter", "true", cwd=self.remote)
        partial = self.root / "partial"
        run("git", "clone", "--filter=blob:none", "--no-checkout", self.remote.as_uri(), str(partial), cwd=self.root)
        run("git", "switch", "main", cwd=partial)
        missing = run("git", "rev-list", "--objects", "--missing=print", "origin/amb/lazy", cwd=partial)
        self.assertIn("?", missing.stdout)
        result = run(sys.executable, str(GB), "amb/lazy", cwd=partial, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((partial / "lazy.bin").read_bytes(), b"lazy blob\0\xff")
        self.assertEqual(run("git", "rev-parse", "HEAD", cwd=partial).stdout.strip(), tip)

    def test_normal_merge_is_pruned_with_permanent_recovery(self) -> None:
        name = "amb/merged"
        tip = self.gone_branch(name)
        remote_before = run("git", "show-ref", cwd=self.remote).stdout

        self.gb()

        self.assert_recoverable(name, tip)
        self.assertEqual(run("git", "show-ref", cwd=self.remote).stdout, remote_before)

    def test_squash_merge_is_pruned_and_original_history_survives_gc(self) -> None:
        name = "amb/squashed"
        tip = self.gone_branch(name, squash=True)
        history = self.git("rev-list", name).stdout
        self.assertNotEqual(
            self.git("merge-base", "--is-ancestor", tip, "main", check=False).returncode,
            0,
        )
        self.git("switch", "-c", "gc-control")
        control = self.commit_file("discarded.txt", b"gc must discard this\n")
        self.git("switch", "main")
        self.git("branch", "-D", "gc-control")

        self.gb()

        self.assert_recoverable(name, tip)
        self.assertEqual(self.git("rev-list", name).stdout, history)
        self.assertNotEqual(
            self.git("cat-file", "-e", control, check=False).returncode, 0,
            "the control commit must be collected to prove gc ran",
        )

    def test_additional_local_commit_is_kept(self) -> None:
        name = "amb/local-work"
        self.gone_branch(name, squash=True)
        self.git("switch", name)
        tip = self.commit_file("local.txt", b"unpublished work\n")
        self.git("switch", "main")

        self.gb()

        self.assert_branch_kept(name, tip)
        self.assertEqual(self.git("show", f"{name}:local.txt").stdout, "unpublished work\n")

    def test_whitespace_only_local_change_is_kept(self) -> None:
        name = "amb/indentation"
        self.gone_branch(name, squash=True)
        self.git("switch", name)
        tip = self.commit_file("feature.txt", b"\tfinished\n")
        self.git("switch", "main")

        self.gb()

        self.assert_branch_kept(name, tip)

    def test_binary_local_change_is_kept(self) -> None:
        name = "amb/binary"
        self.gone_branch(name, squash=True, contents=(b"\0first", b"\0finished"))
        self.git("switch", name)
        tip = self.commit_file("feature.txt", b"\0finished\1")
        self.git("switch", "main")

        self.gb()

        self.assert_branch_kept(name, tip)
        binary = subprocess.run(
            ["git", "show", f"{name}:feature.txt"], cwd=self.repo,
            capture_output=True, check=True,
        ).stdout
        self.assertEqual(binary, b"\0finished\1")

    def test_local_file_mode_change_is_kept(self) -> None:
        name = "amb/executable"
        self.gone_branch(name, squash=True)
        self.git("switch", name)
        (self.repo / "feature.txt").chmod(0o755)
        self.git("commit", "-am", "make executable")
        tip = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("switch", "main")

        self.gb()

        self.assert_branch_kept(name, tip)

    def test_recovery_ref_collision_prevents_pruning(self) -> None:
        name = "amb/collision"
        tip = self.gone_branch(name)
        existing = f"refs/gb/pruned/{name}"
        self.git("update-ref", existing, "main")

        result = self.gb()

        self.assertEqual(self.git("rev-parse", name).stdout.strip(), tip)
        self.assertEqual(self.git("rev-parse", existing).stdout,
                         self.git("rev-parse", "main").stdout)
        self.assertIn("transaction failed", result.stderr)

    def test_concurrent_commit_prevents_pruning(self) -> None:
        name = "amb/racing"
        tip = self.gone_branch(name, squash=True)
        self.git("switch", name)
        newer = self.commit_file("racing.txt", b"concurrently committed work\n")
        self.git("switch", "main")
        self.git("update-ref", f"refs/heads/{name}", tip, newer)
        self.install_git_shim(
            "if 'update-ref' in sys.argv and '--stdin' in sys.argv:\n"
            f"    subprocess.run([real_git, 'update-ref', 'refs/heads/{name}', "
            f"{newer!r}], check=True)"
        )

        result = self.gb()

        self.assert_branch_kept(name, newer)
        self.assertIn("transaction failed", result.stderr)
        self.assertEqual(self.git("show", f"{name}:racing.txt").stdout,
                         "concurrently committed work\n")

    def test_git_proof_failures_keep_the_branch(self) -> None:
        name = "amb/unproven"
        tip = self.gone_branch(name, squash=True)
        original_path = os.environ["PATH"]
        for command in ("diff-tree", "rev-list", "update-ref"):
            with self.subTest(command=command):
                os.environ["PATH"] = original_path
                self.install_git_shim(
                    f"if {command!r} in sys.argv[1:]:\n    sys.exit(128)"
                )

                result = self.gb()

                self.assert_branch_kept(name, tip)
                self.assertIn("warning", result.stderr)

    def test_explicitly_requested_branch_is_not_pruned(self) -> None:
        name = "amb/requested"
        tip = self.gone_branch(name)

        result = self.gb(name, check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("branch", "--show-current").stdout.strip(), name)
        self.assert_branch_kept(name, tip)

    def test_repeated_unproven_branches_produce_one_summary(self) -> None:
        tips = {}
        for name in ("amb/one", "amb/two", "amb/three"):
            self.git("switch", "-c", name)
            tips[name] = self.commit_file(name + ".txt", b"unmerged work\n")
            self.git("push", "-u", "origin", name)
            self.git("switch", "main")
            self.git("push", "origin", "--delete", name)

        for _ in range(2):
            result = self.gb()

            lines = [line for line in result.stderr.splitlines() if line.startswith("gb:")]
            self.assertEqual(lines, ["gb: kept 3 local branches (3 not proven merged)"])
            for name, tip in tips.items():
                self.assert_branch_kept(name, tip)

    def test_broad_fetch_mapping_cannot_prune_recovery_refs(self) -> None:
        name = "amb/recovery-protection"
        tip = self.gone_branch(name, squash=True)
        self.gb()
        recovery = f"refs/gb/pruned/{name}/{tip}"
        self.git("config", "--replace-all", "remote.origin.fetch", "+refs/*:refs/*")
        self.git("switch", "-c", "working")

        result = self.gb(check=False)

        self.assertEqual(result.returncode, 0, result.stderr)
        saved = self.git("rev-parse", "--verify", recovery, check=False)
        self.assertEqual(saved.returncode, 0, "fetch must not delete recovery refs")
        self.assertEqual(saved.stdout.strip(), tip)

    def test_fetch_accepts_missing_or_additional_nonbranch_mappings(self) -> None:
        self.git("config", "--unset-all", "remote.origin.fetch")
        for specification in (None, "+refs/tags/*:refs/tags/*", "+refs/notes/*:refs/notes/*"):
            with self.subTest(specification=specification):
                if specification:
                    self.git("config", "--replace-all", "remote.origin.fetch", specification)
                result = self.gb(check=False)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.git("rev-parse", "origin/main").stdout,
                                 self.git("rev-parse", "main").stdout)

    def test_virtual_history_cannot_make_unmerged_work_prunable(self) -> None:
        name = "amb/replacement"
        self.git("switch", "-c", name)
        tip = self.commit_file("unmerged.txt", b"must remain unmerged\n")
        self.git("push", "-u", "origin", name)
        self.git("switch", "main")
        main_tip = self.commit_file("main.txt", b"real main\n")
        self.git("push", "origin", "main")
        self.git("push", "origin", "--delete", name)
        tree = self.git("rev-parse", "main^{tree}").stdout.strip()
        replacement = self.git(
            "commit-tree", tree, "-p", tip, "-m", "replacement ancestry",
        ).stdout.strip()
        self.git("replace", main_tip, replacement)

        self.gb()

        self.assert_branch_kept(name, tip)
        self.git("replace", "-d", main_tip)
        (self.repo / ".git/info/grafts").write_text(f"{main_tip} {tip}\n")

        self.gb()

        self.assert_branch_kept(name, tip)

    def test_empty_net_change_is_not_treated_as_a_squash_merge(self) -> None:
        name = "amb/empty"
        self.git("switch", "-c", name)
        self.git("commit", "--allow-empty", "-m", "local history")
        tip = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("push", "-u", "origin", name)
        self.git("switch", "main")
        self.git("commit", "--allow-empty", "-m", "different main history")
        self.git("push", "origin", "main")
        self.git("push", "origin", "--delete", name)

        self.gb()

        self.assert_branch_kept(name, tip)

    def test_shallow_squash_history_is_kept(self) -> None:
        name = "amb/shallow"
        for index in range(4):
            self.commit_file("older.txt", str(index).encode())
        tip = self.gone_branch(name, squash=True)
        self.git("push", "origin", name)
        shallow = self.root / "shallow"
        run("git", "clone", "--depth=3", "--no-single-branch", self.remote.as_uri(),
            str(shallow), cwd=self.root)
        run("git", "branch", "--track", name, f"origin/{name}", cwd=shallow)
        self.git("push", "origin", "--delete", name)
        self.assertEqual(run("git", "rev-parse", "--is-shallow-repository", cwd=shallow).stdout.strip(), "true")
        run("git", "merge-base", name, "main", cwd=shallow)

        run(sys.executable, str(GB), cwd=shallow)

        self.assertEqual(run("git", "rev-parse", name, cwd=shallow).stdout.strip(), tip)
        self.assertEqual(run("git", "for-each-ref", "refs/gb/pruned", cwd=shallow).stdout, "")

    def test_binary_squash_with_non_utf8_path_is_recoverable(self) -> None:
        name = "amb/unusual-path"
        path = os.fsdecode(b"binary-\xff\twith\nnewline.bin")
        self.git("switch", "-c", name)
        self.commit_file(path, b"\0first")
        tip = self.commit_file(path, b"\0finished\xff")
        self.git("push", "-u", "origin", name)
        self.git("switch", "main")
        self.commit_file("unrelated.txt", b"main advanced independently\n")
        self.git("merge", "--squash", name)
        self.git("commit", "-m", "squash binary change")
        self.git("push", "origin", "main")
        self.git("push", "origin", "--delete", name)

        self.gb()

        recovery = f"refs/gb/pruned/{name}/{tip}"
        self.assertEqual(self.git("rev-parse", recovery).stdout.strip(), tip)
        self.git("reflog", "expire", "--expire=now", "--all")
        self.git("gc", "--prune=now")
        self.git("branch", name, recovery)
        restored = subprocess.run(
            ["git", "show", f"{name}:{path}"], cwd=self.repo,
            capture_output=True, check=True,
        ).stdout
        self.assertEqual(restored, b"\0finished\xff")

    def test_conflict_resolved_squash_with_different_file_contents_is_kept(self) -> None:
        name = "amb/resolved"
        self.git("switch", "-c", name)
        tip = self.commit_file("tracked.txt", b"feature\n")
        self.git("push", "-u", "origin", name)
        self.git("switch", "main")
        self.commit_file("tracked.txt", b"main\n")
        self.git("merge", "--squash", name, check=False)
        self.commit_file("tracked.txt", b"main and feature\n")
        self.git("push", "origin", "main")
        self.git("push", "origin", "--delete", name)

        self.gb()

        self.assert_branch_kept(name, tip)

    def test_branch_in_detached_worktree_rebase_is_preserved(self) -> None:
        name = "amb/rebasing"
        tip = self.gone_branch(name, squash=True)
        base = self.git("merge-base", name, "main").stdout.strip()
        linked = self.root / "rebasing-worktree"
        self.git("worktree", "add", str(linked), name)
        result = run("git", "rebase", "--onto", "main", base,
                     cwd=linked, check=False)
        self.assertNotEqual(result.returncode, 0)
        state = Path(run("git", "rev-parse", "--absolute-git-dir", cwd=linked).stdout.strip())
        self.assertTrue((state / "rebase-merge" / "head-name").exists())

        self.gb()

        self.assert_branch_kept(name, tip)
        self.assertTrue((state / "rebase-merge" / "head-name").exists())

    def test_stacked_branch_queued_by_rebase_update_refs_is_preserved(self) -> None:
        name = "amb/queued"
        tip = self.gone_branch(name, squash=True)
        base = self.git("merge-base", name, "main").stdout.strip()
        linked = self.root / "stacked-rebase"
        self.git("branch", "amb/rebase-tip", name)
        self.git("worktree", "add", str(linked), "amb/rebase-tip")
        result = run("git", "rebase", "--update-refs", "--onto", "main", base,
                     cwd=linked, check=False)
        self.assertNotEqual(result.returncode, 0)
        state = Path(run("git", "rev-parse", "--absolute-git-dir", cwd=linked).stdout.strip())
        self.assertIn(f"refs/heads/{name}", (state / "rebase-merge/update-refs").read_text())
        self.gb()
        self.assert_branch_kept(name, tip)

    def test_registered_worktrees_and_all_local_files_are_preserved(self) -> None:
        tip = self.gone_branch("amb/eligible", squash=True)
        protected = []
        for kind in ("clean", "ignored", "tracked", "untracked", "locked", "missing"):
            name = f"amb/{kind}"
            path = self.root / (f'checkout "{kind}"\twith\nspaces')
            self.git("branch", name, tip)
            self.git("push", "-u", "origin", name)
            self.git("push", "origin", "--delete", name)
            self.git("worktree", "add", str(path), name)
            local = None
            if kind in ("ignored", "tracked", "untracked"):
                filename = {"ignored": "ignored.bin", "tracked": "tracked.txt",
                            "untracked": "unpublished.bin"}[kind]
                if kind == "ignored":
                    exclude = Path(self.git("rev-parse", "--git-path", "info/exclude").stdout.strip())
                    if not exclude.is_absolute():
                        exclude = self.repo / exclude
                    exclude.write_text("ignored.bin\n")
                local = path / filename
                local.write_bytes(b"preserve exact local bytes\0\xff")
            if kind == "locked":
                self.git("worktree", "lock", str(path))
            if kind == "missing":
                shutil.rmtree(path)
            protected.append((name, path, local, kind))
        registrations = self.git("worktree", "list", "--porcelain", "-z").stdout

        self.gb()

        self.assertEqual(self.git("worktree", "list", "--porcelain", "-z").stdout,
                         registrations)
        for name, path, local, kind in protected:
            with self.subTest(kind=kind):
                self.assert_branch_kept(name, tip)
                self.assertEqual(path.is_dir(), kind != "missing")
                if local:
                    self.assertEqual(local.read_bytes(), b"preserve exact local bytes\0\xff")

    def test_ignored_submodule_changes_cannot_be_hidden_from_merge_evidence(self) -> None:
        old_link = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("update-index", "--add", "--cacheinfo", f"160000,{old_link},module")
        self.git("config", "-f", ".gitmodules", "submodule.module.path", "module")
        self.git("config", "-f", ".gitmodules", "submodule.module.url", "../module.git")
        self.git("config", "-f", ".gitmodules", "submodule.module.ignore", "all")
        self.git("add", ".gitmodules")
        self.git("commit", "-m", "record submodule")
        self.git("push", "origin", "main")
        name = "amb/submodule-work"
        merged_tip = self.gone_branch(name, squash=True)
        self.git("switch", name)
        self.git("update-index", "--cacheinfo", f"160000,{merged_tip},module")
        self.git("commit", "-m", "advance submodule locally")
        tip = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("switch", "main")

        self.gb()

        self.assert_branch_kept(name, tip)

    def test_symbolic_recovery_ref_is_not_trusted_as_permanent_history(self) -> None:
        name = "amb/symbolic-recovery"
        tip = self.gone_branch(name, squash=True)
        self.git("branch", "recovery-anchor", tip)
        recovery = f"refs/gb/pruned/{name}/{tip}"
        self.git("symbolic-ref", recovery, "refs/heads/recovery-anchor")

        self.gb()

        branch = self.git("rev-parse", "--verify", name, check=False)
        self.assertEqual(branch.returncode, 0, "a movable backup cannot authorize pruning")
        self.assertEqual(branch.stdout.strip(), tip)
        self.assertEqual(self.git("symbolic-ref", recovery).stdout.strip(),
                         "refs/heads/recovery-anchor")

    def test_branch_in_detached_worktree_bisect_is_preserved(self) -> None:
        name = "amb/bisecting"
        tip = self.gone_branch(name, squash=True)
        base = self.git("merge-base", name, "main").stdout.strip()
        linked = self.root / "bisecting-worktree"
        self.git("worktree", "add", str(linked), name)
        run("git", "bisect", "start", tip, base, cwd=linked)
        self.assertNotEqual(
            run("git", "symbolic-ref", "-q", "HEAD", cwd=linked, check=False).returncode,
            0,
        )

        self.gb()

        self.assert_branch_kept(name, tip)
        state = Path(run("git", "rev-parse", "--absolute-git-dir", cwd=linked).stdout.strip())
        self.assertTrue((state / "BISECT_START").exists())

    def test_primary_checkout_branch_is_preserved_when_running_from_linked(self) -> None:
        name = "amb/primary-work"
        tip = self.gone_branch(name, squash=True)
        self.git("switch", name)
        linked = self.root / "other-worktree"
        self.git("worktree", "add", "-b", "other", str(linked), "main")

        run(sys.executable, str(GB), cwd=linked)

        self.assert_branch_kept(name, tip)
        self.assertEqual(self.git("symbolic-ref", "--short", "HEAD").stdout.strip(), name)

    def test_git_automatic_maintenance_cannot_discard_registered_worktrees(self) -> None:
        name = "amb/maintenance"
        tip = self.git("rev-parse", "HEAD").stdout.strip()
        linked = self.root / "missing-old-worktree"
        self.git("worktree", "add", "-b", name, str(linked), "main")
        self.git("push", "-u", "origin", name)
        self.git("push", "origin", "--delete", name)
        state = Path(run("git", "rev-parse", "--absolute-git-dir", cwd=linked).stdout.strip())
        shutil.rmtree(linked)
        os.utime(state / "gitdir", (1, 1))
        for key, value in (("gc.auto", "1"), ("gc.autoDetach", "false"),
                           ("maintenance.autoDetach", "false"),
                           ("gc.worktreePruneExpire", "now")):
            self.git("config", key, value)
        objects = 0
        for number in range(10000):
            content = f"gc-probe-{number}".encode()
            header = b"blob " + str(len(content)).encode() + b"\0"
            if hashlib.sha1(header + content).hexdigest().startswith("17"):
                subprocess.run(
                    ["git", "hash-object", "-w", "--stdin"], input=content,
                    cwd=self.repo, capture_output=True, check=True,
                )
                objects += 1
                if objects == 3:
                    break
        self.assertEqual(objects, 3)
        registrations = self.git("worktree", "list", "--porcelain").stdout

        self.gb()

        self.assertEqual(self.git("worktree", "list", "--porcelain").stdout,
                         registrations)
        self.assert_branch_kept(name, tip)

    def test_gw_preserves_the_requested_squash_branch_tip(self) -> None:
        name = "amb/requested-squash"
        tip = self.gone_branch(name, squash=True)
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        launcher = bin_dir / "gb"
        launcher.write_text(
            f"#!{sys.executable}\nimport os, sys\n"
            f"os.execv({sys.executable!r}, [{sys.executable!r}, {str(GB)!r}, *sys.argv[1:]])\n"
        )
        launcher.chmod(0o755)
        os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]

        result = run(sys.executable, str(GB.with_name("gw")), "requested-squash", cwd=self.repo)

        self.assert_branch_kept(name, tip)
        checkout = Path(result.stdout.strip())
        self.assertTrue(checkout.is_dir())
        self.assertEqual(run("git", "rev-parse", "HEAD", cwd=checkout).stdout.strip(), tip)


if __name__ == "__main__":
    unittest.main()
