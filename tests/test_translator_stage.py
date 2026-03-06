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
    calls = 0

    def create(self, **kwargs):
        _FakeCompletions.calls += 1
        user_content = kwargs['messages'][1]['content']
        if '1\thello world' in user_content and '2\thow are you' in user_content:
            return _FakeResp('1\t你好世界\n2\t你好吗')
        return _FakeResp('1\t你好世界')


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
    translation_batch_size = 2


class TranslatorStageTests(unittest.TestCase):
    def test_translate_enabled_batch(self) -> None:
        _FakeCompletions.calls = 0
        sys.modules['openai'] = types.SimpleNamespace(OpenAI=_FakeOpenAI)
        sys.modules['app.settings'] = types.SimpleNamespace(settings=_FakeSettings())
        import app.translator as translator
        importlib.reload(translator)

        t = translator.SubtitleTranslator()
        out = t.translate([Segment(0, 1, 'hello world'), Segment(1, 2, 'how are you')])
        self.assertEqual(out[0].text, '你好世界')
        self.assertEqual(out[1].text, '你好吗')
        self.assertEqual(_FakeCompletions.calls, 1)

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
