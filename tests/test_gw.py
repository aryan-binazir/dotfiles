import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


GW = Path(__file__).resolve().parents[1] / "stow/scripts/gw"


class GwTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.env = {
            key: value for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        self.env.update(HOME=str(self.home), GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.devnull)
        bin_dir = self.base / "bin"
        bin_dir.mkdir()
        self.gb_called = self.base / "gb-called"
        gb = bin_dir / "gb"
        gb.write_text(f'#!/bin/sh\ntouch "{self.gb_called}"\nexit 99\n')
        gb.chmod(0o755)
        self.env["PATH"] = str(bin_dir) + os.pathsep + self.env["PATH"]
        self.repo = self.make_repo(self.base / "repo")

    def tearDown(self) -> None:
        self.assertFalse(self.gb_called.exists(), "list/rm must never invoke gb")

    def run_command(self, *args, cwd=None, check=True):
        return subprocess.run(args, cwd=cwd or self.repo, env=self.env,
                              text=True, capture_output=True, check=check)

    def make_repo(self, path):
        self.run_command("git", "init", "--initial-branch=main", str(path),
                         cwd=self.base)
        self.run_command("git", "config", "user.name", "GW Test", cwd=path)
        self.run_command("git", "config", "user.email", "gw@example.test", cwd=path)
        (path / ".gitignore").write_text("ignored.txt\n")
        (path / "tracked.txt").write_text("original\n")
        self.run_command("git", "add", ".", cwd=path)
        self.run_command("git", "commit", "-m", "initial", cwd=path)
        return path

    def target(self, name):
        return self.home / "repos" / ".worktrees" / self.repo.name / name

    def add_worktree(self, name, *, path=None, repo=None, prefix="amb"):
        path = path or self.target(name)
        self.run_command("git", "worktree", "add", "-b", f"{prefix}/{name}",
                         str(path), cwd=repo or self.repo)
        return path

    def gw(self, *args, cwd=None):
        return self.run_command(sys.executable, str(GW), *args, cwd=cwd, check=False)

    def registrations(self, repo=None):
        return self.run_command("git", "worktree", "list", "--porcelain",
                                cwd=repo or self.repo).stdout

    def test_list_includes_outside_worktrees_and_is_repo_scoped(self):
        standard = self.add_worktree("standard")
        outside = self.add_worktree("outside", path=self.base / "outside checkout")
        other = self.make_repo(self.base / "other")
        unrelated = self.add_worktree("unrelated", path=self.base / "unrelated", repo=other)
        for cwd in (self.repo, standard, outside):
            with self.subTest(cwd=cwd):
                result = self.gw("list", cwd=cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                for path in (self.repo, standard, outside):
                    self.assertIn(str(path), result.stdout)
                self.assertNotIn(str(other), result.stdout)
                self.assertNotIn(str(unrelated), result.stdout)

    def test_clean_remove_unregisters_and_retains_branch(self):
        for requested, prefix in (("plain", "amb"), ("amb/prefixed", "amb"),
                                  ("aryan-binazir/prefixed", "aryan-binazir")):
            with self.subTest(requested=requested):
                name = requested.split("/")[-1]
                target = self.add_worktree(name, prefix=prefix)
                result = self.gw("rm", requested)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse(target.exists())
                self.assertNotIn(str(target), self.registrations())
                self.run_command("git", "show-ref", "--verify", f"refs/heads/{prefix}/{name}")

    def test_refuses_local_changes_and_ignored_files(self):
        for kind in ("tracked", "staged", "untracked", "ignored"):
            with self.subTest(kind=kind):
                target = self.add_worktree(kind)
                filename = {"tracked": "tracked.txt", "staged": "tracked.txt",
                            "untracked": "new.txt", "ignored": "ignored.txt"}[kind]
                local = target / filename
                local.write_text("keep me\n")
                if kind == "staged":
                    self.run_command("git", "add", filename, cwd=target)
                result = self.gw("rm", kind)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("local changes or files", result.stderr)
                self.assertEqual(local.read_text(), "keep me\n")
                self.assertIn(str(target), self.registrations())

    def test_invalid_and_missing_arguments(self):
        for args in ((), ("list", "extra"), ("rm",), ("rm", "x", "extra"),
                     ("rm", ""), ("rm", ".."), ("rm", "."), ("rm", "../x"),
                     ("rm", "/tmp/x"), ("rm", "amb/../x"), ("rm", "amb/"),
                     ("rm", "aryan-binazir/../../x"), ("rm", "other/x"),
                     ("rm", "-x"), ("rm", "missing")):
            with self.subTest(args=args):
                self.assertNotEqual(self.gw(*args).returncode, 0)

    def test_rejects_other_repo_worktree_with_same_repo_basename(self):
        other = self.make_repo(self.base / "other" / self.repo.name)
        target = self.add_worktree("collision", repo=other)
        result = self.gw("rm", "collision")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a registered worktree", result.stderr)
        self.assertTrue(target.exists())
        self.assertIn(str(target), self.registrations(other))

    def test_rm_does_not_follow_branch_to_outside_path(self):
        outside = self.add_worktree("outside", path=self.base / "outside")
        self.assertNotEqual(self.gw("rm", "outside").returncode, 0)
        self.assertTrue(outside.exists())
        self.assertIn(str(outside), self.registrations())

    def test_rm_requires_primary_checkout(self):
        linked = self.add_worktree("linked")
        self.assertNotEqual(self.gw("rm", "linked", cwd=linked).returncode, 0)
        self.assertTrue(linked.exists())

    def test_remove_all_includes_external_paths_and_retains_branches(self):
        standard = self.add_worktree("standard")
        external = self.add_worktree(
            "claude", path=self.base / 'Claude checkout\nwith "quotes"\tand spaces')
        other = self.make_repo(self.base / "other")
        foreign = self.add_worktree("foreign", path=self.base / "foreign", repo=other)
        result = self.gw("rm", "--all")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"skipped: {self.repo}: primary checkout", result.stderr)
        for path, branch in ((standard, "standard"), (external, "claude")):
            self.assertFalse(path.exists())
            self.assertIn(f"removed: {path}", result.stderr)
            self.run_command("git", "show-ref", "--verify", f"refs/heads/amb/{branch}")
        self.assertTrue(foreign.is_dir())
        self.assertIn(str(foreign), self.registrations(other))
        self.assertNotIn(str(foreign), result.stderr)
        self.assertTrue(self.repo.is_dir())
        self.assertEqual(self.gw("rm", "--all").returncode, 0)

    def test_remove_all_from_linked_preserves_current_and_primary(self):
        current = self.add_worktree("current", path=self.base / "current")
        removable = self.add_worktree("removable")
        subdir = current / "subdir"
        subdir.mkdir()
        result = self.gw("rm", "--all", cwd=subdir)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(current.is_dir())
        self.assertTrue(self.repo.is_dir())
        self.assertFalse(removable.exists())
        self.assertIn(f"skipped: {current}: current worktree", result.stderr)
        self.assertIn(f"skipped: {self.repo}: primary checkout", result.stderr)

    def test_remove_all_partial_success_with_blocked_worktrees(self):
        blocked = []
        for kind, filename in (("tracked", "tracked.txt"), ("staged", "tracked.txt"),
                               ("untracked", "new.txt"), ("ignored", "ignored.txt")):
            path = self.add_worktree(kind)
            (path / filename).write_text("preserve me\n")
            if kind == "staged":
                self.run_command("git", "add", filename, cwd=path)
            blocked.append((path, "worktree has local changes or files"))
        locked = self.add_worktree("locked")
        self.run_command("git", "worktree", "lock", "--reason", "keep", str(locked))
        blocked.append((locked, "locked worktree"))
        # A real merge in progress with a clean index/worktree (empty commit).
        merging = self.add_worktree("merging")
        self.run_command("git", "checkout", "-b", "merge-source", cwd=merging)
        self.run_command("git", "commit", "--allow-empty", "-m", "empty", cwd=merging)
        self.run_command("git", "checkout", "amb/merging", cwd=merging)
        self.run_command("git", "merge", "--no-ff", "--no-commit", "merge-source", cwd=merging)
        self.assertEqual(self.run_command("git", "status", "--porcelain", cwd=merging).stdout, "")
        blocked.append((merging, "Git operation in progress"))
        missing = self.add_worktree("missing")
        shutil.rmtree(missing)
        clean = self.add_worktree("zz-clean", path=self.base / "zz-clean")
        result = self.gw("rm", "--all")
        self.assertNotEqual(result.returncode, 0)
        for path, reason in blocked:
            self.assertTrue(path.is_dir())
            self.assertIn(f"skipped: {path}: {reason}", result.stderr)
            self.assertIn(str(path), self.registrations())
        self.assertIn(f"skipped: {missing}: registered path is missing", result.stderr)
        self.assertIn(str(missing), self.registrations())
        self.assertFalse(clean.exists())
        self.assertIn(f"removed: {clean}", result.stderr)
        self.run_command("git", "show-ref", "--verify", "refs/heads/amb/zz-clean")

    def test_force_bulk_discards_local_files_and_unfinished_merge(self):
        targets = []
        for kind, filename in (("tracked", "tracked.txt"), ("staged", "tracked.txt"),
                               ("untracked", "new.txt"), ("ignored", "ignored.txt")):
            path = self.add_worktree(kind)
            (path / filename).write_text("disposable\n")
            if kind == "staged":
                self.run_command("git", "add", filename, cwd=path)
            targets.append((kind, path))
        merging = self.add_worktree("merging")
        self.run_command("git", "checkout", "-b", "merge-source", cwd=merging)
        self.run_command("git", "commit", "--allow-empty", "-m", "empty", cwd=merging)
        self.run_command("git", "checkout", "amb/merging", cwd=merging)
        self.run_command("git", "merge", "--no-ff", "--no-commit", "merge-source", cwd=merging)
        targets.append(("merging", merging))
        plain = self.gw("rm", "--all")
        self.assertNotEqual(plain.returncode, 0)
        self.assertIn("Git operation in progress", plain.stderr)
        for _, path in targets:
            self.assertTrue(path.exists())
        forced = self.gw("rm", "--all", "--force")
        self.assertEqual(forced.returncode, 0, forced.stderr)
        for name, path in targets:
            self.assertFalse(path.exists())
            self.assertNotIn(str(path), self.registrations())
            self.run_command("git", "show-ref", "--verify", f"refs/heads/amb/{name}")
        self.assertTrue(self.repo.is_dir())

    def test_force_preserves_primary_current_locked_and_foreign(self):
        current = self.add_worktree("current")
        locked = self.add_worktree("locked")
        self.run_command("git", "worktree", "lock", str(locked))
        replaced = self.add_worktree("replaced")
        shutil.rmtree(replaced)
        self.make_repo(replaced)
        other = self.make_repo(self.base / "other")
        foreign = self.add_worktree("foreign", path=self.base / "foreign", repo=other)
        missing = self.add_worktree("missing")
        shutil.rmtree(missing)
        removable = self.add_worktree("removable")
        protected = (self.repo, current, locked, replaced, foreign)
        for path in (*protected, removable):
            (path / "ignored.txt").write_text("local data\n")
        subdir = current / "subdir"
        subdir.mkdir()
        result = self.gw("rm", "--force", "--all", cwd=subdir)
        self.assertNotEqual(result.returncode, 0)
        for path in protected:
            self.assertEqual((path / "ignored.txt").read_text(), "local data\n")
        for reason in ("primary checkout", "current worktree", "locked worktree",
                       "not this repository's worktree", "registered path is missing"):
            self.assertIn(reason, result.stderr)
        self.assertFalse(removable.exists())
        self.assertIn(str(foreign), self.registrations(other))
        self.assertIn(str(missing), self.registrations())

    def test_force_only_accepted_once_with_bulk_all(self):
        target = self.add_worktree("dirty")
        (target / "tracked.txt").write_text("keep me\n")
        for args in (("--force",), ("dirty", "--force"), ("--force", "dirty"),
                     ("--all", "--force", "--force"), ("--all", "--all"),
                     ("--all", "-f")):
            with self.subTest(args=args):
                self.assertNotEqual(self.gw("rm", *args).returncode, 0)
                self.assertEqual((target / "tracked.txt").read_text(), "keep me\n")

    def test_remove_all_continues_after_git_remove_failure(self):
        blocked = self.add_worktree("a-submodule")
        source = self.make_repo(self.base / "submodule-source")
        self.run_command("git", "-c", "protocol.file.allow=always", "submodule",
                         "add", str(source), "module", cwd=blocked)
        self.run_command("git", "commit", "-am", "add submodule", cwd=blocked)
        clean = self.add_worktree("z-clean")
        result = self.gw("rm", "--all")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"skipped: {blocked}", result.stderr)
        self.assertIn("submodules", result.stderr)
        self.assertTrue((blocked / "module" / "tracked.txt").exists())
        self.assertFalse(clean.exists())
        self.assertIn(f"removed: {clean}", result.stderr)

    def test_clean_operation_markers_block_single_and_all_removal(self):
        for marker in ("CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge",
                       "rebase-apply", "sequencer", "BISECT_START", "index.lock"):
            with self.subTest(marker=marker):
                name = marker.replace(".", "-")
                path = self.add_worktree(name)
                git_dir = Path(self.run_command(
                    "git", "rev-parse", "--absolute-git-dir", cwd=path).stdout.strip())
                state = git_dir / marker
                if marker in ("rebase-merge", "rebase-apply", "sequencer"):
                    state.mkdir()
                else:
                    state.write_text(self.run_command("git", "rev-parse", "HEAD").stdout)
                for args in (("rm", name), ("rm", "--all")):
                    result = self.gw(*args)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Git operation in progress", result.stderr)
                    self.assertTrue(path.is_dir())
                if state.is_dir():
                    state.rmdir()
                else:
                    state.unlink()
                self.assertEqual(self.gw("rm", name).returncode, 0)

    def test_shell_wrapper_dispatches_force_through_shared_source(self):
        executable = self.base / "bin" / "gw"
        executable.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{GW}" "$@"\n')
        executable.chmod(0o755)
        wrapper = GW.parents[2] / "shell/gw.bash"
        for index, flags in enumerate(("--all --force", "--force --all")):
            target = self.add_worktree(f"wrapper-{index}", prefix="test")
            (target / "ignored.txt").write_text("discard\n")
            result = self.run_command(
                "bash", "--noprofile", "--norc", "-c",
                f'source "$1"; gw rm {flags} || exit; pwd', "bash", str(wrapper))
            self.assertEqual(result.stdout.strip(), str(self.repo))
            self.assertFalse(target.exists())
            self.run_command("git", "show-ref", "--verify", f"refs/heads/test/wrapper-{index}")

    def test_shell_wrapper_dispatches_without_cd_or_eval(self):
        # Exercise the shared wrapper sourced by the live and repo Bash configs.
        wrapper = (GW.parents[2] / "shell/gw.bash").read_text()
        executable = self.base / "bin" / "gw"
        executable.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{GW}" "$@"\n')
        executable.chmod(0o755)
        self.add_worktree("remove")
        self.add_worktree("remove-all")
        script = wrapper + '\ngw list || exit; gw rm remove || exit; gw rm --all || exit; pwd\n'
        result = self.run_command("bash", "--noprofile", "--norc", "-c", script)
        self.assertEqual(result.stdout.splitlines()[-1], str(self.repo))
        self.assertFalse(self.target("remove").exists())
        self.assertFalse(self.target("remove-all").exists())
        result = self.run_command("bash", "--noprofile", "--norc", "-c",
                                  wrapper + '\ngw list extra\n', check=False)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
