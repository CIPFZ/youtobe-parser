from __future__ import annotations

import os
import unittest

from app.pipeline import Pipeline
from app.settings import settings


class PipelineE2ETests(unittest.TestCase):
    def test_pipeline_run_real(self) -> None:
        url = os.getenv('PIPELINE_TEST_URL', '').strip() or settings.source_url.strip()
        if not url:
            self.skipTest('Set PIPELINE_TEST_URL or SOURCE_URL in .env to run real pipeline e2e test.')

        output = Pipeline().run(url)
        self.assertTrue(output.exists())
        self.assertGreater(output.stat().st_size, 0)

        metadata_dir = settings.work_dir.resolve() / settings.metadata_dirname
        self.assertTrue(metadata_dir.exists())
        self.assertGreaterEqual(len(list(metadata_dir.glob('*.video_info.json'))), 1)


if __name__ == '__main__':
    unittest.main()
