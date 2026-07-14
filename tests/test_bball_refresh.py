from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


SCRIPT_PATH = Path(__file__).parents[1] / "stow" / "scripts" / "bball_refresh"


def load_script():
    loader = importlib.machinery.SourceFileLoader("bball_refresh", str(SCRIPT_PATH))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class BballRefreshTest(unittest.TestCase):
    def test_dev_restart_refuses_to_stop_stack_below_ten_percent_free(self) -> None:
        script = load_script()
        usage = SimpleNamespace(total=1_000, used=901, free=99)
        stderr = io.StringIO()

        with (
            mock.patch("shutil.disk_usage", return_value=usage),
            mock.patch("subprocess.run") as run,
            mock.patch("sys.stderr", stderr),
        ):
            status = script.main(["--dev"])

        self.assertEqual(status, 1)
        self.assertIn("refusing to stop the local stack", stderr.getvalue())
        self.assertIn("at least 10% is required before make down", stderr.getvalue())
        run.assert_not_called()

    def test_dev_restart_preserves_down_up_at_ten_percent_free(self) -> None:
        script = load_script()
        usage = SimpleNamespace(total=1_000, used=900, free=100)
        run = mock.Mock(
            side_effect=(
                subprocess.CompletedProcess(["make", "down"], 0),
                subprocess.CompletedProcess(["make", "up"], 0),
            )
        )

        with (
            mock.patch("shutil.disk_usage", return_value=usage),
            mock.patch("subprocess.run", run),
        ):
            status = script.main(["--dev"])

        self.assertEqual(status, 0)
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [["make", "down"], ["make", "up"]],
        )


if __name__ == "__main__":
    unittest.main()
