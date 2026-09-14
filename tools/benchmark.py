#!/usr/bin/env python3
"""PTY redraw timings, optionally with real macOS input-source switching."""
import argparse
import json
import math
import os
from pathlib import Path
import select
import shlex
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from test_plugin import Shell


def now():
    return time.clock_gettime(time.CLOCK_MONOTONIC)


def summary(values):
    ordered = sorted(values)
    return dict(samples=len(values), median_ms=round(statistics.median(values), 3),
                p95_ms=round(ordered[math.ceil(len(values) * .95) - 1], 3),
                max_ms=round(max(values), 3))


def measure_mock(plugin, count):
    shell = Shell(plugin=plugin)
    values = []
    try:
        shell.drain()
        for index in range(count):
            label = f'BENCH-{index}'
            shell.output = b''
            started = now()
            shell.event(f'bench.{index}\t{label}\n'.encode())
            shell.expect(f'[{label}]'.encode())
            values.append((now() - started) * 1000)
        return summary(values)
    finally:
        shell.close()


def measure_prompt_expansions(plugin, count=10):
    shell = Shell(plugin=plugin)
    counter = shell.directory / 'expansions'
    prompt = f'$(print x >> {shlex.quote(str(counter))})WK> '
    try:
        shell.send(f'PROMPT={shlex.quote(prompt)}; true\n')
        shell.drain()
        before = len(counter.read_text().splitlines())
        for _ in range(count):
            shell.send(':\n')
            shell.expect(b'WK> ')
            shell.drain()
        return dict(prompts=count, theme_expansions=len(counter.read_text().splitlines()) - before)
    finally:
        shell.close()


def measure_real(binary, plugin, count):
    initial_id, initial_name = subprocess.check_output([str(binary), '--once']).decode().rstrip('\n').split('\t')
    sources = dict(line.split('\t') for line in
                   subprocess.check_output([str(binary), '--list']).decode().splitlines())
    alternative = next((key for key in sources if key != initial_id), None)
    if not alternative:
        raise RuntimeError('At least two enabled input sources are required')
    with tempfile.TemporaryDirectory() as directory:
        selector = str(Path(directory) / 'select-source')
        subprocess.run(['clang', str(ROOT / 'tests/select-source.c'), '-o', selector,
                        '-framework', 'Carbon'], check=True)
        driver = subprocess.Popen([selector, '--interactive'], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        shell = Shell(binary=binary, plugin=plugin, initial_label=initial_name)
        # A second watcher separates native notification delivery from PTY redraw.
        watcher = subprocess.Popen([str(binary), '--watch'], stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL)
        total, after_select, native, selection = [], [], [], []
        try:
            if not select.select([watcher.stdout], [], [], 5)[0]:
                raise RuntimeError('Watcher did not start')
            os.read(watcher.stdout.fileno(), 4096)
            shell.drain()
            for index in range(count):
                target = alternative if index % 2 == 0 else initial_id
                shell.output = b''
                driver.stdin.write((target + '\n').encode())
                driver.stdin.flush()
                native_data, driver_data = b'', b''
                drawn_at = native_at = None
                deadline = now() + 5
                while now() < deadline and (drawn_at is None or native_at is None or b'\n' not in driver_data):
                    streams = [shell.master, watcher.stdout]
                    if b'\n' not in driver_data:
                        streams.append(driver.stdout)
                    for stream in select.select(streams, [], [], .1)[0]:
                        if stream == shell.master:
                            shell.read(0)
                            if drawn_at is None and f'[{sources[target]}]'.encode() in shell.output:
                                drawn_at = now()
                        elif stream == watcher.stdout:
                            native_data += os.read(watcher.stdout.fileno(), 4096)
                            if native_at is None and (target + '\t').encode() in native_data:
                                native_at = now()
                        else:
                            driver_data += os.read(driver.stdout.fileno(), 4096)
                if drawn_at is None or native_at is None or b'\n' not in driver_data:
                    raise RuntimeError('Input-source switch/redraw timed out')
                started, finished, status = driver_data.decode().strip().split('\t')
                if int(status):
                    raise RuntimeError('Input-source selection failed')
                started, finished = float(started), float(finished)
                total.append((drawn_at - started) * 1000)
                after_select.append((drawn_at - finished) * 1000)
                native.append((native_at - started) * 1000)
                selection.append((finished - started) * 1000)
            return dict(selection_to_pty=summary(total), selection_call=summary(selection),
                        selection_to_native=summary(native), selection_return_to_pty=summary(after_select),
                        note='PTY output arrival, not physical display latency; two independent watchers. '
                             'Negative return-to-PTY values mean redraw preceded selection return.')
        finally:
            try:
                subprocess.run([selector, initial_id], check=True, timeout=5)
                restored = subprocess.check_output([str(binary), '--once']).decode().split('\t')[0]
                if restored != initial_id:
                    raise RuntimeError('Failed to restore original input source')
            finally:
                watcher.terminate()
                watcher.wait(timeout=3)
                watcher.stdout.close()
                shell.close()
                driver.terminate()
                driver.communicate(timeout=3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plugin', type=Path, default=ROOT / 'which-keyboard.plugin.zsh')
    parser.add_argument('--binary', type=Path, default=ROOT / 'build/which-keyboard')
    parser.add_argument('--samples', type=int, default=100)
    parser.add_argument('--real-switch', action='store_true', help='Briefly change macOS input sources; restore on exit')
    parser.add_argument('--switches', type=int, default=10)
    args = parser.parse_args()
    if args.samples < 1 or args.switches < 1:
        parser.error('Sample counts must be positive')
    results = dict(event_to_pty=measure_mock(args.plugin, args.samples),
                   prompt_expansions=measure_prompt_expansions(args.plugin))
    if args.real_switch:
        results['real'] = measure_real(args.binary, args.plugin, args.switches)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
