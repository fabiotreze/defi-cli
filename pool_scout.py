#!/usr/bin/env python3
"""
Pool Scout — Cross-DEX Pool Discovery via DefiLlama Yields API
===============================================================

Finds the most attractive V3 pools across all supported DEXes and chains.
Uses 100% free, no-API-key DefiLlama Yields API.

Data Source:
  DefiLlama Yields API: https://yields.llama.fi/pools
  Rate Limit: ~30 requests/minute (free, no key)
  Coverage: 20,000+ pools across all major DEXes and chains
  Documentation: https://defillama.com/docs/api

Features:
  - Search by token pair (e.g., WETH/USDC) across all DEXes
  - Filter by network, DEX, minimum TVL
  - Sort by APY, TVL, volume, or vol/TVL efficiency
  - Compare current position against alternatives
  - APY trend analysis (1d/7d/30d)
"""

import httpx
from typing import Dict, List, Optional, Any
from datetime import datetime


# ── DefiLlama API Constants ──────────────────────────────────────────────

DEFILLAMA_YIELDS_URL = "https://yields.llama.fi/pools"
DEFILLAMA_TIMEOUT = 20  # seconds

# Map our internal project slugs → DefiLlama project identifiers
PROJECT_MAP = {
    "uniswap_v3": "uniswap-v3",
    "pancakeswap_v3": "pancakeswap-amm-v3",
    "sushiswap_v3": "sushiswap-v3",
}

# Map internal network names → DefiLlama "chain" names.
# DefiLlama uses "chain" where we use "network" — this mapping bridges the two.
NETWORK_TO_CHAIN = {
    "ethereum": "Ethereum",
    "arbitrum": "Arbitrum",
    "polygon": "Polygon",
    "base": "Base",
    "optimism": "Optimism",
    "bsc": "BSC",
    "avalanche": "Avalanche",
}


# ── Pool Scout ────────────────────────────────────────────────────────────


class PoolScout:
    """
    Cross-DEX pool discovery engine powered by DefiLlama Yields API.

    One HTTP call to https://yields.llama.fi/pools returns all V3 pool
    data across every DEX and chain — APY, TVL, volume, IL risk, fee tier.
    No API key required. 100% free.
    """

    def __init__(self):
        self._cache: Optional[List[Dict]] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 120  # Cache for 2 minutes

    async def _fetch_pools(self) -> List[Dict]:
        """Fetch all pools from DefiLlama yields API (cached)."""
        now = datetime.now()
        if (
            self._cache is not None
            and self._cache_time is not None
            and (now - self._cache_time).total_seconds() < self._cache_ttl_seconds
        ):
            return self._cache

        async with httpx.AsyncClient(timeout=DEFILLAMA_TIMEOUT) as client:
            resp = await client.get(DEFILLAMA_YIELDS_URL)
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") != "success":
            raise RuntimeError(f"DefiLlama API error: {data.get('status')}")

        self._cache = data.get("data", [])
        self._cache_time = now
        return self._cache

    def _filter_v3(self, pools: List[Dict]) -> List[Dict]:
        """Keep only V3-compatible project pools."""
        v3_projects = set(PROJECT_MAP.values())
        return [p for p in pools if p.get("project") in v3_projects]

    async def search_pools(
        self,
        token_pair: str = None,
        network: str = None,
        dex: str = None,
        min_tvl: float = 50_000,
        sort_by: str = "apy",
        limit: int = 15,
    ) -> Dict[str, Any]:
        """
        Search for the most attractive V3 pools.

        Args:
            token_pair: e.g., "WETH/USDC" — searches symbol field
            network: e.g., "arbitrum" — filters by chain
            dex: e.g., "uniswap_v3" — filters by project
            min_tvl: Minimum TVL in USD (default: $50K)
            sort_by: "apy", "tvl", "volume", "efficiency" (vol/tvl)
            limit: Max results to return

        Returns:
            Dict with status, pools list, metadata
        """
        try:
            all_pools = await self._fetch_pools()
        except Exception as e:
            return {
                "status": "error",
                "message": f"DefiLlama API error: {e}",
                "pools": [],
            }

        # Filter to V3 only
        pools = self._filter_v3(all_pools)

        # Filter by token pair
        if token_pair:
            tokens = [
                t.strip().upper()
                for t in token_pair.replace("/", "-").replace(" ", "-").split("-")
            ]
            pools = [
                p
                for p in pools
                if all(t in p.get("symbol", "").upper() for t in tokens)
            ]

        # Filter by network
        if network:
            chain_name = NETWORK_TO_CHAIN.get(network.lower(), network.title())
            pools = [
                p for p in pools if p.get("chain", "").lower() == chain_name.lower()
            ]

        # Filter by DEX
        if dex:
            project_id = PROJECT_MAP.get(dex, dex)
            pools = [p for p in pools if p.get("project") == project_id]

        # Filter by min TVL
        pools = [p for p in pools if (p.get("tvlUsd") or 0) >= min_tvl]

        # Sort
        sort_keys = {
            "apy": lambda p: p.get("apy") or 0,
            "tvl": lambda p: p.get("tvlUsd") or 0,
            "volume": lambda p: p.get("volumeUsd1d") or 0,
            "efficiency": lambda p: (
                (p.get("volumeUsd1d") or 0) / max(p.get("tvlUsd") or 1, 1)
            ),
        }
        sort_fn = sort_keys.get(sort_by, sort_keys["apy"])
        pools.sort(key=sort_fn, reverse=True)

        # Limit
        pools = pools[:limit]

        # Format output
        formatted = []
        for p in pools:
            apy = p.get("apy") or 0
            tvl = p.get("tvlUsd") or 0
            vol = p.get("volumeUsd1d") or 0
            formatted.append(
                {
                    "symbol": p.get("symbol", "?"),
                    "dex": p.get("project", "?"),
                    "dex_display": _dex_display(p.get("project", "")),
                    "chain": p.get("chain", "?"),
                    "fee_tier": p.get("poolMeta") or "?",
                    "apy": round(apy, 2),
                    "apy_base": round(p.get("apyBase") or 0, 2),
                    "apy_reward": round(p.get("apyReward") or 0, 2),
                    "tvl_usd": round(tvl, 0),
                    "volume_1d_usd": round(vol, 0),
                    "vol_tvl_ratio": round(vol / max(tvl, 1), 4),
                    "il_risk": p.get("ilRisk", "?"),
                    "stablecoin": p.get("stablecoin", False),
                    "apy_1d_change": round(p.get("apyPct1D") or 0, 2),
                    "apy_7d_change": round(p.get("apyPct7D") or 0, 2),
                    "apy_30d_change": round(p.get("apyPct30D") or 0, 2),
                    "apy_mean_30d": round(p.get("apyMean30d") or 0, 2),
                    "pool_id": p.get("pool", ""),
                }
            )

        return {
            "status": "success",
            "pools": formatted,
            "total_found": len(formatted),
            "filters": {
                "token_pair": token_pair,
                "network": network,
                "dex": dex,
                "min_tvl": min_tvl,
                "sort_by": sort_by,
            },
            "source": "DefiLlama Yields API",
            "source_url": "https://defillama.com/yields",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }


# ── Helpers ───────────────────────────────────────────────────────────────


def _dex_display(project_id: str) -> str:
    """Friendly display name for a DefiLlama project ID."""
    names = {
        "uniswap-v3": "🦄 Uniswap V3",
        "pancakeswap-amm-v3": "🥞 PancakeSwap V3",
        "sushiswap-v3": "🍣 SushiSwap V3",
    }
    return names.get(project_id, project_id)


def format_scout_results(result: Dict) -> str:
    """Format scout results for CLI display."""
    if result["status"] != "success":
        return f"❌ {result.get('message', 'Unknown error')}"

    pools = result["pools"]
    if not pools:
        filters = result.get("filters", {})
        return (
            f"No V3 pools found matching filters:\n"
            f"  Pair: {filters.get('token_pair', 'any')}\n"
            f"  Network: {filters.get('network', 'all')}\n"
            f"  DEX: {filters.get('dex', 'all')}\n"
            f"  Min TVL: ${filters.get('min_tvl', 0):,.0f}\n"
            f"\n💡 Try broadening your search (lower min_tvl or remove network filter)."
        )

    lines = []
    lines.append(f"{'=' * 95}")
    lines.append(f"  🔭 Pool Scout — {result['total_found']} V3 pools found")
    lines.append(f"  Source: DefiLlama Yields API · {result['timestamp']}")
    filters = result.get("filters", {})
    if filters.get("token_pair"):
        lines.append(f"  Search: {filters['token_pair']}")
    if filters.get("network"):
        lines.append(f"  Network: {filters['network'].title()}")
    lines.append(f"{'=' * 95}")
    lines.append("")

    # Header
    hdr = f"  {'#':>2} {'DEX':20s} {'Chain':10s} {'Fee':6s} {'APY%':>8s} {'APY 30d':>8s} {'TVL':>14s} {'Vol 24h':>14s} {'V/T':>6s} {'IL':>4s}"
    lines.append(hdr)
    lines.append(f"  {'-' * (len(hdr) - 2)}")

    for i, p in enumerate(pools, 1):
        dex = p["dex_display"][:20]
        chain = p["chain"][:10]
        fee = str(p["fee_tier"])[:6]
        apy = f"{p['apy']:8.1f}"
        tvl = f"${p['tvl_usd']:>13,.0f}"
        il = p["il_risk"][:4] if isinstance(p["il_risk"], str) else "?"
        apy30 = f"{p['apy_mean_30d']:8.1f}" if p["apy_mean_30d"] else "     N/A"
        vol = f"${p['volume_1d_usd']:>13,.0f}"
        vt = f"{p['vol_tvl_ratio']:.2f}"
        lines.append(
            f"  {i:>2} {dex:20s} {chain:10s} {fee:6s} {apy:>8s} {apy30:>8s} {tvl:>14s} {vol:>14s} {vt:>6s} {il:>4s}"
        )

    lines.append(f"\n{'=' * 95}")
    lines.append("  ⚠️  APY is a snapshot — check 30d average for stability")
    lines.append("  ⚠️  NOT financial advice — always verify before repositioning")
    lines.append(f"{'=' * 95}")

    return "\n".join(lines)


# ── CLI Quick Test ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    import sys

    async def _test():
        pair = sys.argv[1] if len(sys.argv) > 1 else "WETH/USDC"
        net = sys.argv[2] if len(sys.argv) > 2 else None
        print(f"🔭 Searching for {pair}" + (f" on {net}" if net else "") + "...")

        scout = PoolScout()
        result = await scout.search_pools(token_pair=pair, network=net)
        print(format_scout_results(result))

    asyncio.run(_test())
