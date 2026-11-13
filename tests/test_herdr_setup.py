import os, shutil, subprocess, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERDR = "stow/arch-linux/herdr/.config/herdr"
STUB = """#!/bin/sh
echo "$*" >>"$TEST_DIR/calls"
case $2 in
list) cat "$TEST_DIR/state" 2>/dev/null || true ;;
link) echo "[local:$(cd "$3" && pwd -P)]" >>"$TEST_DIR/state" ;;
*) echo "github:$3@${5:-main}" >>"$TEST_DIR/state" ;;
esac
"""


class SetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp = self.tmp = Path(temporary.name).resolve()
        # Copies outside Git, so links never point into the checkout under test.
        for path in (HERDR, "stow/scripts"):
            shutil.copytree(ROOT / path, tmp / path)
        (tmp / "bin").mkdir()
        (tmp / "bin/herdr").write_text(STUB)
        (tmp / "bin/herdr").chmod(0o755)
        self.cfg = tmp / "home/.config/herdr"
        self.env = dict(os.environ, HOME=str(tmp / "home"), TEST_DIR=str(tmp),
                        PATH=f"{tmp}/bin:{os.environ['PATH']}")

    def run_setup(self):
        (self.tmp / "calls").write_text("")
        result = subprocess.run(["bash", self.tmp / HERDR / "setup.sh"], env=self.env,
                                capture_output=True, text=True, timeout=10)
        return result, (self.tmp / "calls").read_text()

    def test_links_registers_and_pins_then_reruns_as_a_no_op(self):
        result, calls = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ("config.toml", "plugins/confirm-close", "plugins/last-workspace",
                     "plugins/config/tab-smart-rename"):
            self.assertEqual(os.readlink(self.cfg / name), str(self.tmp / HERDR / name))
        self.assertTrue((self.tmp / "home/.local/bin/hm").samefile(self.tmp / "stow/scripts/hm"))
        self.assertRegex(calls, r"^plugin list\nplugin link \S+/confirm-close\n"
                         r"plugin link \S+/last-workspace\nplugin install aryan-binazir/herdr-triage\n"
                         r"(plugin install \S+ --ref [0-9a-f]{40}\n){3}$")
        result, calls = self.run_setup()
        self.assertEqual((result.returncode, calls), (0, "plugin list\n"), result.stderr)

    def test_existing_destination_is_left_alone(self):
        self.cfg.mkdir(parents=True)
        (self.cfg / "config.toml").write_text("mine\n")
        result, _ = self.run_setup()
        self.assertIn("exists; not replacing", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.cfg / "config.toml").read_text(), "mine\n")

    def test_symlinked_parent_is_refused(self):
        self.cfg.mkdir(parents=True)
        (self.cfg / "plugins").symlink_to(self.tmp / HERDR / "plugins")
        self.assertIn("is a symlink", self.run_setup()[0].stderr)
