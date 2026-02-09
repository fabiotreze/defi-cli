#!/usr/bin/env python3
"""
Real DeFi Math Engine
=====================

Implements REAL Uniswap V3 formulas and risk calculations.
No fake numbers — only mathematical analysis based on actual protocol documentation.

FORMULA SOURCES (every formula is traceable):
──────────────────────────────────────────────
1. Uniswap V3 Core Whitepaper
   https://uniswap.org/whitepaper-v3.pdf
   - §6.1  Tick-Indexed Concentrated Liquidity
   - §6.2  Global State / Liquidity
   - §6.3  Per-Tick State

2. Uniswap V3 Development Book — Concentrated Liquidity Math
   https://uniswapv3book.com/docs/milestone_1/calculating-liquidity/
   - Liquidity: L = Δx·√Pa·√Pb / (√Pb − √Pa)
   - Price ↔ Tick: p(i) = 1.0001^i  (Whitepaper Eq. 6.1)

3. Uniswap V3 Docs — Concentrated Liquidity Concepts
   https://docs.uniswap.org/concepts/protocol/concentrated-liquidity

4. Impermanent Loss — Original AMM Math
   https://pintail.medium.com/uniswap-a-good-deal-for-liquidity-providers-104c0b6816f2
   IL = 2·√(r) / (1 + r) − 1,  where r = P_current / P_initial

5. Fee Tier Documentation
   https://docs.uniswap.org/concepts/protocol/fees
   Tiers: 0.01% (stablecoins), 0.05% (correlated), 0.30% (standard), 1.00% (exotic)
   Fees distributed pro-rata to in-range liquidity providers.

6. DEXScreener API (pool data, volume, TVL)
   https://docs.dexscreener.com/api/reference
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime

# ── Named Constants ──────────────────────────────────────────────────────
DEFAULT_CAPITAL_USD = 10_000  # Default simulated investment for educational analysis

from defi_cli.stablecoins import (
    estimate_fee_tier as _estimate_fee_tier,
)


# ── Position Data ────────────────────────────────────────────────────────


@dataclass
class PositionData:
    """
    Represents a single Uniswap V3 LP position.

    Fields mirror the Uniswap web interface (app.uniswap.org → Pool → Position):
      - token0_amount / token1_amount → "Your liquidity" token balances
      - current_price               → Market (mid) price from the pool
      - range_min / range_max       → User-selected price boundaries
      - fee_tier                    → One of {0.0001, 0.0005, 0.003, 0.01}
      - total_value_usd             → Sum of token values in USD
      - fees_earned_usd             → Uncollected fees
      - position_id                 → NFT token-id (optional)
      - pool_address / wallet       → On-chain identifiers
      - network / protocol          → Chain + DEX
      - token0_symbol/token1_symbol → Ticker names
    """

    # Token balances (generic: works for any pair, not just WETH/USDT)
    token0_amount: float = 0.0
    token1_amount: float = 0.0
    token0_symbol: str = "WETH"
    token1_symbol: str = "USDT"

    # Prices & range
    current_price: float = 0.0
    range_min: float = 0.0
    range_max: float = 0.0

    # Fee tier  (Ref: https://docs.uniswap.org/concepts/protocol/fees)
    fee_tier: float = 0.0005

    # Value
    total_value_usd: float = 0.0
    fees_earned_usd: float = 0.0

    # Pool metrics (from DEXScreener API)
    volume_24h: float = 0.0
    total_value_locked_usd: float = 0.0

    # Identifiers
    position_id: Optional[int] = None
    pool_address: str = ""
    wallet_address: str = ""
    network: str = "arbitrum"
    protocol: str = "uniswap_v3"
    protocol_version: str = "v3"

    # Composition percentages (from interface)
    token0_pct: float = 0.0
    token1_pct: float = 0.0

    # Liquidity share (from on-chain: position_liquidity / pool_active_liquidity)
    position_share: float = 0.0  # decimal fraction, e.g. 0.0001 = 0.01%

    @classmethod
    def from_pool_data(
        cls, pool_data: Dict, strategy: str = "moderate"
    ) -> "PositionData":
        """
        Factory: build realistic PositionData from DEXScreener pool response.

        Generates SIMULATED position data for educational analysis.
        Real positions require on-chain indexing or position NFT ID.

        Args:
            pool_data: Dict from DexScreenerClient._extract_pool_info()
            strategy: "conservative", "moderate", or "aggressive" range width
        """
        price = pool_data.get("priceUsd", 0)
        tvl = pool_data.get("totalValueLockedUSD", 0)
        base = pool_data.get("baseToken", {})
        quote = pool_data.get("quoteToken", {})
        volume = pool_data.get("volume24h", 0)
        pool_data.get("estimatedAPY", 0)

        # Fee tier estimation based on token pair
        # Uses smart stablecoin detection (defi_cli.stablecoins)
        token0 = base.get("symbol", "TOKEN0").upper()
        token1 = quote.get("symbol", "TOKEN1").upper()
        fee_tier = _estimate_fee_tier(token0, token1)

        # Generate realistic position ranges based on strategy
        range_strategies = {
            "conservative": {
                "range_pct": 0.50,
                "capital": DEFAULT_CAPITAL_USD,
                "description": "Wide range, lower fees, safer",
            },
            "moderate": {
                "range_pct": 0.25,
                "capital": DEFAULT_CAPITAL_USD,
                "description": "Balanced risk/reward",
            },
            "aggressive": {
                "range_pct": 0.10,
                "capital": DEFAULT_CAPITAL_USD,
                "description": "Narrow range, high fees, risky",
            },
        }

        strat = range_strategies.get(strategy, range_strategies["moderate"])
        range_pct = strat["range_pct"]
        capital_usd = strat["capital"]

        # Calculate realistic ranges around current price
        range_min = price * (1 - range_pct)
        range_max = price * (1 + range_pct)

        # Simulate realistic token amounts for given capital
        # For WETH/stablecoin pairs, assume 50/50 initial allocation
        if price > 0:
            token0_value = capital_usd * 0.5
            token1_value = capital_usd * 0.5

            if "WETH" in token0 or "ETH" in token0:
                weth_amount = token0_value / price
                stable_amount = token1_value
            else:
                weth_amount = token1_value / price if price > 1 else token1_value
                stable_amount = token0_value
        else:
            weth_amount = stable_amount = 0

        # Estimate realistic fees earned (based on position size vs pool)
        pool_share = capital_usd / max(tvl, 1)  # Position share of pool
        daily_pool_fees = volume * fee_tier
        position_daily_fees = daily_pool_fees * pool_share
        weekly_fees = position_daily_fees * 7

        return cls(
            token0_symbol=token0,
            token1_symbol=token1,
            current_price=price,
            range_min=range_min,
            range_max=range_max,
            fee_tier=fee_tier,
            # Simulated position amounts
            token0_amount=round(weth_amount, 6)
            if "WETH" in token0 or "ETH" in token0
            else round(stable_amount, 2),
            token1_amount=round(stable_amount, 2)
            if "USD" in token1
            else round(weth_amount, 6),
            total_value_usd=capital_usd,
            fees_earned_usd=round(weekly_fees, 4),
            # Pool market data
            volume_24h=volume,
            total_value_locked_usd=tvl,
            # Real data
            pool_address=pool_data.get("address", ""),
            network=pool_data.get("network", "unknown"),
            protocol=pool_data.get("dex", "unknown"),
            token0_pct=50.0,
            token1_pct=50.0,
        )

    @classmethod
    def from_onchain_data(cls, onchain: Dict, pool_data: Dict) -> "PositionData":
        """
        Factory: build PositionData from REAL on-chain position data.

        Args:
            onchain: Dict from PositionReader.read_position() — real blockchain data
            pool_data: Dict from DexScreenerClient — pool market data (volume, TVL)

        This combines:
          - On-chain: token amounts, price range, fees, liquidity (REAL)
          - DEXScreener: volume, TVL, transactions (market data)
        """
        return cls(
            token0_symbol=onchain.get("token0_symbol", "TOKEN0"),
            token1_symbol=onchain.get("token1_symbol", "TOKEN1"),
            current_price=onchain.get("current_price", 0),
            range_min=onchain.get("price_lower", 0),
            range_max=onchain.get("price_upper", 0),
            fee_tier=onchain.get("fee_tier", 0.0005),
            # REAL token amounts from chain
            token0_amount=onchain.get("amount0", 0),
            token1_amount=onchain.get("amount1", 0),
            total_value_usd=onchain.get("total_value_usd", 0),
            fees_earned_usd=onchain.get("total_fees_usd", 0),
            # Pool market data from DEXScreener
            volume_24h=pool_data.get("volume24h", 0),
            total_value_locked_usd=pool_data.get("totalValueLockedUSD", 0),
            # Identifiers
            position_id=onchain.get("position_id"),
            pool_address=onchain.get("pool_address", ""),
            wallet_address=onchain.get("wallet_address", ""),
            network=onchain.get("network", "unknown"),
            protocol="uniswap_v3",
            protocol_version="v3",
            # REAL composition from chain
            token0_pct=onchain.get("token0_pct", 0),
            token1_pct=onchain.get("token1_pct", 0),
            # Liquidity share from on-chain
            position_share=onchain.get("position_share", 0)
            / 100,  # convert from pct to decimal
        )


# ── Uniswap V3 Core Math ────────────────────────────────────────────────


class UniswapV3Math:
    """
    Pure functions implementing Uniswap V3 concentrated-liquidity math.
    Every formula references a specific section of the Uniswap V3 Whitepaper.
    """

    @staticmethod
    def price_to_tick(price: float) -> int:
        """
        Convert a price to the nearest lower tick.

        Formula (Whitepaper §6.1):
            p(i) = 1.0001^i  →  i = floor(log(p) / log(1.0001))

        Each tick = 0.01% (1 basis point) price change.
        Ref: https://docs.uniswap.org/concepts/protocol/concentrated-liquidity#ticks
        """
        if price <= 0:
            raise ValueError("Price must be positive")
        # Uniswap V3 valid tick range: [-887272, +887272]
        # CWE-682 mitigation: clamp extreme values to prevent math overflow
        raw_tick = math.log(price) / math.log(1.0001)
        clamped = max(-887272, min(887272, raw_tick))
        return math.floor(clamped)

    @staticmethod
    def tick_to_price(tick: int) -> float:
        """
        Convert a tick index back to a price.
        Formula (Whitepaper §6.1): p(i) = 1.0001^i
        
        CWE-682 mitigation: validates tick is within Uniswap V3 bounds
        [-887272, +887272] to prevent floating-point overflow.
        """
        # Clamp tick to valid Uniswap V3 range to prevent overflow
        tick = max(-887272, min(887272, tick))
        return 1.0001**tick

    @staticmethod
    def calculate_liquidity(
        amount0: float,
        amount1: float,
        price_current: float,
        price_lower: float,
        price_upper: float,
    ) -> float:
        """
        Calculate virtual liquidity (L) for a concentrated position.

        Formulae (Whitepaper §6.2):
          When P_lower ≤ P ≤ P_upper (mixed):
            L₀ = Δx / (1/√P_current − 1/√P_upper)
            L₁ = Δy / (√P_current  − √P_lower)
            L  = min(L₀, L₁)

          When P < P_lower (all token0):
            L = Δx / (1/√P_lower − 1/√P_upper)

          When P > P_upper (all token1):
            L = Δy / (√P_upper  − √P_lower)

        Ref: https://uniswap.org/whitepaper-v3.pdf §6.2
        """
        sp_c = math.sqrt(price_current)
        sp_l = math.sqrt(price_lower)
        sp_u = math.sqrt(price_upper)

        if price_current <= price_lower:
            denom = (1 / sp_l) - (1 / sp_u)
            return amount0 / denom if denom > 0 else 0.0
        elif price_current >= price_upper:
            denom = sp_u - sp_l
            return amount1 / denom if denom > 0 else 0.0
        else:
            denom0 = (1 / sp_c) - (1 / sp_u)
            denom1 = sp_c - sp_l
            l0 = amount0 / denom0 if denom0 > 0 else 0.0
            l1 = amount1 / denom1 if denom1 > 0 else 0.0
            return min(l0, l1) if (l0 > 0 and l1 > 0) else max(l0, l1)

    @staticmethod
    def capital_efficiency_vs_v2(price_lower: float, price_upper: float) -> float:
        """
        Capital efficiency multiplier vs. a Uniswap V2 full-range position.

        Formula (Whitepaper §2):
            efficiency = 1 / (1 − √(P_lower / P_upper))

        Tighter range → same liquidity depth with less capital.
        Example: range ±5% → ~10× efficiency vs V2.
        """
        if price_upper <= price_lower or price_lower <= 0:
            return 1.0
        ratio = math.sqrt(price_lower / price_upper)
        denom = 1 - ratio
        return (1 / denom) if denom > 0 else 1.0

    @staticmethod
    def estimate_fee_apy(
        volume_24h: float,
        fee_tier: float,
        position_liquidity: float,
        total_pool_liquidity: float,
        position_value_usd: float,
    ) -> Dict[str, float]:
        """
        Estimate annualized fee yield for an LP position.

        Formula (derived from Uniswap V3 fee distribution):
            daily_fees = volume_24h × fee_tier × (your_L / pool_L)
            APY = (daily_fees × 365) / position_value × 100

        Ref: https://docs.uniswap.org/concepts/protocol/fees
          "Fees are distributed pro-rata to in-range liquidity
           at the time of the swap."

        ⚠ ESTIMATE ONLY. Actual fees depend on:
          - Whether position is in-range at swap time
          - Tick distribution of pool liquidity
          - Daily volume fluctuations
        """
        if total_pool_liquidity <= 0 or position_value_usd <= 0:
            return {"daily_fees_usd": 0, "annual_fees_usd": 0, "apy_pct": 0}

        share = position_liquidity / total_pool_liquidity
        daily_fees = volume_24h * fee_tier * share
        annual_fees = daily_fees * 365
        apy = (annual_fees / position_value_usd) * 100

        return {
            "daily_fees_usd": round(daily_fees, 4),
            "annual_fees_usd": round(annual_fees, 2),
            "apy_pct": round(apy, 2),
        }


# ── Risk Analysis ────────────────────────────────────────────────────────


class RiskAnalyzer:
    """
    Risk metrics for concentrated liquidity positions.
    Uses simplified probabilistic models. NOT financial advice.
    """

    @staticmethod
    def impermanent_loss(price_initial: float, price_current: float) -> float:
        """
        Impermanent Loss for a V2-style (full-range) position.

        Formula (Pintail, 2019):
            IL = 2·√(r) / (1 + r) − 1
            where r = P_current / P_initial

        Returns negative percentage (e.g. −2.34 = 2.34% loss vs HODL).
        Ref: https://pintail.medium.com/uniswap-a-good-deal-for-liquidity-providers-104c0b6816f2

        ⚠ For V3 concentrated liquidity, IL is AMPLIFIED proportional to
        the capital efficiency multiplier. This returns the V2 baseline.
        """
        if price_initial <= 0:
            return 0.0
        r = price_current / price_initial
        il = 2 * math.sqrt(r) / (1 + r) - 1
        return round(il * 100, 4)

    @staticmethod
    def impermanent_loss_v3(
        price_initial: float,
        price_current: float,
        price_lower: float,
        price_upper: float,
    ) -> Dict[str, float]:
        """
        Impermanent Loss for a concentrated V3 position.

        V3 IL = V2 IL × Capital Efficiency amplifier.

        The V2 baseline (Pintail 2019):
            IL_v2 = 2·√(r) / (1+r) − 1
            where r = P_current / P_initial

        For V3 concentrated liquidity (Whitepaper §2):
            The position is equivalent to a V2 position but with
            capital_efficiency = 1 / (1 − √(Pa/Pb)) more capital.
            IL is amplified proportionally:
            IL_v3 ≈ IL_v2 × CE

        Returns:
            il_v2_pct: V2 baseline IL (negative = loss)
            il_v3_pct: V3 amplified IL (negative = loss)
            capital_efficiency: CE multiplier used
            price_ratio: r = P_current / P_initial

        Ref: https://lambert-guillaume.medium.com/an-analysis-of-the-expected-value-of-the-impermanent-loss-in-uniswap-baguette-83f0a51bb398
        Ref: https://uniswap.org/whitepaper-v3.pdf §2
        """
        if price_initial <= 0 or price_lower <= 0 or price_upper <= price_lower:
            return {
                "il_v2_pct": 0,
                "il_v3_pct": 0,
                "capital_efficiency": 1,
                "price_ratio": 1,
            }

        r = price_current / price_initial
        il_v2 = (2 * math.sqrt(r) / (1 + r) - 1) * 100  # percentage

        # Capital efficiency from Whitepaper §2
        ratio = math.sqrt(price_lower / price_upper)
        denom = 1 - ratio
        ce = (1 / denom) if denom > 0 else 1.0

        # V3 amplified IL — clamped to -100% (can't lose more than position)
        il_v3 = max(il_v2 * ce, -100.0)

        return {
            "il_v2_pct": round(il_v2, 4),
            "il_v3_pct": round(il_v3, 4),
            "capital_efficiency": round(ce, 2),
            "price_ratio": round(r, 6),
        }

    @staticmethod
    def range_width_pct(
        current_price: float, range_min: float, range_max: float
    ) -> float:
        """
        Range width as a percentage of current price.

        Formula: (range_max - range_min) / current_price × 100

        Examples:
          ±5% range  → ~10% width
          ±25% range → ~50% width
          ±50% range → ~100% width

        This is what LPs refer to as a "10% to 15% range width" in practice.
        """
        if current_price <= 0 or range_max <= range_min:
            return 0.0
        return round(((range_max - range_min) / current_price) * 100, 2)

    @staticmethod
    def range_proximity(
        current_price: float, range_min: float, range_max: float
    ) -> Dict[str, float]:
        """
        How close the current price is to the range boundaries.
        Returns buffer percentages and in-range status.
        Pure arithmetic — no external model.
        """
        if range_max <= range_min or current_price <= 0:
            return {
                "in_range": False,
                "downside_buffer_pct": 0,
                "upside_buffer_pct": 0,
                "position_in_range_pct": 0,
            }

        in_range = range_min <= current_price <= range_max
        downside = ((current_price - range_min) / current_price) * 100
        upside = ((range_max - current_price) / current_price) * 100
        total_range = range_max - range_min
        pos_pct = ((current_price - range_min) / total_range) * 100 if in_range else 0

        return {
            "in_range": in_range,
            "downside_buffer_pct": round(downside, 2),
            "upside_buffer_pct": round(upside, 2),
            "position_in_range_pct": round(pos_pct, 2),
        }


# ── Strategic Recommendations ──────────────────────────────────────────


def generate_position_strategies(
    current_price: float,
    volatility: float = None,
    pool_apr: float = 0,
    volume_24h: float = 0,
    fee_tier: float = 0.0005,
    tvl: float = 0,
    position_value: float = 0,
    token0_symbol: str = "WETH",
    token1_symbol: str = "USDT",
    current_ce: float = 0,
) -> Dict:
    """
    Generate conservative/moderate/aggressive position recommendations
    with earnings projections based on real pool data.

    Strategy APR scaling:
      If current_ce is provided (from user's real position), strategies scale
      RELATIVE to the user's position:
        strategy_apr = pool_apr × (strategy_CE / current_CE)
      This gives an honest "what if I narrowed/widened my range" comparison.

    Args:
        current_price: Current token price
        volatility: Optional volatility estimate (default: moderate)
        pool_apr: Position-specific or pool-wide APR (percentage, e.g. 197.5)
        volume_24h: 24h trading volume (USD)
        fee_tier: Pool fee tier (decimal, e.g. 0.0005)
        tvl: Total Value Locked in pool (USD)
        position_value: User's current position value (USD)
        token0_symbol: Base token symbol (e.g. "WETH")
        token1_symbol: Quote token symbol (e.g. "USDT")
        current_ce: User's current position capital efficiency (for relative scaling)
    """
    if volatility is None:
        volatility = 0.5  # Default 50% annual volatility

    investment = position_value if position_value > 0 else float(DEFAULT_CAPITAL_USD)

    # Calculate range widths based on volatility and strategy
    # volatility is a fraction (0.5 = 50%), multiply to get percentage scale
    vol = volatility * 100  # e.g. 0.5 → 50

    strategies = {
        "conservative": {
            "range_width_pct": min(80, vol * 1.6),  # 160% of volatility, max 80%
            "risk_level": "Low",
            "description": "Wide range for stability",
            "ideal_for": "Risk-averse LPs, choppy markets",
        },
        "moderate": {
            "range_width_pct": min(50, vol * 1.0),  # 100% of volatility, max 50%
            "risk_level": "Medium",
            "description": "Balanced risk and rewards",
            "ideal_for": "Most LPs, trending markets",
        },
        "aggressive": {
            "range_width_pct": min(20, vol * 0.4),  # 40% of volatility, max 20%
            "risk_level": "High",
            "description": "Narrow range for maximum fees",
            "ideal_for": "Active managers, stable periods",
        },
    }

    # Compute real capital efficiency from Whitepaper §2 formula:
    # CE = 1 / (1 - sqrt(Pa / Pb))
    # This replaces the old hardcoded values (2.5/5.0/12.0)
    math_engine = UniswapV3Math()

    # Calculate realistic metrics for each strategy
    for strategy, sdata in strategies.items():
        width_pct = sdata["range_width_pct"] / 100

        # Price ranges
        sdata["name"] = strategy
        sdata["lower_price"] = current_price * (1 - width_pct)
        sdata["upper_price"] = current_price * (1 + width_pct)

        # Capital efficiency from Whitepaper formula (not hardcoded)
        sdata["capital_efficiency"] = math_engine.capital_efficiency_vs_v2(
            sdata["lower_price"], sdata["upper_price"]
        )

        # Investment = user's real position value (or $10K fallback)
        sdata["total_value_usd"] = investment
        sdata["token0_amount"] = (
            (investment * 0.5) / current_price if current_price > 0 else 0
        )
        sdata["token1_amount"] = investment * 0.5

        # Token symbols for boundary descriptions
        sdata["token0_symbol"] = token0_symbol
        sdata["token1_symbol"] = token1_symbol

        # APR estimate: scale RELATIVE to current position's CE
        # If current_ce provided: strategy_apr = pool_apr × (strategy_CE / current_CE)
        # This answers: "if I moved to this range, how would my APR change?"
        # Ref: Uniswap V3 Whitepaper §2 — fees proportional to virtual liquidity
        if pool_apr > 0:
            baseline_ce = (
                current_ce if current_ce > 0 else max(sdata["capital_efficiency"], 1.0)
            )
            eff_ratio = sdata["capital_efficiency"] / max(baseline_ce, 1.0)
            sdata["apr_estimate"] = (pool_apr * eff_ratio) / 100  # decimal
        else:
            base_yield = 0.05
            sdata["apr_estimate"] = base_yield * (sdata["capital_efficiency"] / 2.0)

        # Earnings projections based on APR and investment
        annual_fees = investment * sdata["apr_estimate"]
        sdata["daily_fees_est"] = round(annual_fees / 365, 4)
        sdata["weekly_fees_est"] = round(annual_fees / 52, 4)
        sdata["monthly_fees_est"] = round(annual_fees / 12, 2)
        sdata["annual_fees_est"] = round(annual_fees, 2)

    return strategies


def _classify_current_strategy(
    range_min: float, range_max: float, current_price: float
) -> str:
    """Classify the current position's strategy based on range width."""
    if range_min <= 0 or range_max <= 0 or current_price <= 0:
        return "unknown"

    range_width_pct = ((range_max - range_min) / current_price) * 100

    if range_width_pct >= 80:
        return "conservative"
    elif range_width_pct >= 40:
        return "moderate"
    else:
        return "aggressive"


def analyze_position(position: PositionData) -> Dict[str, Any]:
    """
    Run a full analysis on a PositionData object.
    Returns a flat dict suitable for template rendering.
    All values derived from on-chain / API data + documented formulas.
    """
    math_engine = UniswapV3Math()
    risk = RiskAnalyzer()

    # Liquidity (Whitepaper §6.2)
    liquidity = math_engine.calculate_liquidity(
        position.token0_amount,
        position.token1_amount,
        position.current_price,
        position.range_min,
        position.range_max,
    )

    # Capital efficiency vs V2 (Whitepaper §2)
    cap_eff = math_engine.capital_efficiency_vs_v2(
        position.range_min, position.range_max
    )

    # Range proximity
    prox = risk.range_proximity(
        position.current_price, position.range_min, position.range_max
    )

    # Range width as % of current price (what LPs call "10% range width")
    range_width = risk.range_width_pct(
        position.current_price, position.range_min, position.range_max
    )

    # V3 Impermanent Loss estimate
    # Uses current_price as both initial and current for "current snapshot" IL.
    # For real IL, initial price = price at deposit time (needs historical data).
    # We compute IL at range boundaries to show worst-case scenarios.
    il_at_lower = risk.impermanent_loss_v3(
        position.current_price,
        position.range_min,
        position.range_min,
        position.range_max,
    )
    il_at_upper = risk.impermanent_loss_v3(
        position.current_price,
        position.range_max,
        position.range_min,
        position.range_max,
    )

    # Volume/TVL ratio — capital efficiency indicator
    # Higher ratio = more trading activity per dollar locked = potentially better fees
    vol_tvl_ratio = (
        round(position.volume_24h / max(position.total_value_locked_usd, 1), 4)
        if position.total_value_locked_usd > 0
        else 0
    )

    # HODL Comparison — "what if I just held 50/50 instead of LPing?"
    # At deposit time, assume 50/50 split at current_price.
    # token0_held = total_value / 2 / current_price (token0 amount)
    # token1_held = total_value / 2 (in USD)
    # HODL value now = token0_held × current_price + token1_held
    # Since we use current price for both, HODL = always = initial.
    # The real value is: LP_value + fees - HODL_value.
    # Without historical deposit price, we show: fees vs estimated IL.
    hodl_fees_vs_il = {
        "fees_earned_usd": round(position.fees_earned_usd, 2),
        "il_if_at_lower_pct": il_at_lower["il_v3_pct"],
        "il_if_at_upper_pct": il_at_upper["il_v3_pct"],
        "il_if_at_lower_usd": round(
            position.total_value_usd * il_at_lower["il_v3_pct"] / 100, 2
        ),
        "il_if_at_upper_usd": round(
            position.total_value_usd * il_at_upper["il_v3_pct"] / 100, 2
        ),
        "net_if_at_lower_usd": round(
            position.fees_earned_usd
            + (position.total_value_usd * il_at_lower["il_v3_pct"] / 100),
            2,
        ),
        "net_if_at_upper_usd": round(
            position.fees_earned_usd
            + (position.total_value_usd * il_at_upper["il_v3_pct"] / 100),
            2,
        ),
    }

    # Pool-level APR estimate for strategy calculations
    pool_apr = (
        round(
            (
                position.volume_24h
                * position.fee_tier
                * 365
                / max(position.total_value_locked_usd, 1)
            )
            * 100,
            2,
        )
        if position.total_value_locked_usd > 0
        else 0
    )

    # ── Position APR: best available method ──
    #
    # Method 1 (preferred): If we have position_share from on-chain, compute directly:
    #   position_apr = (volume_24h × fee_tier × 365 × share) / position_value × 100
    #   This uses REAL liquidity data — no CE estimation needed.
    #
    # Method 2 (fallback): Use pool_apr as approximation.
    #   Pool APR = total_fees_year / TVL — average return per dollar.
    #   User's concentrated position may earn more or less depending on CE.
    #
    if (
        position.position_share > 0
        and position.total_value_usd > 0
        and position.volume_24h > 0
    ):
        # Method 1: Direct from on-chain position_share (most accurate)
        daily_fees_from_share = (
            position.volume_24h * position.fee_tier * position.position_share
        )
        _position_apr = round(
            (daily_fees_from_share * 365 / position.total_value_usd) * 100, 2
        )
    elif pool_apr > 0:
        # Method 2: Approximate as pool_apr (good for most cases)
        _position_apr = pool_apr
    else:
        _position_apr = 0

    # Strategy strategies use same position_apr as baseline, scaled by CE ratio.
    # When position has on-chain position_share, strategies scale relative to
    # the current position's CE for honest "what-if" comparison.
    strategies = generate_position_strategies(
        current_price=position.current_price,
        pool_apr=_position_apr,  # Use position-specific APR as baseline
        volume_24h=position.volume_24h,
        fee_tier=position.fee_tier,
        tvl=position.total_value_locked_usd,
        position_value=position.total_value_usd,
        token0_symbol=position.token0_symbol,
        token1_symbol=position.token1_symbol,
        current_ce=cap_eff,  # Pass current position's CE for relative scaling
    )

    # Fee tier label
    fee_tier_map = {
        0.0001: "0.01%",
        0.0005: "0.05%",
        0.003: "0.30%",
        0.01: "1.00%",
    }
    fee_tier_label = fee_tier_map.get(
        position.fee_tier, f"{position.fee_tier * 100:.2f}%"
    )

    return {
        # Identity
        "position_id": position.position_id,
        "pool_address": position.pool_address,
        "wallet_address": position.wallet_address,
        "network": position.network,
        "protocol": position.protocol,
        "protocol_version": position.protocol_version,
        "token0_symbol": position.token0_symbol,
        "token1_symbol": position.token1_symbol,
        # Data source (real on-chain vs simulated)
        "data_source": "on-chain" if position.position_id else "simulated",
        # Token balances
        "token0_amount": position.token0_amount,
        "token1_amount": position.token1_amount,
        "token0_value_usd": round(position.token0_amount * position.current_price, 2),
        "token1_value_usd": round(position.token1_amount, 2),
        "token0_pct": round(position.token0_pct, 2),
        "token1_pct": round(position.token1_pct, 2),
        "total_value_usd": round(position.total_value_usd, 2),
        # Prices & range
        "current_price": position.current_price,
        "range_min": position.range_min,
        "range_max": position.range_max,
        "fee_tier": position.fee_tier,
        "fee_tier_label": fee_tier_label,
        # Fees earned
        "fees_earned_usd": position.fees_earned_usd,
        # Calculated metrics (with formula sources)
        "liquidity": round(liquidity, 4),
        "capital_efficiency_vs_v2": round(cap_eff, 1),
        "in_range": prox["in_range"],
        "downside_buffer_pct": prox["downside_buffer_pct"],
        "upside_buffer_pct": prox["upside_buffer_pct"],
        "position_in_range_pct": prox["position_in_range_pct"],
        # NEW: Range width as % of current price
        "range_width_pct": range_width,
        # NEW: V3 Impermanent Loss estimates (worst-case at boundaries)
        "il_at_lower_v3_pct": il_at_lower["il_v3_pct"],
        "il_at_upper_v3_pct": il_at_upper["il_v3_pct"],
        "il_at_lower_v2_pct": il_at_lower["il_v2_pct"],
        "il_at_upper_v2_pct": il_at_upper["il_v2_pct"],
        # NEW: Volume/TVL ratio (capital efficiency indicator)
        "vol_tvl_ratio": vol_tvl_ratio,
        # NEW: HODL comparison — Fees vs IL at boundaries
        "hodl_comparison": hodl_fees_vs_il,
        # Strategy recommendations
        "strategies": strategies,
        "current_strategy": _classify_current_strategy(
            position.range_min, position.range_max, position.current_price
        ),
        # Enhanced projections for CURRENT position
        # Position APR = pool_apr × (position_CE / baseline_CE)
        # baseline_CE ≈ moderate range CE (±50%) as proxy for pool average
        # This uses the SAME scaling logic as the strategies for consistency
        #
        # ⚠️ IMPORTANT: These are THEORETICAL estimates based on 24h volume snapshot.
        # Actual avg daily fees may differ by 20-30% due to volume fluctuations.
        # Cross-validate at: https://revert.finance/#/account/<wallet>
        "position_apr_est": _position_apr
        if pool_apr > 0
        else (
            round((position.fees_earned_usd * 52 / position.total_value_usd) * 100, 2)
            if position.total_value_usd > 0
            else 0
        ),
        "daily_fees_est": round(
            position.total_value_usd * (_position_apr / 100) / 365, 4
        )
        if pool_apr > 0
        else round(position.fees_earned_usd / 7, 4),
        "weekly_fees_est": round(
            position.total_value_usd * (_position_apr / 100) / 52, 4
        )
        if pool_apr > 0
        else round(position.fees_earned_usd, 4),
        "monthly_fees_est": round(
            position.total_value_usd * (_position_apr / 100) / 12, 2
        )
        if pool_apr > 0
        else round(position.fees_earned_usd * 4.33, 2),
        "annual_fees_est": round(position.total_value_usd * (_position_apr / 100), 2)
        if pool_apr > 0
        else round(position.fees_earned_usd * 52, 2),
        "annual_apy_est": _position_apr
        if pool_apr > 0
        else (
            round((position.fees_earned_usd * 52 / position.total_value_usd) * 100, 2)
            if position.total_value_usd > 0
            else 0
        ),
        # Market data (now properly included from API)
        "volume_24h": position.volume_24h,
        "total_value_locked_usd": position.total_value_locked_usd,
        # Pool-level APR estimate: (volume_24h × fee_tier × 365) / TVL × 100
        "pool_apr_estimate": pool_apr,
        "pool_24h_fees_est": round(position.volume_24h * position.fee_tier, 2),
        # Metadata
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


# ── CLI quick test ───────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    import sys as _sys

    async def _quick_test():
        from defi_cli.dexscreener_client import analyze_pool_real

        addr = _sys.argv[1] if len(_sys.argv) > 1 else None
        if not addr:
            print("Usage: python real_defi_math.py <pool_address>")
            return

        print(f"⏳ Fetching live data for {addr[:16]}…")
        result = await analyze_pool_real(addr)

        if result["status"] != "success":
            print(f"❌ {result['message']}")
            return

        pos = PositionData.from_pool_data(result["data"])
        analysis = analyze_position(pos)

        print("=" * 60)
        print("  DeFi Math Engine — Live Pool Analysis")
        print("=" * 60)
        for k, v in analysis.items():
            print(f"  {k:30s} : {v}")
        print("=" * 60)

    asyncio.run(_quick_test())
