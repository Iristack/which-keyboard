import hashlib
from pathlib import Path
import platform
import subprocess
import sys
import tarfile
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_release import FILES, package


class ReleaseTests(unittest.TestCase):
    def test_archive_layout_metadata_checksum_and_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            archive = package('v0.1.1', platform.machine(), output)
            checksum = archive.with_name(archive.name + '.sha256').read_text().split()[0]
            self.assertEqual(checksum, hashlib.sha256(archive.read_bytes()).hexdigest())
            prefix = archive.name.removesuffix('.tar.gz')
            with tarfile.open(archive) as tar:
                self.assertEqual(set(tar.getnames()), {f'{prefix}/{name}' for name in (*FILES, 'VERSION')})
                for member in tar.getmembers():
                    self.assertTrue(member.isfile())
                    self.assertEqual((member.uid, member.gid, member.uname, member.gname), (0, 0, '', ''))
                    self.assertEqual(member.mode, 0o755 if member.name.endswith('/build/which-keyboard') else 0o644)
                    target = output / member.name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(tar.extractfile(member).read())
                    target.chmod(member.mode)
            self.assertEqual((output / prefix / 'VERSION').read_text(), 'v0.1.1\n')
            subprocess.run(['zsh', '-n', str(output / prefix / 'which-keyboard.plugin.zsh')], check=True)
            result = subprocess.run([str(output / prefix / 'build/which-keyboard'), '--invalid'], capture_output=True)
            self.assertEqual(result.returncode, 64)
            self.assertIn(b'Usage:', result.stderr)

    def test_rejects_invalid_version_and_mismatched_architecture(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                package('../../escape', platform.machine(), directory)
            other = 'x86_64' if platform.machine() == 'arm64' else 'arm64'
            with self.assertRaises(ValueError):
                package('v0.1.1', other, directory)


if __name__ == '__main__':
    unittest.main()
