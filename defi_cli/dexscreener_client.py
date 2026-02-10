#!/usr/bin/env python3
"""
DeFi CLI — Official DEXScreener Implementation
=================================================
Based on the official documentation: https://docs.dexscreener.com/api/reference

Replaces simulated data with real data from the DEXScreener API.
"""

import asyncio
import re
import time
import httpx
from typing import Dict, Any, Optional
from datetime import datetime

from defi_cli.central_config import config


# ── Rate Limiter (CWE-770 mitigation) ────────────────────────────────────


class _RateLimiter:
    """Token-bucket rate limiter to respect API limits.

    CWE-770: Allocation of Resources Without Limits or Throttling.
    OWASP A05:2021: Security Misconfiguration.

    Prevents exceeding DEXScreener's 300 req/min limit and avoids
    IP bans that would break the tool for all users.
    """

    def __init__(self, max_requests: int, period_seconds: float):
        self._max = max_requests
        self._period = period_seconds
        self._timestamps: list[float] = []

    async def acquire(self) -> None:
        """Wait until a request slot is available."""
        now = time.monotonic()
        # Purge timestamps outside the current window
        self._timestamps = [t for t in self._timestamps if now - t < self._period]
        if len(self._timestamps) >= self._max:
            # Wait until the oldest request expires
            sleep_time = self._period - (now - self._timestamps[0]) + 0.1
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        self._timestamps.append(time.monotonic())


# Shared rate limiters (module-level singletons)
_dexscreener_limiter = _RateLimiter(
    max_requests=250, period_seconds=60
)  # 250/min (safety margin under 300)
_rpc_limiter = _RateLimiter(max_requests=150, period_seconds=60)  # 150/min


class DexScreenerClient:
    """Official DEXScreener API client."""

    def __init__(self):
        self.base_url = config.api.BASE_URL
        self.timeout = config.api.TIMEOUT_SECONDS

    async def get_pool_data(
        self, pool_address: str, network: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Fetches real pool/token data UNIVERSALLY.

        - If network specified: tries only that network
        - Otherwise: auto-detects by searching all major networks
        - Works with pools or individual tokens

        Official endpoint: /latest/dex/pairs/{chainId}/{pairId}
        Rate limit: 300 requests/minute
        """
        try:
            if network:
                # Search specific network
                return await self._search_specific_network(pool_address, network)
            else:
                # AUTO-DETECT: search across all priority networks
                return await self._auto_detect_pool(pool_address)

        except Exception:
            # CWE-209: sanitize error — do not expose internal exception details
            print("❌ Pool data fetch failed. Check the address and try again.")
            return None

    async def _search_specific_network(
        self, address: str, network: str
    ) -> Optional[Dict[str, Any]]:
        """Search on a specific network."""
        if network not in config.api.SUPPORTED_CHAINS:
            print(
                f"❌ Network {network} not supported. Available: {list(config.api.SUPPORTED_CHAINS.keys())}"
            )
            return None

        chain_id = config.api.SUPPORTED_CHAINS[network]
        url = config.api.get_pair_url(chain_id, address)

        print(f"🔍 Searching on {network.upper()}: {address[:12]}...")
        return await self._fetch_pool_data(url, network, address)

    async def _auto_detect_pool(self, address: str) -> Optional[Dict[str, Any]]:
        """Auto-detect the pool's network by searching across priority chains."""
        print(
            f"🌐 AUTO-DETECT: Searching {address[:12]}... across all major networks..."
        )

        async with httpx.AsyncClient(timeout=self.timeout, verify=True) as client:
            # Search priority networks in parallel
            tasks = []
            for network, url in config.api.get_auto_detect_urls(address):
                tasks.append(self._try_network(client, network, url, address))

            # Execute searches in parallel
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Return first with data
            for result in results:
                if result and not isinstance(result, Exception):
                    return result

            # If not found as pool, try as token
            print("🔍 Not found as pool. Trying as TOKEN...")
            return await self._search_as_token(client, address)

    async def _try_network(
        self, client: httpx.AsyncClient, network: str, url: str, address: str
    ) -> Optional[Dict[str, Any]]:
        """Try fetching from a specific network (rate-limited)."""
        try:
            await _dexscreener_limiter.acquire()
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                pairs = data.get("pairs", [])

                if pairs:
                    pair = pairs[0]
                    pool_info = self._extract_pool_info(pair)
                    print(f"✅ FOUND on {network.upper()}: {pool_info['name']}")
                    return pool_info

        except (httpx.HTTPError, KeyError, ValueError, TypeError):
            pass  # Network not available, try next

        return None

    async def _search_as_token(
        self, client: httpx.AsyncClient, token_address: str
    ) -> Optional[Dict[str, Any]]:
        """Search pools where the address is a token (not a pool)."""
        try:
            # Try on major networks as token
            for chain in config.api.PRIORITY_CHAINS:
                try:
                    url = config.api.get_token_search_url(chain, token_address)
                    response = await client.get(url)

                    if response.status_code == 200:
                        data = response.json()
                        if isinstance(data, list) and data:
                            # Pick pool with highest liquidity
                            best_pool = max(
                                data,
                                key=lambda x: float(
                                    x.get("liquidity", {}).get("usd", 0) or 0
                                ),
                            )
                            pool_info = self._extract_pool_info(best_pool)
                            print(
                                f"✅ FOUND as TOKEN on {chain.upper()}: {pool_info['name']}"
                            )
                            return pool_info

                except Exception:
                    continue

        except Exception:
            pass

        print("❌ Not found on any network")
        return None

    async def _fetch_pool_data(
        self, url: str, network: str, address: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch data from a specific URL."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout, verify=True) as client:
                response = await client.get(url)

                if response.status_code == 200:
                    data = response.json()
                    pairs = data.get("pairs", [])

                    if pairs:
                        pair = pairs[0]
                        pool_info = self._extract_pool_info(pair)
                        print(f"✅ Pool found: {pool_info['name']}")
                        return pool_info
                    else:
                        print(f"❌ Pool {address[:12]}... not found on {network}")
                        return None

                elif response.status_code == 429:
                    print("⚠️ Rate limit reached. Please wait and try again.")
                    return None

                else:
                    print(f"❌ HTTP Error {response.status_code}")
                    return None

        except httpx.TimeoutException:
            print("⏰ Timeout fetching pool data")
            return None

        except Exception:
            # CWE-209: generic error message
            print("❌ Network request failed. Please try again.")
            return None

    def _extract_pool_info(self, pair_data: Dict) -> Dict[str, Any]:
        """Extract and format essential pool information."""

        # Extract tokens
        base_token = pair_data.get("baseToken", {})
        quote_token = pair_data.get("quoteToken", {})

        # Extract financial metrics
        liquidity = pair_data.get("liquidity", {})
        volume = pair_data.get("volume", {})
        price_change = pair_data.get("priceChange", {})
        txns = pair_data.get("txns", {})

        # Calculate estimated APY (based on volume/liquidity ratio)
        tvl_usd = float(liquidity.get("usd", 0))
        volume_24h = float(volume.get("h24", 0))

        # Simplified APY: (daily_volume / tvl) * 365 * estimated_fee_tier
        fee_tier_estimate = 0.0005  # 0.05% typical Uniswap V3
        daily_yield = (volume_24h / tvl_usd) if tvl_usd > 0 else 0
        estimated_apy = daily_yield * 365 * fee_tier_estimate * 100

        return {
            "name": f"{base_token.get('symbol', 'UNK')}/{quote_token.get('symbol', 'UNK')}",
            "address": pair_data.get("pairAddress", "N/A"),
            "network": pair_data.get("chainId", "unknown"),
            "dex": pair_data.get("dexId", "unknown"),
            # Tokens
            "baseToken": {
                "symbol": base_token.get("symbol", "UNK"),
                "name": base_token.get("name", "Unknown"),
                "address": base_token.get("address", "N/A"),
            },
            "quoteToken": {
                "symbol": quote_token.get("symbol", "UNK"),
                "name": quote_token.get("name", "Unknown"),
                "address": quote_token.get("address", "N/A"),
            },
            # Financial metrics
            "priceUsd": float(pair_data.get("priceUsd", 0)),
            "totalValueLockedUSD": tvl_usd,
            "volume24h": volume_24h,
            "volume1h": float(volume.get("h1", 0)),
            "priceChange24h": float(price_change.get("h24", 0)),
            "priceChange1h": float(price_change.get("h1", 0)),
            # Transactions
            "txns24h": {
                "buys": txns.get("h24", {}).get("buys", 0),
                "sells": txns.get("h24", {}).get("sells", 0),
                "total": txns.get("h24", {}).get("buys", 0)
                + txns.get("h24", {}).get("sells", 0),
            },
            # Derived metrics
            "estimatedAPY": min(estimated_apy, 999.9),  # Capped at 999.9%
            "volumeToTVLRatio": (volume_24h / tvl_usd) if tvl_usd > 0 else 0,
            # Metadata
            "lastUpdated": datetime.now().isoformat(),
            "dataSource": "DEXScreener",
            "url": pair_data.get("url", ""),
            "pairCreatedAt": pair_data.get("pairCreatedAt", 0),
        }


# Global client
dex_client = DexScreenerClient()


async def analyze_pool_real(
    pool_address: str = None, network: str = None
) -> Dict[str, Any]:
    """
    UNIVERSAL pool/token analysis using REAL DEXScreener data.

    - pool_address: Pool OR token address (any network)
    - network: Specific network (optional — if omitted, auto-detects)

    Works with:
    - Any pool on any DEX
    - Any token (searches its best pools)
    - Any supported network
    - Automatic network detection
    """
    if not pool_address:
        return {
            "status": "error",
            "message": "No address provided. Pass a pool or token address (0x…).",
            "timestamp": datetime.now().isoformat(),
        }

    # Validate address (0x + 40 hex characters)
    if not re.fullmatch(r"0x[0-9a-fA-F]{40}", pool_address):
        return {
            "status": "error",
            "message": f"Invalid address: {pool_address}. Must be 0x followed by 40 hex characters.",
            "timestamp": datetime.now().isoformat(),
        }

    # Fetch real data (universal)
    pool_data = await dex_client.get_pool_data(pool_address, network)

    if pool_data:
        return {
            "status": "success",
            "data": pool_data,
            "timestamp": datetime.now().isoformat(),
            "source": "DEXScreener Universal API",
            "networks_searched": config.api.PRIORITY_CHAINS
            if not network
            else [network],
        }
    else:
        return {
            "status": "error",
            "message": f"Pool/Token {pool_address[:12]}... not found on any network",
            "networks_searched": config.api.PRIORITY_CHAINS
            if not network
            else [network],
            "timestamp": datetime.now().isoformat(),
            "source": "DEXScreener Universal API",
        }


# Universal test function
async def test_universal_pool(address: str | None = None) -> Dict[str, Any] | None:
    """Test the universal implementation with any pool/token."""

    if not address:
        print("❌ No address provided. Pass a pool or token address.")
        return None

    result = await analyze_pool_real(address)

    if result["status"] == "success":
        data = result["data"]
        print("=" * 60)
        print(f"📊 REAL DATA - {data['name']}")
        print("=" * 60)
        print(f"🔥 Pool: {data['name']}")
        print(f"🏪 DEX: {data['dex'].title()}")
        print(f"🌐 Network: {data['network'].title()}")
        print(f"💰 Price: ${data['priceUsd']:,.6f}")
        print(f"💧 TVL: ${data['totalValueLockedUSD']:,.2f}")
        print(f"📈 Volume 24h: ${data['volume24h']:,.2f}")
        print(f"📊 Change 24h: {data['priceChange24h']:+.2f}%")
        print(f"🔥 Estimated APY: {data['estimatedAPY']:.1f}%")
        print(f"🔄 Transactions: {data['txns24h']['total']}")
        print(f"⚡ Updated: {data['lastUpdated'][:19]}")
        print(f"🔗 Link: {data['url']}")
        print("=" * 60)
        print(
            f"🌐 Networks checked: {', '.join(result.get('networks_searched', ['N/A']))}"
        )

        return data
    else:
        print(f"❌ {result['message']}")
        if "networks_searched" in result:
            print(f"🌐 Networks checked: {', '.join(result['networks_searched'])}")
        return None


if __name__ == "__main__":
    # Usage: python -m defi_cli.dexscreener_client <address>
    import sys as _sys

    _addr = _sys.argv[1] if len(_sys.argv) > 1 else None
    if not _addr:
        print("Usage: python -m defi_cli.dexscreener_client <pool_or_token_address>")
    else:
        asyncio.run(test_universal_pool(_addr))
