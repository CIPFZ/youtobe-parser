"""Subtitle Translator worker.

Downloads SRT/VTT files, translates them using an LLM, and outputs ASS format.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from typing import List

import httpx

from app.config import settings
from app.core.task_store import task_store

logger = logging.getLogger(__name__)

# Basic regex for parsing SRT time lines
SRT_TIME_RE = re.compile(
    r"(\d{2}:\d{2}:\d{2}[\.,]\d{3})\s*(?:-->|--!>)\s*(\d{2}:\d{2}:\d{2}[\.,]\d{3})"
)


@dataclass
class SubtitleBlock:
    index: int
    start_time: str
    end_time: str
    text_lines: List[str]


def parse_srt(content: str) -> List[SubtitleBlock]:
    """Parse SRT (or VTT) content into SubtitleBlock objects."""
    blocks: List[SubtitleBlock] = []
    lines = [line.strip() for line in content.strip().splitlines()]
    
    current_block: SubtitleBlock | None = None
    idx = 1
    
    for line in lines:
        if not line:
            if current_block and current_block.text_lines:
                blocks.append(current_block)
                current_block = None
            continue
            
        m = SRT_TIME_RE.search(line)
        if m:
            if current_block and current_block.text_lines:
                blocks.append(current_block)
            current_block = SubtitleBlock(
                index=idx,
                start_time=m.group(1).replace(',', '.'),
                end_time=m.group(2).replace(',', '.'),
                text_lines=[]
            )
            idx += 1
        elif current_block is not None:
            # Ignore WEBVTT header or block indices if they are caught as text
            if not line.isdigit() and line != "WEBVTT":
                current_block.text_lines.append(line)
                
    if current_block and current_block.text_lines:
        blocks.append(current_block)
        
    return blocks


def format_ass_time(time_str: str) -> str:
    """Convert SRT HH:MM:SS.mmm to ASS H:MM:SS.cs"""
    # 00:00:10.500 -> 0:00:10.50
    # Strip leading hour zero if H is < 10 (Actually ASS requires H:MM:SS.cs)
    parts = time_str.split(':')
    if len(parts) == 3:
        h = str(int(parts[0]))
        m = parts[1]
        s_ms = parts[2].split('.')
        s = s_ms[0]
        cs = s_ms[1][:2] if len(s_ms) > 1 else "00"
        return f"{h}:{m}:{s}.{cs}"
    return time_str


def create_ass_header(title: str = "Translated Subtitles") -> str:
    """Generate the standard ASS file header."""
    return f"""[Script Info]
Title: {title}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,65,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,2,2,2,10,10,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


async def call_llm_translation(texts: List[str]) -> List[str]:
    """Call an OpenAI-compatible chat completion API to translate subtitle text."""
    if not texts:
        return []

    if not settings.openai_api_key:
        logger.warning("OPENAI_API_KEY is empty, skip translation and keep original text")
        return texts

    # Map the texts to numbered lines to ensure LLM keeps the order
    prompt = "Translate the following English subtitles to Chinese. Maintain the exact line count and formatting. Return ONLY the translated lines, each preceded by its line number and a separator (e.g., '1|你好').\n\n"
    for i, text in enumerate(texts):
        prompt += f"{i}|{text}\n"

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": "You are a professional subtitle translator. You always return exactly the same number of lines as provided, maintaining the exact 'LineNumber|TranslatedText' format."},
            {"role": "user", "content": prompt}
        ],
        "max_tokens": 2000,
        "temperature": 0.3
    }
    
    logger.debug("Calling LLM API for %d lines", len(texts))
    
    url = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    
    try:
        async with httpx.AsyncClient(timeout=60.0, trust_env=False) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            content = data["choices"][0]["message"]["content"]
            
            # Parse back
            translated_lines = []
            result_map = {}
            for line in content.splitlines():
                if '|' in line:
                    idx_str, txt = line.split('|', 1)
                    if idx_str.strip().isdigit():
                        result_map[int(idx_str.strip())] = txt.strip()
                        
            # Map back to original indices to guarantee order
            for i in range(len(texts)):
                translated_lines.append(result_map.get(i, texts[i]))
                
            return translated_lines
    except httpx.HTTPError as e:
        logger.error(f"LLM API request failed: {e}")
        return texts  # Fallback to original
    except Exception as e:
        logger.error(f"Unexpected error in LLM call: {e}")
        return texts


async def translate_subtitle(path: str, task_id: str) -> None:
    """Download or read subtitle, translate in batches, and output ASS to disk."""
    await task_store.update_task(task_id, status="processing", progress=0.0)
    
    # Determine proxy
    proxy = settings.global_proxy or None

    try:
        # 1. Obtain Content
        content = ""
        if path.startswith("http://") or path.startswith("https://"):
            async with httpx.AsyncClient(proxy=proxy, trust_env=False, follow_redirects=True, timeout=30.0) as client:
                resp = await client.get(path)
                resp.raise_for_status()
                content = resp.text
        else:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Local file not found: {path}")
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

        # 2. Parse
        blocks = parse_srt(content)
        if not blocks:
            raise ValueError("Could not parse subtitle content as SRT/VTT")
            
        await task_store.update_task(task_id, progress=10.0)
        
        # 3. Translate in batches
        batch_size = 50
        translated_blocks = []
        
        for i in range(0, len(blocks), batch_size):
            batch = blocks[i:i + batch_size]
            
            # Combine multi-line text into single line with \N for translation
            texts_to_translate = ["\\N".join(b.text_lines) for b in batch]
            
            translated_texts = await call_llm_translation(texts_to_translate)
            
            for j, translated_text in enumerate(translated_texts):
                b = batch[j]
                # Combine Chinese on top (default size 65) and English on bottom (smaller, size 40, different color if needed)
                original_text = "\\N".join(b.text_lines)
                b.text_lines = [translated_text, "{\\fs40\\c&HCCCCCC&}" + original_text]
                translated_blocks.append(b)
                
            progress = 10.0 + (90.0 * (min(i + batch_size, len(blocks)) / len(blocks)))
            await task_store.update_task(task_id, progress=round(progress, 1))

        # 4. Generate ASS
        ass_content = create_ass_header()
        
        for b in translated_blocks:
            start = format_ass_time(b.start_time)
            end = format_ass_time(b.end_time)
            text = "\\N".join(b.text_lines)
            
            # Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
            ass_content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"

        # 5. Save to Disk
        download_dir = os.path.join(os.getcwd(), "downloads")
        os.makedirs(download_dir, exist_ok=True)
        
        # Determine output filename based on original path if possible, fallback to task_id
        base_name = os.path.basename(path) if not path.startswith("http") else path.split("/")[-1]
        name_no_ext = os.path.splitext(base_name)[0] or task_id
        out_filename = f"{name_no_ext}_{task_id[:6]}.ass"
        out_filepath = os.path.join(download_dir, out_filename)
        
        with open(out_filepath, "w", encoding="utf-8") as f:
            f.write(ass_content)
            
        ass_abs_path = os.path.abspath(out_filepath)

        # 6. Update task with file metadata
        await task_store.update_task(
            task_id,
            status="completed",
            progress=100.0,
            result={
                "output_path": ass_abs_path,
                "output_name": out_filename,
                "source_path": path,
                "format": "ass",
            },
        )
        logger.info("Translation task %s completed successfully. Saved to: %s", task_id, ass_abs_path)

    except Exception as exc:
        logger.exception("Translation task %s failed", task_id)
        await task_store.update_task(
            task_id,
            status="failed",
            error=str(exc)
        )
