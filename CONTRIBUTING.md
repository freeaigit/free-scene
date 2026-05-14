# Contributing to free-scene

Thanks for taking the time to contribute. Two small asks before opening a PR:

## Setup

```bash
git clone https://github.com/freeaigit/free-scene.git
cd free-scene
pip install -e ".[dev]"
pytest
```

ffmpeg must be on `PATH`. The test suite auto-skips ffmpeg-only tests
when it's missing.

## Coding style

- Match the surrounding code — formatting follows what's already there.
- New public functions get a docstring; private helpers (leading `_`)
  generally don't unless behavior is non-obvious.
- Type hints encouraged (`from __future__ import annotations` already
  imported in most modules).

## Commits

Single-purpose commits with a one-line subject under 72 chars, an empty
line, then a body wrapped at 72 cols.

Public commit history for this repo is authored by **freeaigit
&lt;hello@free.ai&gt;**. PRs from external contributors keep their own
author identity — the freeaigit convention applies to commits authored
directly by Free.ai team members.

## Reporting bugs

Open an issue with a minimal reproduction: the CLI flags, the backend
URL/model, and the error or unexpected output. Backend-specific issues
(your own OpenAI-compatible API doesn't return `video_url`) are also
welcome — see [README.md § Supported backends](README.md#supported-backends)
for the response-shape contract.

## Releasing

Maintainers only:
1. Bump `version` in `pyproject.toml` and `freescene/__init__.py`.
2. `python -m build` + `twine upload dist/*` (uses `pypi/free/token`).
3. `git tag -a vX.Y.Z -m "..."` and push.
4. Create a GitHub release pointing at the tag.
