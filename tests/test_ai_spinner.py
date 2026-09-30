"""Exercise the installed entrypoint against a private real tmux server."""
import fcntl
import json
import os
import pty
import re
import select
import shlex
import signal
import struct
import sys
import termios
import threading
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "stow/scripts/ai-spinner.sh"
CONFIG = ROOT / "stow/arch-linux/tmux/.config/tmux/tmux.conf"


@unittest.skipUnless(shutil.which("tmux"), "tmux is required")
class AttentionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="tmux-attention-")
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.socket = str(self.directory / "tmux.sock")
        self.env = {**os.environ, "TERM": "xterm-256color"}
        self.env.pop("TMUX", None)
        self.env.pop("TMUX_PANE", None)
        self.tmux("-f", "/dev/null", "new-session", "-d", "-s", "test", "-x", "100", "-y", "30", "sleep 300")
        self.addCleanup(self.stop_server)
        self.pane = self.tmux("display-message", "-p", "#{pane_id}").strip()
        self.window = self.tmux("display-message", "-p", "#{window_id}").strip()
        self.session = self.tmux("display-message", "-p", "#{session_id}").strip()
        self.tmux("set-option", "-g", "allow-rename", "off")
        self.tmux("set-option", "-g", "@ai_notifications", "off")
        self.sounds = self.directory / "sounds"
        self.tmux("set-option", "-g", "@ai_attention_command", f"printf 'sound\\n' >> '{self.sounds}'")
        self.processes = []

    def tmux(self, *args, check=True):
        result = subprocess.run(["tmux", "-S", self.socket, *args], env=self.env,
                                text=True, capture_output=True, timeout=5, check=check)
        return result.stdout

    def stop_server(self):
        for process in self.processes:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        self.tmux("kill-server", check=False)

    def start_daemon(self, extra_env=None, script=SCRIPT):
        pid = self.tmux("display-message", "-p", "#{pid}").strip()
        env = {**self.env, "TMUX": f"{self.socket},{pid},0", **(extra_env or {})}
        log = open(self.directory / f"daemon-{len(self.processes)}.log", "w")
        self.addCleanup(log.close)
        process = subprocess.Popen(["sh", str(script)], env=env, stdout=log, stderr=log)
        self.processes.append(process)
        return process

    def until(self, condition, message, timeout=8):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return
            time.sleep(0.05)
        logs = "\n".join(path.read_text() for path in self.directory.glob("daemon-*.log"))
        screen = self.tmux("capture-pane", "-pM", "-t", self.pane, check=False)
        self.fail(f"Timed out: {message}\n{logs}\n{screen}")

    def icon(self, scope="window", target=None):
        if scope == "window":
            return self.tmux("display-message", "-p", "-t", target or self.window, "#{E:@ai_spinner}").strip()
        return self.tmux("display-message", "-p", "-t", target or self.session, "#{E:@ai_spinner_s}").strip()

    def working(self, pane=None):
        self.tmux("select-pane", "-t", pane or self.pane, "-T", "⠋ Agent")

    def stopped(self, pane=None):
        self.tmux("select-pane", "-t", pane or self.pane, "-T", "✳ Agent")

    def sound_count(self):
        return len(self.sounds.read_text().splitlines()) if self.sounds.exists() else 0

    def notification_tools(self, platform="Linux"):
        tools = self.directory / "notification-tools"
        tools.mkdir()
        self.notifications = self.directory / "notifications.jsonl"
        body = f"#!{sys.executable}\n" + r'''
import json, os, pathlib, sys, time
name = pathlib.Path(sys.argv[0]).name
if name == "uname":
    print(os.environ["AI_TEST_OS"])
    sys.exit(0)
script = sys.stdin.read() if name == "osascript" else ""
if os.environ.get("AI_TEST_PERMISSION_DELAY") and (name == "terminal-notifier" or ("tty of" in script and "focus targetTerminal" not in script)):
    time.sleep(float(os.environ["AI_TEST_PERMISSION_DELAY"]))
with open(os.environ["AI_TEST_NOTIFICATIONS"], "a") as output:
    output.write(json.dumps({"tool": name, "args": sys.argv[1:], "pid": os.getpid()}) + "\n")
if name == "osascript":
    if "focus targetTerminal" in script:
        if sys.argv[-1] == os.environ.get("AI_TEST_TERMINAL_ID"):
            print("focused")
    elif "tty of" in script:
        print(os.environ.get("AI_TEST_TERMINAL_ID", ""))
        sys.exit(int(os.environ.get("AI_TEST_LOOKUP_EXIT", "0")))
if os.environ.get("AI_TEST_BACKEND_DELAY"):
    time.sleep(float(os.environ["AI_TEST_BACKEND_DELAY"]))
sys.exit(int(os.environ.get("AI_TEST_BACKEND_EXIT", "0")))
'''
        for name in ("uname", "notify-send", "terminal-notifier", "osascript"):
            path = tools / name
            path.write_text(body)
            path.chmod(0o755)
        self.tmux("set-option", "-g", "@ai_notifications", "on")
        return {"PATH": f"{tools}:{self.env['PATH']}", "AI_TEST_OS": platform,
                "AI_TEST_NOTIFICATIONS": str(self.notifications)}

    def notification_records(self):
        if not self.notifications.exists():
            return []
        return [json.loads(line) for line in self.notifications.read_text().splitlines()]

    def test_background_completion_shows_an_informational_desktop_notification(self):
        env = self.notification_tools()
        self.working()
        self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: len(self.notification_records()) == 1, "desktop notification")
        record = self.notification_records()[0]
        self.assertEqual(record["tool"], "notify-send")
        self.assertIn("Agent needs attention", record["args"])
        self.assertTrue(any("test" in argument for argument in record["args"]))
        self.assertNotIn("--action", record["args"])
        self.assertEqual(self.icon(), "✓")
        self.assertEqual(self.sound_count(), 1)

    def test_macos_completion_without_an_exact_terminal_uses_an_informational_notification(self):
        env = self.notification_tools("Darwin")
        self.working()
        self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: len(self.notification_records()) == 1, "macOS notification")
        record = self.notification_records()[0]
        self.assertEqual(record["tool"], "terminal-notifier")
        self.assertIn("Agent needs attention", record["args"])
        self.assertNotIn("-execute", record["args"])
        self.assertNotIn("-activate", record["args"])
        self.assertEqual(self.icon(), "✓")

    def test_foreground_completion_has_sound_without_a_desktop_popup(self):
        env = self.notification_tools()
        self.attach()
        self.working()
        self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.sound_count() == 1, "foreground completion")
        time.sleep(0.5)
        self.assertEqual(self.notification_records(), [])
        self.assertEqual(self.icon(), "")

    def test_disabled_or_failed_desktop_notifications_do_not_stop_attention(self):
        env = self.notification_tools()
        env["AI_TEST_BACKEND_EXIT"] = "7"
        self.tmux("set-option", "-g", "@ai_notifications", "off")
        daemon = self.start_daemon(env)
        for enabled, count in (("off", 0), ("on", 1), ("on", 2)):
            with self.subTest(enabled=enabled, count=count):
                self.tmux("set-option", "-g", "@ai_notifications", enabled)
                self.working()
                self.until(lambda: bool(self.icon()) and "✓" not in self.icon(), "working again")
                self.stopped()
                self.until(lambda: self.icon() == "✓", "unread despite notification failure")
                if count:
                    self.until(lambda: len(self.notification_records()) == count, "attempted popup")
                self.assertIsNone(daemon.poll())
        self.assertEqual(self.sound_count(), 3)

    def test_multiple_completed_panes_notify_once_each_across_reload(self):
        env = self.notification_tools()
        other = self.tmux("split-window", "-d", "-P", "-F", "#{pane_id}", "sleep 300").strip()
        self.working()
        self.working(other)
        self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "both working")
        self.stopped()
        self.stopped(other)
        self.until(lambda: len(self.notification_records()) == 2, "two pane notifications")
        self.start_daemon(env)
        time.sleep(1.5)
        self.assertEqual(len(self.notification_records()), 2)
        self.assertEqual(self.sound_count(), 1)

    def test_macos_without_terminal_notifier_falls_back_to_native_informational_popup(self):
        env = self.notification_tools("Darwin")
        (self.directory / "notification-tools" / "terminal-notifier").unlink()
        self.working()
        self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: len(self.notification_records()) == 1, "native fallback popup")
        self.assertEqual(self.notification_records()[0]["tool"], "osascript")
        self.assertEqual(self.icon(), "✓")

    def mac_notification_callback(self, extra_env=None, timeout=8):
        env = self.notification_tools("Darwin")
        env["AI_TEST_TERMINAL_ID"] = "ghostty-terminal-123"
        env.update(extra_env or {})
        self.env.update(env)
        self.env["TERM"] = "xterm-ghostty"
        self.tmux("new-window", "-t", "test", "-n", "viewed", "sleep 300")
        self.attach()
        self.working()
        self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "background work")
        self.stopped()
        self.until(lambda: any(record["tool"] == "terminal-notifier" for record in self.notification_records()), "mac popup", timeout=timeout)
        record = next(record for record in self.notification_records() if record["tool"] == "terminal-notifier")
        self.assertIn("-execute", record["args"])
        return record["args"][record["args"].index("-execute") + 1]

    def test_mac_permission_prompts_can_wait_longer_than_five_seconds(self):
        callback = self.mac_notification_callback({"AI_TEST_PERMISSION_DELAY": "6"}, timeout=20)
        subprocess.run(["sh", "-c", callback], env=self.env, check=True, timeout=10)
        self.assertEqual(self.tmux("list-clients", "-F", "#{pane_id}").strip(), self.pane)

    def test_failed_replacement_preparation_preserves_the_running_daemon(self):
        self.working()
        old = self.start_daemon()
        self.until(lambda: bool(self.icon()), "original daemon working")
        for failure in ("mktemp", "missing-python", "broken-python"):
            with self.subTest(failure=failure):
                tools = self.directory / failure
                tools.mkdir()
                for name in ("sh", "tmux", "mktemp", "rm", "rmdir"):
                    (tools / name).symlink_to(shutil.which(name))
                if failure == "mktemp":
                    (tools / "flock").symlink_to(shutil.which("flock"))
                    (tools / "mktemp").unlink()
                    (tools / "mktemp").write_text("#!/bin/sh\nexit 1\n")
                    (tools / "mktemp").chmod(0o755)
                elif failure == "broken-python":
                    (tools / "python3").write_text("#!/missing-python-interpreter\n")
                    (tools / "python3").chmod(0o755)
                replacement = self.start_daemon({"PATH": str(tools)})
                self.until(lambda: replacement.poll() is not None, "replacement rejected")
                time.sleep(0.5)
                self.assertIsNone(old.poll())
                self.assertEqual(self.tmux("show-options", "-gqv", "@ai_spinner_pid").strip(), str(old.pid))
        self.stopped()
        self.until(lambda: self.icon() == "✓", "original daemon still detects completion")

    def test_mac_tty_match_produces_a_click_that_focuses_the_exact_pane(self):
        callback = self.mac_notification_callback()
        subprocess.run(["sh", "-c", callback], env=self.env, check=True, timeout=10)
        self.assertEqual(self.tmux("list-clients", "-F", "#{pane_id}").strip(), self.pane)
        focus = self.notification_records()[-1]
        self.assertEqual(focus["tool"], "osascript")
        self.assertIn("ghostty-terminal-123", focus["args"])

    def test_mac_click_targets_original_client_with_a_newer_unrelated_client(self):
        callback = self.mac_notification_callback()
        original = self.tmux("list-clients", "-F", "#{client_name}").strip()
        self.tmux("new-session", "-d", "-s", "other", "sleep 300")
        self.attach(session="other")
        self.until(lambda: len(self.tmux("list-clients", "-F", "#{client_name}").splitlines()) == 2,
                   "two independent clients attached")
        before = self.tmux("list-clients", "-F", "#{client_name} #{session_id} #{window_id} #{pane_id}").splitlines()
        other = next(row for row in before if not row.startswith(original + " "))
        subprocess.run(["sh", "-c", callback], env=self.env, check=True, timeout=10)
        after = self.tmux("list-clients", "-F", "#{client_name} #{session_id} #{window_id} #{pane_id}").splitlines()
        self.assertIn(other, after)
        self.assertIn(f"{original} {self.session} {self.window} {self.pane}", after)

    def test_old_notification_cannot_focus_a_later_completion_in_the_same_pane(self):
        callback = self.mac_notification_callback()
        self.working()
        self.until(lambda: bool(self.icon()) and "✓" not in self.icon(), "resumed work")
        self.stopped()
        self.until(lambda: self.sound_count() == 2 and self.icon() == "✓", "later completion")
        before = self.tmux("list-clients", "-F", "#{pane_id}").strip()
        subprocess.run(["sh", "-c", callback], env=self.env, check=True, timeout=10)
        self.assertEqual(self.tmux("list-clients", "-F", "#{pane_id}").strip(), before)

    def test_installed_symlink_finds_the_notification_helper_in_the_stow_source(self):
        env = self.notification_tools()
        installed = self.directory / "installed"
        installed.mkdir()
        script = installed / "ai-spinner.sh"
        script.symlink_to(SCRIPT)
        self.working()
        self.start_daemon(env, script=script)
        self.until(lambda: bool(self.icon()), "working through installed symlink")
        self.stopped()
        self.until(lambda: len(self.notification_records()) == 1, "helper found beside real source")

    def test_daemon_and_reload_work_without_the_linux_flock_executable(self):
        tools = self.directory / "portable-tools"
        tools.mkdir()
        for name in ("sh", "tmux", "mktemp", "python3", "rm", "rmdir", "cat", "sort", "sleep", "awk"):
            (tools / name).symlink_to(shutil.which(name))
        env = {"PATH": str(tools)}
        self.working()
        old = self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "portable daemon working")
        self.stopped()
        self.until(lambda: self.icon() == "✓" and self.sound_count() == 1, "portable completion")
        new = self.start_daemon(env)
        self.until(lambda: old.poll() is not None, "portable ownership handed over")
        self.assertEqual(self.tmux("show-options", "-gqv", "@ai_spinner_pid").strip(), str(new.pid))
        time.sleep(1)
        self.assertEqual(self.sound_count(), 1)
        self.assertEqual(self.icon(), "✓")

    def test_unsupported_tmux_client_lookup_keeps_mac_popup_informational(self):
        env = self.notification_tools("Darwin")
        env["AI_TEST_TERMINAL_ID"] = "ghostty-terminal-123"
        real_tmux = shutil.which("tmux", path=self.env["PATH"])
        wrapper = self.directory / "notification-tools" / "tmux"
        wrapper.write_text(f"#!{sys.executable}\n" +
                           "import os, sys\n" +
                           "if any('#{L:' in arg for arg in sys.argv[1:]): sys.exit(0)\n" +
                           f"os.execv({real_tmux!r}, [{real_tmux!r}, *sys.argv[1:]])\n")
        wrapper.chmod(0o755)
        self.env.update(env)
        self.env["TERM"] = "xterm-ghostty"
        self.tmux("new-window", "-t", "test", "-n", "viewed", "sleep 300")
        self.attach()
        self.working()
        self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "background work")
        self.stopped()
        self.until(lambda: any(row["tool"] == "terminal-notifier" for row in self.notification_records()),
                   "informational popup")
        popup = next(row for row in self.notification_records() if row["tool"] == "terminal-notifier")
        self.assertNotIn("-execute", popup["args"])
        self.assertEqual(self.icon(), "✓")

    def test_shared_session_does_not_offer_mac_click_navigation(self):
        env = self.notification_tools("Darwin")
        env["AI_TEST_TERMINAL_ID"] = "ghostty-terminal-123"
        self.env.update(env)
        self.env["TERM"] = "xterm-ghostty"
        self.tmux("new-window", "-t", "test", "-n", "viewed", "sleep 300")
        self.attach()
        self.attach()
        self.until(lambda: len(self.tmux("list-clients", "-F", "#{client_name}").splitlines()) == 2, "both clients attached")
        self.working()
        self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "background work")
        self.stopped()
        self.until(lambda: any(row["tool"] == "terminal-notifier" for row in self.notification_records()), "informational popup")
        popup = next(row for row in self.notification_records() if row["tool"] == "terminal-notifier")
        self.assertNotIn("-execute", popup["args"])

    def test_click_does_nothing_if_the_pane_closed_or_another_client_joined(self):
        callback = self.mac_notification_callback()
        self.attach()
        self.until(lambda: len(self.tmux("list-clients", "-F", "#{client_name}").splitlines()) == 2, "second client attached")
        for closed in (False, True):
            with self.subTest(closed=closed):
                if closed:
                    self.tmux("kill-pane", "-t", self.pane)
                before = self.tmux("list-clients", "-F", "#{pane_id}")
                records = len(self.notification_records())
                subprocess.run(["sh", "-c", callback], env=self.env, check=True, timeout=10)
                self.assertEqual(self.tmux("list-clients", "-F", "#{pane_id}"), before)
                self.assertEqual(len(self.notification_records()), records)

    def test_failed_ghostty_focus_does_not_switch_the_tmux_client(self):
        callback = self.mac_notification_callback()
        self.env["AI_TEST_TERMINAL_ID"] = "different-ghostty-terminal"
        before = self.tmux("list-clients", "-F", "#{pane_id}")
        subprocess.run(["sh", "-c", callback], env=self.env, check=True, timeout=10)
        self.assertEqual(self.tmux("list-clients", "-F", "#{pane_id}"), before)

    def test_click_does_not_navigate_a_window_linked_after_the_notification(self):
        callback = self.mac_notification_callback()
        self.tmux("new-session", "-d", "-s", "sibling", "sleep 300")
        self.tmux("link-window", "-d", "-s", self.window, "-t", "sibling")
        before = self.tmux("list-clients", "-F", "#{pane_id}")
        records = len(self.notification_records())
        subprocess.run(["sh", "-c", callback], env=self.env, check=True, timeout=10)
        self.assertEqual(self.tmux("list-clients", "-F", "#{pane_id}"), before)
        self.assertEqual(len(self.notification_records()), records)

    def test_click_follows_a_pane_moved_within_its_original_session(self):
        callback = self.mac_notification_callback()
        destination = self.tmux("new-window", "-d", "-P", "-F", "#{window_id}", "-t", "test", "sleep 300").strip()
        self.tmux("move-pane", "-s", self.pane, "-t", destination)
        subprocess.run(["/bin/sh", "-c", callback], env={**self.env, "PATH": "/no-tools"}, check=True, timeout=10)
        self.assertEqual(self.tmux("list-clients", "-F", "#{pane_id}").strip(), self.pane)

    def test_click_selects_the_completed_split_even_after_focus_acknowledges_its_window(self):
        callback = self.mac_notification_callback()
        sibling = self.tmux("split-window", "-d", "-P", "-F", "#{pane_id}", "-t", self.window, "sleep 300").strip()
        self.tmux("select-pane", "-t", sibling)
        self.tmux("select-window", "-t", self.window)
        self.until(lambda: self.icon() == "", "normal focus acknowledges completed window")
        subprocess.run(["sh", "-c", callback], env=self.env, check=True, timeout=10)
        self.assertEqual(self.tmux("list-clients", "-F", "#{pane_id}").strip(), self.pane)

    def test_closed_pane_notification_cannot_focus_another_terminal(self):
        callback = self.mac_notification_callback()
        self.tmux("kill-pane", "-t", self.pane)
        before = self.tmux("list-clients", "-F", "#{pane_id}")
        records = len(self.notification_records())
        subprocess.run(["sh", "-c", callback], env=self.env, check=True, timeout=10)
        self.assertEqual(self.tmux("list-clients", "-F", "#{pane_id}"), before)
        self.assertEqual(len(self.notification_records()), records)

    def test_renaming_sessions_does_not_change_the_numeric_click_target_or_execute_names(self):
        self.mac_notification_callback()
        marker = self.directory / "must-not-exist"
        hostile = 'quoted " $(touch ' + str(marker) + ') [*]'
        self.tmux("rename-session", "-t", self.session, hostile)
        self.tmux("rename-window", "-t", self.window, hostile)
        notify = ROOT / "stow/scripts/tmux-agent-notify"
        subprocess.run([sys.executable, str(notify), "notify", "--socket", self.socket, "--pane", self.pane],
                       env=self.env, check=True, timeout=10)
        popup = [row for row in self.notification_records() if row["tool"] == "terminal-notifier"][-1]
        callback = popup["args"][popup["args"].index("-execute") + 1]
        subprocess.run(["sh", "-c", callback], env=self.env, check=True, timeout=10)
        self.assertEqual(self.tmux("list-clients", "-F", "#{pane_id}").strip(), self.pane)
        self.assertFalse(marker.exists())

    def test_older_ghostty_api_keeps_mac_notification_informational(self):
        env = self.notification_tools("Darwin")
        env["AI_TEST_LOOKUP_EXIT"] = "1"
        self.env.update(env)
        self.env["TERM"] = "xterm-ghostty"
        self.tmux("new-window", "-t", "test", "-n", "viewed", "sleep 300")
        self.attach()
        self.working()
        self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "background work")
        self.stopped()
        self.until(lambda: any(row["tool"] == "terminal-notifier" for row in self.notification_records()), "legacy API fallback")
        popup = next(row for row in self.notification_records() if row["tool"] == "terminal-notifier")
        self.assertNotIn("-execute", popup["args"])
        self.assertEqual(self.icon(), "✓")

    def test_notification_backend_does_not_hold_the_daemon_handover_lock(self):
        env = self.notification_tools()
        env["AI_TEST_BACKEND_DELAY"] = "30"
        self.working()
        old = self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: len(self.notification_records()) == 1, "slow backend started")
        backend_pid = self.notification_records()[0]["pid"]
        def stop_backend():
            try:
                os.kill(backend_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        self.addCleanup(stop_backend)
        self.start_daemon(env)
        self.until(lambda: old.poll() is not None, "handover before backend finishes", timeout=3)
        self.assertEqual(len(self.notification_records()), 1)

    def test_runtime_popup_mute_survives_config_reload_without_muting_sound(self):
        config = self.directory / "notification-reload.conf"
        config.write_text("\n".join(line for line in CONFIG.read_text().splitlines()
                                  if line.startswith("set ") and "@ai_notifications" in line) + "\n")
        self.tmux("set-option", "-g", "@ai_notifications", "off")
        self.tmux("source-file", str(config))
        self.tmux("source-file", str(config))
        self.assertEqual(self.tmux("show-options", "-gqv", "@ai_notifications").strip(), "off")
        self.assertTrue(self.tmux("show-options", "-gqv", "@ai_attention_command").strip())

    def test_missing_optional_python_or_notifier_preserves_linux_monitoring(self):
        tools = self.directory / "shell-only-tools"
        tools.mkdir()
        for name in ("sh", "tmux", "flock", "mktemp", "rm", "rmdir", "cat", "sort", "sleep", "awk"):
            (tools / name).symlink_to(shutil.which(name))
        copied = self.directory / "ai-spinner.sh"
        shutil.copyfile(SCRIPT, copied)
        self.tmux("set-option", "-g", "@ai_notifications", "on")
        for count, script, env in ((1, SCRIPT, {"PATH": str(tools)}), (2, copied, None)):
            with self.subTest(script=str(script), missing_python=bool(env)):
                self.working()
                daemon = self.start_daemon(env, script=script)
                self.until(lambda: bool(self.icon()) and "✓" not in self.icon(), "monitor without optional tools")
                self.stopped()
                self.until(lambda: self.icon() == "✓" and self.sound_count() == count, "completion without optional tools")
                self.assertIsNone(daemon.poll())

    def test_spinner_animation_does_not_repaint_stationary_application(self):
        body = "\n".join(f"BODY_ROW_{i:02d}: stationary application content" for i in range(20))
        self.tmux("respawn-pane", "-k", "-t", self.pane,
                  'printf "%s\\n" ' + shlex.quote(body) + '; exec sleep 300')
        configured = next(line for line in CONFIG.read_text().splitlines()
                          if line.startswith("set -g @themepack-window-status-current-format "))
        self.tmux("set-option", "-g", "window-status-current-format", shlex.split(configured)[3])
        self.tmux("set-option", "-g", "status-interval", "0")
        self.attach()
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        time.sleep(0.4)
        self.output.clear()
        time.sleep(0.9)
        output = bytes(self.output)
        self.assertNotIn(b"BODY_ROW_", output, "animating the status bar must not repaint application rows")
        frames = {c for c in output.decode(errors="replace") if c in "⡇⠏⠛⠹⢸⣰⣤⣆"}
        self.assertGreaterEqual(len(frames), 2, "spinner must actually animate in the PTY")

    def test_detached_work_is_tracked_without_animating(self):
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "detached work detected")
        frame = self.icon()
        time.sleep(0.9)
        self.assertEqual(self.icon(), frame, "no clients means no animation traffic")
        self.stopped()
        self.until(lambda: self.icon() == "✓" and self.sound_count() == 1, "detached completion still detected")
        self.attach()
        self.until(lambda: self.icon() == "", "view acknowledges completion")
        self.working()
        self.until(lambda: bool(self.icon()), "new work detected")
        frame = self.icon()
        self.until(lambda: self.icon() != frame, "animation resumes for attached client")

    def test_sessions_created_after_start_share_live_animation(self):
        self.attach()
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "first session working")
        pane = self.tmux("new-session", "-d", "-s", "later", "-P", "-F", "#{pane_id}", "sleep 300").strip()
        self.working(pane)
        self.until(lambda: bool(self.icon("session", "later")), "new session working")
        frame = self.icon("session", "later")
        self.until(lambda: self.icon("session", "later") != frame, "new session uses changing global frame")

    def test_animation_state_is_not_exported_to_new_panes(self):
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        pane = self.tmux("new-window", "-d", "-P", "-F", "#{pane_id}", "-t", "test",
                         'printf "FRAME=%s\\n" "${TMUX_AI_SPINNER_FRAME-unset}"; exec sleep 300').strip()
        self.until(lambda: "FRAME=" in self.tmux("capture-pane", "-p", "-t", pane), "new pane environment")
        self.assertIn("FRAME=unset", self.tmux("capture-pane", "-p", "-t", pane))

    def test_idle_and_unread_indicators_do_not_continually_redraw(self):
        self.tmux("new-window", "-t", "test", "sleep 300")
        self.attach()
        self.tmux("set-option", "-g", "status-interval", "0")
        self.start_daemon()
        self.until(lambda: "@ai_spinner_s" in self.tmux("show-options", "-t", self.session), "initial display published")

        def updates():
            messages = self.tmux("show-messages")
            return (messages.count("command: refresh-client -S"),
                    messages.count(" @ai_spinner "), messages.count(" @ai_spinner_s "))

        def assert_quiet():
            time.sleep(0.4)
            before = updates()
            time.sleep(1.3)
            self.assertEqual(updates(), before, "unchanged indicators must not trigger option writes or forced redraws")

        assert_quiet()
        self.working()
        self.until(lambda: bool(self.icon()), "working still animates")
        frame = self.icon()
        self.until(lambda: self.icon() != frame, "animation advances")
        self.stopped()
        self.until(lambda: self.icon() == "✓" and self.icon("session") == "✓", "unread attention")
        assert_quiet()
        self.assertEqual(self.sound_count(), 1)

    def test_idle_command_budget_does_not_grow_per_pane(self):
        for _ in range(19):
            self.tmux("new-window", "-d", "-t", "test", "sleep 300")
        self.attach()
        self.start_daemon()
        self.until(lambda: "@ai_spinner_s" in self.tmux("show-options", "-t", self.session), "initial display")
        time.sleep(0.4)
        before = self.tmux("show-messages").count(" command:")
        time.sleep(2)
        commands = self.tmux("show-messages").count(" command:") - before
        self.assertLessEqual(commands, 18, "idle monitoring must batch snapshots and avoid animation-rate control polling")

    def test_completion_stays_visible_and_sounds_once(self):
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working window indicator")
        self.stopped()
        self.until(lambda: self.icon() == "✓" and self.icon("session") == "✓", "persistent attention at both levels")
        self.until(lambda: self.sound_count() == 1, "one notification")
        time.sleep(2.5)
        self.assertEqual(self.icon(), "✓")
        self.assertEqual(self.sound_count(), 1)

    def attach(self, session="test"):
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
        client = subprocess.Popen(["tmux", "-S", self.socket, "attach-session", "-t", session],
                                  stdin=slave, stdout=slave, stderr=slave, env=self.env)
        os.close(slave)
        self.processes.append(client)
        self.addCleanup(os.close, master)
        self.output = bytearray()
        def drain():
            while client.poll() is None:
                try:
                    if select.select([master], [], [], 0.1)[0]:
                        self.output.extend(os.read(master, 65536))
                except OSError:
                    break
        threading.Thread(target=drain, daemon=True).start()
        self.until(lambda: "attached" in self.tmux("list-clients", "-F", "#{client_flags}"), "PTY client attached")
        return master

    def test_only_viewing_the_done_window_acknowledges_it(self):
        other = self.tmux("new-window", "-P", "-F", "#{window_id}", "-t", "test", "sleep 300").strip()
        self.attach()
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.icon("session") == "✓", "attention while sibling window is viewed")
        self.assertEqual(self.icon(target=other), "")
        self.tmux("select-window", "-t", self.window)
        self.until(lambda: self.icon() == "" and self.icon("session") == "", "view acknowledges relevant window")
        self.assertEqual(self.sound_count(), 1)

    def delay_tmux_response(self, kind):
        """Delay one real response, widening a scheduling gap without faking data."""
        wrapper_dir = self.directory / "wrapper"
        wrapper_dir.mkdir(exist_ok=True)
        wrapper = wrapper_dir / "tmux"
        wrapper.write_text(f"#!{sys.executable}\nREAL = {shutil.which('tmux')!r}\n" + r'''
import os, pathlib, subprocess, sys, time
args = sys.argv[1:]
kind = os.environ.get("TMUX_TEST_GATE_KIND")
gate = pathlib.Path(os.environ["TMUX_TEST_GATE"])
used, blocked, release = (gate.with_suffix(s) for s in (".used", ".blocked", ".release"))
match = (kind == "state" and ("show" in args or "list-panes" in args) and "@ai_attention_state" in " ".join(args)) or (kind == "scan" and "list-panes" in args)
if not match or used.exists():
    os.execv(REAL, [REAL, *args])
result = subprocess.run([REAL, *args], capture_output=True)
if kind != "state" or result.stdout.strip() == b"quiet2" or b"=quiet2|" in result.stdout:
    used.touch()
    blocked.write_bytes(result.stdout)
    deadline = time.monotonic() + 20
    while not release.exists() and gate.parent.exists() and time.monotonic() < deadline:
        time.sleep(.01)
sys.stdout.buffer.write(result.stdout)
sys.stderr.buffer.write(result.stderr)
sys.exit(result.returncode)
''')
        wrapper.chmod(0o755)
        gate = self.directory / "response-gate"
        release = gate.with_suffix(".release")
        self.addCleanup(release.touch)
        env = {"PATH": str(wrapper_dir) + os.pathsep + self.env["PATH"],
               "TMUX_TEST_GATE": str(gate), "TMUX_TEST_GATE_KIND": kind}
        return env, gate.with_suffix(".blocked"), release

    def test_reload_during_completion_does_not_duplicate_sound(self):
        env, blocked, release = self.delay_tmux_response("state")
        self.working()
        old = self.start_daemon(env)
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(blocked.exists, "old daemon sampled the last quiet observation", timeout=12)
        new = self.start_daemon()
        self.until(lambda: self.tmux("show-options", "-gqv", "@ai_spinner_pid").strip() == str(new.pid), "replacement claims ownership")
        time.sleep(0.7)
        release.touch()
        self.until(lambda: old.poll() is not None and self.sound_count() >= 1, "handover completes", timeout=12)
        time.sleep(1.3)
        self.assertEqual(self.sound_count(), 1, "old and new instances must not notify for the same completion")
        self.assertEqual(self.icon(), "✓")
        self.assertIsNone(new.poll())

    def test_moving_unread_pane_during_scan_does_not_acknowledge_old_window(self):
        self.tmux("split-window", "-d", "-t", self.window, "sleep 300")
        destination = self.tmux("new-window", "-d", "-P", "-F", "#{window_id}", "-t", "test", "sleep 300").strip()
        self.working()
        old = self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.icon() == "✓" and self.sound_count() == 1, "unread completion")
        old.terminate()
        old.wait(timeout=5)
        self.attach()
        env, blocked, release = self.delay_tmux_response("scan")
        self.start_daemon(env)
        self.until(blocked.exists, "scan sampled the source window")
        self.tmux("join-pane", "-d", "-s", self.pane, "-t", destination)
        release.touch()
        self.until(lambda: self.icon(target=destination) == "✓", "moved pane retains unread attention", timeout=12)
        self.assertEqual(self.icon(), "")
        self.assertEqual(self.icon("session"), "✓")
        self.assertEqual(self.sound_count(), 1)
        self.tmux("select-window", "-t", destination)
        self.until(lambda: self.icon(target=destination) == "" and self.icon("session") == "", "destination view acknowledges attention")

    def test_long_sound_does_not_hold_daemon_handover_lock(self):
        sound_pid = self.directory / "sound.pid"
        self.tmux("set-option", "-g", "@ai_attention_command", f"printf '%s' $$ > '{sound_pid}'; exec sleep 30")
        def stop_sound():
            if sound_pid.exists():
                try:
                    os.kill(int(sound_pid.read_text()), signal.SIGTERM)
                except ProcessLookupError:
                    pass
        self.addCleanup(stop_sound)
        self.working()
        old = self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.icon() == "✓" and sound_pid.exists(), "long sound started")
        self.start_daemon()
        self.until(lambda: old.poll() is not None, "old owner exits")
        self.working()
        self.until(lambda: bool(self.icon()) and "✓" not in self.icon(), "replacement runs without waiting for sound to finish")

    def test_reload_preserves_unread_without_replaying_sound(self):
        self.working()
        old = self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.icon() == "✓" and self.sound_count() == 1, "done")
        replacement = self.start_daemon()
        self.until(lambda: old.poll() is not None, "old daemon relinquishes ownership")
        time.sleep(2.5)
        self.assertIsNone(replacement.poll())
        self.assertEqual(self.icon(), "✓")
        self.assertEqual(self.icon("session"), "✓")
        self.assertEqual(self.sound_count(), 1)

    def test_session_keeps_done_while_another_window_works(self):
        other = self.tmux("new-window", "-d", "-P", "-F", "#{pane_id}", "-t", "test", "sleep 300").strip()
        self.working()
        self.working(other)
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.icon() == "✓" and "✓" in self.icon("session"), "unread done")
        self.assertRegex(self.icon("session"), r"^✓ [⡇⠏⠛⠹⢸⣰⣤⣆]$")
        time.sleep(1.3)
        self.assertIn("✓", self.icon("session"))
        self.assertEqual(self.sound_count(), 1)

    def test_pane_completion_is_not_hidden_by_another_pane_working(self):
        other = self.tmux("split-window", "-d", "-P", "-F", "#{pane_id}", "-t", self.window, "sleep 300").strip()
        self.working()
        self.working(other)
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: "✓" in self.icon(), "one pane done")
        self.assertRegex(self.icon(), r"^✓ [⡇⠏⠛⠹⢸⣰⣤⣆]$")
        self.assertEqual(self.sound_count(), 1)

    def test_closed_pane_clears_its_unread_without_an_extra_sound(self):
        other = self.tmux("split-window", "-d", "-P", "-F", "#{pane_id}", "-t", self.window, "sleep 300").strip()
        self.working(other)
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped(other)
        self.until(lambda: self.icon() == "✓" and self.sound_count() == 1, "done")
        self.tmux("kill-pane", "-t", other)
        self.until(lambda: self.icon() == "" and self.icon("session") == "", "closed pane leaves no stale attention")
        self.assertEqual(self.sound_count(), 1)

    def test_prefix_s_shows_attention_on_session_and_expanded_window(self):
        # Load the real picker binding, but never the production daemon/plugins.
        binding = next(line for line in CONFIG.read_text().splitlines() if line.startswith("bind s run-shell"))
        config = self.directory / "picker.conf"
        config.write_text(binding.replace("~/.config/tmux/scripts/update-branches.sh", "true") + "\n")
        self.tmux("source-file", str(config))
        self.tmux("rename-window", "-t", self.window, "agent")
        self.tmux("set-option", "-w", "-t", self.window, "@ai_spinner", " ✓")
        self.tmux("set-option", "-t", self.session, "@ai_spinner_s", "✓")
        master = self.attach()
        os.write(master, b"\x02s")
        self.until(lambda: self.tmux("display-message", "-p", "-t", self.pane, "#{pane_in_mode}").strip() == "1", "picker opened")
        self.until(lambda: "✓" in self.output.decode(errors="replace"), "session picker attention")
        self.output.clear()
        self.tmux("send-keys", "-t", self.pane, "Right")
        self.until(lambda: "panes" in self.output.decode(errors="replace"), "expanded window row")
        screen = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", self.output.decode(errors="replace"))
        self.assertRegex(screen, r"agent[^\r\n]*✓[^\r\n]*panes", screen)

    def test_prefix_w_shows_window_attention(self):
        config = self.directory / "window-picker.conf"
        config.write_text("\n".join(line for line in CONFIG.read_text().splitlines() if line.startswith("bind w ")) + "\n")
        self.tmux("source-file", str(config))
        self.tmux("rename-window", "-t", self.window, "agent")
        self.tmux("set-option", "-w", "-t", self.window, "@ai_spinner", " ✓")
        master = self.attach()
        os.write(master, b"\x02w")
        self.until(lambda: "sort:" in self.output.decode(errors="replace"), "window picker")
        screen = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", self.output.decode(errors="replace"))
        self.assertRegex(screen, r"agent[^\r\n]*✓", screen)

    def test_sound_default_reloads_cleanly_and_preserves_mute(self):
        config = self.directory / "sound-reload.conf"
        config.write_text("\n".join(line for line in CONFIG.read_text().splitlines() if line.startswith("set ") and "@ai_attention_command" in line) + "\n")
        self.tmux("set-option", "-g", "@ai_attention_command", "")
        self.tmux("source-file", str(config))
        self.tmux("source-file", str(config))
        self.assertEqual(self.tmux("show-options", "-gqv", "@ai_attention_command").strip(), "")

    def test_default_config_plays_the_completion_sound(self):
        player = self.directory / "canberra-gtk-play"
        player.write_text(f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{self.sounds}'\n")
        player.chmod(0o755)
        self.env["PATH"] = str(self.directory) + os.pathsep + self.env["PATH"]
        self.tmux("set-option", "-gu", "@ai_attention_command")
        config = self.directory / "sound.conf"
        config.write_text("\n".join(line for line in CONFIG.read_text().splitlines() if line.startswith("set ") and "@ai_attention_command" in line) + "\n")
        self.tmux("source-file", str(config))
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.sound_count() == 1, "default sound executable invoked")
        self.assertEqual(self.sounds.read_text().strip(), "-i complete")

    def test_linked_window_is_debounced_once_not_once_per_session(self):
        for name in ("linked1", "linked2"):
            self.tmux("new-session", "-d", "-s", name, "sleep 300")
            self.tmux("link-window", "-s", self.window, "-t", name)
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        time.sleep(1.3)
        self.assertNotIn("✓", self.icon())
        self.assertEqual(self.sound_count(), 0)
        self.until(lambda: self.icon() == "✓", "debounced done")
        for name in ("test", "linked1", "linked2"):
            self.until(lambda name=name: self.icon("session", name) == "✓", f"attention aggregated into {name}")
        self.assertEqual(self.sound_count(), 1)

    def test_unfocused_terminal_does_not_acknowledge_done(self):
        self.tmux("set-option", "-g", "focus-events", "on")
        master = self.attach()
        os.write(master, b"\x1b[O")
        self.until(lambda: "focused" not in self.tmux("list-clients", "-F", "#{client_flags}"), "terminal unfocused")
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.icon() == "✓", "unfocused window retains attention")
        os.write(master, b"\x1b[I")
        self.until(lambda: self.icon() == "", "focus acknowledges attention")
        self.assertEqual(self.sound_count(), 1)

    def test_picker_does_not_acknowledge_the_window_underneath(self):
        self.attach()
        self.tmux("choose-tree", "-t", self.pane)
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.icon() == "✓", "picker preserves unread attention")
        self.tmux("send-keys", "-t", self.pane, "q")
        self.until(lambda: self.icon() == "", "closing picker acknowledges attention")
        self.assertEqual(self.sound_count(), 1)

    def test_foreground_completion_rings_without_leaving_stale_attention(self):
        self.attach()
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.sound_count() == 1, "foreground completion sound")
        self.until(lambda: self.icon() == "" and self.icon("session") == "", "visible completion acknowledged")
        time.sleep(1.3)
        self.assertEqual(self.sound_count(), 1)

    def test_resuming_work_clears_previous_attention_and_can_notify_again(self):
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.icon() == "✓" and self.sound_count() == 1, "first completion")
        self.working()
        self.until(lambda: bool(self.icon()) and "✓" not in self.icon(), "new work supersedes old unread")
        self.stopped()
        self.until(lambda: self.icon() == "✓" and self.sound_count() == 2, "second completion")

    def test_failed_sound_command_does_not_stop_attention_tracking(self):
        self.tmux("set-option", "-g", "@ai_attention_command", "exit 1")
        self.working()
        process = self.start_daemon()
        self.until(lambda: bool(self.icon()), "working")
        self.stopped()
        self.until(lambda: self.icon() == "✓", "attention despite failed sound")
        self.assertIsNone(process.poll())
        self.working()
        self.until(lambda: bool(self.icon()) and "✓" not in self.icon(), "tracking continues")

    def test_pi_spinner_above_todo_footer_is_detected_without_matching_chat_text(self):
        executable = self.directory / "pi"
        shutil.copy2(shutil.which("sh"), executable)
        footer = "\n".join(f"footer widget {number}" for number in range(15))
        busy = " ⠴ Working\n" + footer
        idle = "Previous answer mentioned Working...\n" + footer
        body = ("printf '\\033[2J\\033[H%s\\n' " + shlex.quote(busy) +
                "; while IFS= read -r line; do printf '\\033[2J\\033[H%s\\n' " + shlex.quote(idle) + "; done")
        pane = self.tmux("split-window", "-d", "-h", "-P", "-F", "#{pane_id}", "-t", self.window,
                         shlex.join([str(executable), "-c", body])).strip()
        self.start_daemon()
        self.until(lambda: bool(self.icon()) and "✓" not in self.icon(), "Pi busy marker above 15 footer rows")
        self.tmux("send-keys", "-t", pane, "Done", "Enter")
        self.until(lambda: self.icon() == "✓" and self.sound_count() == 1, "chat text is not mistaken for activity")

    def test_idle_agent_uses_one_text_filter_per_capture(self):
        executable = self.directory / "pi"
        shutil.copy2(shutil.which("sh"), executable)
        self.tmux("new-window", "-d", "-t", "test",
                  shlex.join([str(executable), "-c", "printf 'Ready\\n'; while IFS= read -r line; do :; done"]))
        wrappers = self.directory / "filters"
        wrappers.mkdir()
        calls = self.directory / "filter-calls"
        for name in ("grep", "tail", "awk"):
            real = shutil.which(name)
            self.assertIsNotNone(real)
            wrapper = wrappers / name
            wrapper.write_text(f"#!/bin/sh\nprintf '%s\\n' {name} >> {shlex.quote(str(calls))}\nexec {shlex.quote(real)} \"$@\"\n")
            wrapper.chmod(0o755)
        self.attach()
        before = self.tmux("show-messages").count("command: capture-pane")
        self.start_daemon({"PATH": str(wrappers) + os.pathsep + self.env["PATH"]})
        self.until(lambda: "@ai_spinner_s" in self.tmux("show-options", "-t", self.session), "first scan applied")
        filters = len(calls.read_text().splitlines())
        captures = self.tmux("show-messages").count("command: capture-pane") - before
        self.assertGreaterEqual(captures, 1)
        self.assertLessEqual(filters, captures, "idle panes must not spawn multiple grep/tail stages per capture")

    def test_claude_footer_detects_native_and_named_commands(self):
        self.start_daemon()
        cases = (("2.1.284", "·"), ("claude", "✢"), ("node", "✳"), ("bun", "✶"),
                 ("2.1.284", "✻"), ("2.1.284", "✽"), ("2.1.284", "*"))
        for name, glyph in cases:
            with self.subTest(command=name):
                executable = self.directory / name
                shutil.copy2(shutil.which("sh"), executable)
                body = "while IFS= read -r line; do printf '\\033[2J\\033[H%s\\n' \"$line\"; done"
                pane = self.tmux("new-window", "-d", "-P", "-F", "#{pane_id}", "-t", "test",
                                 shlex.join([str(executable), "-c", body])).strip()
                self.tmux("select-pane", "-t", pane, "-T", "✳ Claude")
                self.until(lambda: self.tmux("display-message", "-p", "-t", pane,
                                            "#{pane_current_command}").strip() == name, "native foreground command")
                self.tmux("send-keys", "-t", pane, f"{glyph} Cogitating… (37s · ↓ 1.8k tokens)", "Enter")
                self.until(lambda: self.tmux("display-message", "-p", "-t", pane,
                                            "#{@ai_attention_state}").strip() == "working", "Claude working")
                self.assertNotIn("✓", self.icon(target=pane))
                self.assertTrue(self.icon("session"))
                self.tmux("send-keys", "-t", pane, "✻ Worked for 37s", "Enter")
                self.until(lambda: self.icon(target=pane) == "✓" and self.icon("session") == "✓",
                           "Claude completion at both scopes")
                self.tmux("kill-pane", "-t", pane)
                self.until(lambda: self.icon("session") == "", "closed Claude cleared")

    def test_claude_footer_ignores_prose_prompts_and_indented_transcripts(self):
        executable = self.directory / "2.1.284"
        shutil.copy2(shutil.which("sh"), executable)
        idle = "\n".join((
            "Ordinary prose… (with parentheses)",
            "  ✶ Cogitating… (37s · ↓ 1.8k tokens)",
            "❯ ✶ Cogitating… (37s · ↓ 1.8k tokens)",
            "✻ Worked for 37s",
            "✶ This is ordinary text… (with parentheses)",
            "✶ Example… (ordinary prose)",
            "  Working on the explanation… (not a status)",
            "❯ Working...",
        ))
        body = "printf '%s\\n' " + shlex.quote(idle) + "; while IFS= read -r line; do :; done"
        self.tmux("respawn-pane", "-k", "-t", self.pane, shlex.join([str(executable), "-c", body]))
        self.start_daemon()
        self.until(lambda: "@ai_spinner_s" in self.tmux("show-options", "-t", self.session), "first scan")
        time.sleep(3)
        self.assertEqual(self.icon(), "")
        self.assertEqual(self.icon("session"), "")
        self.assertEqual(self.sound_count(), 0)

    def test_existing_text_detectors_still_work(self):
        self.start_daemon()
        for name, text in (("pi", "Working..."), ("codex", "esc to interrupt"), ("node", "ctrl+c to stop"), ("cursor-agent", "ctrl+c to stop")):
            with self.subTest(agent=name):
                # A renamed shell provides a real foreground process with the
                # expected command name and synthetic TUI output, without agents.
                executable = self.directory / name
                shutil.copy2(shutil.which("sh"), executable)
                body = f"printf '\\033[2J\\033[H{text}\\n'; while IFS= read -r line; do printf '\\033[2J\\033[H%s\\n' \"$line\"; done"
                pane = self.tmux("split-window", "-d", "-P", "-F", "#{pane_id}", "-t", self.window,
                                 shlex.join([str(executable), "-c", body])).strip()
                self.until(lambda: bool(self.icon()) and "✓" not in self.icon(), f"{name} working text detected")
                self.tmux("send-keys", "-t", pane, "Ready", "Enter")
                self.until(lambda: self.icon() == "✓", f"{name} completion")
                self.tmux("kill-pane", "-t", pane)
                self.until(lambda: self.icon() == "", f"{name} cleanup")
        self.assertEqual(self.sound_count(), 4)

    def test_brief_redraw_does_not_ring_or_mark_done(self):
        self.working()
        self.start_daemon()
        self.until(lambda: bool(self.icon()), "working indicator")
        self.stopped()
        time.sleep(1.3)
        self.assertNotIn("✓", self.icon())
        self.assertEqual(self.sound_count(), 0)
        self.working()
        time.sleep(2.5)
        self.assertNotIn("✓", self.icon())
        self.assertEqual(self.sound_count(), 0)


if __name__ == "__main__":
    unittest.main()
