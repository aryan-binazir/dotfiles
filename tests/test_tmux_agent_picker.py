import fcntl
import os
from pathlib import Path
import pty
import re
import runpy
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
        self.until(lambda: b'SESSION' in self.output[fd] and b'Enter:' in self.output[fd])

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

    def test_reload_removes_four_split_shortcut_without_changing_panes(self):
        before = self.tmux('list-panes', '-a', '-F', '#{pane_id}')
        self.tmux('bind-key', 'g', 'split-window')
        config = self.directory / 'remove-splits.conf'
        config.write_text('\n'.join(line for line in CONFIG.read_text().splitlines()
                                    if line.startswith(('bind g ', 'unbind g'))) + '\n')
        self.tmux('source-file', str(config))
        self.assertNotRegex(self.tmux('list-keys', '-T', 'prefix'),
                            r'(?m)^bind-key\s+-T\s+prefix\s+g\s')
        self.assertEqual(self.tmux('list-panes', '-a', '-F', '#{pane_id}'), before)

    def test_config_restores_terminal_colors_after_gray_popup_defaults(self):
        options = ('popup-style', 'popup-border-style', 'tree-mode-border-style')
        supported = []
        for option in options:
            result = subprocess.run(['tmux', '-S', self.socket, 'show-options', '-gw', option],
                                    env=self.env, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                supported.append(option)
                self.tmux('set-option', '-gw', option, 'fg=white,bg=colour243')
        config = self.directory / 'colors.conf'
        config.write_text('\n'.join(line for line in CONFIG.read_text().splitlines()
                                    if any(option in line for option in options)) + '\n')
        for _ in range(2):
            result = subprocess.run(['tmux', '-S', self.socket, 'source-file', str(config)],
                                    env=self.env, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, '')
            for option in supported:
                self.assertEqual(self.tmux('show-options', '-gwv', option),
                                 'fg=default,bg=default', option)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_navigation_uses_j_and_k_without_typing_a_query(self):
        self.agent('claude', window='first')
        target = self.agent('codex', window='second')
        self.agent('pi', window='third')
        self.load_binding()
        fd, client = self.attach()
        self.open_popup(fd)
        os.write(fd, b'xjjk\r')
        self.until(lambda: self.client_state(client).split()[1] == target)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_initial_selection_uses_the_invoking_clients_exact_agent_pane(self):
        self.agent('claude', window='urgent', state='blocked')
        current = self.agent('codex', window='shared')
        target = self.agent('codex', window='shared')
        self.tmux('join-pane', '-h', '-s', target, '-t', current)
        self.tmux('new-session', '-d', '-s', 'observer', 'sleep 300')
        self.load_binding()
        fd, client = self.attach()
        self.tmux('switch-client', '-c', client, '-t', current)
        _, observer = self.attach('observer')
        before = self.client_state(observer)
        self.open_popup(fd)
        os.write(fd, b'j\r')
        self.until(lambda: self.client_state(client).split()[1] == target)
        self.assertEqual(self.client_state(observer), before)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_initial_selection_can_start_beyond_visible_rows_and_number_shortcuts(self):
        panes = [self.agent('codex', window=f'agent-{i:02}') for i in range(25)]
        self.load_binding()
        fd, client = self.attach()
        self.tmux('switch-client', '-c', client, '-t', panes[23])
        self.open_popup(fd)
        os.write(fd, b'j\r')
        self.until(lambda: self.client_state(client).split()[1] == panes[24])

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_initial_selection_is_not_reapplied_after_automatic_refresh(self):
        self.agent('claude', window='first', state='working')
        current = self.agent('codex', window='second', state='working')
        target = self.agent('pi', window='third', state='working')
        self.load_binding()
        fd, client = self.attach()
        self.tmux('switch-client', '-c', client, '-t', current)
        self.open_popup(fd)
        self.output[fd] = b''
        os.write(fd, b'j')
        self.until(lambda: bool(self.output[fd]))
        self.output[fd] = b''
        self.tmux('set-option', '-p', '-t', target, '@ai_attention_state', 'blocked')
        self.until(lambda: b'!' in self.output[fd])
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == target)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_number_shortcuts_select_the_labeled_rows_without_enter(self):
        panes = [self.agent('codex', window=f'agent-{i}') for i in range(11)]
        rows = [row.split('\t')[2] for row in self.listing().splitlines()[1:]]
        for i, row in enumerate(rows):
            self.assertEqual(row, str(i) if i < 10 else ' ')
        self.load_binding()
        fd, client = self.attach()
        for i in (9, 0, 5):
            with self.subTest(key=i):
                self.open_popup(fd)
                os.write(fd, str(i).encode())
                self.until(lambda: self.client_state(client).split()[1] == panes[i])

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_search_accepts_shortcut_characters_and_escape_restores_navigation(self):
        first = self.agent('claude', window='other', state='done')
        self.agent('codex', window='jk/9')
        self.load_binding()
        fd, client = self.attach()
        before = self.client_state(client)
        self.open_popup(fd)
        os.write(fd, b'9')
        self.keys_and_wait(fd, b'/jk/9', '1/2')
        self.assertEqual(self.client_state(client), before)
        self.keys_and_wait(fd, b'\x1b', '0-9/Enter:')
        self.keys_and_wait(fd, b'/', '2/2')
        self.keys_and_wait(fd, b'\x1b', '0-9/Enter:')
        os.write(fd, b'0')
        self.until(lambda: self.client_state(client).split()[1] == first)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_unavailable_number_preserves_the_highlighted_row(self):
        panes = [self.agent('codex', window=name) for name in ('first', 'second', 'third')]
        self.load_binding()
        fd, client = self.attach()
        for movement, target in ((b'', panes[0]), (b'j', panes[1])):
            with self.subTest(movement=movement):
                self.open_popup(fd)
                os.write(fd, movement + b'9\r')
                self.until(lambda: self.client_state(client).split()[1] == target)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_search_excludes_shortcut_labels_but_matches_window_numbers(self):
        self.agent('claude', window='first')
        target = self.agent('codex', window='second')
        self.agent('pi', window='third')
        self.load_binding()
        fd, client = self.attach()
        self.open_popup(fd)
        self.keys_and_wait(fd, b'/^2', '0/3')
        self.keys_and_wait(fd, b'\x152:', 'Codex')
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == target)

    def test_working_uses_current_tmux_spinner_frame_and_idle_has_no_marker(self):
        pane = self.agent('claude', state='working')
        self.tmux('set-environment', '-gh', 'TMUX_AI_SPINNER_FRAME', '⠹')
        self.assertTrue(self.listing().splitlines()[1].endswith('⠹'))
        self.tmux('set-environment', '-gu', 'TMUX_AI_SPINNER_FRAME')
        self.assertTrue(self.listing().splitlines()[1].endswith('⡇'))
        self.tmux('set-option', '-p', '-t', pane, '@ai_attention_state', '')
        self.assertTrue(self.listing().splitlines()[1].endswith('Claude'))

    def test_lists_agents_in_column_and_attention_order(self):
        idle = self.agent('2.1.289', window='idle')
        working = self.agent('codex', session='bball', window='score', state='quiet1')
        done = self.agent('pi', window='config', state='done')
        blocked = self.agent('claude', session='ember', window='proposal', state='blocked-seen')
        rows = [line.split('\t') for line in self.listing().splitlines()]
        self.assertEqual(rows[0][2], '#')
        self.assertIn('SESSION', rows[0][-1])
        self.assertRegex(rows[0][-1], r'SESSION\s+WINDOW\s+AGENT\s+STATUS')
        self.assertEqual([row[0] for row in rows[1:]], [blocked, done, working, idle])
        for row, expected in zip(rows[1:], [('ember', 'proposal', 'Claude', '!'),
                                          ('home', 'config', 'Pi', '✓'),
                                          ('bball', 'score', 'Codex', '⡇'),
                                          ('home', 'idle', 'Claude', '')]):
            self.assertTrue(all(value in row[-1] for value in expected), row)

    def test_registered_runtime_agents_remain_listed_only_for_the_matching_command(self):
        for command in ('node', 'bun', 'uv'):
            with self.subTest(command=command):
                pane = self.agent(command)
                self.tmux('set-option', '-p', '-t', pane, '@ai_agent_command', command)
                self.assertIn(pane + '\t', self.listing())
                self.tmux('set-option', '-p', '-t', pane, '@ai_agent_command', 'other')
                self.assertNotIn(pane + '\t', self.listing())

    def test_ambiguous_commands_require_a_recognized_attention_state(self):
        known = self.agent('cursor-agent')
        ambiguous = self.agent('node')
        states = [('blocked', '!'), ('blocked-quiet1', '!'),
                  ('blocked-quiet2', '!'), ('blocked-seen', '!'),
                  ('blocked-seen-quiet1', '!'), ('blocked-seen-quiet2', '!'),
                  ('done', '✓'), ('working', '⡇'), ('quiet1', '⡇'),
                  ('quiet2', '⡇'), ('', None), ('unexpected', None)]
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
            for state, label in [('', None), ('unexpected', None), ('done', '✓')]:
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

    def test_pi_conversation_names_require_an_exact_cwd_suffix(self):
        pane = self.agent('pi', window='manual-window')
        folder = self.directory / 'folder - with - separators'
        folder.mkdir()
        self.tmux('respawn-pane', '-k', '-t', pane, '-c', str(folder),
                  shlex.join([str(self.directory / 'pi'), '-c', 'while :; do sleep 1; done']))
        self.until(lambda: self.tmux('display-message', '-p', '-t', pane,
                                    '#{pane_current_path}') == str(folder))
        cases = [('', 'manual-window'), ('hostname', 'manual-window'),
                 ('π - ' + folder.name, 'manual-window'),
                 ('π - Name - different-folder', 'manual-window'),
                 ('π -    - ' + folder.name, 'manual-window'),
                 ('π - \u200b - ' + folder.name, 'manual-window'),
                 ('π - Plan - with - separators - ' + folder.name, 'Plan - with - separators'),
                 ('π - quoted "$(touch never)" \u202e - ' + folder.name, 'quoted "$(touch never)"')]
        for title, expected in cases:
            with self.subTest(title=title):
                self.tmux('select-pane', '-t', pane, '-T', title)
                rows = self.listing().splitlines()
                self.assertEqual(len(rows), 2)
                self.assertIn(':' + expected, rows[1])
                self.assertNotIn('π - ', rows[1])
                self.assertNotIn('\u202e', rows[1])
                self.assertFalse((folder / 'never').exists())

    def test_conversation_titles_do_not_replace_other_provider_window_names(self):
        for command in ('claude', '2.1.296', 'codex', 'cursor-agent', 'node', 'bun', 'uv'):
            pane = self.agent(command, window='manual-' + command, state='working')
            folder = Path(self.tmux('display-message', '-p', '-t', pane, '#{pane_current_path}')).name
            self.tmux('select-pane', '-t', pane, '-T', 'π - Misleading name - ' + folder)
        output = self.listing()
        self.assertNotIn('Misleading name', output)
        for command in ('claude', '2.1.296', 'codex', 'cursor-agent', 'node', 'bun', 'uv'):
            self.assertIn(':manual-' + command, output)

    def test_conversation_title_input_is_bounded_before_python_receives_it(self):
        pane = self.agent('pi', window='manual-window')
        folder = Path(self.tmux('display-message', '-p', '-t', pane, '#{pane_current_path}')).name
        self.tmux('select-pane', '-t', pane, '-T', 'π - ' + 'x' * 300 + ' - ' + folder)
        rows = runpy.run_path(str(SCRIPT))['panes'](self.socket)
        self.assertEqual(len(next(row['pane_title'] for row in rows if row['pane_id'] == pane)), 256)
        self.assertIn(':manual-window', self.listing())

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_conversation_rename_preserves_search_and_selection_and_stops_on_close(self):
        first = self.agent('pi', window='manual-first', state='working')
        target = self.agent('pi', window='manual-second', state='working')
        folder = Path(self.tmux('display-message', '-p', '-t', target, '#{pane_current_path}')).name
        self.tmux('select-pane', '-t', first, '-T', 'π - Needle first - ' + folder)
        titlefile = self.directory / 'title'
        titlefile.write_text('π - Needle second - ' + folder)
        body = ("while :; do printf '\\033]0;%s\\007' \"$(cat " + shlex.quote(str(titlefile))
                + ')"; IFS= read -r line || exit; done')
        self.tmux('respawn-pane', '-k', '-t', target,
                  shlex.join([str(self.directory / 'pi'), '-c', body]))
        self.until(lambda: 'Needle second' in self.listing())
        commands = self.directory / 'commands'
        commands.mkdir()
        queries = self.directory / 'queries'
        wrapper = commands / 'tmux'
        wrapper.write_text('#!/bin/sh\n'
                           'if [ "$3" = list-panes ]; then printf . >> ' + shlex.quote(str(queries))
                           + '; fi\nexec ' + shlex.quote(shutil.which('tmux')) + ' "$@"\n')
        wrapper.chmod(0o755)
        self.tmux('set-environment', '-g', 'PATH', str(commands) + ':' + self.env['PATH'])
        self.tmux('select-window', '-t', first)
        self.load_binding()
        fd, client = self.attach()
        self.open_popup(fd)
        self.keys_and_wait(fd, b'/Needle', '2/2')
        self.output[fd] = b''
        os.write(fd, b'\x1b[B')
        self.until(lambda: bool(self.output[fd]))
        self.output[fd] = b''
        titlefile.write_text('π - Needle renamed - ' + folder)
        self.tmux('send-keys', '-t', target, 'Enter')
        self.tmux('set-option', '-p', '-t', target, '@ai_attention_state', 'done')
        self.until(lambda: b' renamed ' in self.output[fd])
        self.assertIn(b'2/2', self.output[fd])
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == target)
        time.sleep(1.2)
        count = queries.read_text()
        time.sleep(1.3)
        self.assertEqual(queries.read_text(), count)

    def test_malformed_attention_text_does_not_hide_other_agents(self):
        pane = self.agent('claude')
        subprocess.run(['tmux', '-S', self.socket, 'set-option', '-p', '-t', pane,
                        '@ai_attention_state', b'bad\xffstate'], env=self.env, check=True,
                       capture_output=True, timeout=5)
        self.agent('codex', state='done')
        output = self.listing()
        self.assertEqual(len(output.splitlines()), 3)
        self.assertRegex(output, r'Claude(?:\n|$)')
        self.assertRegex(output, r'Codex\s+✓')

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
        self.keys_and_wait(fd, b'/' + pane.encode(), '0/2')
        self.keys_and_wait(fd, '\x15ember proposal Codex ⡇'.encode(), '1/2')
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == pane)
        self.assertEqual(self.client_state(observer), before)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_automatic_refresh_preserves_query_and_highlighted_pane_after_reordering(self):
        self.agent('codex', window='proposal-a', state='working')
        target = self.agent('pi', window='proposal-b', state='working')
        self.agent('claude', window='outside', state='blocked')
        self.load_binding()
        fd, client = self.attach()
        self.open_popup(fd)
        self.keys_and_wait(fd, b'/proposal', '2/3')
        self.output[fd] = b''
        os.write(fd, b'\x1b[B')
        self.until(lambda: bool(self.output[fd]))
        self.output[fd] = b''
        self.tmux('set-option', '-p', '-t', target, '@ai_attention_state', 'done')
        self.until(lambda: '✓' in self.output[fd].decode(errors='replace'))
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == target)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_slow_refresh_keeps_navigation_and_accept_responsive(self):
        self.agent('claude', window='first')
        target = self.agent('codex', window='second')
        self.agent('pi', window='third')
        commands = self.directory / 'commands'
        commands.mkdir()
        pending = self.directory / 'pending'
        started = self.directory / 'started'
        wrapper = commands / 'tmux'
        wrapper.write_text('#!/bin/sh\n'
                           'if [ "$3" = list-panes ] && [ -f "$PICKER_PENDING" ] && [ ! -f "$PICKER_STARTED" ]; then\n'
                           '  printf . >> "$PICKER_STARTED"\n'
                           '  while [ -f "$PICKER_PENDING" ]; do sleep .01; done\n'
                           'fi\nexec ' + shlex.quote(shutil.which('tmux')) + ' "$@"\n')
        wrapper.chmod(0o755)
        self.tmux('set-environment', '-g', 'PATH', str(commands) + ':' + self.env['PATH'])
        self.tmux('set-environment', '-g', 'PICKER_PENDING', str(pending))
        self.tmux('set-environment', '-g', 'PICKER_STARTED', str(started))
        self.load_binding()
        fd, client = self.attach()
        for keys in (b'j\r', b'/second\r'):
            with self.subTest(keys=keys):
                pending.unlink(missing_ok=True)
                started.unlink(missing_ok=True)
                self.tmux('switch-client', '-c', client, '-t', 'home:0')
                self.open_popup(fd)
                pending.touch()
                self.until(started.exists)
                if keys.startswith(b'/'):
                    os.write(fd, keys[:-1])
                    self.until(lambda: '1/3' in re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '',
                                                      self.output[fd].decode(errors='replace')), timeout=1)
                    os.write(fd, keys[-1:])
                else:
                    os.write(fd, keys)
                self.until(lambda: self.client_state(client).split()[1] == target, timeout=2)
                self.assertTrue(pending.exists())

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_all_agent_statuses_are_loaded_before_the_popup_opens(self):
        for command, state in (('claude', 'blocked'), ('pi', 'done'),
                               ('codex', 'working'), ('cursor-agent', '')):
            pane = self.agent(command, state=state)
            if command == 'pi':
                folder = Path(self.tmux('display-message', '-p', '-t', pane, '#{pane_current_path}')).name
                self.tmux('select-pane', '-t', pane, '-T', 'π - Preloaded name - ' + folder)
        commands = self.directory / 'commands'
        commands.mkdir()
        temporary = self.directory / 'popup-temporary'
        temporary.mkdir()
        started = self.directory / 'popup-started'
        release = self.directory / 'popup-release'
        wrapper = commands / 'tmux'
        wrapper.write_text('#!/bin/sh\n'
                           'if [ "$3" = display-popup ]; then\n'
                           '  printf . > "$PICKER_POPUP_STARTED"\n'
                           '  while [ ! -f "$PICKER_POPUP_RELEASE" ]; do sleep .01; done\n'
                           'fi\nexec ' + shlex.quote(shutil.which('tmux')) + ' "$@"\n')
        wrapper.chmod(0o755)
        self.tmux('set-environment', '-g', 'PATH', str(commands) + ':' + self.env['PATH'])
        self.tmux('set-environment', '-g', 'TMPDIR', str(temporary))
        self.tmux('set-environment', '-g', 'PICKER_POPUP_STARTED', str(started))
        self.tmux('set-environment', '-g', 'PICKER_POPUP_RELEASE', str(release))
        self.load_binding()
        fd, client = self.attach()
        self.output[fd] = b''
        os.write(fd, b'\x02b')
        try:
            self.until(started.exists)
            snapshots = list(temporary.glob('tmux-agent-picker-*/snapshot'))
            self.assertEqual(len(snapshots), 1)
            self.assertEqual(snapshots[0].read_text(), self.listing(client))
            self.assertIn('Preloaded name', snapshots[0].read_text())
            self.assertNotIn(b'SESSION', self.output[fd])
            release.touch()
            self.until(lambda: b'SESSION' in self.output[fd] and b'Enter:' in self.output[fd])
            os.write(fd, b'\x1b')
        finally:
            release.touch()

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_snapshot_files_are_removed_after_forced_popup_close_and_detach(self):
        self.agent('codex')
        temporary = self.directory / 'popup-temporary'
        temporary.mkdir()
        self.tmux('set-environment', '-g', 'TMPDIR', str(temporary))
        fd, client = self.attach()
        for close in ('popup', 'detach'):
            with self.subTest(close=close):
                self.output[fd] = b''
                process = subprocess.Popen([sys.executable, str(SCRIPT), 'open', '--socket', self.socket,
                                            '--client', client], env={**self.env, 'TMPDIR': str(temporary)},
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    self.until(lambda: b'SESSION' in self.output[fd] and b'Enter:' in self.output[fd])
                    self.assertTrue(list(temporary.iterdir()))
                    if close == 'popup':
                        self.tmux('display-popup', '-C', '-c', client)
                    else:
                        self.tmux('detach-client', '-t', client)
                    process.communicate(timeout=5)
                    self.assertEqual(list(temporary.iterdir()), [])
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.communicate(timeout=5)

    def test_labels_cannot_inject_terminal_controls_or_break_rows(self):
        name = 'quoted " $(touch never) \u202e'
        pane = self.agent('codex', window=name)
        output = self.listing()
        self.assertEqual(len(output.splitlines()), 2)
        row = output.splitlines()[1].split('\t')
        self.assertEqual(len(row), 4)
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
        self.keys_and_wait(fd, '/✓'.encode(), '0/1')
        self.output[fd] = b''
        self.tmux('set-option', '-p', '-t', pane, '@ai_attention_state', 'done')
        self.until(lambda: b'Codex' in self.output[fd])
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

    def test_old_fzf_reports_upgrade_before_opening_a_popup(self):
        _, client = self.attach()
        commands = self.directory / 'bin'
        commands.mkdir()
        (commands / 'tmux').symlink_to(shutil.which('tmux'))
        fzf = commands / 'fzf'
        fzf.write_text("#!/bin/sh\nprintf '0.72.0\\n'\n")
        fzf.chmod(0o755)
        result = subprocess.run([sys.executable, str(SCRIPT), 'open', '--socket', self.socket,
                                 '--client', client], env={**self.env, 'PATH': str(commands)},
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0)
        self.assertIn('Agent picker requires fzf 0.73+; upgrade fzf',
                      self.tmux('show-messages', '-t', client))

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_empty_picker_stays_open_and_automatically_loads_new_agents(self):
        self.load_binding()
        fd, client = self.attach()
        before = self.client_state(client)
        self.open_popup(fd)
        self.keys_and_wait(fd, b'/', '0/0')
        self.assertEqual(self.client_state(client), before)
        self.output[fd] = b''
        pane = self.agent('codex', window='new-agent')
        self.until(lambda: b'new-agent' in self.output[fd])
        os.write(fd, b'\r')
        self.until(lambda: self.client_state(client).split()[1] == pane)

    @unittest.skipUnless(shutil.which('fzf'), 'fzf is required')
    def test_empty_picker_can_be_closed_without_navigating(self):
        fd, client = self.attach()
        before = self.client_state(client)
        self.output[fd] = b''
        process = subprocess.Popen([sys.executable, str(SCRIPT), 'open', '--socket', self.socket,
                                    '--client', client], env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.until(lambda: b'SESSION' in self.output[fd] and b'Enter:' in self.output[fd])
            self.assertIsNone(process.poll())
            os.write(fd, b'\x1b')
            output, errors = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0)
            self.assertEqual(output + errors, '')
            self.assertEqual(self.client_state(client), before)
        finally:
            if process.poll() is None:
                process.terminate()
            process.communicate(timeout=5)


if __name__ == '__main__':
    unittest.main()
