#!/usr/bin/env python3
from __future__ import annotations

"""Download and prepare fast-whisper model according to current settings.

Usage:
  python tests/download_fast_whisper_model.py
"""

from app.logging_utils import setup_logging
from app.settings import settings
from app.transcriber import _apply_download_proxy_env, _resolve_whisper_model_ref


def main() -> int:
    setup_logging(settings.log_level, settings.log_file)
    _apply_download_proxy_env(settings.whisper_download_proxy.strip())

    model_ref = _resolve_whisper_model_ref()
    print(f"Model prepared: {model_ref}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
