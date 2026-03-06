from __future__ import annotations

import os
import unittest

from app.settings import settings
from app.subtitles import Segment
from app.translator import SubtitleTranslator


class TranslatorStageTests(unittest.TestCase):
    def test_real_openai_translation(self) -> None:
        api_key = settings.openai_api_key.strip() or os.getenv('OPENAI_API_KEY', '').strip()
        if not api_key:
            self.skipTest('Set OPENAI_API_KEY (or OPENAI_API_KEY in .env) to run real translator test.')

        samples = [
            Segment(0.0, 1.0, 'Hello world.'),
            Segment(1.0, 2.0, 'How are you?'),
        ]
        out = SubtitleTranslator().translate(samples)

        self.assertEqual(len(out), 2)
        self.assertNotEqual(out[0].text.strip(), '')
        self.assertNotEqual(out[1].text.strip(), '')


if __name__ == '__main__':
    unittest.main()
