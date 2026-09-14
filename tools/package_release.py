#!/usr/bin/env python3
"""Package the native helper and plugin with a fixed, portable archive layout."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import re
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    'build/which-keyboard': 0o755,
    'which-keyboard.plugin.zsh': 0o644,
    'README.md': 0o644,
    'README_EN.md': 0o644,
    'LICENSE': 0o644,
}


def package(version, arch, output):
    if not re.fullmatch(r'(?:v\d+\.\d+\.\d+|dev-[0-9a-f]{7,40})', version):
        raise ValueError('Use vMAJOR.MINOR.PATCH or dev-COMMIT as the version')
    if arch not in ('arm64', 'x86_64'):
        raise ValueError('Architecture must be arm64 or x86_64')
    actual = subprocess.check_output(['lipo', '-archs', str(ROOT / 'build/which-keyboard')], text=True).strip()
    if actual != arch:
        raise ValueError(f'Expected {arch} binary, found {actual}')
    payloads = [(name, mode, (ROOT / name).read_bytes()) for name, mode in FILES.items()]
    payloads.append(('VERSION', 0o644, (version + '\n').encode()))
    name = f'which-keyboard-{version}-macos-{arch}'
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'{name}.tar.gz'
    # Explicit members and normalized tar metadata prevent workstation files,
    # owner names, resource forks, and local paths from leaking into releases.
    with archive.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w') as tar:
                for relative, mode, data in payloads:
                    info = tarfile.TarInfo(f'{name}/{relative}')
                    info.size = len(data)
                    info.mode = mode
                    info.mtime = 0
                    tar.addfile(info, io.BytesIO(data))
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + '.sha256').write_text(f'{checksum}  {archive.name}\n')
    return archive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--arch', required=True, choices=('arm64', 'x86_64'))
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    args = parser.parse_args()
    print(package(args.version, args.arch, args.output))


if __name__ == '__main__':
    main()
