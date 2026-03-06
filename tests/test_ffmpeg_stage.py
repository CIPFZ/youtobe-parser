from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from app.ffmpeg_tools import ffmpeg_bin, merge_av_with_ass, run_ffmpeg


class FfmpegStageTests(unittest.TestCase):
    def test_ffmpeg_bin_resolves_real_binary(self) -> None:
        path = Path(ffmpeg_bin())
        self.assertTrue(path.exists(), msg=f'ffmpeg binary not found: {path}')

    def test_run_ffmpeg_version(self) -> None:
        run_ffmpeg(['-version'])

    def test_merge_av_with_ass_real(self) -> None:
        with tempfile.TemporaryDirectory(prefix='ffmpeg-stage-') as td:
            root = Path(td)
            video = root / 'video.mp4'
            audio = root / 'audio.m4a'
            ass = root / 'test.ass'
            out = root / 'out.mp4'

            run_ffmpeg(['-f', 'lavfi', '-i', 'testsrc=size=640x360:rate=24', '-t', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(video)])
            run_ffmpeg(['-f', 'lavfi', '-i', 'sine=frequency=600:sample_rate=44100', '-t', '2', '-c:a', 'aac', str(audio)])
            ass.write_text(
                '[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n'
                'Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding\n'
                'Style: Default,Arial,36,&H00FFFFFF,&H0000FFFF,&H00000000,&H55000000,-1,0,0,0,100,100,0,0,1,2,0,2,20,20,20,1\n\n'
                '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'
                'Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,ffmpeg stage test\n',
                encoding='utf-8',
            )

            merge_av_with_ass(video=video, audio=audio, ass=ass, out=out)
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 0)

            probe = subprocess.run([ffmpeg_bin(), '-i', str(out), '-f', 'null', '-'], text=True, capture_output=True, check=False)
            self.assertIn('Video:', probe.stderr)
            self.assertIn('Audio:', probe.stderr)


if __name__ == '__main__':
    unittest.main()
