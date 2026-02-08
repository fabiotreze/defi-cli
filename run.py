#!/usr/bin/env python3
"""
DeFi CLI -- Educational DeFi Analyzer
============================================

Multi-DEX V3-compatible position scanner and analyzer.
Supports: Uniswap V3, PancakeSwap V3, SushiSwap V3.

Usage:
  python run.py list   <wallet> --network <net>                 Scan all DEXes for positions
  python run.py list   <wallet> --network <net> --dex <slug>    Scan specific DEX only
  python run.py pool   --pool <0x…>                             Analyze any pool (DEXScreener)
  python run.py scout  WETH/USDC                                Find best V3 pools for a pair
  python run.py scout  WETH/USDC --network arbitrum             Filter by network
  python run.py report --position <tokenId> --dex <slug>        Report for specific DEX position
  python run.py report --position <tokenId>                     Report (auto-detect network + pool)
  python run.py report --pool <0x…> --position <tokenId>        Report with explicit pool
  python run.py report --pool <0x…>                             Report (simulated position)
  python run.py check                                           Validate app against live pools
  python run.py info                                            System overview + DEX support

Sources:
  Uniswap V3 Whitepaper : https://uniswap.org/whitepaper-v3.pdf
  Uniswap V3 Docs       : https://docs.uniswap.org/
  DEXScreener API        : https://docs.dexscreener.com/api/reference
  DefiLlama Yields API   : https://defillama.com/docs/api
"""

import sys
import asyncio
import argparse
from pathlib import Path

# ── Imports ───────────────────────────────────────────────────────────────

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from defi_cli.central_config import PROJECT_VERSION, PROJECT_NAME
except ImportError:
    PROJECT_VERSION = "1.0.0"
    PROJECT_NAME = "DeFi CLI"

from defi_cli.commands import (
    cmd_info,
    cmd_scout,
    cmd_pool,
    cmd_list,
    cmd_report,
    cmd_check,
    _simple_disclaimer,
    _prompt_address,
)


# ── CLI Parser ────────────────────────────────────────────────────────────


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="defi-cli",
        description=f"DeFi CLI v{PROJECT_VERSION} — Educational DeFi Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py list   0xWALLET --network arbitrum       Scan ALL DEXes for V3 positions
  python run.py list   0xWALLET --dex pancakeswap_v3     Scan PancakeSwap only
  python run.py report --position 5260106                     Report (auto-detect network + pool)
  python run.py report --position 5260106 --network arb        Report on specific network
  python run.py report --position <tokenId> --dex sushiswap_v3 Report for SushiSwap position
  python run.py report --pool <0x…> --position <tokenId>       Report with explicit pool
  python run.py pool   --pool 0x88e6…                    Analyze USDC/WETH pool
  python run.py scout  WETH/USDC                         Find best V3 pools (all chains)
  python run.py scout  WETH/USDC --network arbitrum      Filter by network
  python run.py scout  WETH/USDC --sort efficiency       Sort by Vol/TVL ratio
  python run.py check                                    Integration tests
  python run.py info                                     System overview + DEX support

⭐ Like this tool? Star us on GitHub: github.com/fabiotreze/defi-cli

Supported DEXes (V3-compatible):
  uniswap_v3     🦄 Uniswap V3     — ETH, ARB, POLY, BASE, OP
  pancakeswap_v3 🥞 PancakeSwap V3 — ETH, BSC, ARB, BASE
  sushiswap_v3   🍣 SushiSwap V3   — ETH, ARB, POLY, BASE, OP

How to find your Position ID:
  1. Go to https://app.uniswap.org → Pool → click your position
  2. The URL contains: app.uniswap.org/positions/v3/<network>/<nft_id>
     → Position ID = the number at the end
     → Network = "arbitrum", "ethereum", etc.
  3. Pool address is now AUTO-DETECTED — you only need the Position ID!
  4. Your wallet address is in MetaMask → copy address

Sources:
  DEXScreener API  : https://docs.dexscreener.com/api/reference
  Uniswap V3 Docs  : https://docs.uniswap.org/
  GitHub           : https://github.com/fabiotreze/defi-cli
""",
    )
    parser.add_argument(
        "--version", action="version", version=f"DeFi CLI v{PROJECT_VERSION}"
    )

    sub = parser.add_subparsers(dest="command", help="Available commands")

    # list command — scans ALL compatible DEXes
    list_p = sub.add_parser(
        "list", help="List all V3-compatible positions for a wallet"
    )
    list_p.add_argument("wallet", help="Wallet address (0x…)")
    list_p.add_argument(
        "--network",
        type=str,
        default="arbitrum",
        help="Network: arbitrum, ethereum, polygon, base, optimism, bsc (default: arbitrum)",
    )
    list_p.add_argument(
        "--dex",
        type=str,
        default=None,
        help="Filter by DEX: uniswap_v3, pancakeswap_v3, sushiswap_v3 (default: all)",
    )

    pool_p = sub.add_parser("pool", help="Analyze a pool (DEXScreener)")
    pool_p.add_argument(
        "--pool", type=str, default=None, help="Pool or token contract address (0x…)"
    )

    report_p = sub.add_parser("report", help="Generate HTML pool report")
    report_p.add_argument(
        "--pool",
        type=str,
        default=None,
        help="Pool contract address (0x…) — optional when --position is given (auto-detected via Factory.getPool)",
    )
    report_p.add_argument(
        "--position",
        type=int,
        default=None,
        help="V3 position NFT tokenId (uint256). Pool is auto-detected via Factory.getPool(token0, token1, fee). "
        "Find it: app.uniswap.org → Pool → position URL → /positions/v3/<net>/<tokenId>",
    )
    report_p.add_argument(
        "--wallet",
        type=str,
        default=None,
        help="Your wallet address (0x…) for cross-validation links",
    )
    report_p.add_argument(
        "--network",
        type=str,
        default=None,
        help="Network: arbitrum, ethereum, polygon, base, optimism, bsc (auto-detected if omitted)",
    )
    report_p.add_argument(
        "--dex",
        type=str,
        default=None,
        help="DEX: uniswap_v3, pancakeswap_v3, sushiswap_v3 (default: uniswap_v3)",
    )

    sub.add_parser("check", help="Run integration validation")
    sub.add_parser("info", help="System & architecture info")

    # scout command — cross-DEX pool discovery via DefiLlama
    scout_p = sub.add_parser(
        "scout", help="Find best V3 pools for a token pair (DefiLlama)"
    )
    scout_p.add_argument("pair", help="Token pair, e.g. WETH/USDC")
    scout_p.add_argument(
        "--network",
        type=str,
        default=None,
        help="Filter by network: arbitrum, ethereum, polygon, base, optimism, bsc",
    )
    scout_p.add_argument(
        "--dex",
        type=str,
        default=None,
        help="Filter by DEX: uniswap_v3, pancakeswap_v3, sushiswap_v3",
    )
    scout_p.add_argument(
        "--sort",
        type=str,
        default="apy",
        help="Sort by: apy, tvl, volume, efficiency (default: apy)",
    )
    scout_p.add_argument(
        "--limit", type=int, default=15, help="Max results (default: 15)"
    )
    scout_p.add_argument(
        "--min-tvl",
        type=float,
        default=50000,
        help="Minimum TVL in USD (default: 50000)",
    )

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

    if args.command == "scout":
        asyncio.run(
            cmd_scout(
                pair=args.pair,
                network=args.network,
                dex=args.dex,
                sort=args.sort,
                limit=args.limit,
                min_tvl=args.min_tvl,
            )
        )
        return 0
    if args.command == "list":
        if not _simple_disclaimer():
            print("❌ Consent required.")
            return 1
        asyncio.run(
            cmd_list(
                wallet=args.wallet,
                network=args.network,
                dex=args.dex,
            )
        )
        return 0

    # Consent-required commands
    if args.command == "report":
        cmd_report(
            pool=args.pool,
            position_id=args.position,
            wallet=args.wallet,
            network=args.network,
            dex=args.dex,
        )
        return 0

    if args.command == "pool":
        if not _simple_disclaimer():
            print("❌ Consent required.")
            return 1
        pool_addr = args.pool
        if not pool_addr:
            pool_addr = _prompt_address("pool")
        if not pool_addr:
            return 1
        asyncio.run(cmd_pool(pool_addr))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n❌ Cancelled.")
        sys.exit(130)
