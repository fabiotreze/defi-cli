#!/usr/bin/env python3
"""
Multi-DEX V3 Position Indexer — Wallet Scanner
===============================================

Discovers ALL V3-compatible positions owned by a wallet address.
Scans NonfungiblePositionManager contracts from multiple DEXes:

  Supported DEXes:
    🦄 Uniswap V3    — The original concentrated liquidity protocol
    🥞 PancakeSwap V3 — V3 fork, same positions() ABI
    🍣 SushiSwap V3   — V3 fork, same positions() ABI

Flow per DEX:
  1. balanceOf(wallet)         → How many V3 NFTs the wallet holds
  2. tokenOfOwnerByIndex(w, i) → Token ID at index i
  3. positions(tokenId)        → Position data (token0, token1, fee, ticks, liquidity)
  4. Factory.getPool(t0,t1,f)  → Resolve pool address from token pair + fee

All data comes from public JSON-RPC — no API key, no subgraph, no web3.py.

Contract References:
  NonfungiblePositionManager: https://github.com/Uniswap/v3-periphery/blob/main/contracts/NonfungiblePositionManager.sol
  ERC-721 Enumerable:         https://eips.ethereum.org/EIPS/eip-721
  UniswapV3Factory:           https://github.com/Uniswap/v3-core/blob/main/contracts/UniswapV3Factory.sol
"""

import asyncio
import sys
from typing import Dict, List

from defi_cli.rpc_helpers import (
    # Constants
    RPC_URLS,
    SELECTORS,
    # Encoding
    encode_uint256 as _encode_uint256,
    encode_address as _encode_address,
    encode_uint24 as _encode_uint24,
    # Decoding
    decode_uint as _decode_uint,
    decode_int as _decode_int,
    decode_address as _decode_address,
    decode_string as _decode_string,
    # RPC
    eth_call as _eth_call,
    eth_call_batch as _eth_call_batch,
    # Symbol normalization
    normalize_symbol as _normalize_symbol,
)

# ── DEX Registry (contract addresses per DEX per network) ──────────────
try:
    from defi_cli.dex_registry import (
        get_dexes_for_network,
        get_dex_display_name,
        get_dex_icon,
    )

    _HAS_REGISTRY = True
except ImportError:
    _HAS_REGISTRY = False

# Fallback: Uniswap V3 only (if registry not available)
_FALLBACK_POSITION_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
_FALLBACK_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"

# RPC_URLS and SELECTORS are imported from defi_cli.rpc_helpers (single source of truth).
# ABI encoding/decoding and JSON-RPC client also imported from rpc_helpers.


# ── Progress Bar Helper ─────────────────────────────────────────────────


class ScanProgress:
    """Inline progress bar for wallet scan — zero dependencies."""

    def __init__(self, total: int, bar_width: int = 25):
        self._total = total
        self._done = 0
        self._bar_width = bar_width
        self._hits: list[str] = []  # lines to print above the bar

    def advance(
        self,
        icon: str,
        dex_name: str,
        network: str,
        found: int = 0,
        error: str = "",
    ) -> None:
        """Mark one scan step complete and redraw the progress bar."""
        self._done += 1
        pct = int(self._done / self._total * 100) if self._total else 100
        filled = int(pct / 100 * self._bar_width)
        bar = "█" * filled + "░" * (self._bar_width - filled)

        # If positions were found, print a persistent line above the bar
        if found > 0:
            line = f"  {icon} {dex_name:<16s} {network} — ✅ {found} NFTs"
            self._hits.append(line)
            sys.stdout.write(f"\r{' ' * 80}\r")  # clear bar line
            sys.stdout.write(f"{line}\n")
        elif error:
            line = f"  {icon} {dex_name:<16s} {network} — ⚠️  {error}"
            self._hits.append(line)
            sys.stdout.write(f"\r{' ' * 80}\r")
            sys.stdout.write(f"{line}\n")

        # Draw/update the progress bar
        label = f"{icon} {dex_name:<16s} {network}"
        if self._done >= self._total:
            sys.stdout.write(f"\r  [{'█' * self._bar_width}] 100%  Done!{' ' * 30}\n")
        else:
            sys.stdout.write(f"\r  [{bar}] {pct:3d}%  {label}{' ' * 10}")
        sys.stdout.flush()


# ── Position Indexer ────────────────────────────────────────────────────


class PositionIndexer:
    """
    Discovers all V3-compatible positions owned by a wallet.
    Scans multiple DEXes (Uniswap, PancakeSwap, SushiSwap).

    Usage:
        indexer = PositionIndexer("arbitrum")
        positions = await indexer.list_positions("0x...wallet...")

    Returns:
        List of dicts with position summary (token_id, pair, fee, dex, in_range).
    """

    def __init__(self, network: str = "arbitrum"):
        if network not in RPC_URLS:
            raise ValueError(
                f"Unsupported network: {network}. Available: {list(RPC_URLS.keys())}"
            )
        self.network = network
        self.rpc_url = RPC_URLS[network]

    def _get_dex_contracts(self, dex_slug: str = None) -> List[dict]:
        """
        Get position manager + factory contracts to scan.

        If dex_slug is given, return only that DEX.
        If None, return all compatible DEXes for the network.
        """
        if _HAS_REGISTRY:
            if dex_slug:
                from defi_cli.dex_registry import (
                    get_position_manager_address,
                    get_factory_address,
                )

                pm = get_position_manager_address(dex_slug, self.network)
                factory = get_factory_address(dex_slug, self.network)
                if pm and factory:
                    return [
                        {
                            "slug": dex_slug,
                            "name": get_dex_display_name(dex_slug),
                            "icon": get_dex_icon(dex_slug),
                            "position_manager": pm,
                            "factory": factory,
                        }
                    ]
                return []
            return get_dexes_for_network(self.network)
        else:
            # Fallback: Uniswap V3 only
            return [
                {
                    "slug": "uniswap_v3",
                    "name": "Uniswap V3",
                    "icon": "🦄",
                    "position_manager": _FALLBACK_POSITION_MANAGER,
                    "factory": _FALLBACK_FACTORY,
                }
            ]

    async def get_position_count(self, wallet: str, position_manager: str) -> int:
        """
        Get number of V3 position NFTs owned by a wallet.
        Calls: balanceOf(address) on NonfungiblePositionManager.
        """
        calldata = SELECTORS["balanceOf"] + _encode_address(wallet)
        result = await _eth_call(self.rpc_url, position_manager, calldata)
        return _decode_uint(result, 0)

    async def get_token_ids(
        self, wallet: str, count: int, position_manager: str
    ) -> List[int]:
        """
        Get all token IDs for a wallet using tokenOfOwnerByIndex.
        Batches all calls in a single RPC request for efficiency.
        """
        if count == 0:
            return []

        calls = []
        for i in range(count):
            calldata = (
                SELECTORS["tokenOfOwnerByIndex"]
                + _encode_address(wallet)
                + _encode_uint256(i)
            )
            calls.append((position_manager, calldata))

        try:
            results = await _eth_call_batch(self.rpc_url, calls)
        except Exception:  # noqa: BLE001
            # Fallback to sequential
            results = []
            for to, data in calls:
                try:
                    r = await _eth_call(self.rpc_url, to, data)
                    results.append(r)
                except Exception:  # noqa: BLE001
                    results.append("")

        token_ids = []
        for r in results:
            if r:
                token_ids.append(_decode_uint(r, 0))
        return token_ids

    async def read_position_summary(
        self,
        token_id: int,
        position_manager: str,
        factory: str,
        dex_slug: str = "uniswap_v3",
        dex_name: str = "Uniswap V3",
    ) -> Dict:
        """
        Read minimal position data for listing purposes.
        Calls positions(tokenId) to get token0, token1, fee, ticks, liquidity.
        Then resolves token symbols, pool address, and basic price info.
        """
        # Step 1: Read position NFT
        calldata = SELECTORS["positions"] + _encode_uint256(token_id)
        result = await _eth_call(self.rpc_url, position_manager, calldata)

        pos = {
            "token0": _decode_address(result, 2),
            "token1": _decode_address(result, 3),
            "fee": _decode_uint(result, 4),
            "tickLower": _decode_int(result, 5),
            "tickUpper": _decode_int(result, 6),
            "liquidity": _decode_uint(result, 7),
        }

        # Step 2: Batch — token symbols + pool address
        pool_calldata = (
            SELECTORS["getPool"]
            + _encode_address(pos["token0"])
            + _encode_address(pos["token1"])
            + _encode_uint24(pos["fee"])
        )
        batch_calls = [
            (pos["token0"], SELECTORS["symbol"]),
            (pos["token1"], SELECTORS["symbol"]),
            (factory, pool_calldata),
        ]

        try:
            batch = await _eth_call_batch(self.rpc_url, batch_calls)
        except Exception:  # noqa: BLE001
            batch = ["", "", ""]
            for i, (to, data) in enumerate(batch_calls):
                try:
                    batch[i] = await _eth_call(self.rpc_url, to, data)
                except Exception:  # noqa: BLE001
                    pass

        symbol0 = _normalize_symbol(_decode_string(batch[0])) if batch[0] else "TOKEN0"
        symbol1 = _normalize_symbol(_decode_string(batch[1])) if batch[1] else "TOKEN1"
        pool_address = _decode_address(batch[2], 0) if batch[2] else "0x" + "0" * 40

        # Fee tier label
        fee_pct = pos["fee"] / 10_000  # 500 → 0.05, 3000 → 0.30, 10000 → 1.00
        fee_labels = {100: "0.01%", 500: "0.05%", 3000: "0.30%", 10000: "1.00%"}
        fee_label = fee_labels.get(pos["fee"], f"{fee_pct:.2f}%")

        is_active = pos["liquidity"] > 0

        return {
            "token_id": token_id,
            "token0_symbol": symbol0,
            "token1_symbol": symbol1,
            "token0_address": pos["token0"],
            "token1_address": pos["token1"],
            "pair": f"{symbol0}/{symbol1}",
            "fee_raw": pos["fee"],
            "fee_label": fee_label,
            "fee_tier": pos["fee"] / 1_000_000,
            "tick_lower": pos["tickLower"],
            "tick_upper": pos["tickUpper"],
            "liquidity": pos["liquidity"],
            "is_active": is_active,
            "pool_address": pool_address,
            "network": self.network,
            "protocol_version": "v3",
            "dex_slug": dex_slug,
            "dex_name": dex_name,
            "position_manager": position_manager,
            "factory": factory,
        }

    async def list_positions(
        self,
        wallet: str,
        dex_slug: str | None = None,
        progress: ScanProgress | None = None,
    ) -> List[Dict]:
        """
        Discover and list ALL V3-compatible positions for a wallet.

        Scans all compatible DEXes on the network (or a specific one if dex_slug
        is provided).

        Flow per DEX:
          1. balanceOf(wallet) → count
          2. tokenOfOwnerByIndex(wallet, 0..count-1) → token IDs
          3. For each tokenId: positions(id) → summary

        Args:
            wallet: Ethereum wallet address (0x...)
            dex_slug: Optional DEX slug (e.g., "uniswap_v3") to scan only one DEX.
                      If None, scans all compatible DEXes on the network.
            progress: Optional ScanProgress for inline progress bar updates.

        Returns:
            List of position summaries, sorted by DEX then liquidity (active first).
        """
        if not wallet or not wallet.startswith("0x") or len(wallet) != 42:
            raise ValueError(f"Invalid wallet address: {wallet}")

        dex_contracts = self._get_dex_contracts(dex_slug)
        if not dex_contracts:
            print(f"  ⚠️  No compatible DEXes found for {self.network}")
            return []

        all_positions = []

        async def _scan_dex(dex: Dict) -> List[Dict]:
            """Scan a single DEX for positions (runs concurrently)."""
            dex_name = dex["name"]
            dex_icon = dex["icon"]
            pm = dex["position_manager"]
            factory = dex["factory"]
            positions = []

            if not progress:
                print(f"\n  {dex_icon} Scanning {dex_name} — {self.network.title()}...")
                print(f"     PositionManager: {pm[:16]}...")

            try:
                # Step 1: Count
                count = await self.get_position_count(wallet, pm)
                if not progress:
                    print(f"     📊 Found {count} position NFT(s)")

                if count == 0:
                    if progress:
                        progress.advance(dex_icon, dex_name, self.network, found=0)
                    return positions

                # Step 2: Get all token IDs
                token_ids = await self.get_token_ids(wallet, count, pm)
                if not progress:
                    print(f"     📋 Token IDs: {token_ids}")

                # Step 3: Read each position summary (parallel per DEX)
                async def _read(tid):
                    try:
                        summary = await self.read_position_summary(
                            tid,
                            pm,
                            factory,
                            dex_slug=dex["slug"],
                            dex_name=dex_name,
                        )
                        if not progress:
                            status = (
                                "🟢 Active" if summary["is_active"] else "⚪ Closed"
                            )
                            print(
                                f"     #{tid} — {summary['pair']} "
                                f"{summary['fee_label']} — {status}"
                            )
                        return summary
                    except Exception:
                        if not progress:
                            print(f"     #{tid} — ❌ Position read failed")
                        return None

                summaries = await asyncio.gather(*[_read(tid) for tid in token_ids])
                positions = [s for s in summaries if s is not None]

                if progress:
                    progress.advance(
                        dex_icon, dex_name, self.network, found=len(positions)
                    )

            except Exception:
                if progress:
                    progress.advance(
                        dex_icon, dex_name, self.network, error="scan failed"
                    )
                else:
                    print(f"     ❌ {dex_name} scan failed")

            return positions

        # Scan all DEXes in parallel — each hits independent contracts
        dex_results = await asyncio.gather(
            *[_scan_dex(dex) for dex in dex_contracts],
            return_exceptions=True,
        )
        for result in dex_results:
            if isinstance(result, list):
                all_positions.extend(result)
            elif isinstance(result, Exception):
                print("     ❌ DEX scan encountered an error")

        # Sort: active positions first, then by token_id descending
        all_positions.sort(key=lambda p: (-int(p["is_active"]), -p["token_id"]))

        return all_positions


# ── Standalone CLI ──────────────────────────────────────────────────────


async def _main(
    wallet: str, network: str = "arbitrum", dex_slug: str | None = None
) -> List[Dict]:
    """Quick test: list all V3-compatible positions for a wallet."""
    indexer = PositionIndexer(network)
    positions = await indexer.list_positions(wallet, dex_slug=dex_slug)

    print(f"\n{'=' * 65}")
    if dex_slug:
        from defi_cli.dex_registry import get_dex_display_name

        print(f"  {get_dex_display_name(dex_slug)} Positions — {network.title()}")
    else:
        print(f"  All V3-Compatible Positions — {network.title()}")
    print(f"  👛 Wallet: {wallet[:6]}…{wallet[-4:]}")
    print(f"{'=' * 65}")

    if not positions:
        print("  No positions found.")
        return positions

    # Group by DEX
    from itertools import groupby

    for dex_name, group in groupby(positions, key=lambda p: p["dex_name"]):
        group_list = list(group)
        print(f"\n  {group_list[0].get('dex_slug', '')} — {dex_name}")
        for i, p in enumerate(group_list, 1):
            status = "🟢 Active" if p["is_active"] else "⚪ Closed"
            print(f"\n    {i}. Position #{p['token_id']}")
            print(f"       Pair     : {p['pair']} ({p['fee_label']})")
            print(f"       Pool     : {p['pool_address'][:16]}...")
            print(f"       DEX      : {p['dex_name']}")
            print(f"       Status   : {status}")
            print(f"       Liquidity: {p['liquidity']:,}")

    print(f"\n{'=' * 65}")
    active = sum(1 for p in positions if p["is_active"])
    dex_count = len(set(p["dex_name"] for p in positions))
    print(
        f"  Total: {len(positions)} positions ({active} active) across {dex_count} DEX(es)"
    )
    print(f"{'=' * 65}")

    return positions


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python position_indexer.py <wallet_address> [network] [dex_slug]")
        print("  wallet_address : Your Ethereum wallet (0x...)")
        print(
            "  network        : arbitrum | ethereum | polygon | base | optimism | bsc"
        )
        print("  dex_slug       : uniswap_v3 | pancakeswap_v3 | sushiswap_v3")
        print("                   (omit to scan ALL compatible DEXes)")
        sys.exit(1)
    _wallet = sys.argv[1]
    _net = sys.argv[2] if len(sys.argv) > 2 else "arbitrum"
    _dex = sys.argv[3] if len(sys.argv) > 3 else None
    asyncio.run(_main(_wallet, _net, _dex))
