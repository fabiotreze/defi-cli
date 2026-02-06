"""
Test Suite — DeFi CLI Formula Validation
=========================================

Tests every mathematical formula in real_defi_math.py against known inputs,
verifying correctness with reverse calculations and documented expected values.

Formula Sources:
  - Uniswap V3 Whitepaper §6.1, §6.2, §2
  - Pintail (2019) — Impermanent Loss
  - Uniswap V3 Docs — Fee Distribution

Run:  python -m pytest tests/test_math.py -v
"""

import math
import pytest

from real_defi_math import (
    UniswapV3Math,
    RiskAnalyzer,
    PositionData,
    analyze_position,
    generate_position_strategies,
    _classify_current_strategy,
)


# ── Helpers ──────────────────────────────────────────────────────────────

def expected_il(r: float) -> float:
    """Reference impermanent loss: IL = 2√r/(1+r) - 1 (Pintail formula)."""
    return (2 * math.sqrt(r) / (1 + r) - 1) * 100


def expected_ce(pa: float, pb: float) -> float:
    """Reference capital efficiency: CE = 1/(1 - √(Pa/Pb)) (Whitepaper §2)."""
    return 1 / (1 - math.sqrt(pa / pb))


# ── Tick ↔ Price Roundtrip (Whitepaper §6.1) ────────────────────────────

class TestTickPrice:
    """p(i) = 1.0001^i  ↔  i = floor(log(p)/log(1.0001))"""

    @pytest.mark.parametrize("price", [100, 500, 1000, 1800, 2000, 3500, 10000])
    def test_roundtrip_standard_prices(self, price: float):
        tick = UniswapV3Math.price_to_tick(price)
        recovered = UniswapV3Math.tick_to_price(tick)
        error_pct = abs(recovered - price) / price * 100
        assert error_pct < 0.01, f"Roundtrip error {error_pct:.4f}% for price={price}"

    @pytest.mark.parametrize("price", [0.0001, 0.0005, 0.001, 0.01, 0.1])
    def test_roundtrip_small_prices(self, price: float):
        tick = UniswapV3Math.price_to_tick(price)
        recovered = UniswapV3Math.tick_to_price(tick)
        error_pct = abs(recovered - price) / price * 100
        assert error_pct < 0.01

    def test_tick_increases_with_price(self):
        """Higher price → higher tick index."""
        t1 = UniswapV3Math.price_to_tick(1000)
        t2 = UniswapV3Math.price_to_tick(2000)
        t3 = UniswapV3Math.price_to_tick(3000)
        assert t1 < t2 < t3

    def test_known_tick_value(self):
        """1.0001^0 = 1.0 — tick 0 always maps to price 1."""
        assert UniswapV3Math.tick_to_price(0) == pytest.approx(1.0, abs=1e-10)

    def test_price_to_tick_returns_int(self):
        tick = UniswapV3Math.price_to_tick(2000)
        assert isinstance(tick, int)

    def test_negative_price_raises(self):
        with pytest.raises(ValueError):
            UniswapV3Math.price_to_tick(-100)

    def test_zero_price_raises(self):
        with pytest.raises(ValueError):
            UniswapV3Math.price_to_tick(0)


# ── Impermanent Loss (Pintail 2019) ─────────────────────────────────────

class TestImpermanentLoss:
    """IL = 2√r / (1+r) - 1, where r = P_current / P_initial"""

    @pytest.mark.parametrize("ratio,expected", [
        (1.0, 0.0),         # no change → no IL
        (1.5, -2.0204),     # 50% up: 2√1.5/(1+1.5)-1 = -2.02%
        (2.0, -5.7191),     # 2× price
        (0.5, -5.7191),     # 50% down (symmetric to 2×)
        (4.0, -20.0),       # 4× price
        (0.25, -20.0),      # 75% down (symmetric to 4×)
    ])
    def test_known_il_values(self, ratio: float, expected: float):
        initial = 1000.0
        current = initial * ratio
        result = RiskAnalyzer.impermanent_loss(initial, current)
        assert result == pytest.approx(expected, abs=0.01)

    def test_il_symmetry(self):
        """IL(2×) == IL(0.5×) — impermanent loss is symmetric around 1."""
        il_up = RiskAnalyzer.impermanent_loss(1000, 2000)    # r=2
        il_down = RiskAnalyzer.impermanent_loss(1000, 500)    # r=0.5
        assert il_up == pytest.approx(il_down, abs=0.001)

    def test_il_always_negative_or_zero(self):
        """Impermanent loss is always ≤ 0."""
        for ratio in [0.1, 0.5, 1.0, 1.5, 2.0, 5.0, 10.0]:
            il = RiskAnalyzer.impermanent_loss(1000, 1000 * ratio)
            assert il <= 0.0001  # tolerance for floating point

    def test_il_increases_with_divergence(self):
        """More price divergence → more IL."""
        il_2x = abs(RiskAnalyzer.impermanent_loss(1000, 2000))
        il_3x = abs(RiskAnalyzer.impermanent_loss(1000, 3000))
        il_5x = abs(RiskAnalyzer.impermanent_loss(1000, 5000))
        assert il_2x < il_3x < il_5x

    def test_il_initial_zero_returns_zero(self):
        """Edge: initial price = 0 should not crash."""
        result = RiskAnalyzer.impermanent_loss(0, 1000)
        assert result == 0.0

    def test_il_matches_formula_exactly(self):
        """Verify against independently computed values."""
        for r in [0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0]:
            result = RiskAnalyzer.impermanent_loss(1000, 1000 * r)
            expected = expected_il(r)
            assert result == pytest.approx(expected, abs=0.01)


# ── Capital Efficiency (Whitepaper §2) ───────────────────────────────────

class TestCapitalEfficiency:
    """CE = 1 / (1 - √(Pa/Pb))"""

    @pytest.mark.parametrize("pa,pb,expected_approx", [
        (1800, 2200, 10.47),   # 1/(1-√(1800/2200))
        (1000, 3000, 2.37),    # 1/(1-√(1000/3000))
        (1500, 2500, 4.44),    # 1/(1-√(1500/2500))
        (100, 10000, 1.11),    # 1/(1-√(100/10000))
    ])
    def test_known_ce_values(self, pa, pb, expected_approx):
        result = UniswapV3Math.capital_efficiency_vs_v2(pa, pb)
        assert result == pytest.approx(expected_approx, abs=0.01)

    def test_ce_matches_formula(self):
        for pa, pb in [(1800, 2200), (1000, 3000), (500, 5000)]:
            result = UniswapV3Math.capital_efficiency_vs_v2(pa, pb)
            ref = expected_ce(pa, pb)
            assert result == pytest.approx(ref, abs=0.01)

    def test_narrower_range_higher_ce(self):
        """Narrower range → higher capital efficiency."""
        ce_wide = UniswapV3Math.capital_efficiency_vs_v2(1000, 3000)
        ce_med = UniswapV3Math.capital_efficiency_vs_v2(1500, 2500)
        ce_tight = UniswapV3Math.capital_efficiency_vs_v2(1800, 2200)
        assert ce_wide < ce_med < ce_tight

    def test_ce_always_gte_one(self):
        """V3 is always at least as efficient as V2."""
        for pa, pb in [(100, 10000), (1000, 3000), (1800, 2200)]:
            assert UniswapV3Math.capital_efficiency_vs_v2(pa, pb) >= 1.0

    def test_ce_invalid_returns_one(self):
        assert UniswapV3Math.capital_efficiency_vs_v2(2000, 2000) == 1.0  # equal
        assert UniswapV3Math.capital_efficiency_vs_v2(3000, 2000) == 1.0  # inverted
        assert UniswapV3Math.capital_efficiency_vs_v2(0, 2000) == 1.0     # zero lower
        assert UniswapV3Math.capital_efficiency_vs_v2(-1, 2000) == 1.0    # negative


# ── Liquidity (Whitepaper §6.2) ──────────────────────────────────────────

class TestLiquidity:
    """L = Δx / (1/√P - 1/√Pb)"""

    def test_positive_liquidity(self):
        L = UniswapV3Math.calculate_liquidity(1.0, 2000, 2000, 1800, 2200)
        assert L > 0

    def test_narrower_range_higher_liquidity(self):
        """Same capital, narrower range → more liquidity concentration."""
        L_wide = UniswapV3Math.calculate_liquidity(1.0, 2000, 2000, 1000, 3000)
        L_tight = UniswapV3Math.calculate_liquidity(1.0, 2000, 2000, 1800, 2200)
        assert L_tight > L_wide

    def test_more_capital_more_liquidity(self):
        """More tokens → more liquidity."""
        L_small = UniswapV3Math.calculate_liquidity(0.5, 1000, 2000, 1800, 2200)
        L_large = UniswapV3Math.calculate_liquidity(5.0, 10000, 2000, 1800, 2200)
        assert L_large > L_small

    def test_below_range_uses_token0_only(self):
        """Price below range: all token0, formula uses Δx only."""
        L = UniswapV3Math.calculate_liquidity(1.0, 0, 1500, 1800, 2200)
        assert L > 0

    def test_above_range_uses_token1_only(self):
        """Price above range: all token1, formula uses Δy only."""
        L = UniswapV3Math.calculate_liquidity(0, 3000, 2500, 1800, 2200)
        assert L > 0

    def test_zero_amounts_return_zero(self):
        L = UniswapV3Math.calculate_liquidity(0, 0, 2000, 1800, 2200)
        assert L == 0.0


# ── Fee APY Estimate ─────────────────────────────────────────────────────

class TestFeeAPY:
    """APY = (daily_fees / position_value) × 365 × 100"""

    def test_known_apy(self):
        """$1M volume, 0.30% fee, equal share of $10M pool."""
        result = UniswapV3Math.estimate_fee_apy(
            volume_24h=1_000_000,
            fee_tier=0.003,
            position_liquidity=100,
            total_pool_liquidity=100,
            position_value_usd=10_000_000,
        )
        expected_daily = 1_000_000 * 0.003 * 1.0  # $3,000/day
        expected_apy = (expected_daily * 365 / 10_000_000) * 100  # 10.95%
        assert result["apy_pct"] == pytest.approx(expected_apy, abs=0.01)
        assert result["daily_fees_usd"] == pytest.approx(expected_daily, abs=0.01)

    def test_higher_share_higher_apy(self):
        """Larger liquidity share → higher APY."""
        r1 = UniswapV3Math.estimate_fee_apy(1_000_000, 0.003, 10, 1000, 10000)
        r2 = UniswapV3Math.estimate_fee_apy(1_000_000, 0.003, 100, 1000, 10000)
        assert r2["apy_pct"] > r1["apy_pct"]

    def test_zero_pool_liquidity(self):
        result = UniswapV3Math.estimate_fee_apy(1_000_000, 0.003, 100, 0, 10000)
        assert result["apy_pct"] == 0

    def test_zero_position_value(self):
        result = UniswapV3Math.estimate_fee_apy(1_000_000, 0.003, 100, 1000, 0)
        assert result["apy_pct"] == 0


# ── Range Proximity ──────────────────────────────────────────────────────

class TestRangeProximity:

    def test_in_range(self):
        r = RiskAnalyzer.range_proximity(2000, 1800, 2200)
        assert r["in_range"] is True
        assert r["downside_buffer_pct"] > 0
        assert r["upside_buffer_pct"] > 0

    def test_below_range(self):
        r = RiskAnalyzer.range_proximity(1500, 1800, 2200)
        assert r["in_range"] is False

    def test_above_range(self):
        r = RiskAnalyzer.range_proximity(2500, 1800, 2200)
        assert r["in_range"] is False

    def test_at_boundary_lower(self):
        r = RiskAnalyzer.range_proximity(1800, 1800, 2200)
        assert r["in_range"] is True

    def test_at_boundary_upper(self):
        r = RiskAnalyzer.range_proximity(2200, 1800, 2200)
        assert r["in_range"] is True

    def test_invalid_range(self):
        r = RiskAnalyzer.range_proximity(2000, 2200, 1800)  # inverted
        assert r["in_range"] is False

    def test_zero_price(self):
        r = RiskAnalyzer.range_proximity(0, 1800, 2200)
        assert r["in_range"] is False


# ── Strategy Classification ──────────────────────────────────────────────

class TestStrategyClassification:

    def test_conservative(self):
        assert _classify_current_strategy(1000, 3000, 2000) == "conservative"

    def test_moderate(self):
        assert _classify_current_strategy(1500, 2500, 2000) == "moderate"

    def test_aggressive(self):
        assert _classify_current_strategy(1850, 2150, 2000) == "aggressive"

    def test_invalid(self):
        assert _classify_current_strategy(0, 0, 0) == "unknown"


# ── Strategy Generation ─────────────────────────────────────────────────

class TestStrategies:

    def test_returns_three_strategies(self):
        s = generate_position_strategies(2000)
        assert "conservative" in s
        assert "moderate" in s
        assert "aggressive" in s

    def test_conservative_wider_than_aggressive(self):
        s = generate_position_strategies(2000)
        c_width = s["conservative"]["upper_price"] - s["conservative"]["lower_price"]
        a_width = s["aggressive"]["upper_price"] - s["aggressive"]["lower_price"]
        assert c_width > a_width


# ── Full Analysis Pipeline ───────────────────────────────────────────────

class TestAnalyzePosition:
    """Integration: full pipeline from PositionData → analyze_position()."""

    @pytest.fixture
    def sample_position(self):
        return PositionData(
            weth_amount=1.0,
            usdt_amount=2000.0,
            token0_symbol="WETH",
            token1_symbol="USDC",
            current_price=2000.0,
            range_min=1800.0,
            range_max=2200.0,
            fee_tier=0.0005,
            total_value_usd=4000.0,
            fees_earned_usd=10.0,
            volume_24h=100_000_000.0,
            total_value_locked_usd=50_000_000.0,
            pool_address="0x" + "a" * 40,
            network="ethereum",
            protocol="uniswap_v3",
        )

    def test_returns_all_core_fields(self, sample_position):
        result = analyze_position(sample_position)
        core_fields = [
            "current_price", "range_min", "range_max",
            "liquidity", "capital_efficiency_vs_v2",
            "in_range", "downside_buffer_pct", "upside_buffer_pct",
            "total_value_usd", "fee_tier", "fee_tier_label",
            "strategies", "generated_at",
        ]
        for field in core_fields:
            assert field in result, f"Missing field: {field}"

    def test_in_range_when_price_within_bounds(self, sample_position):
        result = analyze_position(sample_position)
        assert result["in_range"] is True

    def test_liquidity_positive(self, sample_position):
        result = analyze_position(sample_position)
        assert result["liquidity"] > 0

    def test_capital_efficiency_gt_one(self, sample_position):
        result = analyze_position(sample_position)
        assert result["capital_efficiency_vs_v2"] > 1.0

    def test_fee_tier_label_correct(self, sample_position):
        result = analyze_position(sample_position)
        assert result["fee_tier_label"] == "0.05%"

    def test_out_of_range(self):
        pos = PositionData(
            current_price=1500.0,  # below range
            range_min=1800.0,
            range_max=2200.0,
            weth_amount=1.0,
            total_value_usd=3000.0,
        )
        result = analyze_position(pos)
        assert result["in_range"] is False
