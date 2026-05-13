"""Unit tests for the script-parsing fallback paths.

The LLM call itself is mocked — we only want to lock in the prompt-cleanup
behaviour: numbered/bulleted list stripping, <think> tag removal, and the
"too few scenes → pad with idea" fallback.
"""
import re

from freescene.script import _parse_scenes, _fallback_pad


def test_parse_scenes_strips_list_prefixes():
    raw = """1. A wide shot of the city skyline at dawn, soft gold light.
2) Medium shot, an astronaut waters a small alien plant.
- Close-up: the plant's leaves unfurl.
"""
    out = _parse_scenes(raw, n=3, idea="ignored", style="cinematic")
    assert len(out) == 3
    assert all(not re.match(r"^\s*[-*\d]", s) for s in out)
    assert "city skyline" in out[0]
    assert "astronaut waters" in out[1]
    assert "leaves unfurl" in out[2]


def test_parse_scenes_strips_think_block():
    raw = """<think>The user wants 2 scenes. Let me plan...</think>
Wide shot, neon-lit alley at midnight, rain reflections.
Tracking shot following a lone runner past steaming vents."""
    out = _parse_scenes(raw, n=2, idea="ignored", style="noir")
    assert len(out) == 2
    assert "<think>" not in out[0]
    assert "neon-lit" in out[0]
    assert "lone runner" in out[1]


def test_parse_scenes_pads_when_llm_short():
    """LLM returned only 1 usable line; we requested 3 → pad with idea."""
    raw = "Single scene from a confused LLM."
    out = _parse_scenes(raw, n=3, idea="A dragon makes tea.", style="fantasy")
    assert len(out) == 3
    assert out[0] == "Single scene from a confused LLM."
    assert "A dragon makes tea." in out[1]
    assert "fantasy" in out[1]


def test_fallback_pad_with_seed():
    out = _fallback_pad("idea", n=4, style="anime", seed=["seed1", "seed2"])
    assert len(out) == 4
    assert out[0] == "seed1"
    assert out[1] == "seed2"
    assert "idea" in out[2]
    assert "anime" in out[2]
