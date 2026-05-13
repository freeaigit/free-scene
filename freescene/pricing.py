"""Token-cost estimator + paywall-aware UX helpers.

Mirrors Free.ai's production cost formulas (gpu_api/main.py:_video_generate_inner)
so users see the same number the backend will charge — no surprise 402s.

Cost model (self-hosted video on api.free.ai):
  per_scene  = max(5000, duration_per_scene * 2500)
  total      = num_scenes * per_scene + ~100 (script-writing LLM)

  $1 = 750,000 tokens. So 30,000 tokens ≈ 4¢ of compute cost.

Daily free pools (api.free.ai defaults):
  anonymous (no API key)               → 2,500/day
  registered + email confirmed         → 30,000/day  (covers 1 full default movie)
"""
from __future__ import annotations

from dataclasses import dataclass


TOKENS_PER_DOLLAR = 750_000
ANON_DAILY_POOL = 2_500
REGISTERED_DAILY_POOL = 30_000   # bumped from 5K on 2026-05-13 to cover one full default movie


@dataclass
class CostEstimate:
    per_scene_tokens: int
    script_tokens: int
    total_tokens: int
    usd_cost: float       # at $1 = 750K tokens
    affordable_with_anon: bool
    affordable_with_registered: bool

    @property
    def hint(self) -> str:
        """One-line affordability summary for the CLI banner."""
        if self.affordable_with_anon:
            return "fits in the anonymous daily pool (2,500 tokens)"
        if self.affordable_with_registered:
            return (
                "fits in the registered-account daily pool (30,000 tokens) — "
                "sign up free at https://free.ai/signup/"
            )
        return (
            "exceeds the free daily pool — set FREE_API_KEY for your account "
            "credits, or sign up at https://free.ai/signup/ + buy $5 pack (200K tokens, ~40 scenes)"
        )


def estimate(num_scenes: int, duration_per_scene: int) -> CostEstimate:
    """Estimate token + USD cost for a freescene run.

    Matches gpu_api/main.py:_video_generate_inner exactly so the user sees
    the same number the backend will charge.
    """
    per_scene = max(5000, duration_per_scene * 2500)
    # Script-writing LLM cost: chat completion of ~600 tokens prompt+output,
    # rounded to ~100 tokens after the platform's flat-rate min.
    script = 100
    total = script + num_scenes * per_scene
    return CostEstimate(
        per_scene_tokens=per_scene,
        script_tokens=script,
        total_tokens=total,
        usd_cost=total / TOKENS_PER_DOLLAR,
        affordable_with_anon=(total <= ANON_DAILY_POOL),
        affordable_with_registered=(total <= REGISTERED_DAILY_POOL),
    )
