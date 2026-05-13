"""Per-scene video render — POST to /v1/video/generate, download the result.

The hosted backend (api.free.ai) and most self-hosted vLLM/diffusers shims
share the same OpenAI-shaped contract: POST {prompt, model, duration} →
JSON with ``video_url`` (or ``output_url`` / ``url``). Mismatched contracts
are tolerated as long as one of those keys carries the asset.
"""
from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

import httpx

from .config import Config


logger = logging.getLogger(__name__)


class RenderError(RuntimeError):
    """Raised when a scene fails to render (transport, HTTP, or asset)."""


async def render_scene(
    prompt: str,
    *,
    config: Config,
    duration_s: int = 4,
    out_dir: Optional[Path] = None,
    scene_index: int = 0,
) -> Path:
    """Render one scene and save the clip to disk. Returns the local path.

    The video model + render endpoint come from ``config``. ``out_dir``
    defaults to a per-process tempdir so concurrent runs don't clobber.
    """
    if not prompt.strip():
        raise ValueError("prompt is empty")
    out_dir = Path(out_dir) if out_dir else Path(tempfile.gettempdir()) / "freescene"
    out_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "prompt": prompt.strip(),
        "model": config.video_model,
        "duration": duration_s,
    }
    url = f"{config.effective_video_url}/v1/video/generate/"
    headers = {**config.auth_headers(), "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=config.timeout_video_s) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code != 200:
            raise RenderError(
                f"render_scene[{scene_index}]: HTTP {r.status_code} from {url}: "
                f"{r.text[:300]}"
            )
        try:
            data = r.json()
        except Exception as e:
            raise RenderError(f"render_scene[{scene_index}]: non-JSON response: {e}") from e

        asset_url = (
            data.get("video_url")
            or data.get("output_url")
            or data.get("url")
            or data.get("output")
        )
        if not asset_url:
            raise RenderError(
                f"render_scene[{scene_index}]: response missing video_url/output_url; "
                f"got keys: {list(data.keys())[:10]}"
            )
        return await _download(client, asset_url, config, out_dir, scene_index)


async def _download(
    client: httpx.AsyncClient,
    asset_url: str,
    config: Config,
    out_dir: Path,
    scene_index: int,
) -> Path:
    """Fetch the rendered asset to a local mp4 file."""
    # Relative URLs (e.g. /static/outputs/abc.mp4) resolve against the video
    # API root.
    if asset_url.startswith("/"):
        asset_url = config.effective_video_url + asset_url

    parsed = urlparse(asset_url)
    suffix = os.path.splitext(parsed.path)[1] or ".mp4"
    out_path = out_dir / f"scene_{scene_index:03d}{suffix}"

    r = await client.get(asset_url, headers=config.auth_headers())
    if r.status_code != 200:
        raise RenderError(
            f"render_scene[{scene_index}]: download HTTP {r.status_code} from "
            f"{asset_url}"
        )
    out_path.write_bytes(r.content)
    if out_path.stat().st_size == 0:
        raise RenderError(f"render_scene[{scene_index}]: empty asset at {asset_url}")
    return out_path


async def render_all(
    prompts: list[str],
    *,
    config: Config,
    duration_s: int = 4,
    out_dir: Optional[Path] = None,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
) -> list[Path]:
    """Render scenes sequentially; emit progress for the CLI."""
    out_dir = Path(out_dir) if out_dir else Path(tempfile.gettempdir()) / "freescene"
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for i, prompt in enumerate(prompts):
        if on_progress:
            on_progress(i, len(prompts), prompt)
        path = await render_scene(
            prompt,
            config=config,
            duration_s=duration_s,
            out_dir=out_dir,
            scene_index=i,
        )
        paths.append(path)
    if on_progress:
        on_progress(len(prompts), len(prompts), "")
    return paths
