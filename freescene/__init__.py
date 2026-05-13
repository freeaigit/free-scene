"""freescene — multi-scene AI movie maker.

Public API:
    from freescene import make_movie, Config

    cfg = Config()  # reads FREE_API_KEY / FREE_API_URL from env
    result = make_movie(
        idea="A retired astronaut tends a rooftop garden in Tokyo...",
        num_scenes=3,
        style="cinematic, warm, realistic",
        video_model="cogvideox",
        config=cfg,
    )
    print(result.output_path)

CLI:
    freescene "A retired astronaut..." --scenes 3 --style anime

The pipeline is identical to free.ai/video/movie/:
  LLM writes N scene prompts → each scene rendered as a short video clip
  → ffmpeg-concat into one mp4. Backends are pluggable via OpenAI-compatible
  endpoints, so you can run against Free.ai's hosted GPUs, your own vLLM,
  Ollama, or any OpenAI-shaped API.
"""

from .config import Config
from .pipeline import make_movie, MovieResult

__version__ = "0.1.0"
__all__ = ["make_movie", "Config", "MovieResult", "__version__"]
