#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

import subprocess
import sys
from pathlib import Path


SKILLS_REPO = Path("~/repos/skills").expanduser()
TARGET_DIR = Path("~/repos/cc-config/skills/sym_linked").expanduser()
CC_CONFIG_SKILLS_DIR = Path("~/repos/cc-config/skills").expanduser()
AGENTS_SOURCE = Path("~/repos/cc-config/AGENTS.md").expanduser()
SOURCE_DIRS = [
    SKILLS_REPO / "skills" / "engineering",
    SKILLS_REPO / "skills" / "productivity",
]
APP_SKILL_DIRS = [
    ("codex", Path("~/.codex").expanduser(), Path("~/.codex/skills").expanduser()),
    ("claude", Path("~/.claude").expanduser(), Path("~/.claude/skills").expanduser()),
    ("cursor", Path("~/.cursor").expanduser(), Path("~/.cursor/skills").expanduser()),
]
APP_INSTRUCTION_LINKS = [
    ("codex", Path("~/.codex").expanduser(), Path("~/.codex/AGENTS.md").expanduser()),
    ("claude", Path("~/.claude").expanduser(), Path("~/.claude/CLAUDE.md").expanduser()),
    ("cursor", Path("~/.cursor").expanduser(), Path("~/.cursor/AGENTS.md").expanduser()),
]


def require_dir(path: Path, label: str) -> None:
    if not path.exists():
        raise RuntimeError(f"{label} does not exist: {path}")
    if not path.is_dir():
        raise RuntimeError(f"{label} is not a directory: {path}")


def pull_skills() -> None:
    require_dir(SKILLS_REPO, "skills repo")

    print(f"Pulling {SKILLS_REPO}")
    try:
        subprocess.run(["git", "-C", str(SKILLS_REPO), "pull", "--ff-only"], check=True)
    except subprocess.CalledProcessError as error:
        raise RuntimeError(f"git pull failed in {SKILLS_REPO}") from error


def symlink_skills() -> None:
    for source_dir in SOURCE_DIRS:
        require_dir(source_dir, "source skills directory")

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Syncing skills into {TARGET_DIR}")

    created = 0
    replaced = 0
    unchanged = 0

    for source_dir in SOURCE_DIRS:
        for source_path in sorted(source_dir.iterdir()):
            if not source_path.is_dir():
                continue

            target_path = TARGET_DIR / source_path.name
            if target_path.is_symlink():
                if target_path.resolve(strict=False) == source_path:
                    unchanged += 1
                    continue
                print(f"Relinking {target_path.name}: {target_path} -> {source_path}")
                target_path.unlink()
                replaced += 1
            elif target_path.exists():
                raise RuntimeError(f"target exists and is not a symlink: {target_path}")
            else:
                print(f"Linking {target_path.name}: {target_path} -> {source_path}")
                created += 1

            target_path.symlink_to(source_path)

    print(
        "Done: "
        f"{created} created, "
        f"{replaced} replaced, "
        f"{unchanged} unchanged"
    )


def iter_cc_config_skill_dirs() -> list[Path]:
    require_dir(CC_CONFIG_SKILLS_DIR, "cc-config skills directory")

    skill_dirs: list[Path] = []
    stack = [CC_CONFIG_SKILLS_DIR]
    seen_real_dirs: set[Path] = set()

    while stack:
        current_dir = stack.pop()
        real_dir = current_dir.resolve(strict=False)
        if real_dir in seen_real_dirs:
            continue
        seen_real_dirs.add(real_dir)

        if (current_dir / "SKILL.md").is_file():
            skill_dirs.append(current_dir)
            continue

        for child in sorted(current_dir.iterdir(), reverse=True):
            if child.name == "backups":
                continue
            if child.is_dir():
                stack.append(child)

    return sorted(skill_dirs, key=lambda path: path.relative_to(CC_CONFIG_SKILLS_DIR).parts)


def skill_priority(path: Path) -> tuple[int, tuple[str, ...]]:
    parts = path.relative_to(CC_CONFIG_SKILLS_DIR).parts
    if len(parts) == 1:
        return (0, parts)
    if parts[0] in {"personal_dev", "personal_other"}:
        return (1, parts)
    if parts[0] == ".system":
        return (2, parts)
    if parts[0] == "sym_linked":
        return (3, parts)
    return (4, parts)


def flat_skill_sources(skill_dirs: list[Path]) -> tuple[list[Path], list[tuple[str, Path, Path]]]:
    chosen: dict[str, Path] = {}
    duplicates: list[tuple[str, Path, Path]] = []

    for source_path in sorted(skill_dirs, key=skill_priority):
        skill_name = source_path.name
        if skill_name in chosen:
            duplicates.append((skill_name, source_path, chosen[skill_name]))
            continue
        chosen[skill_name] = source_path

    return (list(chosen.values()), duplicates)


def prepare_app_skills_dir(app_name: str, app_skills_dir: Path) -> bool:
    if app_skills_dir.is_symlink():
        if app_skills_dir.resolve(strict=False) != CC_CONFIG_SKILLS_DIR:
            print(
                f"Skipping {app_name}: "
                f"skills directory is a symlink to {app_skills_dir.readlink()}"
            )
            return False

        print(
            f"Converting {app_name}: "
            f"replacing skills root symlink with flat directory: {app_skills_dir}"
        )
        app_skills_dir.unlink()

    if app_skills_dir.exists() and not app_skills_dir.is_dir():
        print(f"Skipping {app_name}: skills path is not a directory: {app_skills_dir}")
        return False

    app_skills_dir.mkdir(parents=True, exist_ok=True)
    return True


def sync_one_skill(source_path: Path, target_path: Path) -> str:

    if target_path.is_symlink():
        if target_path.readlink() == source_path:
            return "unchanged"
        print(f"Relinking {target_path}: {target_path.readlink()} -> {source_path}")
        target_path.unlink()
        target_path.symlink_to(source_path)
        return "replaced"

    if target_path.exists():
        print(f"Skipping {target_path}: exists and is not a symlink")
        return "skipped"

    print(f"Linking {target_path} -> {source_path}")
    target_path.symlink_to(source_path)
    return "created"


def sync_instruction_links() -> None:
    require_dir(AGENTS_SOURCE.parent, "cc-config directory")
    if not AGENTS_SOURCE.is_file():
        raise RuntimeError(f"agents source file does not exist: {AGENTS_SOURCE}")

    print(f"Syncing instruction links from {AGENTS_SOURCE}")
    counts = {
        "created": 0,
        "replaced": 0,
        "unchanged": 0,
        "skipped": 0,
    }

    for app_name, app_dir, target_path in APP_INSTRUCTION_LINKS:
        if not app_dir.exists():
            print(f"Skipping {app_name}: app directory does not exist: {app_dir}")
            continue
        if not app_dir.is_dir():
            print(f"Skipping {app_name}: app path is not a directory: {app_dir}")
            continue

        result = sync_one_skill(AGENTS_SOURCE, target_path)
        counts[result] += 1

    print(
        "Instruction links done: "
        f"{counts['created']} created, "
        f"{counts['replaced']} replaced, "
        f"{counts['unchanged']} unchanged, "
        f"{counts['skipped']} skipped"
    )


def remove_stale_top_level_links(app_skills_dir: Path, desired_names: set[str]) -> int:
    removed = 0

    for target_path in sorted(app_skills_dir.iterdir()):
        if not target_path.is_symlink():
            continue
        if target_path.name in desired_names:
            continue

        print(f"Removing stale skill link {target_path}: {target_path.readlink()}")
        target_path.unlink()
        removed += 1

    return removed


def prune_empty_parents(path: Path, root: Path) -> None:
    current_path = path
    while current_path != root:
        try:
            current_path.rmdir()
        except OSError:
            return
        current_path = current_path.parent


def cleanup_nested_skill_links(app_skills_dir: Path) -> int:
    removed = 0

    for group_name in [".system", "personal_dev", "personal_other", "sym_linked"]:
        group_path = app_skills_dir / group_name
        if group_path.is_symlink():
            continue
        if not group_path.is_dir():
            continue

        for target_path in sorted(group_path.iterdir()):
            if not target_path.is_symlink():
                continue

            print(f"Removing nested skill link {target_path}: {target_path.readlink()}")
            target_path.unlink()
            removed += 1

        prune_empty_parents(group_path, app_skills_dir)

    return removed


def sync_app_skill_dirs() -> None:
    skill_dirs = iter_cc_config_skill_dirs()
    flat_skill_dirs, duplicates = flat_skill_sources(skill_dirs)
    desired_names = {source_path.name for source_path in flat_skill_dirs}
    print(f"Found {len(skill_dirs)} cc-config skills; syncing {len(flat_skill_dirs)} flat names")

    for skill_name, skipped_path, kept_path in duplicates:
        print(f"Skipping duplicate flat name {skill_name}: {skipped_path} (kept {kept_path})")

    for app_name, app_dir, app_skills_dir in APP_SKILL_DIRS:
        if not app_dir.exists():
            print(f"Skipping {app_name}: app directory does not exist: {app_dir}")
            continue
        if not app_dir.is_dir():
            print(f"Skipping {app_name}: app path is not a directory: {app_dir}")
            continue
        if not prepare_app_skills_dir(app_name, app_skills_dir):
            continue

        print(f"Syncing flat cc-config skills into {app_skills_dir}")
        stale_removed = remove_stale_top_level_links(app_skills_dir, desired_names)

        counts = {
            "created": 0,
            "replaced": 0,
            "unchanged": 0,
            "skipped": 0,
        }

        for source_path in flat_skill_dirs:
            target_path = app_skills_dir / source_path.name
            result = sync_one_skill(source_path, target_path)
            counts[result] += 1

        nested_removed = cleanup_nested_skill_links(app_skills_dir)

        print(
            f"{app_name} done: "
            f"{counts['created']} created, "
            f"{counts['replaced']} replaced, "
            f"{counts['unchanged']} unchanged, "
            f"{counts['skipped']} skipped, "
            f"{stale_removed} stale links removed, "
            f"{nested_removed} nested links removed"
        )


def main() -> int:
    pull_skills()
    symlink_skills()
    sync_app_skill_dirs()
    sync_instruction_links()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        raise SystemExit(130)
    except Exception as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(1)
