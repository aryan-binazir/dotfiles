from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "stow/scripts/sync_skills.py"


class SyncSkillsTest(unittest.TestCase):
    def setUp(self) -> None:
        spec = importlib.util.spec_from_file_location("sync_skills", SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repo = self.root / "cursor-plugins"
        self.skills = self.repo / "pstack/skills"
        self.target = self.root / "cc-config/skills/sym_linked"
        self.target.mkdir(parents=True)
        for name in ("unslop", "arena", "architect", "new-upstream-skill"):
            skill = self.skills / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(name)
        patcher = patch.multiple(self.module, CURSOR_PLUGINS_REPO=self.repo, TARGET_DIR=self.target)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_only_unslop_is_selected(self) -> None:
        self.assertEqual(self.module.iter_pstack_skill_dirs(), [self.skills / "unslop"])

    def test_cleanup_removes_only_pstack_links_and_is_repeatable(self) -> None:
        for name in ("unslop", "arena", "new-upstream-skill", "missing-upstream-skill"):
            (self.target / name).symlink_to(self.skills / name)
        other = self.root / "matt-pocock/architect"
        other.mkdir(parents=True)
        (self.target / "architect").symlink_to(other)
        (self.target / "notes").write_text("keep")
        (self.target / "local-skill").mkdir()
        self.module.remove_excluded_pstack_links()
        self.module.remove_excluded_pstack_links()
        self.assertEqual({path.name for path in self.target.iterdir()}, {"unslop", "architect", "notes", "local-skill"})
        self.assertEqual((self.target / "unslop").readlink(), self.skills / "unslop")
        self.assertEqual((self.target / "architect").readlink(), other)
        self.assertEqual((self.target / "notes").read_text(), "keep")

    def test_app_cleanup_preserves_other_sources(self) -> None:
        app = self.root / "app/skills"
        app.mkdir(parents=True)
        config_skills = self.target.parent
        (app / "arena").symlink_to(config_skills / "sym_linked/arena")
        (app / "unslop").symlink_to(config_skills / "sym_linked/unslop")
        (app / "external").symlink_to(self.root / "other-repo/external")
        with patch.object(self.module, "CC_CONFIG_SKILLS_DIR", config_skills):
            removed = self.module.remove_stale_top_level_links(app, {"unslop"})
        self.assertEqual(removed, 1)
        self.assertEqual({path.name for path in app.iterdir()}, {"unslop", "external"})


if __name__ == "__main__":
    unittest.main()
