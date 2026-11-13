import json
import os
import shlex
import socket
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
HERDR_CONFIG = ROOT / "stow/arch-linux/herdr/.config/herdr"
PLUGIN = HERDR_CONFIG / "plugins/confirm-close"
SCRIPT = PLUGIN / "confirm.sh"


class ConfirmCloseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.calls = self.directory / "calls.jsonl"
        cli = self.directory / "herdr binary"
        cli.write_text(
            f"#!{sys.executable}\n"
            "import json, os, sys\n"
            "with open(os.environ['TEST_CALLS'], 'a') as output:\n"
            "    output.write(json.dumps({'args': sys.argv[1:], "
            "'socket': os.environ.get('HERDR_SOCKET_PATH')}) + '\\n')\n"
            "if os.environ.get('TEST_ERROR'):\n"
            "    print(os.environ['TEST_ERROR'], file=sys.stderr)\n"
            "    sys.exit(1)\n"
        )
        cli.chmod(0o755)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith("HERDR_")}
        self.env.update(
            HERDR_ACTIVE_PANE_ID="w1:p2",
            HERDR_PANE_ID="w9:p9",
            HERDR_SOCKET_PATH=str(self.directory / "private.sock"),
            HERDR_BIN_PATH=str(cli),
            TEST_CALLS=str(self.calls),
        )

    def run_helper(self, answer, env=None):
        return subprocess.run(
            ["bash", str(SCRIPT)], input=answer, env=env or self.env,
            capture_output=True, text=True, timeout=5,
        )

    def records(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] \
            if self.calls.exists() else []

    def test_only_y_or_Y_closes_the_invoker_and_the_prompt_never_changes(self):
        (self.directory / "herdr").symlink_to(self.env["HERDR_BIN_PATH"])
        fallback = {**self.env, "PATH": f"{self.directory}{os.pathsep}{self.env['PATH']}"}
        del fallback["HERDR_BIN_PATH"]
        for answer in ("y", "Y", "n", "N", "\n", "\x1b", "q", "\\", ""):
            for env in (self.env, fallback):
                with self.subTest(answer=answer, fallback=env is fallback):
                    self.calls.unlink(missing_ok=True)
                    result = self.run_helper(answer, env)
                    self.assertEqual((result.returncode, result.stdout), (0, "\033[?25l Kill? (y/n) "))
                    closed = [{"args": ["pane", "close", "w1:p2"], "socket": self.env["HERDR_SOCKET_PATH"]}]
                    self.assertEqual(self.records(), closed if answer in ("y", "Y") else [])

    def test_missing_pane_or_server_context_never_attempts_a_close(self):
        for key in ("HERDR_ACTIVE_PANE_ID", "HERDR_SOCKET_PATH"):
            for env in ({**self.env, key: ""}, {k: v for k, v in self.env.items() if k != key}):
                with self.subTest(key=key, unset=key not in env):
                    self.assertEqual(self.run_helper("y", env).returncode, 1)
                    self.assertEqual(self.records(), [])

    def test_close_failures_stay_visible_without_retrying(self):
        for error, screen in (("pane_not_found", "Close failed.\nAny key."),
                              ("confirmation_required: worktree group", "Use workspace\nclose. Any key.")):
            with self.subTest(error=error):
                self.calls.unlink(missing_ok=True)
                result = self.run_helper("yn", {**self.env, "TEST_ERROR": error})
                self.assertEqual(result.returncode, 1)
                self.assertIn(screen, result.stdout)
                self.assertEqual(len(self.records()), 1)


@unittest.skipUnless(shutil.which("herdr") and shutil.which("tmux"), "Herdr and tmux are required")
class HerdrRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="herdr-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        home = self.directory / "home with spaces"
        config = home / ".config/herdr"
        (config / "plugins").mkdir(parents=True)
        (config / "plugins/confirm-close").symlink_to(PLUGIN, target_is_directory=True)
        staged = self.directory / "config.toml"
        staged.write_text((HERDR_CONFIG / "config.toml").read_text() +
                          '\n[update]\nversion_check = false\nmanifest_check = false\n'
                          '\n[ui.sound]\nenabled = false\n')
        (config / "config.toml").symlink_to(staged)
        self.env = {key: value for key, value in os.environ.items()
                    if not key.startswith(("HERDR_", "TMUX")) and key not in ("BASH_ENV", "ENV")}
        self.env.update(
            HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
            XDG_STATE_HOME=str(self.directory / "state"),
            XDG_RUNTIME_DIR=str(self.directory / "run"),
            TERM="xterm-256color", SHELL=shutil.which("bash"),
            HERDR_SOCKET_PATH=str(config / "herdr.sock"),
        )
        Path(self.env["XDG_RUNTIME_DIR"]).mkdir(mode=0o700)
        self.socket = str(self.directory / "tmux.sock")
        self.addCleanup(self.stop_servers)
        validation = self.cli("config", "check")
        self.assertIn("config: ok", validation.stdout + validation.stderr)
        self.tmux("-f", "/dev/null", "new-session", "-d", "-s", "test", "-x", "140", "-y", "40",
                  "exec env -u TMUX -u TMUX_PANE " + shlex.quote(shutil.which("herdr")))
        self.until(lambda: self.cli("pane", "list", check=False).returncode == 0, "server ready")
        self.api("plugin", "link", str(config / "plugins/confirm-close"))
        self.until(lambda: "spaces" in self.screen(), "client ready")

    def cli(self, *args, check=True):
        return subprocess.run(["herdr", *args], env=self.env, cwd=self.directory,
                              capture_output=True, text=True, check=check, timeout=10)

    def api(self, *args):
        return json.loads(self.cli(*args).stdout)["result"]

    def tmux(self, *args, check=True):
        return subprocess.run(["tmux", "-S", self.socket, *args], env=self.env,
                              capture_output=True, text=True, check=check, timeout=5).stdout

    def screen(self):
        return self.tmux("capture-pane", "-p", "-t", "test", check=False)

    def until(self, condition, message):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.05)
        self.fail(f"Timed out: {message}\n{self.screen()}")

    def stop_servers(self):
        try:
            self.cli("server", "stop", check=False)
        finally:
            self.tmux("kill-server", check=False)
        with socket.socket(socket.AF_UNIX) as probe:
            self.assertNotEqual(probe.connect_ex(self.env["HERDR_SOCKET_PATH"]), 0,
                                "private Herdr server survived cleanup")

    def pane_ids(self):
        return {pane["pane_id"] for pane in self.api("pane", "list")["panes"]}

    def prefix(self, key):
        self.tmux("send-keys", "-t", "test", "C-b", key)

    def open_dialog(self):
        self.prefix("x")
        self.until(lambda: "Kill? (y/n)" in self.screen(), "confirmation popup")

    def test_compact_dialog_cancels_and_closes_its_invoker_after_focus_changes(self):
        original = self.api("pane", "current")["pane"]["pane_id"]
        self.open_dialog()
        lines = self.screen().splitlines()
        top = next(index for index, line in enumerate(lines) if "┌" in line and "┐" in line)
        left, right = lines[top].index("┌"), lines[top].index("┐")
        self.assertIn("┌Close pane", lines[top])
        self.assertEqual(lines[top + 3][left:right + 1], "└" + "─" * 16 + "┘")
        dialog = "\n".join(lines[top:top + 4])
        self.assertNotIn("popup", dialog)
        self.assertNotIn(original, dialog)
        self.assertEqual(self.tmux("display-message", "-p", "-t", "test", "#{cursor_flag}").strip(), "0")
        other = self.api("pane", "split", original, "--direction", "right", "--no-focus")["pane"]["pane_id"]
        before = self.pane_ids()
        for answer in ("n", "Enter", "Escape"):
            self.tmux("send-keys", "-t", "test", answer)
            self.until(lambda: "Kill? (y/n)" not in self.screen(), "popup dismissed")
            self.assertEqual(self.pane_ids(), before)
            self.open_dialog()
        self.api("pane", "focus", "--pane", original, "--direction", "right")
        self.assertEqual(self.api("pane", "current")["pane"]["pane_id"], other)
        self.tmux("send-keys", "-t", "test", "y")
        self.until(lambda: original not in self.pane_ids(), "original pane closed")
        self.assertEqual(self.pane_ids(), {other})

    def test_protected_group_close_keeps_every_pane_and_shows_the_error(self):
        repo = self.directory / "repository"
        worktree = self.directory / "checkout"
        subprocess.run(["git", "init", "-b", "main", str(repo)], env=self.env,
                       check=True, capture_output=True, timeout=5)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                        "commit", "--allow-empty", "-m", "fixture"], env=self.env,
                       check=True, capture_output=True, timeout=5)
        subprocess.run(["git", "-C", str(repo), "worktree", "add", "-b", "feature", str(worktree)],
                       env=self.env, check=True, capture_output=True, timeout=5)
        created = self.api("workspace", "create", "--cwd", str(repo), "--label", "group-root", "--focus")
        original = created["root_pane"]["pane_id"]
        self.api("worktree", "open", "--workspace", created["workspace"]["workspace_id"],
                 "--path", str(worktree), "--no-focus")
        before = self.pane_ids()
        self.until(lambda: "group-root" in self.screen(), "primary workspace visible")
        self.open_dialog()
        self.tmux("send-keys", "-t", "test", "y")
        self.until(lambda: "Any key" in self.screen(), "close refusal stays visible")
        self.assertIn("Use workspace", self.screen())
        self.assertIn("close.", self.screen())
        self.assertEqual(self.pane_ids(), before)
        self.tmux("send-keys", "-t", "test", "n")
        self.until(lambda: "Any key" not in self.screen(), "error dismissed")
        self.assertEqual(self.pane_ids(), before)

    def test_split_keypresses_match_tmux_and_keep_alt_directions(self):
        for key, direction in (("%", "right"), ('"', "down"), ("M-Enter", "down"), ("alt+shift+enter", "right")):
            with self.subTest(key=key):
                created = self.api("tab", "create", "--label", "split-check", "--focus")
                pane = created["root_pane"]["pane_id"]
                self.until(lambda: "split-check" in self.screen(), "new tab visible")
                if key == "alt+shift+enter":
                    self.tmux("send-keys", "-t", "test", "-H", "1b", "5b", "31", "33", "3b", "34", "75")
                elif key.startswith("M-"):
                    self.tmux("send-keys", "-t", "test", key)
                else:
                    self.prefix(key)
                self.until(lambda: len(self.api("pane", "layout", "--pane", pane)["layout"]["panes"]) == 2,
                           "two panes after split")
                layout = self.api("pane", "layout", "--pane", pane)["layout"]
                self.assertEqual(layout["splits"][0]["direction"], direction)
                self.api("tab", "close", created["tab"]["tab_id"])
                self.until(lambda: "split-check" not in self.screen(), "test tab closed")


if __name__ == "__main__":
    unittest.main()
