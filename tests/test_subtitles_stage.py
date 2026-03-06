from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.subtitles import Segment, sec_to_ass, sec_to_srt, write_ass, write_srt


class SubtitlesStageTests(unittest.TestCase):
    def test_time_format_helpers(self) -> None:
        self.assertEqual(sec_to_srt(3661.257), '01:01:01,257')
        self.assertEqual(sec_to_ass(3661.257), '1:01:01.25')

    def test_write_srt_and_ass(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            srt = base / 'a.srt'
            ass = base / 'a.ass'
            segments = [Segment(0.0, 1.2, 'hello\nworld')]

            write_srt(segments, srt)
            write_ass(segments, ass)

            srt_text = srt.read_text(encoding='utf-8')
            ass_text = ass.read_text(encoding='utf-8')

            self.assertIn('00:00:00,000 --> 00:00:01,199', srt_text)
            self.assertIn('hello\nworld', srt_text)
            self.assertIn('[Events]', ass_text)
            self.assertIn(r'hello\Nworld', ass_text)


if __name__ == '__main__':
    unittest.main()
