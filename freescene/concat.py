"""ffmpeg-concat — stitch scene clips into one mp4.

Two-pass strategy mirroring Free.ai's production path:
  1. ``-c copy`` stream-copy via the concat demuxer (fast, lossless) — works
     when every clip shares codec + container.
  2. On failure (mismatched codecs / container quirks), fall back to a full
     re-encode at libx264 veryfast + AAC.

Requires ``ffmpeg`` on $PATH. We check this once on import-time so the CLI
can surface a clean error message instead of dying mid-render.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Iterable


logger = logging.getLogger(__name__)


class FFmpegMissingError(RuntimeError):
    """Raised when ``ffmpeg`` isn't on $PATH."""


class ConcatError(RuntimeError):
    """Raised when both stream-copy and re-encode passes fail."""


def ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise FFmpegMissingError(
            "ffmpeg not found on PATH. Install via your package manager:\n"
            "  macOS:  brew install ffmpeg\n"
            "  Debian: sudo apt-get install ffmpeg\n"
            "  Win:    https://www.gyan.dev/ffmpeg/builds/"
        )


def concat_clips(
    clip_paths: Iterable[Path],
    output_path: Path,
    *,
    concat_timeout_s: int = 120,
    reencode_timeout_s: int = 600,
) -> Path:
    """Concatenate ``clip_paths`` into a single mp4 at ``output_path``.

    Returns ``output_path`` on success. Raises ``ConcatError`` on failure.
    """
    ensure_ffmpeg()
    clips = [Path(p).resolve() for p in clip_paths]
    if not clips:
        raise ValueError("concat_clips: no clips provided")
    for p in clips:
        if not p.is_file():
            raise FileNotFoundError(f"clip missing: {p}")

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    listfile = output_path.with_suffix(".list.txt")

    # ffmpeg concat demuxer wants single-quoted paths, one per line.
    listfile.write_text("\n".join(f"file '{p}'" for p in clips) + "\n")

    try:
        # Pass 1 — stream copy (no re-encode).
        copy_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(listfile), "-c", "copy", str(output_path),
        ]
        copy_proc = subprocess.run(
            copy_cmd, capture_output=True, text=True, timeout=concat_timeout_s,
        )
        if copy_proc.returncode == 0 and output_path.stat().st_size > 0:
            return output_path

        logger.info(
            "freescene.concat: stream-copy failed (rc=%s), retrying with re-encode",
            copy_proc.returncode,
        )

        # Pass 2 — full re-encode for mismatched codecs / containers.
        reencode_cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(listfile), "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "23", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            str(output_path),
        ]
        reencode_proc = subprocess.run(
            reencode_cmd, capture_output=True, text=True, timeout=reencode_timeout_s,
        )
        if reencode_proc.returncode == 0 and output_path.stat().st_size > 0:
            return output_path
        raise ConcatError(
            f"ffmpeg concat failed (copy rc={copy_proc.returncode}, "
            f"re-encode rc={reencode_proc.returncode}). "
            f"Last stderr: {reencode_proc.stderr[-400:]}"
        )
    finally:
        try:
            listfile.unlink()
        except OSError:
            pass
