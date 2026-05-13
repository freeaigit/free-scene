"""End-to-end orchestrator: idea → script → scenes → render → concat."""
from __future__ import annotations

import asyncio
import logging
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from .concat import concat_clips, ensure_ffmpeg
from .config import Config
from .render import render_all
from .script import write_script


logger = logging.getLogger(__name__)


@dataclass
class MovieResult:
    """Result of a successful ``make_movie`` run."""

    output_path: Path
    scenes: list[str]
    scene_clip_paths: list[Path] = field(default_factory=list)
    elapsed_s: float = 0.0
    job_id: str = ""

    def __str__(self) -> str:  # nicer CLI/repr output
        return (
            f"MovieResult(output={self.output_path}, "
            f"scenes={len(self.scenes)}, elapsed={self.elapsed_s:.1f}s)"
        )


# Progress callback signature: (phase, current, total, detail)
ProgressFn = Callable[[str, int, int, str], None]


async def make_movie_async(
    idea: str,
    *,
    num_scenes: int = 3,
    style: str = "cinematic, warm, realistic",
    duration_per_scene: int = 3,
    output_path: Optional[Path] = None,
    config: Optional[Config] = None,
    on_progress: Optional[ProgressFn] = None,
) -> MovieResult:
    """Async orchestrator. Use ``make_movie()`` for sync callers."""
    cfg = config or Config.from_env()
    ensure_ffmpeg()  # fail fast — clear error before we hit the LLM

    if not idea or not idea.strip():
        raise ValueError("idea is required")
    if num_scenes < 1:
        raise ValueError("num_scenes must be >= 1")

    job_id = uuid.uuid4().hex[:12]
    work_dir = Path(tempfile.mkdtemp(prefix=f"freescene_{job_id}_"))
    started = time.time()

    def _emit(phase: str, current: int, total: int, detail: str = "") -> None:
        if on_progress:
            on_progress(phase, current, total, detail)

    _emit("scriptwriting", 0, num_scenes, idea)
    scenes = await write_script(idea, num_scenes, style, cfg)
    _emit("scenes_ready", 0, num_scenes, "")

    def _render_progress(i: int, total: int, current_prompt: str) -> None:
        _emit("rendering", i, total, current_prompt)

    clip_paths = await render_all(
        scenes,
        config=cfg,
        duration_s=duration_per_scene,
        out_dir=work_dir,
        on_progress=_render_progress,
    )

    _emit("concatenating", num_scenes, num_scenes, "")
    out = Path(output_path) if output_path else work_dir / f"{job_id}.mp4"
    final = concat_clips(clip_paths, out)

    elapsed = time.time() - started
    _emit("done", num_scenes, num_scenes, str(final))

    return MovieResult(
        output_path=final,
        scenes=scenes,
        scene_clip_paths=clip_paths,
        elapsed_s=elapsed,
        job_id=job_id,
    )


def make_movie(
    idea: str,
    *,
    num_scenes: int = 3,
    style: str = "cinematic, warm, realistic",
    duration_per_scene: int = 3,
    output_path: Optional[Path] = None,
    config: Optional[Config] = None,
    on_progress: Optional[ProgressFn] = None,
) -> MovieResult:
    """Synchronous wrapper around ``make_movie_async``."""
    return asyncio.run(
        make_movie_async(
            idea,
            num_scenes=num_scenes,
            style=style,
            duration_per_scene=duration_per_scene,
            output_path=output_path,
            config=config,
            on_progress=on_progress,
        )
    )
