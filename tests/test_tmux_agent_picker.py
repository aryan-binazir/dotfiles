"""Drive the agent picker through its CLI and a private tmux server."""
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import shlex
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time
import unittest

from test_ai_spinner import copy_shell

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'stow/scripts/tmux-agent-picker'
CONFIG = ROOT / 'stow/arch-linux/tmux/.config/tmux/tmux.conf'


@unittest.skipUnless(shutil.which('tmux'), 'tmux is required')
class PickerTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='agent-picker-')
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.socket = str(self.directory / 'tmux.sock')
        self.env = {**os.environ, 'TERM': 'xterm-256color'}
        self.env.pop('TMUX', None)
        self.env.pop('TMUX_PANE', None)
        self.tmux('-f', '/dev/null', 'new-session', '-d', '-s', 'home', '-x', '120', '-y', '35', 'sleep 300')
        self.addCleanup(lambda: self.tmux('kill-server', check=False))
        self.tmux('set', '-g', 'allow-rename', 'off')
        self.tmux('set', '-g', 'assume-paste-time', '0')
        self.tmux('set', '-g', 'status', 'off')
        self.clients = []
        self.output = {}
        self.addCleanup(self.close_clients)

    def tmux(self, *args, check=True):
        return subprocess.run(['tmux', '-S', self.socket, *args], env=self.env,
                              capture_output=True, text=True, check=check, timeout=5).stdout.strip()

    def close_clients(self):
        for process, fd in self.clients:
            try:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            finally:
                os.close(fd)

    def agent(self, command, session='home', window='agent', state=''):
        executable = self.directory / command
        if not executable.exists():
            copy_shell(executable)
        if session not in self.tmux('list-sessions', '-F', '#{session_name}').splitlines():
            self.tmux('new-session', '-d', '-s', session, 'sleep 300')
        pane = self.tmux('new-window', '-d', '-t', session + ':', '-n', window, '-P', '-F', '#{pane_id}',
                         shlex.join([str(executable), '-c', 'while :; do sleep 1; done']))
        self.tmux('set-option', '-p', '-t', pane, '@ai_attention_state', state)
        self.until(lambda: self.tmux('display', '-p', '-t', pane, '#{pane_current_command}') == command)
        return pane

    def until(self, condition, timeout=5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.pump()
            if condition():
                return
            time.sleep(.03)
        self.fail('Timed out waiting for picker behavior')

    def pump(self):
        for _, fd in self.clients:
            while select.select([fd], [], [], 0)[0]:
                try:
                    self.output[fd] += os.read(fd, 65536)
                except OSError:
                    break

    def attach(self, session='home'):
        before = self.tmux('list-clients', '-F', '#{client_name}').splitlines()
        fd, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 35, 120, 0, 0))
        process = subprocess.Popen(['tmux', '-S', self.socket, 'attach', '-t', session],
                                   env=self.env, stdin=slave, stdout=slave, stderr=slave)
        os.close(slave)
        self.clients.append((process, fd))
        self.output[fd] = b''
        self.until(lambda: len(self.tmux('list-clients').splitlines()) > len(before))
        client = next(c for c in self.tmux('list-clients', '-F', '#{client_name}').splitlines() if c not in before)
        return fd, client

    def client_state(self, client):
        rows = self.tmux('list-clients', '-F', '#{client_name}\t#{session_id} #{pane_id}')
        return dict(row.split('\t', 1) for row in rows.splitlines())[client]

    def load_binding(self, source=SCRIPT):
        home = self.directory / 'home with spaces'
        scripts = home / '.config/tmux/scripts'
        scripts.mkdir(parents=True)
        (scripts / 'tmux-agent-picker').symlink_to(source)
        self.tmux('set-environment', '-g', 'HOME', str(home))
        binding = next(line for line in CONFIG.read_text().splitlines() if line.startswith('bind b '))
        config = self.directory / 'picker.conf'
        config.write_text(binding + '\n')
        self.tmux('source-file', str(config))

    def open_popup(self, fd):
        self.output[fd] = b''
        os.write(fd, b'\x02b')
        self.until(lambda: b'SESSION' in self.output[fd] and b'Search agents' in self.output[fd])

    def keys_and_wait(self, fd, keys, text):
        self.output[fd] = b''
        os.write(fd, keys)
        self.until(lambda: text in re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '',
                                          self.output[fd].decode(errors='replace')))

    def listing(self, client=None):
        args = [sys.executable, str(SCRIPT), 'list', '--socket', self.socket]
        if client:
            args += ['--client', client]
        return subprocess.run(args, env=self.env, text=True, capture_output=True, check=True, timeout=5).stdout

    def test_lists_agents_in_column_and_attention_order(self):
        idle = self.agent('2.1.289', window='idle')
        working = self.agent('codex', session='bball', window='score', state='quiet1')
        done = self.agent('pi', window='config', state='done')
        blocked = self.agent('claude', session='ember', window='proposal', state='blocked-seen')
        rows = [line.split('\t') for line in self.listing().splitlines()]
        self.assertIn('SESSION', rows[0][-1])
        self.assertRegex(rows[0][-1], r'SESSION\s+WINDOW\s+AGENT\s+STATUS')
        self.assertEqual([row[0] for row in rows[1:]], [blocked, done, working, idle])
        for row, expected in zip(rows[1:], [('ember', 'proposal', 'Claude', 'Needs input'),
                                          ('home', 'config', 'Pi', 'Done'),
                                          ('bball', 'score', 'Codex', 'Working'),
                                          ('home', 'idle', 'Claude', 'Idle')]):
            self.assertTrue(all(value in row[-1] for value in expected), row)

    def test_ambiguous_commands_require_a_recognized_attention_state(self):
        known = self.agent('cursor-agent')
        ambiguous = self.agent('node')
        states = [('blocked', 'Needs input'), ('blocked-quiet1', 'Needs input'),
                  ('blocked-quiet2', 'Needs input'), ('blocked-seen', 'Needs input'),
                  ('blocked-seen-quiet1', 'Needs input'), ('blocked-seen-quiet2', 'Needs input'),
                  ('done', 'Done'), ('working', 'Working'), ('quiet1', 'Working'),
                  ('quiet2', 'Working'), ('', None), ('unexpected', None)]
        for state, label in states:
            with self.subTest(state=state):
                self.tmux('set-option', '-p', '-t', ambiguous, '@ai_attention_state', state)
                rows = {row.split('\t')[0]: row for row in self.listing().splitlines()[1:]}
                self.assertIn('Cursor', rows[known])
                if label:
                    self.assertIn('node', rows[ambiguous])
                    self.assertTrue(rows[ambiguous].endswith(label))
                else:
                    self.assertNotIn(ambiguous, rows)

    def test_pi_titles_do_not_bypass_ambiguous_runtime_eligibility_or_labels(self):
        for command in ('node', 'bun', 'uv'):
            pane = self.agent(command)
            self.tmux('select-pane', '-t', pane, '-T', 'π - project')
            for state, label in [('', None), ('unexpected', None), ('done', 'Done')]:
                with self.subTest(command=command, state=state):
                    self.tmux('set-option', '-p', '-t', pane, '@ai_attention_state', state)
                    rows = {row.split('\t')[0]: row for row in self.listing().splitlines()[1:]}
                    if label:
                        self.assertRegex(rows[pane], command + r'\s+' + label)
                    else:
                        self.assertNotIn(pane, rows)
            self.tmux('kill-pane', '-t', pane)

    def test_stale_pi_title_does_not_turn_an_ordinary_shell_into_an_agent(self):
        pane = self.agent('sh')
        self.tmux('select-pane', '-t', pane, '-T', 'π - old project')
        self.assertEqual(len(self.listing().splitlines()), 1)

    def test_malformed_attention_text_does_not_hide_other_agents(self):
        pane = self.agent('claude')
        subprocess.run(['tmux', '-S', self.socket, 'set-option', '-p', '-t', pane,
                        '@ai_attention_state', b'bad\xffstate'], env=self.env, check=True,
                       capture_output=True, timeout=5)
        self.agent('codex', state='done')
        output = self.listing()
        self.assertEqual(len(output.splitlines()), 3)
        self.assertRegex(output, r'Claude\s+Idle')
        self.assertRegex(output, r'Codex\s+Done')

    def test_linked_panes_appear_once_in_the_invoking_clients_session(self):
        pane = self.agent('codex', window='same')
        window = self.tmux('display', '-p', '-t', pane, '#{window_id}')
        self.tmux('new-session', '-d', '-s', 'linked', 'sleep 300')
        self.tmux('link-window', '-s', window, '-t', 'linked:')
        _, client = self.attach('linked')
        rows = self.listing(client).splitlines()[1:]
        self.assertEqual(len(rows), 1)
        self.assertIn('linked', rows[0])
        self.assertEqual(rows[0].split('\t')[1], self.client_state(client).split()[0])

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_popup_filters_and_enters_the_exact_pane_in_the_invoking_client(self):
        pane = self.agent('codex', session='ember', window='proposal', state='working')
        self.agent('claude', window='other', state='blocked')
        self.tmux('new-session', '-d', '-s', 'observer', 'sleep 300')
        self.load_binding()
        fd, client = self.attach()
        _, observer = self.attach('observer')
        before = self.client_state(observer)
        self.open_popup(fd)
        self.keys_and_wait(fd, pane.encode(), '0/2')
        self.keys_and_wait(fd, b'\x15ember proposal Codex Working', '1/2')
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == pane)
        self.assertEqual(self.client_state(observer), before)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_manual_refresh_updates_status_and_preserves_the_query(self):
        self.agent('claude', session='aaa', window='other', state='done')
        pane = self.agent('codex', session='ember', window='proposal', state='working')
        self.load_binding()
        fd, client = self.attach()
        self.open_popup(fd)
        self.keys_and_wait(fd, b'proposal Done', '0/2')
        self.tmux('set-option', '-p', '-t', pane, '@ai_attention_state', 'done')
        self.keys_and_wait(fd, b'\x12', '1/2')
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == pane)

    def test_labels_cannot_inject_terminal_controls_or_break_rows(self):
        name = 'quoted " $(touch never) \u202e'
        pane = self.agent('codex', window=name)
        output = self.listing()
        self.assertEqual(len(output.splitlines()), 2)
        row = output.splitlines()[1].split('\t')
        self.assertEqual(len(row), 3)
        self.assertEqual(row[0], pane)
        self.assertIn('$(touch never)', row[-1])
        self.assertNotIn('\x1b', output)
        self.assertNotIn('\u202e', output)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_escape_leaves_focus_and_unread_attention_unchanged(self):
        pane = self.agent('claude', state='done')
        self.load_binding()
        fd, client = self.attach()
        before = self.client_state(client)
        self.open_popup(fd)
        self.output[fd] = b''
        os.write(fd, b'\x1b')
        self.until(lambda: b'\x1b[?25h' in self.output[fd])
        self.assertEqual(self.client_state(client), before)
        self.assertEqual(self.tmux('show-option', '-pqv', '-t', pane, '@ai_attention_state'), 'done')
        self.open_popup(fd)
        self.output[fd] = b''
        os.write(fd, b'\x1b')
        self.until(lambda: b'\x1b[?25h' in self.output[fd])

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_closed_target_reports_message_without_switching(self):
        pane = self.agent('codex')
        self.load_binding()
        fd, client = self.attach()
        before = self.client_state(client)
        self.open_popup(fd)
        self.tmux('kill-pane', '-t', pane)
        os.write(fd, b'\r')
        self.until(lambda: 'That agent pane has closed' in self.tmux('show-messages', '-t', client))
        self.assertEqual(self.client_state(client), before)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_moved_target_is_followed_and_zoom_preserved(self):
        pane = self.agent('codex', session='ember')
        destination = self.tmux('new-window', '-d', '-t', 'home:', '-P', '-F', '#{pane_id}', 'sleep 300')
        self.load_binding()
        fd, client = self.attach()
        self.open_popup(fd)
        self.tmux('move-pane', '-s', pane, '-t', destination)
        self.tmux('resize-pane', '-Z', '-t', destination)
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == pane)
        self.assertEqual(self.tmux('display', '-p', '-t', pane, '#{window_zoomed_flag}'), '1')

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_linked_windows_share_active_pane_without_switching_observer_session(self):
        pane = self.agent('codex')
        window = self.tmux('display', '-p', '-t', pane, '#{window_id}')
        other = self.tmux('split-window', '-t', pane, '-P', '-F', '#{pane_id}', 'sleep 300')
        self.tmux('new-session', '-d', '-s', 'linked', 'sleep 300')
        self.tmux('link-window', '-s', window, '-t', 'linked:')
        self.tmux('select-window', '-t', 'linked:' + window)
        self.load_binding()
        fd, client = self.attach()
        _, observer = self.attach('linked')
        session, active = self.client_state(observer).split()
        self.assertEqual(active, other)
        self.open_popup(fd)
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == pane)
        self.assertEqual(self.client_state(observer).split(), [session, pane])

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_linked_target_uses_the_session_shown_in_the_picker(self):
        pane = self.agent('codex')
        window = self.tmux('display', '-p', '-t', pane, '#{window_id}')
        self.tmux('new-session', '-d', '-s', 'linked', 'sleep 300')
        self.tmux('link-window', '-s', window, '-t', 'linked:')
        self.load_binding()
        fd, client = self.attach('linked')
        session = self.client_state(client).split()[0]
        self.open_popup(fd)
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == pane)
        self.assertEqual(self.client_state(client).split()[0], session)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_reload_works_from_an_installed_symlink_with_shell_metacharacters_in_the_source_path(self):
        source = self.directory / "source '){literal}" / 'tmux-agent-picker'
        source.parent.mkdir()
        shutil.copy(SCRIPT, source)
        pane = self.agent('codex', window='proposal', state='working')
        self.load_binding(source)
        fd, client = self.attach()
        self.open_popup(fd)
        self.keys_and_wait(fd, b'Done', '0/1')
        self.tmux('set-option', '-p', '-t', pane, '@ai_attention_state', 'done')
        self.keys_and_wait(fd, b'\x12', '1/1')
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == pane)

    def test_missing_fzf_reports_an_actionable_message(self):
        _, client = self.attach()
        commands = self.directory / 'bin'
        commands.mkdir()
        (commands / 'tmux').symlink_to(shutil.which('tmux'))
        result = subprocess.run([sys.executable, str(SCRIPT), 'open', '--socket', self.socket, '--client', client],
                                env={**self.env, 'PATH': str(commands)}, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout + result.stderr, '')
        self.assertIn('Agent picker requires fzf on PATH', self.tmux('show-messages', '-t', client))

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_empty_picker_explains_that_no_agents_were_detected(self):
        _, client = self.attach()
        before = self.client_state(client)
        result = subprocess.run([sys.executable, str(SCRIPT), 'open', '--socket', self.socket, '--client', client],
                                env=self.env, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn('No AI panes detected', self.tmux('show-messages', '-t', client))
        self.assertEqual(self.client_state(client), before)


if __name__ == '__main__':
    unittest.main()
