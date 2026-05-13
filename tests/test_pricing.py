"""Lock in the cost estimator so it never drifts from the backend."""
from freescene.pricing import estimate, ANON_DAILY_POOL, REGISTERED_DAILY_POOL


def test_minimum_scene_is_5000_tokens():
    """Per-scene cost has a 5K floor regardless of duration."""
    est = estimate(num_scenes=1, duration_per_scene=2)
    assert est.per_scene_tokens == 5000
    assert est.total_tokens == 5100  # 100 script + 1 × 5000


def test_duration_overrides_floor():
    """At duration >= 3, the per-second rate beats the floor."""
    est = estimate(num_scenes=1, duration_per_scene=4)
    assert est.per_scene_tokens == 10000  # 4 × 2500
    assert est.total_tokens == 10100


def test_default_3_scene_3s_movie_cost():
    """CLI defaults — 3 scenes × 3s = 22,600 tokens, ~3¢. Fits in 30K pool."""
    est = estimate(num_scenes=3, duration_per_scene=3)
    assert est.per_scene_tokens == 7500
    assert est.total_tokens == 22600
    assert 0.029 < est.usd_cost < 0.031


def test_anon_pool_cannot_fit_a_single_scene():
    """Honest answer to 'is the anon pool enough?' — no."""
    cheapest = estimate(num_scenes=1, duration_per_scene=2)
    assert cheapest.total_tokens > ANON_DAILY_POOL
    assert not cheapest.affordable_with_anon


def test_registered_pool_fits_default_movie():
    """30K pool covers the default 3-scene 3-second movie with 7K to spare."""
    default = estimate(num_scenes=3, duration_per_scene=3)
    assert default.total_tokens <= REGISTERED_DAILY_POOL
    assert default.affordable_with_registered


def test_registered_pool_cannot_fit_long_movie():
    """5×6s movie costs 75K — too big for the 30K daily pool."""
    long_movie = estimate(num_scenes=5, duration_per_scene=6)
    assert long_movie.total_tokens > REGISTERED_DAILY_POOL
    assert not long_movie.affordable_with_registered


def test_hint_messaging_routes_correctly():
    """The CLI banner picks the right fork by tier."""
    # Default 3-scene 3-second movie fits in the registered pool but not anon.
    default = estimate(num_scenes=3, duration_per_scene=3)
    assert "registered-account daily pool" in default.hint
    assert "30,000" in default.hint
    # A 5-scene 6-second movie exceeds the daily pool entirely.
    long_movie = estimate(num_scenes=5, duration_per_scene=6)
    assert "exceeds the free daily pool" in long_movie.hint
    assert "buy" in long_movie.hint
