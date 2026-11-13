import os, shutil, subprocess, tempfile, unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERDR = "stow/arch-linux/herdr/.config/herdr"
TRIAGE = "aryan-binazir/herdr-triage"
OLD, NEW = "a" * 40, "b" * 40
HERDR_STUB = """#!/bin/sh
echo "$*" >>"$TEST_DIR/calls"
touch "$TEST_DIR/state"
case $2 in
list) cat "$TEST_DIR/state"; exit ;;
link) key="local:$(cd "$3" && pwd -P)"; line="${4#--} [$key]" ;;
*) key="github:$3@"; line="enabled [$key${5:-main}]" ;;
esac
grep -vF "[$key" "$TEST_DIR/state" >"$TEST_DIR/kept"
{ cat "$TEST_DIR/kept"; echo "$line"; } >"$TEST_DIR/state"
"""
GIT_STUB = """#!/bin/sh
[ "$1" = ls-remote ] && [ -n "${TRIAGE_HEAD-}" ] || exit 128
printf '%s\\tHEAD\\n' "$TRIAGE_HEAD"
"""


class SetupTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        tmp = self.tmp = Path(temporary.name).resolve()
        for path in (HERDR, "stow/scripts"):
            shutil.copytree(ROOT / path, tmp / path)
        (tmp / "bin").mkdir()
        for name, stub in (("herdr", HERDR_STUB), ("git", GIT_STUB)):
            (tmp / "bin" / name).write_text(stub)
            (tmp / "bin" / name).chmod(0o755)
        self.cfg = tmp / "home/.config/herdr"
        self.env = dict(os.environ, HOME=str(tmp / "home"), TEST_DIR=str(tmp),
                        PATH=f"{tmp}/bin:{os.environ['PATH']}")

    def setup_sh(self, head=OLD):
        (self.tmp / "calls").write_text("")
        env = dict(self.env, TRIAGE_HEAD=head) if head else self.env
        return subprocess.run(["bash", self.tmp / HERDR / "setup.sh"], env=env,
                              capture_output=True, text=True, timeout=10)

    def run_setup(self, head=OLD):
        result = self.setup_sh(head)
        self.assertEqual(result.returncode, 0, result.stderr)
        return (self.tmp / "calls").read_text()

    def relinks(self, confirm_close="--enabled"):
        return (f"plugin list\nplugin link {self.cfg}/plugins/confirm-close {confirm_close}\n"
                f"plugin link {self.cfg}/plugins/last-workspace --enabled\n")

    def disable(self, key):
        state = self.tmp / "state"
        state.write_text("".join(line.replace("enabled [", "disabled [") if key in line else line
                                 for line in state.read_text().splitlines(keepends=True)))

    def test_links_registers_and_pins_then_reruns_only_refresh_local_plugins(self):
        calls = self.run_setup()
        for name in ("config.toml", "plugins/confirm-close", "plugins/last-workspace",
                     "plugins/config/tab-smart-rename"):
            self.assertEqual(os.readlink(self.cfg / name), str(self.tmp / HERDR / name))
        self.assertTrue((self.tmp / "home/.local/bin/hm").samefile(self.tmp / "stow/scripts/hm"))
        self.assertRegex(calls, "^" + self.relinks() + f"plugin install {TRIAGE} --ref {OLD}\n"
                         r"(plugin install \S+ --ref [0-9a-f]{40}\n){3}$")
        self.assertEqual(self.run_setup(), self.relinks())

    def test_triage_follows_upstream_head_and_stays_put_offline(self):
        self.run_setup()
        self.assertEqual(self.run_setup(NEW), self.relinks() + f"plugin install {TRIAGE} --ref {NEW}\n")
        self.assertEqual(self.run_setup(None), self.relinks())

    def test_disabled_plugins_stay_disabled(self):
        self.run_setup()
        self.disable("confirm-close]")
        self.disable(TRIAGE)
        for _ in range(2):
            self.assertEqual(self.run_setup(NEW), self.relinks("--disabled"))

    def test_existing_destination_is_left_alone(self):
        self.cfg.mkdir(parents=True)
        (self.cfg / "config.toml").write_text("mine\n")
        result = self.setup_sh()
        self.assertIn("exists; not replacing", result.stderr)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.cfg / "config.toml").read_text(), "mine\n")

    def test_symlinked_parent_is_refused(self):
        self.cfg.mkdir(parents=True)
        (self.cfg / "plugins").symlink_to(self.tmp / HERDR / "plugins")
        result = self.setup_sh()
        self.assertIn("is a symlink", result.stderr)
