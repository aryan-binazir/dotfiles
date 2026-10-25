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
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]
HERDR_CONFIG = ROOT / "stow/arch-linux/herdr/.config/herdr"
SCRIPT = HERDR_CONFIG / "scripts/confirm-close.sh"


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

    def test_confirmation_closes_only_the_invoking_pane_on_its_server(self):
        result = self.run_helper("y")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.records(), [{
            "args": ["pane", "close", "w1:p2"],
            "socket": self.env["HERDR_SOCKET_PATH"],
        }])

    def test_other_keys_and_eof_cancel_without_closing(self):
        for answer in ("n", "N", "\n", "\x1b", "q", "\\", ""):
            with self.subTest(answer=answer):
                result = self.run_helper(answer)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.records(), [])

    def test_uppercase_confirmation_works_with_the_path_fallback(self):
        env = self.env.copy()
        cli = env.pop("HERDR_BIN_PATH")
        (self.directory / "herdr").symlink_to(cli)
        env["PATH"] = str(self.directory) + os.pathsep + env["PATH"]
        result = self.run_helper("Y", env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.records()[0]["args"], ["pane", "close", "w1:p2"])

    def test_missing_pane_or_server_context_never_attempts_a_close(self):
        for key in ("HERDR_ACTIVE_PANE_ID", "HERDR_SOCKET_PATH"):
            for value in (None, ""):
                with self.subTest(key=key, value=value):
                    env = self.env.copy()
                    if value is None:
                        env.pop(key)
                    else:
                        env[key] = value
                    result = self.run_helper("y", env)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.records(), [])

    def test_group_close_refusal_is_shown_without_escalating_or_retrying(self):
        env = {**self.env, "TEST_ERROR": "confirmation_required: closing this pane would close a worktree group"}
        result = self.run_helper("yn", env)
        self.assertNotEqual(result.returncode, 0)
        output = result.stdout + result.stderr
        self.assertIn("confirmation_required", output)
        self.assertIn("workspace", output)
        self.assertIn("Press any key", output)
        self.assertEqual(self.records(), [{
            "args": ["pane", "close", "w1:p2"],
            "socket": self.env["HERDR_SOCKET_PATH"],
        }])


class HerdrConfigTests(unittest.TestCase):
    def setUp(self):
        self.keys = tomllib.loads((HERDR_CONFIG / "config.toml").read_text())["keys"]

    def test_other_close_bindings_are_unchanged(self):
        self.assertEqual(self.keys["close_tab"], "prefix+ampersand")
        self.assertEqual(self.keys["close_workspace"], "prefix+shift+k")

    def test_tmux_prefix_split_directions_preserve_alt_shortcuts(self):
        self.assertEqual(self.keys["split_horizontal"], ['prefix+"', "alt+enter"])
        self.assertEqual(self.keys["split_vertical"], ["prefix+percent", "alt+shift+enter"])

    def test_prefix_x_runs_the_symlinked_confirmation_popup(self):
        self.assertEqual(self.keys["close_pane"], "alt+esc")
        bindings = [item for item in self.keys["command"] if item["key"] == "prefix+x"]
        self.assertEqual(len(bindings), 1)
        self.assertEqual(bindings[0]["type"], "popup")
        with tempfile.TemporaryDirectory(prefix="herdr home ") as home:
            installed = Path(home) / ".config/herdr/scripts/confirm-close.sh"
            installed.parent.mkdir(parents=True)
            installed.symlink_to(SCRIPT)
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith("HERDR_")}
            env.update(HOME=home, HERDR_ACTIVE_PANE_ID="w1:p2", HERDR_SOCKET_PATH="unused.sock")
            result = subprocess.run(
                ["sh", "-c", bindings[0]["command"]], input="n", env=env,
                capture_output=True, text=True, timeout=5,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Close pane w1:p2?", result.stdout)


@unittest.skipUnless(shutil.which("herdr") and shutil.which("tmux"), "Herdr and tmux are required")
class HerdrRuntimeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="herdr-", dir="/tmp")
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        home = self.directory / "home with spaces"
        config = home / ".config/herdr"
        (config / "scripts").mkdir(parents=True)
        (config / "scripts/confirm-close.sh").symlink_to(SCRIPT)
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

    def test_confirmation_can_cancel_and_keeps_the_invoker_after_focus_changes(self):
        original = self.api("pane", "current")["pane"]["pane_id"]
        other = self.api("pane", "split", original, "--direction", "right", "--no-focus")["pane"]["pane_id"]
        before = self.pane_ids()
        for answer in ("n", "Enter", "Escape"):
            self.prefix("x")
            self.until(lambda: f"Close pane {original}?" in self.screen(), "confirmation popup")
            self.assertEqual(self.pane_ids(), before)
            self.tmux("send-keys", "-t", "test", answer)
            self.until(lambda: f"Close pane {original}?" not in self.screen(), "popup dismissed")
            self.assertEqual(self.pane_ids(), before)
        self.prefix("x")
        self.until(lambda: f"Close pane {original}?" in self.screen(), "confirmation popup")
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
        self.prefix("x")
        self.until(lambda: f"Close pane {original}?" in self.screen(), "confirmation popup")
        self.tmux("send-keys", "-t", "test", "y")
        self.until(lambda: "Press any key" in self.screen(), "close refusal stays visible")
        self.assertIn("confirmation_required", self.screen())
        self.assertEqual(self.pane_ids(), before)
        self.tmux("send-keys", "-t", "test", "n")
        self.until(lambda: "Press any key" not in self.screen(), "error dismissed")
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
