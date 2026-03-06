from __future__ import annotations

import importlib
import sys
import types
import unittest

from app.subtitles import Segment


class _FakeResp:
    def __init__(self, text: str):
        self.choices = [type('Choice', (), {'message': type('Message', (), {'content': text})()})()]


class _FakeCompletions:
    def create(self, **kwargs):
        return _FakeResp('你好世界')


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeOpenAI:
    def __init__(self, **kwargs):
        self.chat = _FakeChat()


class _FakeSettings:
    openai_api_key = 'key'
    openai_base_url = 'https://example.com/v1'
    openai_model = 'gpt'
    target_language = 'zh-CN'


class TranslatorStageTests(unittest.TestCase):
    def test_translate_enabled(self) -> None:
        sys.modules['openai'] = types.SimpleNamespace(OpenAI=_FakeOpenAI)
        sys.modules['app.settings'] = types.SimpleNamespace(settings=_FakeSettings())
        import app.translator as translator
        importlib.reload(translator)

        t = translator.SubtitleTranslator()
        out = t.translate([Segment(0, 1, 'hello world')])
        self.assertEqual(out[0].text, '你好世界')

    def test_translate_disabled_passthrough(self) -> None:
        class _NoKeySettings(_FakeSettings):
            openai_api_key = ''

        sys.modules['openai'] = types.SimpleNamespace(OpenAI=_FakeOpenAI)
        sys.modules['app.settings'] = types.SimpleNamespace(settings=_NoKeySettings())
        import app.translator as translator
        importlib.reload(translator)

        t = translator.SubtitleTranslator()
        s = [Segment(0, 1, 'hello')]
        self.assertEqual(t.translate(s), s)


if __name__ == '__main__':
    unittest.main()
