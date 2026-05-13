"""Smoke test for ffmpeg-concat. Requires ffmpeg on PATH at test time —
the test is skipped automatically if ffmpeg is missing."""
import shutil
import subprocess
from pathlib import Path

import pytest

from freescene.concat import concat_clips, ensure_ffmpeg, FFmpegMissingError


needs_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None,
    reason="ffmpeg not installed",
)


def test_ensure_ffmpeg_raises_when_missing(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: None)
    with pytest.raises(FFmpegMissingError):
        ensure_ffmpeg()


@needs_ffmpeg
def test_concat_two_synthetic_clips(tmp_path: Path):
    """Generate two tiny silent mp4s with ffmpeg, concat them, expect a
    valid mp4 roughly twice the input length."""
    clip_a = tmp_path / "a.mp4"
    clip_b = tmp_path / "b.mp4"
    # 1-second 64×64 black video, no audio.
    for clip in (clip_a, clip_b):
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi",
                "-i", "color=c=black:s=64x64:d=1:r=24",
                "-pix_fmt", "yuv420p",
                str(clip),
            ],
            check=True, capture_output=True,
        )

    out = tmp_path / "joined.mp4"
    result = concat_clips([clip_a, clip_b], out)
    assert result == out
    assert out.exists() and out.stat().st_size > 0

    # Probe duration — should be ~2.0s (allow a wide tolerance for keyframe
    # alignment + re-encode rounding).
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(out)],
        check=True, capture_output=True, text=True,
    )
    duration = float(probe.stdout.strip())
    assert 1.5 <= duration <= 3.0, f"expected ~2s, got {duration:.2f}s"
