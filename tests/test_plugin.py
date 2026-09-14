import errno
import fcntl
import os
from pathlib import Path
import pty
import select
import shlex
import signal
import struct
import subprocess
import tempfile
import termios
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Shell:
    def __init__(self, binary=None, plugin=None, initial_label='ABC'):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.events = self.directory / 'events'
        os.mkfifo(self.events)
        self.pid_file = self.directory / 'pid'
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', 30, 160, 0, 0))
        env = dict(os.environ, TERM='xterm-256color', ZDOTDIR=str(self.directory),
                   WK_TEST_EVENTS=str(self.events), WK_TEST_PID=str(self.pid_file),
                   WHICH_KEYBOARD_BINARY=str(binary or ROOT / 'tests/fake-helper.py'))
        self.process = subprocess.Popen(['zsh', '-f'], stdin=slave, stdout=slave,
                                        stderr=slave, env=env, start_new_session=True)
        os.close(slave)
        self.output = b''
        self.send("unsetopt beep; setopt promptsubst; PROMPT='WK> '; RPROMPT='BASE'; source "
                  + shlex.quote(str(plugin or ROOT / 'which-keyboard.plugin.zsh')) + '\n')
        self.expect(f'[{initial_label}]'.encode())

    def send(self, text):
        os.write(self.master, text.encode())

    def event(self, data):
        with self.events.open('ab') as stream:
            stream.write(data)

    def read(self, timeout=0.1):
        if select.select([self.master], [], [], timeout)[0]:
            try:
                result = os.read(self.master, 65536)
                self.output += result
                return result
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise
        return b''

    def drain(self):
        while self.read(0.05):
            pass
        self.output = b''

    def expect(self, text, timeout=4):
        deadline = time.monotonic() + timeout
        while text not in self.output and time.monotonic() < deadline:
            self.read()
        if text not in self.output:
            raise AssertionError(f'Missing {text!r}; got {self.output!r}')

    def close(self):
        if self.process.poll() is None:
            self.send('\x03exit\n')
            deadline = time.monotonic() + 3
            while self.process.poll() is None and time.monotonic() < deadline:
                self.read(0.05)
            if self.process.poll() is None:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        # Tests should clean up even when testing a broken lifecycle implementation.
        if self.pid_file.exists():
            try:
                os.kill(int(self.pid_file.read_text()), signal.SIGTERM)
            except ProcessLookupError:
                pass
        os.close(self.master)
        self.temp.cleanup()


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.shell = Shell()

    def tearDown(self):
        self.shell.close()

    def assert_process_exits(self, pid):
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return
            self.shell.read(0.05)
        self.fail(f'Helper {pid} did not exit')

    def test_async_update_preserves_edited_buffer_and_cursor(self):
        s = self.shell
        # Insert in the middle after an asynchronous redraw.
        s.send('print -r -- AC\x1b[D')
        s.drain()
        s.event('test.pinyin\t拼音\n'.encode())
        s.expect('[拼音]'.encode())  # no input sent to the terminal to trigger it
        s.send('B\n')
        s.expect(b'\r\nABC\r\n')
        self.assertIn(b'BASE', s.output)

    def test_partial_and_malformed_records_do_not_block(self):
        s = self.shell
        s.drain()
        s.event(b'bad-record\ninvalid\tbad\x1bname\nnext\tPar')
        s.send('print STILL_RESPONSIVE\n')
        s.expect(b'\r\nSTILL_RESPONSIVE\r\n')
        s.event(b'tial\n')
        s.expect(b'[Partial]')

    def test_prompt_data_cannot_execute_code(self):
        s = self.shell
        marker = s.directory / 'should-not-exist'
        s.drain()
        s.event(f'evil\t$(touch {marker}) `%n` %F{{red}}\n'.encode())
        s.expect(b'$(touch ')
        s.send('\n')
        s.expect(b'%F{red}')
        self.assertFalse(marker.exists())
        self.assertNotIn(b'command not found', s.output)

    def test_repeat_source_and_unload_restore_prompt(self):
        s = self.shell
        first_pid = s.pid_file.read_text()
        s.send('source ' + shlex.quote(str(ROOT / 'which-keyboard.plugin.zsh')) + '\n')
        s.send("print -r -- CHECK:${_WK_PID}; which-keyboard-unload; print -r -- RESTORED:${RPROMPT}\n")
        s.expect(f'CHECK:{first_pid}\r\n'.encode())
        s.expect(b'RESTORED:BASE\r\n')
        self.assert_process_exits(int(first_pid))

    def test_theme_change_and_custom_label(self):
        s = self.shell
        s.send("WHICH_KEYBOARD_LABELS[com.apple.keylayout.ABC]=EN; RPROMPT='NEW'; which-keyboard-refresh\n")
        s.expect(b'[EN]')
        s.send('which-keyboard-unload; print -r -- RESTORED:${RPROMPT}\n')
        s.expect(b'RESTORED:NEW\r\n')

    def test_left_position_preserves_editing_and_restores_both_sides(self):
        s = self.shell
        s.send('WHICH_KEYBOARD_POSITION=left; which-keyboard-refresh\n')
        s.expect(b'[ABC]\x1b[39m WK> ')
        s.send('print -r -- AC\x1b[D')
        s.drain()
        s.event(b'new\tNew\n')
        s.expect(b'[New]\x1b[39m WK> ')
        s.send('B\n')
        s.expect(b'\r\nABC\r\n')
        s.send('which-keyboard-unload; print -r -- RESTORED:${PROMPT}:${RPROMPT}\n')
        s.expect(b'RESTORED:WK> :BASE\r\n')

    def test_changing_sides_restores_theme_and_secondary_prompts(self):
        s = self.shell
        s.send("PROMPT2='MORE> '; RPROMPT2='SECOND'; WHICH_KEYBOARD_POSITION=left; which-keyboard-refresh\n")
        s.expect(b'[ABC]\x1b[39m WK> ')
        s.send("print -r -- 'first\n")
        s.expect(b'[ABC]\x1b[39m MORE> ')
        s.send("second'\n")
        s.expect(b'\r\nfirst\r\nsecond\r\n')
        s.send("PROMPT='CHANGED> '; WHICH_KEYBOARD_POSITION=right; which-keyboard-refresh; print -r -- LEFT:${PROMPT}:${PROMPT2}\n")
        s.expect(b'LEFT:CHANGED> :MORE> \r\n')
        s.send('which-keyboard-unload; print -r -- RIGHT:${RPROMPT}:${RPROMPT2}\n')
        s.expect(b'RIGHT:BASE:SECOND\r\n')

    def test_helper_death_removes_indicator_and_restarts_next_line(self):
        s = self.shell
        pid = int(s.pid_file.read_text())
        s.drain()
        os.kill(pid, signal.SIGTERM)
        # Observe the disconnect redraw before asking for the next prompt.
        s.expect(b'WK> ')
        s.send("print -r -- STATE:${WHICH_KEYBOARD_INPUT_SOURCE_ID}:END\n")
        s.expect(b'STATE::END\r\n')
        s.expect(b'[ABC]')
        self.assertNotEqual(pid, int(s.pid_file.read_text()))

    def test_exit_cleans_up_helper(self):
        s = self.shell
        pid = int(s.pid_file.read_text())
        s.send('exit\n')
        deadline = time.monotonic() + 4
        while s.process.poll() is None and time.monotonic() < deadline:
            s.read(0.05)
        self.assertIsNotNone(s.process.poll())
        self.assert_process_exits(pid)

    def test_refresh_preserves_last_command_status(self):
        s = self.shell
        s.send("PROMPT='RC:%? > '; false\n")
        s.expect(b'RC:1 > ')
        s.drain()
        s.event(b'new\tNew\n')
        s.expect(b'[New]')
        self.assertIn(b'RC:1 > ', s.output)

    def test_cached_prompt_expands_theme_once_and_ignores_duplicate_events(self):
        s = self.shell
        counter = s.directory / 'expansions'
        prompt = f'$(print x >> {shlex.quote(str(counter))})WK> '
        s.send(f'PROMPT={shlex.quote(prompt)}; true\n')
        s.drain()
        self.assertEqual(counter.read_text().splitlines(), ['x'])
        s.event(b'com.apple.keylayout.ABC\tABC\n')
        s.read(.1)
        self.assertEqual(counter.read_text().splitlines(), ['x'])

    def test_identical_labels_do_not_reexpand_theme(self):
        s = self.shell
        counter = s.directory / 'expansions'
        prompt = f'$(print x >> {shlex.quote(str(counter))})WK> '
        s.send("WHICH_KEYBOARD_LABELS[com.apple.keylayout.ABC]=Same; "
               "WHICH_KEYBOARD_LABELS[other]=Same; "
               f'PROMPT={shlex.quote(prompt)}; true\n')
        s.drain()
        self.assertEqual(counter.read_text().splitlines(), ['x'])
        s.event(b'other\tOther\n')
        s.read(.1)
        self.assertEqual(counter.read_text().splitlines(), ['x'])
        s.send('print -r -- STATE:$WHICH_KEYBOARD_INPUT_SOURCE_ID\n')
        s.expect(b'STATE:other\r\n')

    def test_multiline_input_survives_refresh(self):
        s = self.shell
        s.send("print -r -- 'first\n")
        s.drain()
        s.event(b'new\tNew\n')
        s.expect(b'New')
        s.send("second'\n")
        s.expect(b'\r\nfirst\r\nsecond\r\n')

    def test_running_command_is_not_redrawn(self):
        s = self.shell
        s.send('sleep 0.4; print FINISHED\n')
        s.drain()
        s.event(b'new\tDuringCommand\n')
        s.expect(b'FINISHED\r\n')
        s.expect(b'[DuringCommand]')
        self.assertLess(s.output.index(b'FINISHED'), s.output.index(b'[DuringCommand]'))


class NativeTests(unittest.TestCase):
    @unittest.skipUnless(os.environ.get('WK_TEST_REAL_SWITCH') == '1',
                         'opt-in test briefly changes the macOS input source')
    def test_real_input_source_notification(self):
        binary = str(ROOT / 'build/which-keyboard')
        initial = subprocess.check_output([binary, '--once']).decode().split('\t')[0]
        sources = subprocess.check_output([binary, '--list']).decode().splitlines()
        alternative = next((line.split('\t')[0] for line in sources
                            if line.split('\t')[0] != initial), None)
        if not alternative:
            self.skipTest('At least two enabled input sources are needed')
        with tempfile.TemporaryDirectory() as directory:
            selector = str(Path(directory) / 'select-source')
            subprocess.run(['clang', str(ROOT / 'tests/select-source.c'), '-o', selector,
                            '-framework', 'Carbon'], check=True, capture_output=True)
            process = subprocess.Popen([binary, '--watch'], stdout=subprocess.PIPE,
                                       stderr=subprocess.DEVNULL)
            try:
                self.assertTrue(select.select([process.stdout], [], [], 5)[0])
                os.read(process.stdout.fileno(), 4096)
                started = time.monotonic()
                subprocess.run([selector, alternative], check=True, capture_output=True)
                data = b''
                deadline = time.monotonic() + 5
                while alternative.encode() not in data and time.monotonic() < deadline:
                    if select.select([process.stdout], [], [], 0.1)[0]:
                        data += os.read(process.stdout.fileno(), 4096)
                self.assertIn(alternative.encode() + b'\t', data)
                print(f'\nReal source notification, including selector launch: '
                      f'{(time.monotonic() - started) * 1000:.0f} ms')
            finally:
                try:
                    subprocess.run([selector, initial], check=True, capture_output=True)
                    restored = subprocess.check_output([binary, '--once']).decode().split('\t')[0]
                    self.assertEqual(restored, initial)
                finally:
                    process.terminate()
                    process.wait(timeout=3)
                    process.stdout.close()

    def test_cli_rejects_unknown_arguments(self):
        result = subprocess.run([str(ROOT / 'build/which-keyboard'), '--bad'], capture_output=True)
        self.assertEqual(result.returncode, 64)
        self.assertIn(b'Usage:', result.stderr)

    def test_snapshot_protocol(self):
        result = subprocess.run([str(ROOT / 'build/which-keyboard'), '--once'],
                                capture_output=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        fields = result.stdout.decode().rstrip('\n').split('\t')
        self.assertEqual(len(fields), 2)
        self.assertTrue(all(fields))

    def test_native_watch_and_refresh_signal(self):
        process = subprocess.Popen([str(ROOT / 'build/which-keyboard'), '--watch'],
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        try:
            self.assertTrue(select.select([process.stdout], [], [], 5)[0])
            initial = os.read(process.stdout.fileno(), 4096)
            self.assertIn(b'\t', initial)
            process.send_signal(signal.SIGUSR1)
            self.assertTrue(select.select([process.stdout], [], [], 5)[0])
            refreshed = os.read(process.stdout.fileno(), 4096)
            self.assertIn(b'\t', refreshed)
            self.assertTrue(refreshed.endswith(b'\n'))
        finally:
            process.terminate()
            process.wait(timeout=3)
            process.stdout.close()


if __name__ == '__main__':
    unittest.main()
