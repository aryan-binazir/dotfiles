from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest import mock


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "stow" / "scripts" / "backup-git-repos"
)
SPEC = importlib.util.spec_from_loader(
    "backup_git_repos", SourceFileLoader("backup_git_repos", str(SCRIPT_PATH))
)
assert SPEC is not None
assert SPEC.loader is not None
backup_git_repos = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = backup_git_repos
SPEC.loader.exec_module(backup_git_repos)


class BackupRepositoryTests(unittest.TestCase):
    def test_existing_verified_daily_bundle_is_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "backups"
            destination = root / "project"
            destination.mkdir(parents=True)
            repo_path = Path(temp_dir) / "repo"
            repo_path.mkdir()
            existing = destination / "example-2026-07-21.bundle"
            existing.write_text("existing", encoding="utf-8")
            repo = backup_git_repos.RepositoryConfig(
                name="example", path=repo_path, destination="project"
            )

            with (
                mock.patch.object(backup_git_repos, "validate_git_repo"),
                mock.patch.object(backup_git_repos, "fetch_origin_main"),
                mock.patch.object(backup_git_repos, "confirm_origin_main"),
                mock.patch.object(backup_git_repos, "verify_bundle") as verify,
                mock.patch.object(backup_git_repos, "apply_retention") as retention,
                mock.patch.object(backup_git_repos, "collect_bundle_refs") as collect,
            ):
                result = backup_git_repos.backup_repository(
                    repo,
                    code_backups_root=root,
                    destinations={"project": "project"},
                    date_stamp="2026-07-21",
                )

            self.assertEqual(result, existing)
            verify.assert_called_once_with(existing, repo_path)
            retention.assert_called_once()
            collect.assert_not_called()

    def test_existing_invalid_daily_bundle_still_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "backups"
            destination = root / "project"
            destination.mkdir(parents=True)
            repo_path = Path(temp_dir) / "repo"
            repo_path.mkdir()
            existing = destination / "example-2026-07-21.bundle"
            existing.write_text("invalid", encoding="utf-8")
            repo = backup_git_repos.RepositoryConfig(
                name="example", path=repo_path, destination="project"
            )

            with (
                mock.patch.object(backup_git_repos, "validate_git_repo"),
                mock.patch.object(backup_git_repos, "fetch_origin_main"),
                mock.patch.object(backup_git_repos, "confirm_origin_main"),
                mock.patch.object(
                    backup_git_repos,
                    "verify_bundle",
                    side_effect=backup_git_repos.BackupError("invalid bundle"),
                ),
                mock.patch.object(backup_git_repos, "apply_retention") as retention,
            ):
                with self.assertRaisesRegex(
                    backup_git_repos.BackupError, "invalid bundle"
                ):
                    backup_git_repos.backup_repository(
                        repo,
                        code_backups_root=root,
                        destinations={"project": "project"},
                        date_stamp="2026-07-21",
                    )

            retention.assert_not_called()


if __name__ == "__main__":
    unittest.main()
