#!/usr/bin/env python3
"""Controllable byte stream for PTY tests; never queries or changes the OS IME."""
import os
from pathlib import Path
import signal
import sys

signal.signal(signal.SIGUSR1, lambda *_: None)
Path(os.environ['WK_TEST_PID']).write_text(str(os.getpid()))
sys.stdout.buffer.write(b'com.apple.keylayout.ABC\tABC\n')
sys.stdout.buffer.flush()
with os.fdopen(os.open(os.environ['WK_TEST_EVENTS'], os.O_RDWR), 'rb', buffering=0) as events:
    while True:
        chunk = events.read(4096)
        if chunk:
            sys.stdout.buffer.write(chunk)
            sys.stdout.buffer.flush()
