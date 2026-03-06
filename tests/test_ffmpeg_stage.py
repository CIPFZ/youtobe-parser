from __future__ import annotations

import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


class _FakeSettings:
    ffmpeg_path = ''


class FfmpegStageTests(unittest.TestCase):
    def _load_module(self):
        sys.modules['app.settings'] = types.SimpleNamespace(settings=_FakeSettings())
        sys.modules['imageio_ffmpeg'] = types.SimpleNamespace(get_ffmpeg_exe=lambda: '/tmp/imageio-ffmpeg')
        import app.ffmpeg_tools as ff
        importlib.reload(ff)
        return ff

    def test_ffmpeg_bin_priority_custom(self) -> None:
        ff = self._load_module()
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / 'ffmpeg'
            fake.write_text('bin')
            ff.settings.ffmpeg_path = str(fake)
            self.assertEqual(ff.ffmpeg_bin(), str(fake))

    def test_ffmpeg_bin_custom_missing(self) -> None:
        ff = self._load_module()
        ff.settings.ffmpeg_path = '/not/exist/ffmpeg'
        with self.assertRaises(FileNotFoundError):
            ff.ffmpeg_bin()

    def test_run_ffmpeg_invocation(self) -> None:
        ff = self._load_module()
        with mock.patch('app.ffmpeg_tools.ffmpeg_bin', return_value='/usr/bin/ffmpeg'), mock.patch('subprocess.run') as run:
            ff.run_ffmpeg(['-version'])
            run.assert_called_once_with(['/usr/bin/ffmpeg', '-y', '-version'], check=True)


if __name__ == '__main__':
    unittest.main()
