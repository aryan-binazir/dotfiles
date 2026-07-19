from __future__ import annotations

import importlib.machinery
import importlib.util
import subprocess
import unittest
from pathlib import Path
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
    def test_default_refresh_syncs_repos_then_rolls_workloads(self) -> None:
        script = load_script()

        def run_command(argv, **_kwargs):
            if argv == ["git", "status", "--porcelain"]:
                return subprocess.CompletedProcess(argv, 0, stdout="")
            return subprocess.CompletedProcess(argv, 0)

        with mock.patch("subprocess.run", side_effect=run_command) as run:
            status = script.main([])

        self.assertEqual(status, 0)
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [
                ["git", "status", "--porcelain"],
                ["gb"],
                ["git", "status", "--porcelain"],
                ["gb"],
                ["make", "rolling-refresh"],
            ],
        )

    def test_dev_refresh_rolls_workloads_without_stopping_cluster(self) -> None:
        script = load_script()
        run = mock.Mock(
            return_value=subprocess.CompletedProcess(["make", "rolling-refresh"], 0)
        )

        with (
            mock.patch("subprocess.run", run),
        ):
            status = script.main(["--dev"])

        self.assertEqual(status, 0)
        self.assertEqual(
            [call.args[0] for call in run.call_args_list],
            [["make", "rolling-refresh"]],
        )

    def test_maintenance_mode_is_not_available(self) -> None:
        script = load_script()
        run = mock.Mock()

        with mock.patch("subprocess.run", run), self.assertRaises(SystemExit) as error:
            script.main(["--maintenance"])

        self.assertEqual(error.exception.code, 2)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
