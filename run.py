#!/usr/bin/env python3
"""
DeFi CLI v1.0.0 — Educational DeFi Analyzer
============================================

Usage:
  python run.py pool   <address>                  Analyse any pool (DEXScreener API)
  python run.py report <address> --position <id>   Generate report with real position data
  python run.py report <address>                   Generate report (simulated position)
  python run.py check                              Validate app against live Uniswap pools
  python run.py info                               System & architecture overview

Sources:
  Uniswap V3 Whitepaper : https://uniswap.org/whitepaper-v3.pdf
  Uniswap V3 Docs       : https://docs.uniswap.org/
  DEXScreener API        : https://docs.dexscreener.com/api/reference
"""

import sys
import asyncio
import argparse
import re
from pathlib import Path
from datetime import datetime

# ── Imports ───────────────────────────────────────────────────────────────

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from defi_cli.central_config import PROJECT_VERSION, PROJECT_NAME
except ImportError:
    PROJECT_VERSION = "1.0.0"
    PROJECT_NAME = "DeFi CLI"

try:
    from defi_cli.legal_disclaimers import (
        CLI_DISCLAIMER,
        get_jurisdiction_specific_warning,
        show_donation_addresses,
    )
except ImportError:
    CLI_DISCLAIMER = "⚠️ WARNING: Educational tool — NOT financial advice"
    get_jurisdiction_specific_warning = lambda x: "🚨 High risk — do your own research"
    show_donation_addresses = lambda: "💝 Donation info unavailable"


# ── Helpers ───────────────────────────────────────────────────────────────

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
            print('  ❌ You must type exactly: I agree')
        return accepted
    except (KeyboardInterrupt, EOFError):
        print("\n  ❌ Cancelled.")
        return False


# ── Commands ──────────────────────────────────────────────────────────────

def cmd_info():
    """Display system and architecture information."""
    print(f"\n📊 {PROJECT_NAME} v{PROJECT_VERSION}")
    print("=" * 55)
    print("🔗 Protocol   : Uniswap V3 (concentrated liquidity)")
    print("🌐 On-Chain   : Ethereum, Arbitrum, Base, Polygon, Optimism")
    print("🌐 Pool Data  : All DEXScreener networks (Avalanche, Solana, Fantom, …)")
    print("📡 Data Source : DEXScreener API (real-time, free, no key)")
    print()
    print("📁 Files:")
    print("   run.py                — CLI entry point")
    print("   real_defi_math.py     — Uniswap V3 math engine")
    print("   html_generator.py     — HTML report generator")
    print("   defi_cli/             — API client, config, disclaimers")
    print()
    print("📚 References:")
    print("   Uniswap V3 Whitepaper : https://uniswap.org/whitepaper-v3.pdf")
    print("   Uniswap V3 Docs       : https://docs.uniswap.org/")
    print("   DEXScreener API       : https://docs.dexscreener.com/api/reference")
    print()
    print("💝 Support: Donation addresses in disclaimers")


async def cmd_pool(address: str):
    """Analyse a pool using DEXScreener API (real data)."""
    from defi_cli.dexscreener_client import analyze_pool_real

    result = await analyze_pool_real(address)

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
        if d.get("url"):
            print(f"  🔗 Link     : {d['url']}")
    else:
        print(f"\n❌ {result['message']}")
        if "networks_searched" in result:
            print(f"   Searched: {', '.join(result['networks_searched'])}")

    print("\n🔗 Data: https://dexscreener.com")


def cmd_report(address: str = None, position_id: int = None,
               wallet: str = None, network: str = None):
    """Generate an HTML report — with real position data when --position is given."""
    if not _require_consent():
        print("  ❌ Report generation requires explicit consent.")
        return

    from real_defi_math import PositionData, analyze_position
    from html_generator import generate_position_report
    from defi_cli.dexscreener_client import analyze_pool_real

    if not address:
        address = _prompt_address("pool")
        if not address:
            return

    # ── Fetch DEXScreener pool data (always) ─────────────────────────
    print(f"⏳ Fetching pool data for {address[:16]}…")
    result = asyncio.run(analyze_pool_real(address))

    if result["status"] != "success":
        print(f"\n❌ {result['message']}")
        return

    pool_data = result["data"]

    # ── If --position given, read real on-chain data ─────────────────
    if position_id:
        try:
            from position_reader import PositionReader
            net = network or pool_data.get("network", "arbitrum")
            print(f"⛓️  Reading on-chain position #{position_id} ({net})…")
            reader = PositionReader(net)
            onchain = asyncio.run(reader.read_position(position_id, address))

            # Build PositionData from REAL on-chain data
            pos = PositionData.from_onchain_data(onchain, pool_data)
            print(f"  ✅ Real position: ${onchain['total_value_usd']:,.2f} | "
                  f"Fees: ${onchain['total_fees_usd']:,.2f}")
        except Exception as e:
            print(f"  ⚠️  On-chain read failed ({e}), using simulated data")
            pos = PositionData.from_pool_data(pool_data)
            onchain = None
    else:
        pos = PositionData.from_pool_data(pool_data)
        onchain = None

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

    print(f"\n✅ Report generated!")
    print(f"   📄 {path}")
    print(f"\n   Open:  open \"{path}\"")





async def cmd_check():
    """
    Run integration checks against live Uniswap pools.
    Validates: API connectivity, data integrity, risk engine, math pipeline.
    """
    from defi_cli.dexscreener_client import analyze_pool_real

    POOLS = [
        {"addr": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
         "net": "ethereum", "pair": "USDC/WETH", "desc": "ETH: USDC/WETH 0.05%"},
        {"addr": "0x2f5e87C9312fa29aed5c179E456625D79015299c",
         "net": "arbitrum", "pair": "WBTC/WETH", "desc": "ARB: WBTC/WETH 0.05%"},
        {"addr": "0xD36ec33c8bed5a9F7B6630855f1533455b98a418",
         "net": "polygon", "pair": "USDC/USDC", "desc": "POLY: USDC.e/USDC 0.01%"},
        {"addr": "0xd0b53D9277642d899DF5C87A3966A349A798F224",
         "net": "base", "pair": "WETH/USDC", "desc": "BASE: WETH/USDC 0.05%"},
    ]

    print(f"\n🧪 DeFi CLI v{PROJECT_VERSION} — Integration Check")
    print("=" * 55)
    print(f"   Pools: {len(POOLS)} | Chains: ETH, ARB, POLY, BASE")
    print(f"   API: DEXScreener (real-time)")
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
            print(f"    ❌ Not found")
            total_fail += 1
            continue

        d = result["data"]
        checks = [
            ("Network",   d["network"] == pool["net"]),
            ("Tokens",    len(set(d["name"].upper().split("/")) &
                              set(pool["pair"].upper().split("/"))) >= 1),
            ("TVL > 0",   d.get("totalValueLockedUSD", 0) > 0),
            ("Price > 0", d.get("priceUsd", 0) > 0),
            ("DEX",       "uniswap" in d.get("dex", "").lower()),
            ("URL",       d.get("url", "").startswith("https://")),
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
    print(f"\n  ▸ Math engine")
    try:
        from real_defi_math import PositionData, analyze_position
        pos = PositionData.from_pool_data({
            "priceUsd": 2000, "totalValueLockedUSD": 1e7,
            "volume24h": 5e6, "estimatedAPY": 15,
            "baseToken": {"symbol": "WETH"}, "quoteToken": {"symbol": "USDC"},
            "address": "0x" + "0" * 40, "network": "ethereum", "dex": "uniswap",
        })
        a = analyze_position(pos)
        print(f"    ✅ analyze_position() → {len(a)} fields")
        total_ok += 1
    except Exception as e:
        print(f"    ❌ Math error: {e}")
        total_fail += 1

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


# ── CLI Parser ────────────────────────────────────────────────────────────

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defi-cli",
        description=f"DeFi CLI v{PROJECT_VERSION} — Educational DeFi Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py pool   0x88e6…                          Analyse USDC/WETH pool
  python run.py report 0x88e6…                           Report (simulated)
  python run.py report <pool> --position <nft_id>        Report with real data
  python run.py check                                    Integration tests
  python run.py info                                     System overview

How to find your Pool Address and Position ID:
  1. Go to https://app.uniswap.org → Pool → click your position
  2. The URL will look like: app.uniswap.org/positions/v3/<network>/<nft_id>
     → Position ID = the number at the end, Network = the chain name
  3. Click the pool link (e.g. "WETH/USDT 0.05%") → the URL contains the pool address:
     app.uniswap.org/explore/pools/<network>/<pool_address>
     → Pool Address = the 0x… address
  4. Your wallet address is in MetaMask (or your wallet app) → copy address

Sources:
  DEXScreener API  : https://docs.dexscreener.com/api/reference
  Uniswap V3 Docs  : https://docs.uniswap.org/
  GitHub           : https://github.com/fabiotreze/defi-cli
""",
    )
    parser.add_argument("--version", action="version",
                        version=f"DeFi CLI v{PROJECT_VERSION}")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    pool_p = sub.add_parser("pool", help="Analyse a pool (DEXScreener)")
    pool_p.add_argument("address", nargs="?", help="Pool or token address (0x…)")

    report_p = sub.add_parser("report", help="Generate HTML pool report")
    report_p.add_argument("address", nargs="?", help="Pool address (0x…). Find it on Uniswap: app.uniswap.org → Pool → click your position → pool address in the URL")
    report_p.add_argument("--position", type=int, default=None,
                          help="Uniswap V3 position NFT ID (reads real data from chain). "
                               "Find it on Uniswap: app.uniswap.org → Pool → click your position → the number in the URL (e.g. /positions/v3/arbitrum/1234567 → 1234567)")
    report_p.add_argument("--wallet", type=str, default=None,
                          help="Your wallet address (0x…). Find it in MetaMask or your wallet app → copy address")
    report_p.add_argument("--network", type=str, default=None,
                          help="Network: arbitrum, ethereum, polygon, base, optimism (auto-detected if omitted)")

    sub.add_parser("check", help="Run integration validation")
    sub.add_parser("donate", help="Show donation addresses")
    sub.add_parser("info", help="System & architecture info")

    return parser


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    # No-consent commands
    if args.command == "info":
        cmd_info()
        return 0
    if args.command == "check":
        ok = asyncio.run(cmd_check())
        return 0 if ok else 1
    if args.command == "donate":
        from defi_cli.legal_disclaimers import show_donation_addresses
        print(show_donation_addresses())
        return 0

    # Consent-required commands
    if args.command == "report":
        cmd_report(
            address=getattr(args, "address", None),
            position_id=getattr(args, "position", None),
            wallet=getattr(args, "wallet", None),
            network=getattr(args, "network", None),
        )
        return 0

    if args.command == "pool":
        if not _simple_disclaimer():
            print("❌ Consent required.")
            return 1
        addr = args.address
        if not addr:
            addr = _prompt_address("pool")
        if not addr:
            return 1
        asyncio.run(cmd_pool(addr))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n❌ Cancelled.")
        sys.exit(130)

