import contextlib
import importlib.machinery
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "stow/scripts/kill-desktop-agents"
SLEEP = "import time; time.sleep(120)"


@unittest.skipUnless(sys.platform == "linux", "Linux process controls required")
class KillDesktopAgentsTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        loader = importlib.machinery.SourceFileLoader("kill_desktop_agents", str(SCRIPT))
        spec = importlib.util.spec_from_loader(loader.name, loader)
        self.module = importlib.util.module_from_spec(spec)
        with patch.object(sys, "dont_write_bytecode", True):
            loader.exec_module(self.module)
        self.module.DESKTOP_EXECUTABLES = {
            str(self.directory / "chatgpt/ChatGPT"),
            str(self.directory / "claude-desktop/claude-desktop"),
        }

    def executable(self, relative):
        executable = self.directory / relative
        executable.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(sys.executable, executable)
        return str(executable)

    def spawn(self, executable, source=SLEEP, *args):
        process = subprocess.Popen(
            [executable, "-u", "-c", source, *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )

        def cleanup():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
            process.stdout.close()
            process.stderr.close()

        self.addCleanup(cleanup)
        return process

    def run_command(self, *args):
        output = io.StringIO()
        with patch.object(sys, "argv", [str(SCRIPT), *args]), contextlib.redirect_stdout(output):
            result = self.module.main()
        return result, output.getvalue()

    def test_kills_desktop_trees_but_preserves_cli_and_impostors(self):
        desktop_pids = set()
        protected_pids = set()
        roots = []
        for package, app, cli in [
            ("chatgpt", "ChatGPT", "codex"),
            ("claude-desktop", "claude-desktop", "claude"),
        ]:
            desktop = self.executable(f"{package}/{app}")
            backend = self.executable(f"{package}/resources/{cli}")
            terminal_agent = self.executable(f"cli/{cli}")
            parent_source = (
                "import json, subprocess, sys, time; "
                f"helper = subprocess.Popen([{sys.executable!r}, '-c', {SLEEP!r}]); "
                f"backend = subprocess.Popen([{backend!r}, '-c', {SLEEP!r}]); "
                f"cli = subprocess.Popen([{terminal_agent!r}, '-c', {SLEEP!r}]); "
                "print(json.dumps([helper.pid, backend.pid, cli.pid]), flush=True); "
                "time.sleep(120)"
            )
            parent = self.spawn(desktop, parent_source)
            roots.append(parent)
            helper_pid, backend_pid, cli_pid = json.loads(parent.stdout.readline())
            desktop_pids.update([parent.pid, helper_pid, backend_pid])
            protected_pids.add(cli_pid)
            protected_pids.add(self.spawn(terminal_agent).pid)
            impostor = self.executable(f"impostors/{app}")
            protected_pids.add(self.spawn(impostor, SLEEP, desktop).pid)

        result, output = self.run_command("--dry-run")
        self.assertEqual(result, 0)
        listed_pids = {int(line.split(":", 1)[0]) for line in output.splitlines() if ":" in line}
        self.assertEqual(listed_pids, desktop_pids)
        self.assertTrue(desktop_pids <= self.module.snapshot().keys())

        result, output = self.run_command()
        self.assertEqual(result, 0)
        self.assertIn("Stopped 6 desktop app/helper processes.", output)
        for process in roots:
            self.assertEqual(process.wait(timeout=5), -signal.SIGKILL)
        remaining = self.module.snapshot()
        self.assertFalse(desktop_pids & remaining.keys())
        self.assertTrue(protected_pids <= remaining.keys())
        for pid in protected_pids:
            state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
            self.assertNotIn(state, {"T", "t"})

        result, output = self.run_command()
        self.assertEqual(result, 0)
        self.assertIn("No desktop app processes found.", output)

    def test_resumes_frozen_processes_if_cleanup_fails(self):
        desktop = self.executable("chatgpt/ChatGPT")
        parent = self.spawn(desktop)
        real_signal = signal.pidfd_send_signal

        def fail_kill(fd, sig):
            if sig == signal.SIGKILL:
                raise PermissionError("simulated failure")
            return real_signal(fd, sig)

        with patch.object(signal, "pidfd_send_signal", side_effect=fail_kill):
            with contextlib.redirect_stderr(io.StringIO()):
                result, _ = self.run_command()
        self.assertEqual(result, 1)
        self.assertIsNone(parent.poll())
        state = Path(f"/proc/{parent.pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        self.assertNotIn(state, {"T", "t"})

    def test_refuses_to_freeze_its_own_caller_tree(self):
        processes = {os.getpid(): (os.getppid(), 0, next(iter(self.module.DESKTOP_EXECUTABLES)))}
        with patch.object(self.module, "snapshot", return_value=processes):
            with patch.object(signal, "pidfd_send_signal") as send_signal:
                with contextlib.redirect_stderr(io.StringIO()):
                    result, _ = self.run_command()
        self.assertEqual(result, 1)
        send_signal.assert_not_called()


if __name__ == "__main__":
    unittest.main()
