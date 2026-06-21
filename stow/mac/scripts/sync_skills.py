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
SOURCE_DIRS = [
    SKILLS_REPO / "skills" / "engineering",
    SKILLS_REPO / "skills" / "productivity",
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


def main() -> int:
    pull_skills()
    symlink_skills()
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
