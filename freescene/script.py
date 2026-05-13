"""LLM → N scene prompts.

Mirrors the prompt shape Free.ai uses on /v1/video/movie/ in production:
a film-director system prompt, the user's idea, N scenes, one per line.
Strips ``<think>...</think>`` reasoning blocks (Qwen3 / DeepSeek style)
and naturally falls back to padding the idea if the LLM is unreachable.
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

import httpx

from .config import Config


logger = logging.getLogger(__name__)

_SYSTEM_TEMPLATE = (
    "You are a film director writing scene prompts for a short AI-generated "
    "video. The user provides an idea. Output EXACTLY {n} scene prompts "
    "(one per line, no numbering, no commentary). Each prompt must be a "
    "single concrete visual sentence describing camera framing, subject, "
    "action, and lighting — under 30 words. Maintain visual continuity "
    "across scenes. Style: {style}."
)

_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)
_LIST_PREFIX = re.compile(r"^\s*(?:\d+[.)\]]\s*|[-*•]\s*)")


async def write_script(
    idea: str,
    num_scenes: int,
    style: str,
    config: Config,
) -> list[str]:
    """Ask the configured LLM for ``num_scenes`` scene prompts.

    Returns exactly ``num_scenes`` strings. If the LLM is unreachable or
    returns fewer usable lines than requested, the result is padded with
    the original idea so the render phase still proceeds.
    """
    if num_scenes < 1:
        raise ValueError("num_scenes must be >= 1")
    sys_prompt = _SYSTEM_TEMPLATE.format(n=num_scenes, style=style or "cinematic")
    payload = {
        "model": config.llm_model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": idea},
        ],
        "max_tokens": 600,
        "temperature": 0.7,
        "stream": False,
    }
    url = f"{config.effective_llm_url}/v1/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=config.timeout_llm_s) as client:
            r = await client.post(url, json=payload, headers=config.auth_headers())
            r.raise_for_status()
            data = r.json()
            content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        logger.warning(
            "freescene.script: LLM unreachable at %s (%s) — falling back to idea repeats",
            url, e,
        )
        return _fallback_pad(idea, num_scenes, style)
    return _parse_scenes(content, num_scenes, idea, style)


def _parse_scenes(content: str, n: int, idea: str, style: str) -> list[str]:
    """Extract up to ``n`` scene-prompt lines from an LLM response."""
    content = _THINK_RE.sub("", content or "").strip()
    lines = []
    for raw in content.splitlines():
        line = _LIST_PREFIX.sub("", raw).strip()
        # Drop empty + meta-commentary; accept anything reasonably-sized.
        if 8 <= len(line) <= 320:
            lines.append(line)
    if len(lines) >= n:
        return lines[:n]
    return _fallback_pad(idea, n, style, seed=lines)


def _fallback_pad(idea: str, n: int, style: str, seed: Iterable[str] = ()) -> list[str]:
    out = list(seed)
    style_tag = (style or "cinematic").strip()
    while len(out) < n:
        out.append(f"{idea.strip()} — {style_tag}")
    return out[:n]
