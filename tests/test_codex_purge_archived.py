import contextlib
import fcntl
import importlib.machinery
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "stow/scripts/codex-purge-archived"


def load_module():
    spec = importlib.util.spec_from_loader(
        "codex_purge_archived",
        importlib.machinery.SourceFileLoader("codex_purge_archived", str(SCRIPT)),
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


purge = load_module()

T1 = "019f0000-0000-7000-8000-000000000001"  # archived, file present
T2 = "019f0000-0000-7000-8000-000000000002"  # archived, file missing
T3 = "019f0000-0000-7000-8000-000000000003"  # unarchived, file in sessions/
T4 = "019f0000-0000-7000-8000-000000000004"  # orphan file, no row
T5 = "019f0000-0000-7000-8000-000000000005"  # unarchived, but file also in archive dir
T6 = "019f0000-0000-7000-8000-000000000006"  # archived, rollout_path points to sessions/
T7 = "019f0000-0000-7000-8000-000000000007"  # archived, rollout_path is a symlink
T8 = "019f0000-0000-7000-8000-000000000008"  # archived, rollout_path outside codex home
PARENT = T1


def rollout_name(tid: str) -> str:
    return f"rollout-2026-08-01T10-00-00-{tid}.jsonl"


def create_db(path: Path, name: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    statements: list[tuple[str, str]] = []
    kind = None
    buf: list[str] = []
    for line in purge.EXPECTED_SCHEMA[name].splitlines():
        if line.startswith("-- "):
            if buf:
                statements.append((kind, "\n".join(buf)))
            kind = line.split()[1]
            buf = []
        else:
            buf.append(line)
    if buf:
        statements.append((kind, "\n".join(buf)))
    for want in ("table", "index", "trigger"):
        for kind, sql in statements:
            if kind != want:
                continue
            if sql.startswith("CREATE TABLE sqlite_sequence"):
                conn.execute("CREATE TABLE _seq_tmp(id INTEGER PRIMARY KEY AUTOINCREMENT)")
                conn.execute("DROP TABLE _seq_tmp")
                continue
            conn.execute(sql)
    conn.executemany(
        "INSERT INTO _sqlx_migrations(version, description, success, checksum, execution_time) "
        "VALUES (?, ?, 1, X'00', 0)",
        purge.EXPECTED_MIGRATIONS[name],
    )
    conn.commit()
    conn.close()


class Home:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.archive = root / "archived_sessions"
        self.sessions = root / "sessions" / "2026" / "08" / "01"
        self.archive.mkdir()
        self.sessions.mkdir(parents=True)
        (root / "thread-writer-locks").mkdir()
        create_db(root / purge.STATE_DB, purge.STATE_DB)
        create_db(root / purge.HISTORY_DB, purge.HISTORY_DB)
        self.history_lines: list[str] = []
        self.index_lines: list[str] = []

    def state(self):
        return contextlib.closing(sqlite3.connect(self.root / purge.STATE_DB, isolation_level=None))

    def history(self):
        return contextlib.closing(sqlite3.connect(self.root / purge.HISTORY_DB, isolation_level=None))

    def add_thread(self, tid: str, *, archived: bool, rollout_path: Path, write_file: bool = True):
        with self.state() as s:
            s.execute(
                "INSERT INTO threads(id, rollout_path, created_at, updated_at, source, "
                "model_provider, cwd, title, sandbox_policy, approval_mode, archived, archived_at) "
                "VALUES (?, ?, 1, 2, 'cli', 'openai', '/tmp', 't', '{}', 'never', ?, ?)",
                (tid, str(rollout_path), int(archived), 3 if archived else None),
            )
            s.execute(
                "INSERT INTO thread_attachments(id, thread_id, attachment_type, identity_key, "
                "payload, created_at) VALUES (?, ?, 'file', 'k', '{}', 1)",
                (f"att-{tid}", tid),
            )
            s.execute(
                "INSERT INTO thread_dynamic_tools(thread_id, position, name, description, "
                "input_schema) VALUES (?, 0, 'n', 'd', '{}')",
                (tid,),
            )
            if tid != PARENT:
                s.execute(
                    "INSERT INTO thread_spawn_edges(parent_thread_id, child_thread_id, status) "
                    "VALUES (?, ?, 'done')",
                    (PARENT, tid),
                )
        with self.history() as h:
            h.execute(
                "INSERT INTO thread_history_projection_state VALUES (?, 0, 0)", (tid,)
            )
            h.execute(
                "INSERT INTO thread_turns(thread_id, turn_id, rollout_ordinal, status) "
                "VALUES (?, 'turn', 0, 'completed')",
                (tid,),
            )
            h.executemany(
                "INSERT INTO thread_items(thread_id, turn_id, item_id, rollout_ordinal, "
                "created_at_ms, item_json) VALUES (?, 'turn', ?, ?, 1, '{}')",
                [(tid, "i1", 1), (tid, "i2", 2)],
            )
            h.execute(
                "INSERT INTO thread_realtime_items(thread_id, item_id, rollout_ordinal, "
                "created_at_ms, item_type, item_json) VALUES (?, 'r1', 0, 1, 'x', '{}')",
                (tid,),
            )
        if write_file:
            rollout_path.write_text('{"type":"session_meta"}\n')
        self.history_lines.append(json.dumps({"session_id": tid, "ts": 1, "text": "hi"}))
        self.index_lines.append(json.dumps({"id": tid, "thread_name": "n", "updated_at": "t"}))

    def write_jsonl(self) -> None:
        extra_history = ['{"session_id":"unrelated","ts":1,"text":"x"}', "not json at all"]
        (self.root / "history.jsonl").write_text(
            "\n".join(self.history_lines + extra_history) + "\n"
        )
        (self.root / "session_index.jsonl").write_text(
            "\n".join(self.index_lines + ['{"id":"unrelated","thread_name":"n"}']) + "\n"
        )

    def counts(self, tid: str) -> dict[str, int]:
        out = {}
        with self.state() as s:
            out["threads"] = s.execute("SELECT COUNT(*) FROM threads WHERE id=?", (tid,)).fetchone()[0]
            out["attachments"] = s.execute(
                "SELECT COUNT(*) FROM thread_attachments WHERE thread_id=?", (tid,)
            ).fetchone()[0]
            out["tools"] = s.execute(
                "SELECT COUNT(*) FROM thread_dynamic_tools WHERE thread_id=?", (tid,)
            ).fetchone()[0]
            out["edges"] = s.execute(
                "SELECT COUNT(*) FROM thread_spawn_edges WHERE child_thread_id=?", (tid,)
            ).fetchone()[0]
        with self.history() as h:
            for table in purge.HISTORY_TABLES:
                out[table] = h.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE thread_id=?", (tid,)
                ).fetchone()[0]
        history = (self.root / "history.jsonl").read_text()
        index = (self.root / "session_index.jsonl").read_text()
        out["history_lines"] = history.count(tid)
        out["index_lines"] = index.count(tid)
        return out


def standard_home(root: Path) -> Home:
    home = Home(root)
    home.add_thread(T1, archived=True, rollout_path=home.archive / rollout_name(T1))
    home.add_thread(T2, archived=True, rollout_path=home.archive / rollout_name(T2), write_file=False)
    home.add_thread(T3, archived=False, rollout_path=home.sessions / rollout_name(T3))
    (home.archive / rollout_name(T4)).write_text("orphan\n")
    home.history_lines.append(json.dumps({"session_id": T4, "ts": 1, "text": "orphan"}))
    home.add_thread(T5, archived=False, rollout_path=home.sessions / rollout_name(T5))
    (home.archive / rollout_name(T5)).write_text("stray copy of live thread\n")
    home.add_thread(T6, archived=True, rollout_path=home.sessions / rollout_name(T6), write_file=False)
    (home.archive / rollout_name(T6)).write_text("file where row does not point\n")
    (root / "real-target.jsonl").write_text("symlink target\n")
    home.add_thread(T7, archived=True, rollout_path=home.archive / rollout_name(T7), write_file=False)
    os.symlink(root / "real-target.jsonl", home.archive / rollout_name(T7))
    home.add_thread(T8, archived=True, rollout_path=root / "elsewhere" / rollout_name(T8), write_file=False)
    (home.archive / "notes.txt").write_text("unrelated\n")
    with home.state() as s:
        s.execute(
            "INSERT INTO rollout_migration_skipped_rollouts VALUES ('m', ?, 1, 1, 'failed', 1)",
            (f"archived_sessions/{rollout_name(T4)}",),
        )
    home.write_jsonl()
    return home


def run(home: Home, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--codex-home", str(home.root), "--yes", *args],
        text=True,
        capture_output=True,
        check=False,
    )


def snapshot(root: Path) -> dict[str, bytes]:
    out = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not path.name.endswith((".sqlite", "-wal", "-shm")):
            out[str(path.relative_to(root))] = path.read_bytes()
    for name in (purge.STATE_DB, purge.HISTORY_DB):
        conn = sqlite3.connect(f"file:{root / name}?mode=ro", uri=True)
        out[f"dump:{name}"] = "\n".join(conn.iterdump()).encode()
        conn.close()
    return out


class PurgeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.home = standard_home(self.root)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_fixture_matches_pinned_schema(self) -> None:
        for name in (purge.STATE_DB, purge.HISTORY_DB):
            conn = sqlite3.connect(self.root / name)
            self.assertEqual(purge.schema_dump(conn), purge.EXPECTED_SCHEMA[name])
            self.assertEqual(purge.migration_list(conn), purge.EXPECTED_MIGRATIONS[name])
            conn.close()

    def test_dry_run_changes_nothing_and_is_deterministic(self) -> None:
        before = snapshot(self.root)
        first = run(self.home, "--dry-run")
        second = run(self.home, "--dry-run", "-v")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(snapshot(self.root), before)
        self.assertEqual(first.stdout, run(self.home, "--dry-run").stdout)
        self.assertIn("mode: DRY RUN", first.stdout)
        self.assertIn("archived thread rows to delete: 2", first.stdout)
        self.assertIn("transcript already missing:   1", first.stdout)
        self.assertIn("orphan transcript files (no thread row): 1", first.stdout)
        self.assertIn("transcript files to unlink: 2", first.stdout)
        self.assertIn("thread_items: 4", first.stdout)
        self.assertIn("history.jsonl: 3", first.stdout)
        self.assertIn("session_index.jsonl: 2", first.stdout)
        self.assertIn("rollout_migration_skipped_rollouts: 1", first.stdout)
        for tid in (T1, T2, T4):
            self.assertIn(tid, second.stdout)
        for tid, reason in (
            (T5, "file in archived_sessions/ but thread row is not archived"),
            (T6, "rollout_path is not inside archived_sessions/"),
            (T6, "file in archived_sessions/ but archived row points elsewhere"),
            (T7, "rollout_path is a symlink"),
            (rollout_name(T7), "symlink in archived_sessions/"),
            (T8, "rollout_path is not inside archived_sessions/"),
            ("notes.txt", "unrecognized file name"),
        ):
            self.assertIn(f"{tid}: {reason}", first.stdout)

    def test_live_run_deletes_archived_and_preserves_the_rest(self) -> None:
        result = run(self.home)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("mode: LIVE", result.stdout)
        for tid in (T1, T2):
            self.assertEqual(set(self.home.counts(tid).values()), {0}, tid)
        self.assertFalse((self.home.archive / rollout_name(T1)).exists())
        self.assertFalse((self.home.archive / rollout_name(T4)).exists())
        self.assertNotIn(T4, (self.root / "history.jsonl").read_text())
        with self.home.state() as s:
            self.assertEqual(
                s.execute("SELECT COUNT(*) FROM rollout_migration_skipped_rollouts").fetchone()[0], 0
            )
        # untouched: unarchived threads, inconsistent rows, symlinks, unrelated files
        for tid in (T3, T5, T6, T7, T8):
            counts = self.home.counts(tid)
            self.assertEqual(counts["threads"], 1, tid)
            self.assertEqual(counts["thread_items"], 2, tid)
            self.assertEqual(counts["history_lines"], 1, tid)
            self.assertEqual(counts["index_lines"], 1, tid)
        self.assertTrue((self.home.sessions / rollout_name(T3)).exists())
        self.assertTrue((self.home.archive / rollout_name(T5)).exists())
        self.assertTrue((self.home.archive / rollout_name(T6)).exists())
        self.assertTrue((self.home.archive / rollout_name(T7)).is_symlink())
        self.assertEqual((self.root / "real-target.jsonl").read_text(), "symlink target\n")
        self.assertTrue((self.home.archive / "notes.txt").exists())
        history = (self.root / "history.jsonl").read_text()
        self.assertIn('"session_id":"unrelated"', history)
        self.assertIn("not json at all", history)
        self.assertIn('"id":"unrelated"', (self.root / "session_index.jsonl").read_text())
        self.assertTrue(history.endswith("\n"))

    def test_repeat_run_is_a_noop(self) -> None:
        self.assertEqual(run(self.home).returncode, 0)
        after_first = snapshot(self.root)
        again = run(self.home)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("nothing to delete", again.stdout)
        self.assertEqual(snapshot(self.root), after_first)

    def test_schema_change_stops_before_deleting(self) -> None:
        before = snapshot(self.root)
        with self.home.state() as s:
            s.execute("ALTER TABLE threads ADD COLUMN surprise TEXT")
        result = run(self.home)
        self.assertEqual(result.returncode, purge.EXIT_SCHEMA)
        self.assertIn("schema differs from pinned schema", result.stderr)
        self.assertIn("surprise", result.stderr)
        with self.home.state() as s:
            s.execute("PRAGMA writable_schema=OFF")
        self.assertEqual(snapshot(self.root)["dump:" + purge.HISTORY_DB], before["dump:" + purge.HISTORY_DB])
        self.assertTrue((self.home.archive / rollout_name(T1)).exists())

    def test_migration_change_stops_before_deleting(self) -> None:
        with self.home.history() as h:
            h.execute(
                "INSERT INTO _sqlx_migrations(version, description, success, checksum, execution_time) "
                "VALUES (7, 'future', 1, X'00', 0)"
            )
        result = run(self.home)
        self.assertEqual(result.returncode, purge.EXIT_SCHEMA)
        self.assertIn("_sqlx_migrations differ", result.stderr)
        self.assertEqual(self.home.counts(T1)["threads"], 1)

    def test_missing_database_stops(self) -> None:
        (self.root / purge.HISTORY_DB).unlink()
        result = run(self.home, "--dry-run")
        self.assertEqual(result.returncode, purge.EXIT_SCHEMA)
        self.assertIn("database missing", result.stderr)
        self.assertTrue((self.home.archive / rollout_name(T1)).exists())

    def test_archive_dir_symlink_refused(self) -> None:
        real = self.root / "real-archive"
        self.home.archive.rename(real)
        os.symlink(real, self.home.archive)
        result = run(self.home)
        self.assertEqual(result.returncode, purge.EXIT_SCHEMA)
        self.assertIn("is a symlink", result.stderr)
        self.assertTrue((real / rollout_name(T1)).exists())
        self.assertEqual(self.home.counts(T1)["threads"], 1)

    def test_open_sqlite_readers_do_not_block(self) -> None:
        reader_state = sqlite3.connect(self.root / purge.STATE_DB, isolation_level=None)
        reader_state.execute("BEGIN")
        reader_state.execute("SELECT COUNT(*) FROM threads").fetchone()
        reader_hist = sqlite3.connect(self.root / purge.HISTORY_DB, isolation_level=None)
        reader_hist.execute("BEGIN")
        reader_hist.execute("SELECT COUNT(*) FROM thread_items").fetchone()
        try:
            result = run(self.home, "--lock-timeout", "1")
        finally:
            reader_state.close()
            reader_hist.close()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.home.counts(T1)["threads"], 0)

    def test_competing_sqlite_writer_exits_before_deleting(self) -> None:
        before = snapshot(self.root)
        writer = sqlite3.connect(self.root / purge.STATE_DB, isolation_level=None)
        writer.execute("BEGIN IMMEDIATE")
        try:
            result = run(self.home, "--lock-timeout", "0.5")
        finally:
            writer.close()
        self.assertEqual(result.returncode, purge.EXIT_LOCKED, result.stdout)
        self.assertIn("nothing deleted", result.stderr)
        self.assertEqual(snapshot(self.root), before)

    def test_competing_jsonl_writer_exits_before_deleting(self) -> None:
        before = snapshot(self.root)
        fd = os.open(self.root / "history.jsonl", os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            result = run(self.home, "--lock-timeout", "0.5")
        finally:
            os.close(fd)
        self.assertEqual(result.returncode, purge.EXIT_LOCKED, result.stdout)
        self.assertIn("history.jsonl", result.stderr)
        self.assertEqual(snapshot(self.root), before)

    def test_thread_writer_lock_skips_only_that_thread(self) -> None:
        lock = self.root / "thread-writer-locks" / f"{T1}.lock"
        lock.touch()
        fd = os.open(lock, os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            result = run(self.home)
        finally:
            os.close(fd)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"{T1}: thread writer lock is held", result.stdout)
        self.assertEqual(self.home.counts(T1)["threads"], 1)
        self.assertTrue((self.home.archive / rollout_name(T1)).exists())
        self.assertEqual(self.home.counts(T2)["threads"], 0)
        self.assertFalse((self.home.archive / rollout_name(T4)).exists())

    def test_jsonl_lines_appended_under_lock_survive(self) -> None:
        # A writer that takes flock after ours is released must see the rewritten
        # inode. Simulate by appending after the run and checking both survive.
        run(self.home)
        with open(self.root / "history.jsonl", "a") as f:
            f.write('{"session_id":"later","ts":2,"text":"y"}\n')
        text = (self.root / "history.jsonl").read_text()
        self.assertIn('"session_id":"unrelated"', text)
        self.assertIn('"session_id":"later"', text)
        self.assertNotIn(T1, text)

    def test_failure_after_commit_is_reclaimed_on_rerun(self) -> None:
        # Make the archive dir read-only so unlink fails after the database
        # commit, then restore it and rerun.
        self.home.archive.chmod(0o500)
        try:
            result = run(self.home)
        finally:
            self.home.archive.chmod(0o700)
        self.assertEqual(result.returncode, purge.EXIT_ERROR, result.stdout)
        self.assertIn("rerun to reclaim", result.stdout)
        self.assertEqual(self.home.counts(T1)["threads"], 0)
        self.assertTrue((self.home.archive / rollout_name(T1)).exists())
        again = run(self.home)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("orphan transcript files (no thread row): 2", again.stdout)
        self.assertFalse((self.home.archive / rollout_name(T1)).exists())
        self.assertFalse((self.home.archive / rollout_name(T4)).exists())
        self.assertIn("nothing to delete", run(self.home).stdout)

    def test_filter_jsonl_keeps_unparseable_and_unrelated_lines(self) -> None:
        data = b'{"id":"a"}\nbroken\n\n{"id":"b"}\n{"id":"c"}'
        new, removed = purge.filter_jsonl(data, "id", {"a", "c"})
        self.assertEqual(removed, 2)
        self.assertEqual(new, b'broken\n\n{"id":"b"}\n')


if __name__ == "__main__":
    unittest.main()
