#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging

from app.discovery.repository import init_db, upsert_candidates
from app.discovery.service import run_discovery_once
from app.logging_utils import setup_logging
from app.settings import settings


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Daily YouTube discovery: fetch + score + store')
    p.add_argument('--top-n', type=int, default=0, help='Override DISCOVERY_TOP_N')
    p.add_argument('--days-back', type=int, default=0, help='Override DISCOVERY_DAYS_BACK')
    p.add_argument('--dry-run', action='store_true', help='Do not write DB, only print results')
    return p.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(settings.log_level, settings.log_file)
    logger = logging.getLogger(__name__)

    raw, selected = run_discovery_once(top_n=args.top_n, days_back=args.days_back)
    if args.dry_run:
        for idx, x in enumerate(selected, start=1):
            print(f'{idx:02d}. score={x.score:.3f} views={x.view_count} comments={x.comment_count} lang={x.language_hint} url={x.url}')
        return

    db_path = settings.discovery_db_path.resolve()
    init_db(db_path)
    count = upsert_candidates(db_path, selected)
    print(f'完成: discovered={count} db={db_path}')


if __name__ == '__main__':
    main()
