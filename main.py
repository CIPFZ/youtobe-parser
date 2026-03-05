#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging

from app.logging_utils import setup_logging
from app.pipeline import Pipeline
from app.settings import settings


def main() -> None:
    parser = argparse.ArgumentParser(description='高效版 YouTube 全流程处理器（纯 Python）')
    parser.add_argument('url', help='视频链接')
    args = parser.parse_args()

    setup_logging(settings.log_level, settings.log_file)
    logger = logging.getLogger(__name__)
    logger.info('Pipeline started for url=%s', args.url)

    output = Pipeline().run(args.url)
    logger.info('Pipeline completed. output=%s', output)
    print(f'完成: {output}')


if __name__ == '__main__':
    main()
