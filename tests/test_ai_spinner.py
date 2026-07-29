from __future__ import annotations

import os
import re
import signal
import subprocess
import tempfile
import textwrap
import time
import unittest
from pathlib import Path


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "stow"
    / "arch-linux"
    / "tmux"
    / ".config"
    / "tmux"
    / "scripts"
    / "ai-spinner.sh"
)

TMUX_STUB = """\
#!/bin/sh

case "$*" in
    "list-windows -a -F "*)
        printf '@1\\n'
        ;;
    "list-sessions -F "*)
        printf '$1\\n'
        ;;
    "has-session")
        exit 0
        ;;
    "show -gqv @ai_spinner_pid")
        printf '%s\\n' "$PPID"
        ;;
    "list-panes -a -F "*)
        sleep 0.3
        printf '$1|@1|%%1|claude|⠋ working\\n'
        ;;
    "list-clients -F "*)
        printf 'test-client\\n'
        ;;
    "refresh-client "*)
        date +%s%N >> "$AI_SPINNER_TEST_LOG"
        ;;
esac

exit 0
"""


class AiSpinnerTest(unittest.TestCase):
    def test_every_frame_transition_moves_two_dots(self) -> None:
        script = SCRIPT_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"^f0=(\S+) f1=(\S+) f2=(\S+) f3=(\S+) "
            r"f4=(\S+) f5=(\S+) f6=(\S+) f7=(\S+)$",
            script,
            re.MULTILINE,
        )
        self.assertIsNotNone(match)
        assert match is not None

        frames = [ord(frame) - 0x2800 for frame in match.groups()]
        transitions = [
            (current ^ following).bit_count()
            for current, following in zip(frames, frames[1:] + frames[:1])
        ]

        self.assertEqual(transitions, [2] * 8)

    def test_slow_detection_does_not_pause_animation(self) -> None:
        script = SCRIPT_PATH.read_text(encoding="utf-8")
        sleep_match = re.search(r"^\s*sleep ([0-9.]+)$", script, re.MULTILINE)
        self.assertIsNotNone(sleep_match)
        assert sleep_match is not None
        frame_interval_seconds = float(sleep_match.group(1))

        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir)
            tmux_stub = test_dir / "tmux"
            tmux_stub.write_text(textwrap.dedent(TMUX_STUB), encoding="utf-8")
            tmux_stub.chmod(0o755)
            refresh_log = test_dir / "refresh.log"
            refresh_log.touch()

            env = os.environ.copy()
            env["PATH"] = f"{test_dir}:{env['PATH']}"
            env["AI_SPINNER_TEST_LOG"] = str(refresh_log)

            process = subprocess.Popen(
                [str(SCRIPT_PATH)],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                time.sleep(2.6)
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=1)

            refresh_times = [
                int(timestamp)
                for timestamp in refresh_log.read_text(encoding="utf-8").splitlines()
            ]
            self.assertGreaterEqual(
                len(refresh_times), int(2 / frame_interval_seconds)
            )

            gaps_ms = [
                (current - previous) / 1_000_000
                for previous, current in zip(refresh_times, refresh_times[1:])
            ]
            self.assertLessEqual(
                max(gaps_ms), frame_interval_seconds * 1_000 + 150
            )


if __name__ == "__main__":
    unittest.main()
