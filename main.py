#!/usr/bin/env python3
from __future__ import annotations

import argparse

from app.pipeline import Pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description='高效版 YouTube 全流程处理器（纯 Python）')
    parser.add_argument('url', help='视频链接')
    args = parser.parse_args()

    output = Pipeline().run(args.url)
    print(f'完成: {output}')


if __name__ == '__main__':
    main()
