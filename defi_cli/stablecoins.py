"""
Stablecoin Detection — On-Chain Token Classification
=====================================================

Provides smart stablecoin detection for:
  - Fee tier estimation (0.01% for stable-stable pairs)
  - USD value calculation (token ≈ $1 assumption)
  - Pair classification (stable-stable, stable-volatile, volatile-volatile)

Known stablecoins are recognized by normalized symbol.
Covers all major USD/EUR/GBP pegged tokens across Ethereum, Arbitrum,
Polygon, Base, Optimism, BSC.

Reference:
  Uniswap V3 Fee Tiers: https://docs.uniswap.org/concepts/protocol/fees
  - 0.01% (100)  → stable-stable pairs (USDC/USDT, DAI/USDC)
  - 0.05% (500)  → correlated pairs (WETH/stETH, WBTC/WETH)
  - 0.30% (3000) → standard pairs (WETH/USDC, LINK/USDC)
  - 1.00% (10000)→ exotic / low-liquidity pairs
"""

from typing import Tuple

# ── Known Stablecoin Symbols ────────────────────────────────────────────
# Normalized to uppercase. Includes bridged variants (.e, .b, etc.)
# Sources: CoinGecko stablecoin category, DeFiLlama stablecoin tracker.

STABLECOIN_SYMBOLS: frozenset = frozenset({
    # USD-pegged — major
    "USDC", "USDT", "DAI", "BUSD", "TUSD", "FRAX", "LUSD",
    "USDP", "GUSD", "SUSD", "CUSD", "USDD", "PYUSD", "GHO",
    "FDUSD", "CRVUSD", "MKUSD",

    # USD-pegged — bridged variants
    "USDC.E", "USDT.E", "DAI.E",        # Avalanche / Polygon bridged
    "USDBC", "USDCE",                     # Base variants
    "AXLUSDC",                             # Axelar-bridged USDC

    # EUR-pegged (treated as stable for pair classification)
    "EURS", "EURT", "AGEUR", "CEUR", "EURC",

    # GBP-pegged
    "GBPT",

    # Algorithmic / CDP stables
    "MIM", "DOLA", "ALUSD", "USDS",

    # Rebasing / yield-bearing stables
    "OUSD",
})


def is_stablecoin(symbol: str) -> bool:
    """
    Check if a token symbol is a known stablecoin.

    Args:
        symbol: Token symbol (case-insensitive).

    Returns:
        True if the symbol matches a known stablecoin.

    Examples:
        >>> is_stablecoin("USDC")
        True
        >>> is_stablecoin("usdt.e")
        True
        >>> is_stablecoin("WETH")
        False
    """
    return symbol.strip().upper() in STABLECOIN_SYMBOLS


def is_stablecoin_pair(symbol0: str, symbol1: str) -> bool:
    """
    Check if BOTH tokens in a pair are stablecoins.

    Stable-stable pairs typically use the 0.01% (100) fee tier.

    Args:
        symbol0: First token symbol.
        symbol1: Second token symbol.

    Returns:
        True if both tokens are stablecoins.

    Examples:
        >>> is_stablecoin_pair("USDC", "USDT")
        True
        >>> is_stablecoin_pair("WETH", "USDC")
        False
    """
    return is_stablecoin(symbol0) and is_stablecoin(symbol1)


def has_stablecoin(symbol0: str, symbol1: str) -> bool:
    """
    Check if at least one token in the pair is a stablecoin.

    Useful for USD value estimation: if one side is a stablecoin,
    its amount ≈ USD value directly.

    Args:
        symbol0: First token symbol.
        symbol1: Second token symbol.

    Returns:
        True if at least one token is a stablecoin.
    """
    return is_stablecoin(symbol0) or is_stablecoin(symbol1)


def classify_pair(symbol0: str, symbol1: str) -> str:
    """
    Classify a token pair for fee tier estimation.

    Returns:
        "stable-stable"   — Both tokens are stablecoins (→ 0.01% fee tier)
        "stable-volatile"  — One stablecoin + one volatile (→ 0.05% or 0.30%)
        "volatile-volatile"— Neither is a stablecoin (→ 0.30% or 1.00%)

    Examples:
        >>> classify_pair("USDC", "USDT")
        'stable-stable'
        >>> classify_pair("WETH", "USDC")
        'stable-volatile'
        >>> classify_pair("LINK", "UNI")
        'volatile-volatile'
    """
    s0 = is_stablecoin(symbol0)
    s1 = is_stablecoin(symbol1)
    if s0 and s1:
        return "stable-stable"
    elif s0 or s1:
        return "stable-volatile"
    return "volatile-volatile"


def stablecoin_side(symbol0: str, symbol1: str) -> int:
    """
    Identify which side of the pair is the stablecoin.

    Returns:
        0  — token0 is the stablecoin
        1  — token1 is the stablecoin
        -1 — neither or both are stablecoins

    Useful for USD value calculation: the stablecoin side has amount ≈ USD.
    """
    s0 = is_stablecoin(symbol0)
    s1 = is_stablecoin(symbol1)
    if s0 and not s1:
        return 0
    elif s1 and not s0:
        return 1
    return -1


# ── Correlated Assets (same base, e.g. WETH/stETH, WBTC/cbBTC) ────────
# These pairs typically use the 0.05% fee tier.

CORRELATED_GROUPS: list[frozenset[str]] = [
    frozenset({"WETH", "ETH", "STETH", "WSTETH", "RETH", "CBETH", "METH", "SWETH", "ANKRETH"}),
    frozenset({"WBTC", "BTC", "TBTC", "CBBTC", "RENBTC", "SBTC"}),
]


def is_correlated_pair(symbol0: str, symbol1: str) -> bool:
    """
    Check if two tokens are correlated (same underlying asset).

    Correlated pairs typically use the 0.05% (500) fee tier.

    Examples:
        >>> is_correlated_pair("WETH", "stETH")
        True
        >>> is_correlated_pair("WBTC", "cbBTC")
        True
        >>> is_correlated_pair("WETH", "USDC")
        False
    """
    s0 = symbol0.strip().upper()
    s1 = symbol1.strip().upper()
    for group in CORRELATED_GROUPS:
        if s0 in group and s1 in group:
            return True
    return False


def estimate_fee_tier(symbol0: str, symbol1: str) -> float:
    """
    Estimate the most likely Uniswap V3 fee tier for a token pair.

    Fee tier docs: https://docs.uniswap.org/concepts/protocol/fees

    Returns:
        float — one of {0.0001, 0.0005, 0.003, 0.01}

    Examples:
        >>> estimate_fee_tier("USDC", "USDT")
        0.0001
        >>> estimate_fee_tier("WETH", "stETH")
        0.0005
        >>> estimate_fee_tier("WETH", "USDC")
        0.0005
        >>> estimate_fee_tier("LINK", "USDC")
        0.003
        >>> estimate_fee_tier("SHIB", "DOGE")
        0.01
    """
    if is_stablecoin_pair(symbol0, symbol1):
        return 0.0001   # 0.01% — stable-stable

    if is_correlated_pair(symbol0, symbol1):
        return 0.0005   # 0.05% — correlated assets

    # ETH or BTC pairs with stablecoins → standard
    pair = classify_pair(symbol0, symbol1)
    if pair == "stable-volatile":
        upper = {symbol0.strip().upper(), symbol1.strip().upper()}
        # Major volatile assets with stables typically use 0.05% or 0.30%
        major_volatile = {"WETH", "ETH", "WBTC", "BTC"}
        if upper & major_volatile:
            return 0.0005  # 0.05% — ETH/USDC, WBTC/USDT
        return 0.003       # 0.30% — LINK/USDC, UNI/USDT

    return 0.01  # 1.00% — exotic volatile-volatile
