# free-scene

**Multi-scene AI movie maker.** Give it a story idea, get a stitched mp4.

```
$ freescene "A retired astronaut tends a rooftop garden in Tokyo, she finds a small alien plant. Tone: quiet, hopeful, Ghibli-esque."

─────────────────────────────── freescene ────────────────────────────────
Idea: A retired astronaut tends a rooftop garden in Tokyo, she finds a small alien plant. Tone: quiet, hopeful, Ghibli-esque.
Scenes: 3  Style: cinematic, warm, realistic  Duration/scene: 4s
LLM: qwen7b  Video: cogvideox  Backend: https://api.free.ai

⠼ Rendering scene 2/3…  ━━━━━━━━━━━━━━━━━━━━━━━━━━━╸━━━━━━━━━━ 4/5 0:01:14

──────────────────────────────── Done ────────────────────────────────────
Output: /tmp/freescene_abc123def456/abc123def456.mp4
Job ID: abc123def456  Elapsed: 167.4s
```

## How it works

1. **Script** — an LLM acts as film director and writes N scene prompts from your one-line idea.
2. **Render** — each prompt is rendered as a short video clip via an OpenAI-compatible video API.
3. **Concat** — `ffmpeg` stitches the clips into one mp4. Stream-copy first; falls back to libx264 re-encode if codecs/containers don't match.

Same pipeline that powers [free.ai/video/movie/](https://free.ai/video/movie/), extracted into a standalone, self-installable CLI.

## Install

```bash
pip install freeai-scene
```

You also need `ffmpeg` on `PATH`:

```bash
# macOS
brew install ffmpeg

# Debian/Ubuntu
sudo apt-get install ffmpeg

# Windows
winget install Gyan.FFmpeg
```

## Cost upfront — be honest

| What you're running                       | Tokens | Anon (2,500/day) | Registered (30,000/day) | $5 pack (200K) |
|-------------------------------------------|--------|------------------|-------------------------|----------------|
| **Single 2-second scene** (cheapest)      | 5,100  | 🚫               | ✅ 5/day                 | ~40 scenes     |
| **Default 3-scene 3-second movie**        | 22,600 | 🚫               | ✅ **1 full movie/day**  | ~9 movies      |
| **3-scene 4-second movie**                | 30,100 | 🚫               | 🚫 (100 over)           | ~6 movies      |
| **5-scene 6-second movie**                | 75,100 | 🚫               | 🚫                      | ~2 movies      |

Per-scene cost is `max(5,000, duration × 2,500)`. The CLI prints a cost
estimate + affordability hint before each run; `--dry-run` shows it
without spending.

**Free tier sweet spot:** a [free.ai](https://free.ai/signup/) signup
gets you **30,000 tokens/day** — exactly enough for one default 3-scene
4-second movie every 24 hours, forever. For more, set `FREE_API_KEY` to
your account credits, grab a $5 pack (200K tokens, ~6 movies), or run
against your own GPU (see [supported backends](#supported-backends)) for
$0.

## Quick start

No setup required — try a dry run first to see the cost:

```bash
freescene "Cyberpunk Tokyo at dawn, a lone hacker on a rooftop" --scenes 5 --style scifi --dry-run
```

Render it for real (needs an API key or your own backend — see above):

```bash
freescene "Cyberpunk Tokyo at dawn, a lone hacker on a rooftop" --scenes 5 --style scifi
```

For your full account quota:

```bash
export FREE_API_KEY=fk_live_...
freescene "Pixar squirrel learns to surf" -n 4 -s 3d -d 6
```

Bring your own backend (any OpenAI-compatible LLM + video API):

```bash
export FREE_API_URL=http://localhost:8080
export FREE_API_KEY=$YOUR_TOKEN
export LLM_MODEL=qwen3-30b
export VIDEO_MODEL=hunyuan-video
freescene "A drone flight over Mars colonies"
```

Mix and match — script-writing LLM on OpenAI, video render on a local vLLM:

```bash
export LLM_API_URL=https://api.openai.com
export LLM_MODEL=gpt-5
export VIDEO_API_URL=http://localhost:7860
export VIDEO_MODEL=cogvideox
freescene "Submarine exploring an alien reef"
```

## CLI reference

```
freescene IDEA [OPTIONS]

  -n, --scenes INTEGER             Number of scene clips (1-12, default 3)
  -s, --style TEXT                 Style preset or free-form descriptor
                                   Presets: cinematic, anime, documentary,
                                   noir, 3d, vintage, scifi, fantasy
  -d, --duration INTEGER           Seconds per scene (2-12, default 4)
  -m, --video-model TEXT           Per-scene render model
      --llm-model TEXT             Script-writing model
      --api-url TEXT               OpenAI-compatible API root
      --api-key TEXT               Bearer token
  -o, --output FILE                Output .mp4 path
      --show-script                Print scene prompts before rendering
      --quiet                      Suppress progress UI (prints output path only)
      --version                    Show version
  -h, --help                       Show help
```

## Python API

```python
from freescene import make_movie, Config

cfg = Config(
    api_url="https://api.free.ai",
    api_key="fk_live_...",
    video_model="cogvideox",
)

result = make_movie(
    idea="A retired astronaut tends a rooftop garden in Tokyo...",
    num_scenes=3,
    style="ghibli-inspired, soft",
    duration_per_scene=4,
    config=cfg,
)

print(result.output_path)   # PosixPath('/tmp/.../abc123.mp4')
print(result.scenes)        # ['wide shot of ...', 'medium shot ...', 'close-up ...']
print(result.elapsed_s)     # 167.4
```

Async variant for when you're already inside an event loop:

```python
from freescene.pipeline import make_movie_async

result = await make_movie_async(idea="...", num_scenes=3)
```

## Environment variables

| Var              | Default                   | Purpose                                           |
|------------------|---------------------------|---------------------------------------------------|
| `FREE_API_URL`   | `https://api.free.ai`     | OpenAI-compatible API root                        |
| `FREE_API_KEY`   | _(none)_                  | Bearer token                                      |
| `LLM_API_URL`    | inherits `FREE_API_URL`   | Override for `/v1/chat/completions` only          |
| `LLM_MODEL`      | `qwen7b`                  | Script-writing model id                           |
| `VIDEO_API_URL`  | inherits `FREE_API_URL`   | Override for `/v1/video/generate/` only           |
| `VIDEO_MODEL`    | `cogvideox`               | Per-scene render model                            |

## Supported backends

Anything that speaks OpenAI's chat-completions shape for scripts and a `POST /v1/video/generate/` returning `{video_url|output_url|url}` for renders. Verified backends:

- **Free.ai** (default) — `cogvideox`, `hunyuan-video`, `wan-i2v` for video; `qwen7b`, `qwen3-30b`, GPT, Claude, Gemini etc. for the script.
- **Your own vLLM + diffusers shim** — set `FREE_API_URL` to your gateway.
- **OpenAI** for scripts — set `LLM_API_URL=https://api.openai.com`, `LLM_MODEL=gpt-5`, plus a separate `VIDEO_API_URL` for render.

If your video API returns a different JSON key, file an issue with a sample response — happy to widen the parser.

## Development

```bash
git clone https://github.com/freeaigit/free-scene.git
cd free-scene
pip install -e ".[dev]"
pytest
```

Tests cover the LLM-output parser (mocked) and the ffmpeg-concat path (real ffmpeg, auto-skipped if not installed).

## License

MIT. See [LICENSE](LICENSE).

## Credits

Extracted from [Free.ai](https://free.ai)'s `/video/movie/` pipeline. Use the hosted version at [free.ai/video/movie/](https://free.ai/video/movie/) if you don't want to manage your own GPU.
