"""Configuration — env vars + CLI overrides."""
from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_API_URL = "https://api.free.ai"
DEFAULT_LLM_MODEL = "qwen7b"
DEFAULT_VIDEO_MODEL = "cogvideox"


@dataclass
class Config:
    """Backend configuration.

    Defaults point at Free.ai's hosted GPUs. To use your own infra:
      - Set ``FREE_API_URL`` (or pass ``api_url``) to your OpenAI-compatible
        endpoint root. The pipeline POSTs to ``{api_url}/v1/chat/completions``
        and ``{api_url}/v1/video/generate``.
      - Set ``FREE_API_KEY`` for Bearer auth (skip if your endpoint is open).
      - Set ``LLM_API_URL`` / ``VIDEO_API_URL`` if your script-writing LLM
        and video-render service live at different hosts (e.g. OpenAI for the
        script, a local vLLM or Replicate for the video).

    Environment variables (all optional):
      FREE_API_URL     → api_url (default: https://api.free.ai)
      FREE_API_KEY     → api_key (default: anonymous; subject to daily pool)
      LLM_API_URL      → overrides api_url for /v1/chat/completions only
      LLM_MODEL        → script-writing model id (default: qwen7b)
      VIDEO_API_URL    → overrides api_url for /v1/video/generate only
      VIDEO_MODEL      → per-scene render model (default: cogvideox)
    """

    api_url: str = DEFAULT_API_URL
    api_key: str | None = None
    llm_api_url: str | None = None
    llm_model: str = DEFAULT_LLM_MODEL
    video_api_url: str | None = None
    video_model: str = DEFAULT_VIDEO_MODEL
    timeout_llm_s: float = 60.0
    timeout_video_s: float = 600.0  # cogvideox can take ~60-90s/clip; hunyuan longer

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            api_url=os.environ.get("FREE_API_URL", DEFAULT_API_URL),
            api_key=os.environ.get("FREE_API_KEY"),
            llm_api_url=os.environ.get("LLM_API_URL"),
            llm_model=os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL),
            video_api_url=os.environ.get("VIDEO_API_URL"),
            video_model=os.environ.get("VIDEO_MODEL", DEFAULT_VIDEO_MODEL),
        )

    @property
    def effective_llm_url(self) -> str:
        return (self.llm_api_url or self.api_url).rstrip("/")

    @property
    def effective_video_url(self) -> str:
        return (self.video_api_url or self.api_url).rstrip("/")

    def auth_headers(self) -> dict[str, str]:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}
