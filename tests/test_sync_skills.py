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
        for name in ("unslop", "statechart", "create-formal-verification-skill", "maintain-formal-verification-skill", "arena", "architect", "new-upstream-skill"):
            skill = self.skills / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(name)
        patcher = patch.multiple(self.module, CURSOR_PLUGINS_REPO=self.repo, TARGET_DIR=self.target)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_only_allowed_skills_are_selected(self) -> None:
        self.assertEqual(self.module.iter_pstack_skill_dirs(), [
            self.skills / "create-formal-verification-skill",
            self.skills / "maintain-formal-verification-skill",
            self.skills / "statechart",
            self.skills / "unslop",
        ])

    def test_cleanup_removes_only_pstack_links_and_is_repeatable(self) -> None:
        for name in ("unslop", "statechart", "create-formal-verification-skill", "maintain-formal-verification-skill", "arena", "new-upstream-skill", "missing-upstream-skill"):
            (self.target / name).symlink_to(self.skills / name)
        other = self.root / "matt-pocock/architect"
        other.mkdir(parents=True)
        (self.target / "architect").symlink_to(other)
        (self.target / "notes").write_text("keep")
        (self.target / "local-skill").mkdir()
        self.module.remove_excluded_pstack_links()
        self.module.remove_excluded_pstack_links()
        self.assertEqual({path.name for path in self.target.iterdir()}, {"unslop", "statechart", "create-formal-verification-skill", "maintain-formal-verification-skill", "architect", "notes", "local-skill"})
        for name in ("unslop", "statechart", "create-formal-verification-skill", "maintain-formal-verification-skill"):
            self.assertEqual((self.target / name).readlink(), self.skills / name)
        self.assertEqual((self.target / "architect").readlink(), other)
        self.assertEqual((self.target / "notes").read_text(), "keep")

    def test_opencode_targets_use_global_config_directory(self) -> None:
        config = Path("~/.config/opencode").expanduser()
        self.assertIn(("opencode", config, config / "skills"), self.module.APP_SKILL_DIRS)
        self.assertIn(("opencode", config, config / "AGENTS.md"), self.module.APP_INSTRUCTION_LINKS)

    def test_opencode_sync_links_skills_and_instructions_repeatably(self) -> None:
        config = self.root / ".config/opencode"
        app_skills = config / "skills"
        app_skills.mkdir(parents=True)
        config_skills = self.target.parent
        skill = config_skills / "personal_dev/review"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text("review")
        agents = config_skills.parent / "AGENTS.md"
        agents.write_text("shared instructions")
        (app_skills / "stale").symlink_to(config_skills / "removed")
        external = self.root / "external"
        external.mkdir()
        (app_skills / "external").symlink_to(external)
        local = app_skills / "local"
        local.mkdir()
        (local / "SKILL.md").write_text("keep local skill")

        with patch.multiple(
            self.module,
            CC_CONFIG_SKILLS_DIR=config_skills,
            AGENTS_SOURCE=agents,
            APP_SKILL_DIRS=[("opencode", config, app_skills)],
            APP_INSTRUCTION_LINKS=[("opencode", config, config / "AGENTS.md")],
        ):
            for _ in range(2):
                self.module.sync_app_skill_dirs()
                self.module.sync_instruction_links()

        self.assertEqual((app_skills / "review").readlink(), skill)
        self.assertEqual((config / "AGENTS.md").readlink(), agents)
        self.assertEqual((app_skills / "external").readlink(), external)
        self.assertEqual((local / "SKILL.md").read_text(), "keep local skill")
        self.assertEqual({path.name for path in app_skills.iterdir()}, {"review", "external", "local"})

    def test_opencode_sync_preserves_existing_instructions(self) -> None:
        config = self.root / ".config/opencode"
        config.mkdir(parents=True)
        instructions = config / "AGENTS.md"
        instructions.write_text("local instructions")
        agents = self.target.parent.parent / "AGENTS.md"
        agents.write_text("shared instructions")
        with patch.multiple(
            self.module,
            AGENTS_SOURCE=agents,
            APP_INSTRUCTION_LINKS=[("opencode", config, instructions)],
        ):
            self.module.sync_instruction_links()
        self.assertFalse(instructions.is_symlink())
        self.assertEqual(instructions.read_text(), "local instructions")

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
