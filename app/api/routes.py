from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.parser import parse_video_url, ParseError
import asyncio
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class ParseRequest(BaseModel):
    video_url: str


@router.post("/parse")
async def parse_url(req: ParseRequest):
    """
    Parse a YouTube URL and return video metadata + available format direct links.
    """
    if not req.video_url.strip():
        raise HTTPException(status_code=400, detail="video_url is required")

    try:
        result = await asyncio.to_thread(parse_video_url, req.video_url.strip())
        return result
    except asyncio.CancelledError:
        logger.warning(f"Request cancelled for {req.video_url} (server shutdown or client disconnect)")
        from fastapi import Response
        return Response(status_code=499)
    except ParseError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@router.get("/parse-stream")
async def parse_url_stream(video_url: str):
    """
    Stream video parsing results (useful for playlists).
    Server-Sent Events (SSE) endpoint.
    """
    if not video_url or not video_url.strip():
        raise HTTPException(status_code=400, detail="video_url is required")

    from app.services.parser import parse_video_url_stream
    from sse_starlette.sse import EventSourceResponse

    async def event_generator():
        try:
            async for data in parse_video_url_stream(video_url.strip()):
                yield {"data": data}
        except asyncio.CancelledError:
            logger.warning(f"SSE stream cancelled for {video_url}")
            return
        except Exception as e:
            logger.error(f"SSE stream error for {video_url}: {e}")
            yield {"data": f'{{"error": "{str(e)}"}}'}

    return EventSourceResponse(event_generator())


class ProxyRequest(BaseModel):
    proxy_url: str


@router.get("/proxies")
async def get_proxies():
    from app.services.proxy_manager import proxy_manager
    return {"proxies": proxy_manager.get_all_proxies()}


@router.post("/proxies")
async def add_proxy(req: ProxyRequest):
    from app.services.proxy_manager import proxy_manager
    if not req.proxy_url.strip():
        raise HTTPException(status_code=400, detail="proxy_url is required")
    added = proxy_manager.add_proxy(req.proxy_url)
    if not added:
        raise HTTPException(status_code=400, detail="Proxy already exists or is empty")
    return {"status": "success", "proxy": req.proxy_url}


@router.delete("/proxies")
async def remove_proxy(req: ProxyRequest):
    from app.services.proxy_manager import proxy_manager
    if not req.proxy_url.strip():
        raise HTTPException(status_code=400, detail="proxy_url is required")
    removed = proxy_manager.remove_proxy(req.proxy_url)
    if not removed:
        raise HTTPException(status_code=404, detail="Proxy not found")
    return {"status": "success", "proxy": req.proxy_url}
