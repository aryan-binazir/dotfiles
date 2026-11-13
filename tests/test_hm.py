import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


HM = Path(__file__).resolve().parents[1] / "stow/scripts/hm"
STUB = """#!{python}
import json, os, sys
with open(os.environ["CALLS"], "a") as calls:
    calls.write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1:] == ["workspace", "list"]:
    print(json.dumps({{"result": {{"workspaces": json.loads(os.environ["WORKSPACES"])}}}}))
if sys.argv[1:] == ["pane", "list"]:
    print(json.dumps({{"result": {{"panes": json.loads(os.environ["PANES"])}}}}))
"""


class HmTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name).resolve()
        bin_dir = self.home / "bin"
        bin_dir.mkdir()
        (bin_dir / "herdr").write_text(STUB.format(python=sys.executable))
        (bin_dir / "fzf").write_text('#!/bin/sh\ncat > "$HOME/picker"\nexit 1\n')
        for stub in bin_dir.iterdir():
            stub.chmod(0o755)
        self.calls = self.home / "calls"
        self.env = dict(os.environ, HOME=str(self.home), HERDR_ENV="1",
                        PATH=f"{bin_dir}:{os.environ['PATH']}", CALLS=str(self.calls))

    def hm(self, *args, workspaces=(), panes=()):
        env = dict(self.env, WORKSPACES=json.dumps(workspaces), PANES=json.dumps(panes))
        result = subprocess.run(["bash", str(HM), *args], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return self.calls.read_text().splitlines() if self.calls.exists() else []

    def test_picker_lists_each_useful_directory_once(self):
        keep = ["repos", "repos/app", "repos/.worktrees/app-fix", "repos/a/b/c/d/e",
                ".config/nvim", "notes"]
        junk = ["repos/app/.git/objects", "repos/app/node_modules/dep", ".cache/x",
                ".local/share", "a/b/c/d/e/f"]
        for path in keep + junk:
            (self.home / path).mkdir(parents=True, exist_ok=True)
        self.hm()
        listed = (self.home / "picker").read_text().splitlines()
        self.assertEqual(len(listed), len(set(listed)))
        for path in keep:
            self.assertIn(str(self.home / path), listed)
        for path in junk:
            self.assertNotIn(str(self.home / path), listed)

    def test_reuses_only_the_workspace_for_the_picked_directory(self):
        for path in ("a/src/lib", "b/src", "c/src"):
            (self.home / path).mkdir(parents=True)
        workspaces = [{"workspace_id": "w1", "label": "src"},
                      {"workspace_id": "w2", "label": "src"},
                      {"workspace_id": "w3", "label": "home"}]
        panes = [{"workspace_id": "w1", "cwd": str(self.home / "b/src")},
                 {"workspace_id": "w2", "cwd": str(self.home / "a/src/lib")},
                 {"workspace_id": "w3", "cwd": str(self.home / "c/src")}]
        self.assertIn("workspace focus w2",
                      self.hm(str(self.home / "a/src"), workspaces=workspaces, panes=panes))
        self.assertIn(f"workspace create --cwd {self.home / 'c/src'} --label src --focus",
                      self.hm(str(self.home / "c/src"), workspaces=workspaces, panes=panes))


if __name__ == "__main__":
    unittest.main()
