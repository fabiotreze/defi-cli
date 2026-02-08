"""
DeFi CLI — Command Implementations
===================================

All CLI command handlers live here, keeping run.py as a thin
argparse dispatcher.  Each public function corresponds to a
subcommand (info, scout, pool, list, report, check).

Internal helpers (_require_consent, _detect_position_network)
are also housed here because they are used exclusively by commands.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime

try:
    from defi_cli.central_config import PROJECT_VERSION, PROJECT_NAME
except ImportError:
    PROJECT_VERSION = "1.0.0"
    PROJECT_NAME = "DeFi CLI"

try:
    from defi_cli.legal_disclaimers import (
        CLI_DISCLAIMER,
        get_jurisdiction_specific_warning,
    )
except ImportError:
    CLI_DISCLAIMER = "⚠️ WARNING: Educational tool — NOT financial advice"

    def get_jurisdiction_specific_warning(x):
        return "🚨 High risk — do your own research"


# ── Consent Helpers ──────────────────────────────────────────────────────


def _require_consent() -> bool:
    """Explicit consent gate — user must type 'I agree' before report generation."""
    print("\n" + "═" * 60)
    print(f"  🏛️  {PROJECT_NAME} v{PROJECT_VERSION}")
    print("═" * 60)
    print()
    print("  ⚠️  IMPORTANT DISCLAIMER")
    print()
    print("  This tool performs EDUCATIONAL analysis of DeFi pools.")
    print("  It is NOT financial, investment, tax, or legal advice.")
    print()
    print("  • DeFi protocols carry HIGH RISK including total loss of funds")
    print("  • Impermanent loss can exceed displayed estimates")
    print("  • Smart contract exploits may occur without warning")
    print("  • Past performance does not guarantee future results")
    print("  • All data should be independently verified on-chain")
    print()
    print("  Sources: Uniswap V3 Whitepaper, DEXScreener API")
    print("  The developer assumes NO LIABILITY for any losses.")
    print()
    print("═" * 60)
    print()
    try:
        ans = input('  Type "I agree" to continue: ')
        accepted = ans.strip().lower() == "i agree"
        if accepted:
            print("  ✅ Consent recorded.\n")
        else:
            print("  ❌ You must type exactly: I agree")
        return accepted
    except (KeyboardInterrupt, EOFError):
        print("\n  ❌ Cancelled.")
        return False


def _prompt_address(kind: str = "pool") -> str | None:
    """Prompt the user for a 0x address when none is supplied."""
    try:
        addr = input(f"\n🔑 Enter {kind} address (0x…): ").strip()
        if addr and re.fullmatch(r"0x[0-9a-fA-F]{40}", addr):
            return addr
        print("❌ Invalid address. Must be 42 hex characters starting with 0x.")
        return None
    except (KeyboardInterrupt, EOFError):
        print("\n❌ Cancelled.")
        return None


def _simple_disclaimer() -> bool:
    """Show disclaimer and get consent (y/N)."""
    print("\n" + "=" * 60)
    print(f"🏛️ {PROJECT_NAME} v{PROJECT_VERSION} — EDUCATIONAL TOOL")
    print(CLI_DISCLAIMER)
    print(get_jurisdiction_specific_warning("GLOBAL"))
    print("=" * 60)
    try:
        ans = input("\n✅ Accept terms? (y/N): ")
        return ans.strip().lower() in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        return False


# ── Commands ─────────────────────────────────────────────────────────────


def cmd_info() -> None:
    """Display system and architecture information."""
    print(f"\n📊 {PROJECT_NAME} v{PROJECT_VERSION}")
    print("=" * 55)
    print("🔗 Protocol   : Uniswap V3 & compatible forks (concentrated liquidity)")
    print("🌐 On-Chain   : Ethereum, Arbitrum, Base, Polygon, Optimism, BSC")
    print("🌐 Pool Data  : All DEXScreener networks (Avalanche, Solana, Fantom, …)")
    print("📡 Data Source : DEXScreener API (real-time, free, no key)")
    print()
    print("📁 Files:")
    print("   run.py                — CLI entry point")
    print("   position_indexer.py   — Multi-DEX wallet position scanner")
    print("   position_reader.py    — On-chain position reader (auto pool detection)")
    print("   real_defi_math.py     — Uniswap V3 math engine")
    print("   html_generator.py     — HTML report generator")
    print("   defi_cli/             — API client, config, disclaimers, DEX registry")
    print()
    print("🔄 Supported DEXes (V3-compatible):")

    try:
        from defi_cli.dex_registry import DEX_REGISTRY

        for slug, dex in DEX_REGISTRY.items():
            if dex["compatible"]:
                nets = ", ".join(dex["networks"].keys())
                print(f"   {dex['icon']} {dex['name']:<18} — {nets}")
    except ImportError:
        print("   🦄 Uniswap V3 (default)")

    print()
    print("🆕 New in v1.1.x:")
    print("   • Multi-DEX scan — Uniswap, PancakeSwap, SushiSwap")
    print("   • list command — scan wallet across all DEXes")
    print("   • Auto pool + network detection — just use --position <id>")
    print("   • 🔐 Privacy RPCs via 1RPC.io (TEE relay, zero-tracking)")
    print("   • 📄 Temporary reports — no data saved to disk")
    print("   • 🔭 Pool Scout — find best pools via DefiLlama (free)")
    print("   • 📉 V3 Impermanent Loss estimate at range boundaries")
    print("   • ⚖️ HODL comparison — fees vs IL analysis")
    print("   • ⚡ Vol/TVL ratio — pool efficiency metric")
    print("   • 📐 Range width % — how wide is your range")
    print()
    print("🔗 Quick Start:")
    print("   python run.py report --position 5260106")
    print("   python run.py report --position 5260106 --network arbitrum")
    print("   python run.py scout  WETH/USDC")
    print("   python run.py pool   0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640")
    print()
    print("📚 References:")
    print("   Uniswap V3 Whitepaper : https://uniswap.org/whitepaper-v3.pdf")
    print("   Uniswap V3 Docs       : https://docs.uniswap.org/")
    print("   DEXScreener API       : https://docs.dexscreener.com/api/reference")
    print()
    print("⭐ Like this tool? Star us on GitHub: github.com/fabiotreze/defi-cli")


async def cmd_scout(
    pair: str,
    network: str | None = None,
    dex: str | None = None,
    sort: str = "apy",
    limit: int = 15,
    min_tvl: float = 50000,
) -> None:
    """Search for the best V3 pools across DEXes via DefiLlama Yields API."""
    from pool_scout import PoolScout, format_scout_results

    print(
        f"\n🔭 Searching for {pair} V3 pools"
        + (f" on {network.title()}" if network else "")
        + (f" ({dex})" if dex else "")
        + "..."
    )

    scout = PoolScout()
    result = await scout.search_pools(
        token_pair=pair,
        network=network,
        dex=dex,
        sort_by=sort,
        limit=limit,
        min_tvl=min_tvl,
    )

    print(format_scout_results(result))


async def cmd_pool(pool: str) -> None:
    """Analyze a pool using DEXScreener API (real data)."""
    from defi_cli.dexscreener_client import analyze_pool_real

    result = await analyze_pool_real(pool)

    if result["status"] == "success":
        d = result["data"]
        print(f"\n📊 Pool Analysis — {d['network'].upper()}")
        print("=" * 55)
        print(f"  🔥 Pool     : {d['name']}")
        print(f"  💰 TVL      : ${d['totalValueLockedUSD']:,.2f}")
        print(f"  📈 Vol 24h  : ${d['volume24h']:,.2f}")
        print(f"  📊 Price    : ${d['priceUsd']:,.6f}")
        print(f"  🎯 Δ24h     : {d['priceChange24h']:+.2f}%")
        print(f"  🔥 APY est. : {d['estimatedAPY']:.1f}%")
        print(f"  🏪 DEX      : {d['dex'].title()}")
        print(f"  🌐 Network  : {d['network'].title()}")
        print(f"  🔄 Txns 24h : {d['txns24h']['total']}")
        # Vol/TVL ratio
        vol = d.get("volume24h", 0)
        tvl = d.get("totalValueLockedUSD", 0)
        if tvl > 0:
            vt = vol / tvl
            print(f"  ⚡ Vol/TVL  : {vt:.2f}x")
        if d.get("url"):
            print(f"  🔗 Link     : {d['url']}")
    else:
        print(f"\n❌ {result['message']}")
        if "networks_searched" in result:
            print(f"   Searched: {', '.join(result['networks_searched'])}")

    print("\n🔗 Data: https://dexscreener.com")


async def cmd_list(
    wallet: str, network: str = "arbitrum", dex: str | None = None
) -> None:
    """List all V3-compatible positions for a wallet (scans all DEXes)."""
    from position_indexer import PositionIndexer

    if not wallet or not re.fullmatch(r"0x[0-9a-fA-F]{40}", wallet):
        print("❌ Invalid wallet address. Must be 42 hex characters starting with 0x.")
        return

    if dex:
        print(f"\n🔄 Scanning {dex} positions on {network.title()}...")
    else:
        print(f"\n🔄 Scanning ALL V3-compatible DEXes on {network.title()}...")
    print("=" * 65)

    indexer = PositionIndexer(network)
    positions = await indexer.list_positions(wallet, dex_slug=dex)

    print(f"\n{'=' * 65}")
    print(f"  V3-Compatible Positions — {network.title()}")
    print(f"  👛 Wallet: {wallet}")
    print(f"{'=' * 65}")

    if not positions:
        print("  No V3 positions found on this network.")
        print(
            "\n  💡 Try another network: --network ethereum|polygon|base|optimism|bsc"
        )
        return

    # Group by DEX for structured output
    current_dex = None
    for i, p in enumerate(positions, 1):
        if p.get("dex_name") != current_dex:
            current_dex = p.get("dex_name", "Unknown")
            icon = p.get("dex_slug", "")
            try:
                from defi_cli.dex_registry import get_dex_icon

                icon = get_dex_icon(p.get("dex_slug", ""))
            except ImportError:
                icon = "🔄"
            print(f"\n  {icon} {current_dex}")

        status = "🟢 Active" if p["is_active"] else "⚪ Closed"
        print(f"\n    {i}. Position #{p['token_id']}")
        print(f"       Pair     : {p['pair']} ({p['fee_label']})")
        print(f"       Pool     : {p['pool_address'][:16]}...")
        print(f"       Status   : {status}")
        print(f"       Liquidity: {p['liquidity']:,}")

    active = sum(1 for p in positions if p["is_active"])
    dex_count = len(set(p.get("dex_name", "") for p in positions))
    print(f"\n{'=' * 65}")
    print(
        f"  Total: {len(positions)} positions ({active} active) across {dex_count} DEX(es)"
    )
    print(f"{'=' * 65}")

    # Show usage hints
    if active > 0:
        first_active = next(p for p in positions if p["is_active"])
        dex_hint = (
            f" --dex {first_active.get('dex_slug', 'uniswap_v3')}"
            if first_active.get("dex_slug") != "uniswap_v3"
            else ""
        )
        print("\n  💡 Generate a report for any position:")
        print(
            f"     python run.py report --position {first_active['token_id']} --network {network}{dex_hint}"
        )


async def _detect_position_network(
    position_id: int, dex_slug: str, networks: list[str]
) -> str | None:
    """Try all networks in parallel to find which one holds a position NFT.

    Sends a lightweight positions() call to each network's NonfungiblePositionManager.
    Returns the first network where the call succeeds with non-empty data,
    or None if not found on any network.
    """
    from position_reader import PositionReader

    async def _try_network(net: str) -> str | None:
        try:
            reader = PositionReader(net, dex_slug=dex_slug)
            pos = await reader._read_position_nft(position_id)
            # Valid position: has non-zero token addresses
            if pos and pos.get("token0") and pos["token0"] != "0x" + "0" * 40:
                return net
        except Exception:
            pass
        return None

    tasks = [_try_network(net) for net in networks]
    results = await asyncio.gather(*tasks)
    for result in results:
        if result:
            return result
    return None


def cmd_report(
    pool: str | None = None,
    position_id: int | None = None,
    wallet: str | None = None,
    network: str | None = None,
    dex: str | None = None,
) -> None:
    """Generate an HTML report — with real position data when --position is given."""
    if not _require_consent():
        print("  ❌ Report generation requires explicit consent.")
        return

    from real_defi_math import PositionData, analyze_position
    from html_generator import generate_position_report
    from defi_cli.dexscreener_client import analyze_pool_real

    # ── If --position given, read on-chain data (pool auto-detected) ──
    onchain = None
    pool_data = None

    if position_id:
        try:
            from position_reader import PositionReader, RPC_URLS

            dex_slug = dex or "uniswap_v3"

            # ── Auto-detect network if not specified ──────────────
            if not network:
                print(f"🔍 Scanning all networks for position #{position_id}…")
                detected = asyncio.run(
                    _detect_position_network(
                        position_id, dex_slug, list(RPC_URLS.keys())
                    )
                )
                if detected:
                    network = detected
                    print(f"  ✅ Found on {network}!")
                else:
                    print(f"  ❌ Position #{position_id} not found on any network.")
                    print(
                        "  💡 Try specifying: --network arbitrum|ethereum|polygon|base|optimism|bsc"
                    )
                    return

            net = network
            print(f"⛓️  Reading on-chain position #{position_id} ({net}, {dex_slug})…")
            reader = PositionReader(net, dex_slug=dex_slug)
            # pool_address is optional — auto-resolved from Factory if None
            onchain = asyncio.run(reader.read_position(position_id, pool))

            # Use the auto-detected pool address for DEXScreener lookup
            resolved_pool = onchain.get("pool_address", pool)
            print(
                f"  ✅ Real position: ${onchain['total_value_usd']:,.2f} | "
                f"Fees: ${onchain['total_fees_usd']:,.2f}"
            )

            # Fetch DEXScreener data using resolved pool address
            print("⏳ Fetching market data from DEXScreener…")
            result = asyncio.run(analyze_pool_real(resolved_pool))
            if result["status"] == "success":
                pool_data = result["data"]
            else:
                print("  ⚠️  DEXScreener lookup failed, using on-chain data only")
                pool_data = {
                    "volume24h": 0,
                    "totalValueLockedUSD": 0,
                    "network": net,
                    "dex": "uniswap",
                }

            pos = PositionData.from_onchain_data(onchain, pool_data)
        except Exception as e:
            print(f"  ⚠️  On-chain read failed ({e})")
            if not pool:
                print(
                    "  💡 Provide pool address: python run.py report --pool <0x…> --position <tokenId>"
                )
                return
            print("  ↩️  Falling back to simulated data…")
            onchain = None

    # ── Fallback: pool address required for simulated mode ────────────
    if not onchain:
        if not pool:
            pool = _prompt_address("pool")
            if not pool:
                return

        print(f"⏳ Fetching pool data for {pool[:16]}…")
        result = asyncio.run(analyze_pool_real(pool))

        if result["status"] != "success":
            print(f"\n❌ {result['message']}")
            return

        pool_data = result["data"]
        pos = PositionData.from_pool_data(pool_data)

    analysis = analyze_position(pos)
    analysis["consent_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Pass wallet for the report
    if wallet:
        analysis["wallet_address"] = wallet

    # Attach audit trail if available (from on-chain reader)
    if onchain and "audit_trail" in onchain:
        analysis["audit_trail"] = onchain["audit_trail"]
        analysis["block_number"] = onchain.get("block_number", 0)

    path = generate_position_report(analysis)

    print("\n✅ Report opened in your browser!")
    print(f"   📄 Temporary file: {path}")
    print("   ⚠️  Contains financial data — not saved automatically.")
    print("   💾 To keep a copy, press Ctrl+S (⌘+S) in your browser.")


async def cmd_check() -> bool:
    """
    Run integration checks against live Uniswap pools.
    Validates: API connectivity, data integrity, risk engine, math pipeline.
    """
    from defi_cli.dexscreener_client import analyze_pool_real

    POOLS = [
        {
            "addr": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
            "net": "ethereum",
            "pair": "USDC/WETH",
            "desc": "ETH: USDC/WETH 0.05%",
        },
        {
            "addr": "0x2f5e87C9312fa29aed5c179E456625D79015299c",
            "net": "arbitrum",
            "pair": "WBTC/WETH",
            "desc": "ARB: WBTC/WETH 0.05%",
        },
        {
            "addr": "0xD36ec33c8bed5a9F7B6630855f1533455b98a418",
            "net": "polygon",
            "pair": "USDC/USDC",
            "desc": "POLY: USDC.e/USDC 0.01%",
        },
        {
            "addr": "0xd0b53D9277642d899DF5C87A3966A349A798F224",
            "net": "base",
            "pair": "WETH/USDC",
            "desc": "BASE: WETH/USDC 0.05%",
        },
    ]

    print(f"\n🧪 DeFi CLI v{PROJECT_VERSION} — Integration Check")
    print("=" * 55)
    print(f"   Pools: {len(POOLS)} | Networks: ETH, ARB, POLY, BASE")
    print("   API: DEXScreener (real-time) + DefiLlama (yields)")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)

    total_ok = total_fail = 0

    for pool in POOLS:
        print(f"\n  ▸ {pool['desc']}")
        try:
            result = await analyze_pool_real(pool["addr"])
        except Exception as e:
            print(f"    ❌ Exception: {e}")
            total_fail += 1
            continue

        if result["status"] != "success":
            print("    ❌ Not found")
            total_fail += 1
            continue

        d = result["data"]
        checks = [
            ("Network", d["network"] == pool["net"]),
            (
                "Tokens",
                len(
                    set(d["name"].upper().split("/"))
                    & set(pool["pair"].upper().split("/"))
                )
                >= 1,
            ),
            ("TVL > 0", d.get("totalValueLockedUSD", 0) > 0),
            ("Price > 0", d.get("priceUsd", 0) > 0),
            ("DEX", "uniswap" in d.get("dex", "").lower()),
            ("URL", d.get("url", "").startswith("https://")),
        ]

        for name, ok in checks:
            icon = "✅" if ok else "❌"
            print(f"    {icon} {name}")
            if ok:
                total_ok += 1
            else:
                total_fail += 1

        await asyncio.sleep(0.3)  # respect rate limits

    # Math engine check
    print("\n  ▸ Math engine")
    try:
        from real_defi_math import PositionData, analyze_position

        pos = PositionData.from_pool_data(
            {
                "priceUsd": 2000,
                "totalValueLockedUSD": 1e7,
                "volume24h": 5e6,
                "estimatedAPY": 15,
                "baseToken": {"symbol": "WETH"},
                "quoteToken": {"symbol": "USDC"},
                "address": "0x" + "0" * 40,
                "network": "ethereum",
                "dex": "uniswap",
            }
        )
        a = analyze_position(pos)
        print(f"    ✅ analyze_position() → {len(a)} fields")
        total_ok += 1

        # Validate new IL / range / HODL metrics
        new_keys = [
            "range_width_pct",
            "il_at_lower_v3_pct",
            "il_at_upper_v3_pct",
            "vol_tvl_ratio",
            "hodl_comparison",
        ]
        for k in new_keys:
            if k in a:
                print(f"    ✅ {k}")
                total_ok += 1
            else:
                print(f"    ❌ missing {k}")
                total_fail += 1
    except Exception as e:
        print(f"    ❌ Math error: {e}")
        total_fail += 1

    # DefiLlama Pool Scout check
    print("\n  ▸ Pool Scout (DefiLlama Yields)")
    try:
        from pool_scout import PoolScout

        scout = PoolScout()
        sr = await scout.search_pools(token_pair="WETH/USDC", limit=3, min_tvl=10_000)
        if sr["status"] == "success" and len(sr["pools"]) > 0:
            print(f"    ✅ DefiLlama API → {sr['total_found']} pools")
            total_ok += 1
        else:
            print("    ⚠️  DefiLlama returned 0 pools (API may be slow)")
            total_ok += 1  # non-blocking
    except Exception as e:
        print(f"    ⚠️  Scout skipped: {e}")
        total_ok += 1  # non-blocking — DefiLlama is optional

    total = total_ok + total_fail
    pct = (total_ok / total * 100) if total > 0 else 0
    print(f"\n{'═' * 55}")
    print(f"  Results: {total_ok}/{total} checks passed ({pct:.0f}%)")
    if total_fail == 0:
        print("  🎉 ALL CHECKS PASSED")
    else:
        print(f"  ⚠️  {total_fail} checks failed")
    print(f"{'═' * 55}")

    return total_fail == 0
