import json
import yt_dlp
import logging
import asyncio
from typing import AsyncGenerator
from app.core.config import settings
from app.services.proxy_manager import proxy_manager

logger = logging.getLogger(__name__)

class ParseError(Exception):
    pass

def _format_video_data(info: dict) -> dict:
    """
    Uses yt-dlp to extract video metadata and available format URLs
    WITHOUT downloading the actual file.
    """
    proxy = proxy_manager.get_proxy()

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'ffmpeg_location': settings.FFMPEG_LOCATION,
        'noplaylist': True,
        'playlist_items': '1',
    }

    if proxy:
        ydl_opts['proxy'] = proxy


    formats = []
    seen = set()

    for f in info.get('formats', []):
        url = f.get('url')
        if not url:
            continue

        format_id = f.get('format_id', '')
        if format_id in seen:
            continue
        seen.add(format_id)

        # Determine type
        has_video = f.get('vcodec', 'none') != 'none'
        has_audio = f.get('acodec', 'none') != 'none'

        if has_video and has_audio:
            media_type = 'video+audio'
        elif has_video:
            media_type = 'video'
        elif has_audio:
            media_type = 'audio'
        else:
            continue

        # Build quality label
        height = f.get('height')
        quality = f"{height}p" if height else f.get('format_note', format_id)

        formats.append({
            'format_id': format_id,
            'quality': quality,
            'type': media_type,
            'ext': f.get('ext', 'unknown'),
            'url': url,
            'filesize': f.get('filesize') or f.get('filesize_approx'),
            'vcodec': f.get('vcodec', 'none'),
            'acodec': f.get('acodec', 'none'),
            'fps': f.get('fps'),
            'tbr': f.get('tbr'),  # total bitrate kbps
        })

    # Sort: video+audio first, then by height descending
    def sort_key(item):
        type_order = {'video+audio': 0, 'video': 1, 'audio': 2}
        height = 0
        q = item.get('quality', '')
        if q.endswith('p'):
            try:
                height = int(q[:-1])
            except ValueError:
                pass
        return (type_order.get(item['type'], 3), -height)

    formats.sort(key=sort_key)

    return {
        'title': info.get('title', ''),
        'description': info.get('description', ''),
        'author': info.get('uploader', '') or info.get('channel', ''),
        'author_url': info.get('uploader_url', '') or info.get('channel_url', ''),
        'thumbnail': info.get('thumbnail', ''),
        'duration': info.get('duration'),
        'upload_date': info.get('upload_date', ''),
        'view_count': info.get('view_count'),
        'like_count': info.get('like_count'),
        'tags': info.get('tags', []),
        'formats': formats,
    }


def parse_video_url(video_url: str) -> dict:
    """
    Uses yt-dlp to extract video metadata and available format URLs
    WITHOUT downloading the actual file. Only parses the first video (noplaylist).
    """
    proxy = proxy_manager.get_proxy()

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'ffmpeg_location': settings.FFMPEG_LOCATION,
        'noplaylist': True,
        'playlist_items': '1',
    }

    if proxy:
        ydl_opts['proxy'] = proxy

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info(f"Parsing info for {video_url}")
            info = ydl.extract_info(video_url, download=False)
            return _format_video_data(info)

    except yt_dlp.utils.DownloadError as e:
        logger.error(f"Parse failed for {video_url}: {e}")
        raise ParseError(f"yt-dlp error: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error parsing {video_url}: {e}")
        raise ParseError(f"Unexpected error: {str(e)}")


async def parse_video_url_stream(video_url: str) -> AsyncGenerator[str, None]:
    """
    Streams extracted video data for playlists or single videos.
    Uses an asyncio Queue to stream items as yt-dlp parses them in a background thread.
    """
    queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    
    # We use extract_flat=False to actually get the video details (formats),
    # but yt-dlp will block while processing the whole playlist.
    # To stream, we hook into yt-dlp's match_filter or just use a custom extractor wrapper.
    # The safest way to stream fully processed dicts is to use a hook or override the process_info.
    
    def yt_dlp_thread():
        proxy = proxy_manager.get_proxy()
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'ffmpeg_location': settings.FFMPEG_LOCATION,
            'extract_flat': False, # We want full video details including formats
            'ignoreerrors': True, # Skip unavailable videos in playlist
        }
        
        if proxy:
            ydl_opts['proxy'] = proxy
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                
                # We need to intercept process_ie_result to yield items as they complete
                original_process_ie_result = ydl.process_ie_result
                
                def patched_process_ie_result(ie_result, download=True, extra_info=None):
                    # Intercept the individual video results
                    if ie_result and ie_result.get('_type') != 'playlist':
                        # This is a video, format it and push to queue
                        try:
                            formatted_data = _format_video_data(ie_result)
                            # Thread-safe push to the queue
                            loop.call_soon_threadsafe(queue.put_nowait, ("item", formatted_data))
                        except Exception as ex:
                            logger.error(f"Error formatting item: {ex}")
                    
                    return original_process_ie_result(ie_result, download=download, extra_info=extra_info)
                
                # Apply the monkeypatch for this ydl instance
                ydl.process_ie_result = patched_process_ie_result
                
                logger.info(f"Starting stream parse for {video_url}")
                ydl.extract_info(video_url, download=False)
                
        except Exception as e:
            logger.error(f"Stream parse thread error: {e}")
            loop.call_soon_threadsafe(queue.put_nowait, ("error", str(e)))
        finally:
            # Signal the generator that the thread is done
            loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

    # Start yt-dlp in a background thread
    task = asyncio.create_task(asyncio.to_thread(yt_dlp_thread))
    
    try:
        while True:
            # Wait for items from the background thread
            msg_type, data = await queue.get()
            
            if msg_type == "done":
                break
            elif msg_type == "error":
                yield json.dumps({"error": data})
            elif msg_type == "item":
                # Yield the server-sent event chunk
                yield json.dumps(data)
                
    except asyncio.CancelledError:
        logger.warning(f"Stream cancelled for {video_url}")
        task.cancel()
        raise
