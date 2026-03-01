"""Client for the PO Token Provider service.

The provider runs as a Docker container (brainicism/bgutil-ytdl-pot-provider)
and exposes an HTTP API to generate YouTube Proof-of-Origin tokens.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# Timeout for token requests (seconds)
_REQUEST_TIMEOUT = 15.0


@dataclass
class POToken:
    """A PO Token result from the provider."""
    content_binding: str
    po_token: str


async def fetch_po_token(video_id: str = "") -> Optional[POToken]:
    """Fetch a PO token from the HTTP provider service.

    Args:
        video_id: Optional YouTube video ID for context.

    Returns:
        POToken with visitor_data and po_token, or None if unavailable.
    """
    if not settings.po_token_server:
        logger.debug("PO Token server not configured, skipping")
        return None

    url = f"{settings.po_token_server.rstrip('/')}/get_pot"
    payload = {}
    if video_id:
        payload["video_id"] = video_id

    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        content_binding = data.get("contentBinding") or data.get("content_binding", "")
        po_token = data.get("poToken") or data.get("po_token", "")

        if not po_token:
            logger.warning("PO Token provider returned empty token: %s", data)
            return None

        logger.info("PO Token obtained (content_binding=%s…)", content_binding[:16] if content_binding else "?")
        return POToken(content_binding=content_binding, po_token=po_token)

    except httpx.ConnectError:
        logger.warning("PO Token provider unreachable at %s — proceeding without token", url)
        return None
    except httpx.HTTPStatusError as exc:
        logger.warning("PO Token provider returned %s — proceeding without token", exc.response.status_code)
        return None
    except Exception:
        logger.exception("Unexpected error fetching PO token")
        return None
