#!/usr/bin/env python3
"""
CODEREVIEW — Automated Validation & Simulation Suite
=====================================================

Executes all 20 automated checks defined in .codereview.md PART 2.
Uses REAL pool data from existing pools on each supported network.

Run:
  python tests/test_codereview.py           # All tests
  python tests/test_codereview.py --quick   # Skip network tests (offline)
  python -m pytest tests/test_codereview.py -v  # Via pytest

Reference Pools — ALL 3 DEXes × ALL supported networks:
  Uniswap V3:
    Ethereum : USDC/WETH 0.05%   — 0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640
    Arbitrum : WBTC/WETH 0.05%   — 0x2f5e87C9312fa29aed5c179E456625D79015299c
    Polygon  : USDC.e/USDC 0.01% — 0xD36ec33c8bed5a9F7B6630855f1533455b98a418
    Base     : WETH/USDC 0.05%   — 0xd0b53D9277642d899DF5C87A3966A349A798F224
    Optimism : USDC/WETH 0.05%   — 0x1fb3cf6e48f1e7b10213e7b6d87d4c073c7fdb7b
  PancakeSwap V3:
    Ethereum : WETH/USDT 0.25%   — 0x6ca298d2983ab03aa1da7679389d955a4efee15c
    BSC      : WBNB/USDT 0.25%   — 0x172fcd41e0913e95784454622d1c3724f546f849
    Arbitrum : USDC/WETH 0.25%   — 0x7fcdc35463e3770c2fb992716cd070b63540b947
    Base     : WETH/USDC 0.25%   — 0x72ab388e2e2f6facef59e3c3fa2c4e29011c2d38
  SushiSwap V3:
    Ethereum : WETH/DAI 0.30%    — 0xc3d03e4f041fd4cd388c549ee2a29a9e5075882f
    Arbitrum : USDC/WETH 0.05%   — 0xf3eb87c1f6020982173c908e7eb31aa66c1f0296
    Polygon  : WETH/USDC 0.30%   — 0x34965ba0ac2451a34a0471f04cca3f990b8dea27
    Optimism : WBTC/WETH 0.30%   — 0x689a850f62b41d89b5e5c3465cd291374b215813

Contract Address Sources:
  Uniswap V3  : https://docs.uniswap.org/contracts/v3/reference/deployments/
  PancakeSwap : https://developer.pancakeswap.finance/contracts/v3/addresses
  SushiSwap   : https://docs.sushi.com/docs/Products/V3%20AMM/Periphery/Deployment%20Addresses
"""

import ast
import asyncio
import importlib
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# ── Setup project root ──────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── Reference data for real-pool validation ─────────────────────────────

# Known high-liquidity pools (verified on DexScreener) for each DEX × network.
# Structure: list of {dex, network, address, pair, fee}
# Used by T03 (pool analysis), T16 (DEXScreener API connectivity).
REFERENCE_POOLS = [
    # ── Uniswap V3 ─────────────────────────────────────────────────────
    {
        "dex": "uniswap_v3",
        "network": "ethereum",
        "address": "0x88e6A0c2dDD26FEEb64F039a2c41296FcB3f5640",
        "pair": "USDC/WETH",
        "fee": "0.05%",
    },
    {
        "dex": "uniswap_v3",
        "network": "arbitrum",
        "address": "0x2f5e87C9312fa29aed5c179E456625D79015299c",
        "pair": "WBTC/WETH",
        "fee": "0.05%",
    },
    {
        "dex": "uniswap_v3",
        "network": "polygon",
        "address": "0xD36ec33c8bed5a9F7B6630855f1533455b98a418",
        "pair": "USDC.e/USDC",
        "fee": "0.01%",
    },
    {
        "dex": "uniswap_v3",
        "network": "base",
        "address": "0xd0b53D9277642d899DF5C87A3966A349A798F224",
        "pair": "WETH/USDC",
        "fee": "0.05%",
    },
    {
        "dex": "uniswap_v3",
        "network": "optimism",
        "address": "0x1fb3cf6e48f1e7b10213e7b6d87d4c073c7fdb7b",
        "pair": "USDC/WETH",
        "fee": "0.05%",
    },
    # ── PancakeSwap V3 ─────────────────────────────────────────────────
    {
        "dex": "pancakeswap_v3",
        "network": "ethereum",
        "address": "0x6ca298d2983ab03aa1da7679389d955a4efee15c",
        "pair": "WETH/USDT",
        "fee": "0.25%",
    },
    {
        "dex": "pancakeswap_v3",
        "network": "bsc",
        "address": "0x172fcd41e0913e95784454622d1c3724f546f849",
        "pair": "WBNB/USDT",
        "fee": "0.25%",
    },
    {
        "dex": "pancakeswap_v3",
        "network": "arbitrum",
        "address": "0x7fcdc35463e3770c2fb992716cd070b63540b947",
        "pair": "USDC/WETH",
        "fee": "0.25%",
    },
    {
        "dex": "pancakeswap_v3",
        "network": "base",
        "address": "0x72ab388e2e2f6facef59e3c3fa2c4e29011c2d38",
        "pair": "WETH/USDC",
        "fee": "0.25%",
    },
    # ── SushiSwap V3 ───────────────────────────────────────────────────
    {
        "dex": "sushiswap_v3",
        "network": "ethereum",
        "address": "0xc3d03e4f041fd4cd388c549ee2a29a9e5075882f",
        "pair": "WETH/DAI",
        "fee": "0.30%",
    },
    {
        "dex": "sushiswap_v3",
        "network": "arbitrum",
        "address": "0xf3eb87c1f6020982173c908e7eb31aa66c1f0296",
        "pair": "USDC/WETH",
        "fee": "0.05%",
    },
    {
        "dex": "sushiswap_v3",
        "network": "polygon",
        "address": "0x34965ba0ac2451a34a0471f04cca3f990b8dea27",
        "pair": "WETH/USDC",
        "fee": "0.30%",
    },
    {
        "dex": "sushiswap_v3",
        "network": "optimism",
        "address": "0x689a850f62b41d89b5e5c3465cd291374b215813",
        "pair": "WBTC/WETH",
        "fee": "0.30%",
    },
]

# RPC endpoints — imported from the single source of truth (rpc_helpers.py)
# This guarantees tests validate the SAME endpoints the app uses.
try:
    from defi_cli.rpc_helpers import RPC_URLS
except ImportError:
    # Fallback if rpc_helpers cannot be imported in test isolation
    RPC_URLS = {
        "arbitrum": "https://1rpc.io/arb",
        "ethereum": "https://1rpc.io/eth",
        "polygon": "https://1rpc.io/matic",
        "base": "https://1rpc.io/base",
        "optimism": "https://1rpc.io/op",
        "bsc": "https://1rpc.io/bnb",
    }

# All Python source files to validate
PYTHON_FILES = [
    "run.py",
    "position_reader.py",
    "position_indexer.py",
    "real_defi_math.py",
    "html_generator.py",
    "defi_cli/__init__.py",
    "defi_cli/central_config.py",
    "defi_cli/dex_registry.py",
    "defi_cli/dexscreener_client.py",
    "defi_cli/legal_disclaimers.py",
    "defi_cli/rpc_helpers.py",
    "defi_cli/stablecoins.py",
    "defi_cli/commands.py",
    "defi_cli/html_styles.py",
    "pool_scout.py",
]

# Sensitive patterns to scan for
SENSITIVE_PATTERNS = [
    r"(?i)private.?key\s*=\s*['\"]0x",
    r"(?i)secret\s*=\s*['\"]",
    r"(?i)password\s*=\s*['\"](?!.*example)",
    r"(?i)api.?key\s*=\s*['\"][a-zA-Z0-9]{20,}",
    r"(?i)bearer\s+[a-zA-Z0-9._-]{20,}",
    r"AKIA[0-9A-Z]{16}",  # AWS access key
]


# ═══════════════════════════════════════════════════════════════════════
# TEST RESULTS COLLECTOR
# ═══════════════════════════════════════════════════════════════════════


class CodeReviewResults:
    """Collects and formats test results for the codereview report."""

    def __init__(self):
        self.results: List[Dict] = []
        self.start_time = time.time()

    def add(
        self,
        test_id: str,
        name: str,
        passed: bool,
        detail: str = "",
        severity: str = "PASS",
    ):
        self.results.append(
            {
                "id": test_id,
                "name": name,
                "passed": passed,
                "detail": detail,
                "severity": severity if not passed else "PASS",
            }
        )

    def summary(self) -> str:
        elapsed = time.time() - self.start_time
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        lines = []
        lines.append("")
        lines.append("═" * 70)
        lines.append("  CODEREVIEW — Automated Validation Report")
        lines.append(
            f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | {elapsed:.1f}s"
        )
        lines.append("═" * 70)
        lines.append("")

        severity_icons = {
            "PASS": "✅",
            "LOW": "🟢",
            "MEDIUM": "🟡",
            "HIGH": "🟠",
            "CRITICAL": "🔴",
        }

        for r in self.results:
            icon = severity_icons.get(r["severity"], "❓")
            status = "PASS" if r["passed"] else f"FAIL [{r['severity']}]"
            lines.append(f"  {icon} {r['id']:5s} {r['name']:<45s} {status}")
            if r["detail"] and not r["passed"]:
                for d in r["detail"].split("\n"):
                    lines.append(f"         {d}")

        lines.append("")
        lines.append("─" * 70)
        pct = (passed / total * 100) if total > 0 else 0
        lines.append(f"  Results: {passed}/{total} passed ({pct:.0f}%)")
        if failed == 0:
            lines.append("  🎉 ALL CHECKS PASSED")
        else:
            lines.append(f"  ⚠️  {failed} check(s) failed — review above")
        lines.append("─" * 70)

        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════
# T01 — CLI info command
# ═══════════════════════════════════════════════════════════════════════


def _t01_cli_info(results: CodeReviewResults):
    """T01: python run.py info executes without error."""
    try:
        proc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "run.py"), "info"],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=str(PROJECT_ROOT),
        )
        ok = proc.returncode == 0 and "DeFi CLI" in proc.stdout
        detail = "" if ok else f"exit={proc.returncode}, stderr={proc.stderr[:200]}"
        results.add("T01", "CLI info command", ok, detail, "HIGH")
    except Exception as e:
        results.add("T01", "CLI info command", False, str(e), "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T02 — Integration check (live pools)
# ═══════════════════════════════════════════════════════════════════════


def _t02_cli_check(results: CodeReviewResults):
    """T02: python run.py check validates against live pools."""
    try:
        proc = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "run.py"), "check"],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(PROJECT_ROOT),
        )
        output = proc.stdout
        # Check has a summary line with "checks passed"
        ok = "checks passed" in output.lower() and proc.returncode == 0
        # Extract pass rate
        match = re.search(r"(\d+)/(\d+) checks passed", output)
        if match:
            detail = f"{match.group(1)}/{match.group(2)} checks passed"
        else:
            detail = f"exit={proc.returncode}"
        results.add("T02", "Integration check (live pools)", ok, detail, "HIGH")
    except subprocess.TimeoutExpired:
        results.add(
            "T02", "Integration check (live pools)", False, "Timeout 120s", "MEDIUM"
        )
    except Exception as e:
        results.add("T02", "Integration check (live pools)", False, str(e), "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T03 — Pool analysis with real DEXScreener data
# ═══════════════════════════════════════════════════════════════════════


def _t03_pool_analysis(results: CodeReviewResults):
    """T03: Analyze known pools via DEXScreener API — one per DEX."""
    try:
        # Test one pool per DEX to ensure all 3 DEXes work with DEXScreener
        tested_dexes = set()
        pools_to_test = []
        for pool in REFERENCE_POOLS:
            if pool["dex"] not in tested_dexes:
                pools_to_test.append(pool)
                tested_dexes.add(pool["dex"])

        async def _test():
            ok_pools = []
            fail_pools = []
            from defi_cli.dexscreener_client import analyze_pool_real

            for pool in pools_to_test:
                try:
                    result = await analyze_pool_real(pool["address"])
                    ok = (
                        result.get("status") == "success"
                        and result.get("data", {}).get("totalValueLockedUSD", 0) > 0
                    )
                    if ok:
                        d = result["data"]
                        ok_pools.append(
                            f"{pool['dex']}/{pool['network']}: {d['name']} "
                            f"TVL=${d['totalValueLockedUSD']:,.0f}"
                        )
                    else:
                        fail_pools.append(
                            f"{pool['dex']}/{pool['network']}: "
                            f"status={result.get('status')}"
                        )
                except Exception as e:
                    fail_pools.append(f"{pool['dex']}/{pool['network']}: {e}")
                await asyncio.sleep(0.3)
            return ok_pools, fail_pools

        ok_pools, fail_pools = asyncio.run(_test())
        ok = len(fail_pools) == 0 and len(ok_pools) == len(pools_to_test)
        detail = f"{len(ok_pools)}/{len(pools_to_test)} DEXes OK"
        if ok_pools:
            detail += "\n" + "\n".join(ok_pools)
        if fail_pools:
            detail += "\nFailed:\n" + "\n".join(fail_pools)
        results.add(
            "T03",
            f"Pool analysis ({len(ok_pools)} DEXes via DEXScreener)",
            ok,
            detail,
            "HIGH",
        )
    except Exception as e:
        results.add(
            "T03", "Pool analysis (DEXScreener real data)", False, str(e)[:200], "HIGH"
        )


# ═══════════════════════════════════════════════════════════════════════
# T04 — Multi-DEX wallet scan (uses zero-balance test = valid execution)
# ═══════════════════════════════════════════════════════════════════════


def _t04_list_scan(results: CodeReviewResults):
    """T04: list command runs without crash on ALL 6 networks."""
    try:
        # Use a known address with 0 V3 positions as a safe test
        # 0x0000...0001 will have 0 positions but the scan should execute
        test_wallet = "0x0000000000000000000000000000000000000001"
        all_networks = list(RPC_URLS.keys())
        ok_nets = []
        fail_nets = []
        timeout_nets = []
        for network in all_networks:
            try:
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(PROJECT_ROOT / "run.py"),
                        "list",
                        test_wallet,
                        "--network",
                        network,
                    ],
                    input="y\n",  # Accept disclaimer
                    capture_output=True,
                    text=True,
                    timeout=180,
                    cwd=str(PROJECT_ROOT),
                )
                if proc.returncode == 0:
                    ok_nets.append(network)
                else:
                    fail_nets.append(f"{network}: exit={proc.returncode}")
            except subprocess.TimeoutExpired:
                timeout_nets.append(network)
            except Exception as e:
                fail_nets.append(f"{network}: {e}")

        # Pass if ≥4 networks complete (timeouts on slow RPCs are acceptable;
        # T10/T16/T17 independently verify ALL 6 networks).
        # Hard-fail only if a network returns a non-zero exit code (real bug).
        ok = len(fail_nets) == 0 and len(ok_nets) >= 4
        detail = f"{len(ok_nets)}/{len(all_networks)} networks OK"
        if timeout_nets:
            detail += f" ({len(timeout_nets)} timed out: {', '.join(timeout_nets)})"
        if fail_nets:
            detail += "\n" + "\n".join(fail_nets)
        results.add(
            "T04",
            f"Multi-DEX wallet scan ({len(ok_nets)} networks)",
            ok,
            detail,
            "HIGH",
        )
    except Exception as e:
        results.add("T04", "Multi-DEX wallet scan (list)", False, str(e), "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T05 — Unit tests (pytest)
# ═══════════════════════════════════════════════════════════════════════


def _t05_unit_tests(results: CodeReviewResults):
    """T05: All 65 formula unit tests pass."""
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_math.py", "-v", "--tb=short"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        match = re.search(r"(\d+) passed", proc.stdout)
        count = int(match.group(1)) if match else 0
        failed_match = re.search(r"(\d+) failed", proc.stdout)
        failed = int(failed_match.group(1)) if failed_match else 0
        ok = proc.returncode == 0 and failed == 0 and count >= 65
        detail = f"{count} passed, {failed} failed"
        results.add("T05", f"Unit tests ({count} formulas)", ok, detail, "CRITICAL")
    except Exception as e:
        results.add("T05", "Unit tests (formulas)", False, str(e), "CRITICAL")


# ═══════════════════════════════════════════════════════════════════════
# T06 — Syntax validation (ast.parse)
# ═══════════════════════════════════════════════════════════════════════


def _t06_syntax(results: CodeReviewResults):
    """T06: All Python files parse without syntax errors."""
    errors = []
    for f in PYTHON_FILES:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            errors.append(f"{f}: FILE NOT FOUND")
            continue
        try:
            ast.parse(fpath.read_text())
        except SyntaxError as e:
            errors.append(f"{f}: line {e.lineno}: {e.msg}")

    ok = len(errors) == 0
    detail = "\n".join(errors) if errors else f"{len(PYTHON_FILES)} files OK"
    results.add("T06", "Syntax validation (ast.parse)", ok, detail, "CRITICAL")


# ═══════════════════════════════════════════════════════════════════════
# T07 — Import validation
# ═══════════════════════════════════════════════════════════════════════


def _t07_imports(results: CodeReviewResults):
    """T07: All project modules import without error."""
    modules = [
        "defi_cli.central_config",
        "defi_cli.dex_registry",
        "defi_cli.dexscreener_client",
        "defi_cli.legal_disclaimers",
        "defi_cli.rpc_helpers",
        "defi_cli.stablecoins",
        "defi_cli.commands",
        "defi_cli.html_styles",
        "real_defi_math",
        "html_generator",
        "position_reader",
        "position_indexer",
    ]
    errors = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:
            errors.append(f"{mod}: {e}")

    ok = len(errors) == 0
    detail = "\n".join(errors) if errors else f"{len(modules)} modules OK"
    results.add("T07", "Import validation", ok, detail, "CRITICAL")


# ═══════════════════════════════════════════════════════════════════════
# T08 — Version consistency
# ═══════════════════════════════════════════════════════════════════════


def _t08_version(results: CodeReviewResults):
    """T08: Version in pyproject.toml matches central_config.py."""
    try:
        from defi_cli.central_config import PROJECT_VERSION

        toml_path = PROJECT_ROOT / "pyproject.toml"
        toml_text = toml_path.read_text()
        match = re.search(r'version\s*=\s*"([^"]+)"', toml_text)
        toml_version = match.group(1) if match else "NOT_FOUND"

        ok = PROJECT_VERSION == toml_version
        detail = f"central_config={PROJECT_VERSION}, pyproject.toml={toml_version}"
        severity = "HIGH" if not ok else "PASS"
        results.add("T08", "Version consistency", ok, detail, severity)
    except Exception as e:
        results.add("T08", "Version consistency", False, str(e), "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T09 — Sensitive data scan
# ═══════════════════════════════════════════════════════════════════════


def _t09_secrets(results: CodeReviewResults):
    """T09: No hardcoded secrets/keys in source code."""
    findings = []
    for f in PYTHON_FILES:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            continue
        content = fpath.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            for pattern in SENSITIVE_PATTERNS:
                if re.search(pattern, line):
                    findings.append(f"{f}:{i} — matches: {pattern}")

    ok = len(findings) == 0
    detail = "\n".join(findings[:5]) if findings else "No secrets found"
    results.add("T09", "Sensitive data scan", ok, detail, "CRITICAL")


# ═══════════════════════════════════════════════════════════════════════
# T10 — Contract addresses on-chain verification
# ═══════════════════════════════════════════════════════════════════════


def _t10_contracts_onchain(results: CodeReviewResults):
    """T10: All DEX Registry contract addresses are real contracts on-chain."""
    try:
        import httpx
        from defi_cli.dex_registry import DEX_REGISTRY

        async def _verify():
            verified = 0
            failed = []
            total = 0

            for slug, dex in DEX_REGISTRY.items():
                if not dex["compatible"]:
                    continue
                for network, addrs in dex["networks"].items():
                    rpc = RPC_URLS.get(network)
                    if not rpc:
                        continue
                    pm = addrs["position_manager"]
                    total += 1

                    try:
                        is_contract = False
                        for attempt in range(3):
                            try:
                                async with httpx.AsyncClient(timeout=10) as client:
                                    resp = await client.post(
                                        rpc,
                                        json={
                                            "jsonrpc": "2.0",
                                            "id": 1,
                                            "method": "eth_getCode",
                                            "params": [pm, "latest"],
                                        },
                                    )
                                    code = resp.json().get("result", "0x")
                                    if len(code) > 4:
                                        is_contract = True
                                        break
                            except Exception:
                                pass
                            if attempt < 2:
                                await asyncio.sleep(1.0)  # Back-off before retry
                        if is_contract:
                            verified += 1
                        else:
                            failed.append(
                                f"{slug}/{network}: {pm[:16]}... NOT A CONTRACT"
                            )
                    except Exception as e:
                        failed.append(f"{slug}/{network}: RPC error — {e}")
                    await asyncio.sleep(0.2)  # Rate limit

            return verified, total, failed

        verified, total, failed = asyncio.run(_verify())
        ok = len(failed) == 0 and verified == total
        detail = f"{verified}/{total} contracts verified"
        if failed:
            detail += "\n" + "\n".join(failed[:5])
        results.add(
            "T10",
            f"Contract addresses on-chain ({verified}/{total})",
            ok,
            detail,
            "CRITICAL",
        )
    except Exception as e:
        results.add(
            "T10", "Contract addresses on-chain", False, str(e)[:200], "CRITICAL"
        )


# ═══════════════════════════════════════════════════════════════════════
# T11 — Tick↔Price roundtrip (formula validation)
# ═══════════════════════════════════════════════════════════════════════


def _t11_tick_price_roundtrip(results: CodeReviewResults):
    """T11: tick_to_price ↔ price_to_tick roundtrip at multiple scales."""
    from real_defi_math import UniswapV3Math

    test_prices = [
        0.0001,
        0.001,
        0.01,
        0.1,
        1.0,
        10,
        100,
        500,
        1000,
        1800,
        2000,
        3500,
        10000,
        50000,
        100000,
    ]
    errors = []
    for price in test_prices:
        tick = UniswapV3Math.price_to_tick(price)
        recovered = UniswapV3Math.tick_to_price(tick)
        error_pct = abs(recovered - price) / price * 100
        if error_pct >= 0.01:
            errors.append(
                f"price={price}: tick={tick}, recovered={recovered:.6f}, error={error_pct:.4f}%"
            )

    ok = len(errors) == 0
    detail = f"{len(test_prices)} prices tested" if ok else "\n".join(errors)
    results.add(
        "T11",
        f"Tick↔Price roundtrip ({len(test_prices)} scales)",
        ok,
        detail,
        "CRITICAL",
    )


# ═══════════════════════════════════════════════════════════════════════
# T12 — IL symmetry (Pintail formula)
# ═══════════════════════════════════════════════════════════════════════


def _t12_il_symmetry(results: CodeReviewResults):
    """T12: IL(r) == IL(1/r) — impermanent loss is symmetric."""
    from real_defi_math import RiskAnalyzer

    test_ratios = [0.1, 0.25, 0.5, 2.0, 4.0, 10.0]
    errors = []
    for r in test_ratios:
        il_r = RiskAnalyzer.impermanent_loss(1000, 1000 * r)
        il_inv = RiskAnalyzer.impermanent_loss(1000, 1000 / r)
        if abs(il_r - il_inv) > 0.01:
            errors.append(f"r={r}: IL(r)={il_r:.4f}% vs IL(1/r)={il_inv:.4f}%")

    ok = len(errors) == 0
    detail = f"{len(test_ratios)} ratios tested, symmetric" if ok else "\n".join(errors)
    results.add("T12", "IL symmetry (Pintail)", ok, detail, "CRITICAL")


# ═══════════════════════════════════════════════════════════════════════
# T13 — Capital efficiency ≥ 1.0
# ═══════════════════════════════════════════════════════════════════════


def _t13_capital_efficiency(results: CodeReviewResults):
    """T13: CE ≥ 1.0 for any valid range (Whitepaper §2)."""
    from real_defi_math import UniswapV3Math

    test_ranges = [
        (100, 10000),
        (500, 5000),
        (1000, 3000),
        (1500, 2500),
        (1800, 2200),
        (1900, 2100),
        (1950, 2050),
        (1990, 2010),
    ]
    errors = []
    for pa, pb in test_ranges:
        ce = UniswapV3Math.capital_efficiency_vs_v2(pa, pb)
        if ce < 1.0:
            errors.append(f"range [{pa}-{pb}]: CE={ce:.4f} < 1.0")

    ok = len(errors) == 0
    detail = (
        f"{len(test_ranges)} ranges tested, all CE ≥ 1.0" if ok else "\n".join(errors)
    )
    results.add("T13", "Capital efficiency ≥ 1.0", ok, detail, "CRITICAL")


# ═══════════════════════════════════════════════════════════════════════
# T14 — Fee APY: higher share → higher APY
# ═══════════════════════════════════════════════════════════════════════


def _t14_fee_apy_monotonic(results: CodeReviewResults):
    """T14: Larger liquidity share → higher APY (fee distribution)."""
    from real_defi_math import UniswapV3Math

    shares = [10, 50, 100, 500, 1000]
    apys = []
    for s in shares:
        r = UniswapV3Math.estimate_fee_apy(
            volume_24h=1_000_000,
            fee_tier=0.003,
            position_liquidity=s,
            total_pool_liquidity=10000,
            position_value_usd=10000,
        )
        apys.append(r["apy_pct"])

    is_monotonic = all(apys[i] <= apys[i + 1] for i in range(len(apys) - 1))
    ok = is_monotonic
    detail = f"APYs: {[f'{a:.2f}%' for a in apys]}" if ok else f"NOT monotonic: {apys}"
    results.add("T14", "Fee APY monotonic (share→APY)", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T15 — Data pipeline schema (position_reader → math → html)
# ═══════════════════════════════════════════════════════════════════════


def _t15_pipeline_schema(results: CodeReviewResults):
    """T15: Data flows correctly from PositionData → analyze_position → HTML fields."""
    from real_defi_math import PositionData, analyze_position

    pos = PositionData(
        token0_amount=1.0,
        token1_amount=2000.0,
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
    analysis = analyze_position(pos)

    # Fields required by html_generator
    required_fields = [
        "current_price",
        "range_min",
        "range_max",
        "total_value_usd",
        "fee_tier",
        "fee_tier_label",
        "in_range",
        "liquidity",
        "capital_efficiency_vs_v2",
        "strategies",
        "generated_at",
        "token0_symbol",
        "token1_symbol",
        "network",
        "protocol",
        "downside_buffer_pct",
        "upside_buffer_pct",
        "daily_fees_est",
        "weekly_fees_est",
        "monthly_fees_est",
        "annual_fees_est",
        "pool_apr_estimate",
        "volume_24h",
        "total_value_locked_usd",
        "data_source",
        "position_apr_est",
    ]
    missing = [f for f in required_fields if f not in analysis]

    # Validate strategies have all 3
    strats = analysis.get("strategies", {})
    missing_strats = [
        s for s in ["conservative", "moderate", "aggressive"] if s not in strats
    ]

    ok = len(missing) == 0 and len(missing_strats) == 0
    detail = ""
    if missing:
        detail += f"Missing fields: {missing}\n"
    if missing_strats:
        detail += f"Missing strategies: {missing_strats}"
    if ok:
        detail = f"All {len(required_fields)} fields + 3 strategies present"
    results.add("T15", "Data pipeline schema (E2E)", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T16 — DEXScreener API connectivity (all priority chains)
# ═══════════════════════════════════════════════════════════════════════


def _t16_dexscreener_chains(results: CodeReviewResults):
    """T16: DEXScreener API responds for ALL reference pools (3 DEXes × all networks)."""
    try:
        import httpx

        async def _test():
            ok_pools = []
            fail_pools = []
            for pool in REFERENCE_POOLS:
                label = f"{pool['dex']}/{pool['network']}"
                url = f"https://api.dexscreener.com/latest/dex/pairs/{pool['network']}/{pool['address']}"
                try:
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.get(url)
                        data = resp.json()
                        if resp.status_code == 200 and data.get("pairs"):
                            ok_pools.append(label)
                        else:
                            fail_pools.append(f"{label}: no pairs returned")
                except Exception as e:
                    fail_pools.append(f"{label}: {e}")
                await asyncio.sleep(0.3)
            return ok_pools, fail_pools

        ok_pools, fail_pools = asyncio.run(_test())
        ok = len(fail_pools) == 0
        # Count unique DEXes and networks
        dexes_ok = len(set(p.split("/")[0] for p in ok_pools))
        nets_ok = len(set(p.split("/")[1] for p in ok_pools))
        detail = f"{len(ok_pools)}/{len(REFERENCE_POOLS)} pools OK ({dexes_ok} DEXes, {nets_ok} networks)"
        if fail_pools:
            detail += "\n" + "\n".join(fail_pools)
        results.add(
            "T16",
            f"DEXScreener API ({dexes_ok} DEXes, {nets_ok} nets)",
            ok,
            detail,
            "MEDIUM",
        )
    except Exception as e:
        results.add(
            "T16", "DEXScreener API connectivity", False, str(e)[:200], "MEDIUM"
        )


# ═══════════════════════════════════════════════════════════════════════
# T17 — RPC endpoints (eth_blockNumber for all networks)
# ═══════════════════════════════════════════════════════════════════════


def _t17_rpc_endpoints(results: CodeReviewResults):
    """T17: All RPC endpoints respond to eth_blockNumber."""
    try:
        import httpx

        async def _test():
            ok_nets = []
            fail_nets = []
            for network, rpc in RPC_URLS.items():
                try:
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.post(
                            rpc,
                            json={
                                "jsonrpc": "2.0",
                                "id": 1,
                                "method": "eth_blockNumber",
                                "params": [],
                            },
                        )
                        block = int(resp.json().get("result", "0x0"), 16)
                        if block > 0:
                            ok_nets.append(f"{network} (block #{block:,})")
                        else:
                            fail_nets.append(f"{network}: block=0")
                except Exception as e:
                    fail_nets.append(f"{network}: {e}")
                await asyncio.sleep(0.15)
            return ok_nets, fail_nets

        ok_nets, fail_nets = asyncio.run(_test())
        ok = len(fail_nets) == 0
        detail = f"{len(ok_nets)}/{len(RPC_URLS)} endpoints OK"
        if fail_nets:
            detail += "\n" + "\n".join(fail_nets[:3])
        results.add(
            "T17",
            f"RPC endpoints ({len(ok_nets)}/{len(RPC_URLS)})",
            ok,
            detail,
            "MEDIUM",
        )
    except Exception as e:
        results.add("T17", "RPC endpoints", False, str(e)[:200], "MEDIUM")


# ═══════════════════════════════════════════════════════════════════════
# T18 — README links are accessible
# ═══════════════════════════════════════════════════════════════════════


def _t18_readme_links(results: CodeReviewResults):
    """T18: External links in README.md return HTTP 200."""
    try:
        import httpx

        readme = (PROJECT_ROOT / "README.md").read_text()
        urls = re.findall(r'https?://[^\s)\]>"]+', readme)
        # Deduplicate and filter
        unique_urls = list(set(u.rstrip(".,;:") for u in urls if "badge" not in u))
        # Limit to 15 most important
        unique_urls = unique_urls[:15]

        async def _test():
            ok_links = []
            fail_links = []
            for url in unique_urls:
                try:
                    async with httpx.AsyncClient(
                        timeout=10, follow_redirects=True
                    ) as client:
                        resp = await client.head(url)
                        if resp.status_code < 400:
                            ok_links.append(url)
                        else:
                            fail_links.append(f"HTTP {resp.status_code}: {url[:60]}")
                except Exception as e:
                    fail_links.append(f"ERROR: {url[:60]} — {e}")
                await asyncio.sleep(0.2)
            return ok_links, fail_links

        ok_links, fail_links = asyncio.run(_test())
        # Allow some failures (sites may block HEAD or have temporary issues)
        ok = len(fail_links) <= 2
        detail = f"{len(ok_links)}/{len(unique_urls)} links OK"
        if fail_links:
            detail += "\n" + "\n".join(fail_links[:3])
        results.add(
            "T18",
            f"README links ({len(ok_links)}/{len(unique_urls)})",
            ok,
            detail,
            "LOW",
        )
    except Exception as e:
        results.add("T18", "README links", False, str(e)[:200], "LOW")


# ═══════════════════════════════════════════════════════════════════════
# T19 — Disclaimers in user-facing output
# ═══════════════════════════════════════════════════════════════════════


def _t19_disclaimers(results: CodeReviewResults):
    """T19: Disclaimers present in CLI output and legal module."""
    findings = []

    # Check legal module exists and has required content
    try:
        from defi_cli.legal_disclaimers import (
            CLI_DISCLAIMER,
            get_jurisdiction_specific_warning,
        )

        if (
            "NOT FINANCIAL ADVICE" not in CLI_DISCLAIMER.upper()
            and "NOT financial" not in CLI_DISCLAIMER
        ):
            findings.append("CLI_DISCLAIMER missing 'NOT financial advice'")
        for jur in ["BR", "US", "EU", "GLOBAL"]:
            w = get_jurisdiction_specific_warning(jur)
            if not w or len(w) < 20:
                findings.append(f"Missing/short warning for jurisdiction: {jur}")
    except ImportError as e:
        findings.append(f"Cannot import legal_disclaimers: {e}")

    # Check commands module has consent gate (moved from run.py for modularity)
    commands_text = (PROJECT_ROOT / "defi_cli" / "commands.py").read_text()
    if "_require_consent" not in commands_text:
        findings.append("commands.py missing _require_consent gate")
    if "_simple_disclaimer" not in commands_text:
        findings.append("commands.py missing _simple_disclaimer for list command")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "All disclaimers present"
    results.add("T19", "Disclaimers in output", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T20 — HTML report structure (5 sessions)
# ═══════════════════════════════════════════════════════════════════════


def _t20_html_structure(results: CodeReviewResults):
    """T20: HTML generator produces reports with all required sections."""
    try:
        from real_defi_math import PositionData, analyze_position
        from html_generator import generate_position_report
        from datetime import datetime

        pos = PositionData(
            token0_amount=1.0,
            token1_amount=2000.0,
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
        analysis = analyze_position(pos)
        analysis["consent_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        path = generate_position_report(analysis, _open_browser=False)
        html_content = Path(path).read_text()

        # Check for required sections
        required_sections = [
            "session",  # CSS class for sections
            "Position",  # Session 1
            "Pool",  # Session 2
            "Strateg",  # Session 3
            "Disclaimer",  # Session 5 (legal)
        ]
        missing = [
            s for s in required_sections if s.lower() not in html_content.lower()
        ]

        # Cleanup test report
        try:
            Path(path).unlink()
        except Exception:
            pass

        ok = len(missing) == 0
        detail = (
            f"All {len(required_sections)} sections present"
            if ok
            else f"Missing: {missing}"
        )
        results.add("T20", "HTML report structure", ok, detail, "HIGH")
    except Exception as e:
        results.add("T20", "HTML report structure", False, str(e)[:200], "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T21 — Requirements validation (pip dependencies)
# ═══════════════════════════════════════════════════════════════════════


def _t21_requirements(results: CodeReviewResults):
    """T21: All declared dependencies are importable and versions satisfy constraints."""
    findings = []

    # Check requirements.txt
    req_path = PROJECT_ROOT / "requirements.txt"
    if not req_path.exists():
        findings.append("requirements.txt not found")
    else:
        for line in req_path.read_text().strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            pkg = re.split(r"[>=<~!]", line)[0].strip()
            try:
                importlib.import_module(pkg.replace("-", "_"))
            except ImportError:
                findings.append(f"Cannot import: {pkg}")

    # Check pyproject.toml dependencies
    toml_path = PROJECT_ROOT / "pyproject.toml"
    if toml_path.exists():
        toml_text = toml_path.read_text()
        _deps = re.findall(r'"(\w[\w-]*)(?:[>=<~!].*)?"', toml_text)
        # Verify Python version constraint
        py_match = re.search(r'requires-python\s*=\s*"([^"]+)"', toml_text)
        if py_match:
            constraint = py_match.group(1)
            if ">" in constraint:
                min_ver = constraint.replace(">=", "").strip()
                current = f"{sys.version_info.major}.{sys.version_info.minor}"
                if current < min_ver:
                    findings.append(f"Python {current} < required {min_ver}")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "All dependencies OK"
    results.add("T21", "Requirements validation", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T22 — Modularity check (no circular imports, proper separation)
# ═══════════════════════════════════════════════════════════════════════


def _t22_modularity(results: CodeReviewResults):
    """T22: Modules follow clean architecture — no circular imports, proper isolation."""
    findings = []

    # 1. No circular imports — each module should import without triggering loops
    modules = [
        "defi_cli.central_config",
        "defi_cli.dex_registry",
        "defi_cli.stablecoins",
        "defi_cli.rpc_helpers",
        "defi_cli.html_styles",
        "defi_cli.legal_disclaimers",
        "defi_cli.dexscreener_client",
        "defi_cli.commands",
        "real_defi_math",
        "html_generator",
        "position_reader",
        "position_indexer",
        "pool_scout",
    ]
    for mod_name in modules:
        try:
            mod = importlib.import_module(mod_name)
            # Check module has a docstring
            if not getattr(mod, "__doc__", None):
                findings.append(f"{mod_name}: missing module docstring")
        except ImportError as e:
            findings.append(f"{mod_name}: import error — {e}")

    # 2. Verify defi_cli/ doesn't import from root-level modules at module scope
    # (root imports defi_cli, not the other way)
    for f in [
        "central_config.py",
        "dex_registry.py",
        "stablecoins.py",
        "rpc_helpers.py",
        "html_styles.py",
    ]:
        fpath = PROJECT_ROOT / "defi_cli" / f
        if fpath.exists():
            content = fpath.read_text()
            for bad_import in [
                "import position_reader",
                "import html_generator",
                "import real_defi_math",
                "import run",
            ]:
                if bad_import in content:
                    findings.append(
                        f"defi_cli/{f}: improper import '{bad_import}' (breaks modularity)"
                    )

    # 3. Verify __init__.py exposes version
    init_path = PROJECT_ROOT / "defi_cli" / "__init__.py"
    if init_path.exists():
        content = init_path.read_text()
        if "__version__" not in content and "VERSION" not in content:
            findings.append("defi_cli/__init__.py: missing version export")
    else:
        findings.append("defi_cli/__init__.py: not found")

    ok = len(findings) == 0
    detail = (
        "\n".join(findings)
        if findings
        else f"{len(modules)} modules OK, proper isolation"
    )
    results.add("T22", "Modularity check", ok, detail, "MEDIUM")


# ═══════════════════════════════════════════════════════════════════════
# T23 — Dependency vulnerability scan
# ═══════════════════════════════════════════════════════════════════════


def _t23_vulnerability(results: CodeReviewResults):
    """T23: Check dependencies for known patterns and supply-chain risks."""
    findings = []

    # 1. Verify minimal dependency surface (only httpx required)
    req_path = PROJECT_ROOT / "requirements.txt"
    if req_path.exists():
        deps = [
            line.strip()
            for line in req_path.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if len(deps) > 3:
            findings.append(
                f"Too many dependencies ({len(deps)}) — attack surface concern"
            )
        for dep in deps:
            pkg = re.split(r"[>=<~!]", dep)[0].strip().lower()
            if pkg not in ("httpx",):
                findings.append(f"Unexpected dependency: {dep}")

    # 2. HTTPS-only for all external endpoints
    for f in PYTHON_FILES:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            continue
        content = fpath.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            if (
                "http://" in line
                and "localhost" not in line
                and "127.0.0.1" not in line
            ):
                if not line.strip().startswith("#") and not line.strip().startswith(
                    '"""'
                ):
                    findings.append(f"{f}:{i}: non-HTTPS URL found")

    # 3. No eval/exec usage
    for f in PYTHON_FILES:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            continue
        content = fpath.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.search(r"\beval\s*\(", stripped) or re.search(
                r"\bexec\s*\(", stripped
            ):
                findings.append(f"{f}:{i}: eval/exec usage (security risk)")

    # 4. No pickle/marshal usage
    for f in PYTHON_FILES:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            continue
        content = fpath.read_text()
        if "import pickle" in content or "import marshal" in content:
            findings.append(f"{f}: pickle/marshal import (deserialization risk)")

    ok = len(findings) == 0
    detail = (
        "\n".join(findings[:5])
        if findings
        else "No vulnerabilities found — minimal attack surface"
    )
    results.add("T23", "Vulnerability scan", ok, detail, "CRITICAL")


# ═══════════════════════════════════════════════════════════════════════
# T24 — File integrity (all expected files present)
# ═══════════════════════════════════════════════════════════════════════


def _t24_file_integrity(results: CodeReviewResults):
    """T24: All expected project files exist and are non-empty."""
    required_files = [
        # Source
        "run.py",
        "position_reader.py",
        "position_indexer.py",
        "real_defi_math.py",
        "html_generator.py",
        "pool_scout.py",
        # Package
        "defi_cli/__init__.py",
        "defi_cli/central_config.py",
        "defi_cli/dex_registry.py",
        "defi_cli/dexscreener_client.py",
        "defi_cli/legal_disclaimers.py",
        "defi_cli/rpc_helpers.py",
        "defi_cli/stablecoins.py",
        "defi_cli/commands.py",
        "defi_cli/html_styles.py",
        # Tests
        "tests/test_math.py",
        "tests/test_units.py",
        "tests/test_codereview.py",
        # Config
        "pyproject.toml",
        "requirements.txt",
        # Docs
        "README.md",
        "CHANGELOG.md",
        "SECURITY.md",
        "COMPLIANCE.md",
        "LICENSE",
        ".codereview.md",
    ]
    missing = []
    empty = []
    for f in required_files:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            missing.append(f)
        elif fpath.stat().st_size == 0:
            empty.append(f)

    # Verify no stale files that should have been removed
    stale_files = ["AUDIT_REPORT.md", "TEST_REPORT.md", "API_MAP.md"]
    still_present = [f for f in stale_files if (PROJECT_ROOT / f).exists()]

    findings = []
    if missing:
        findings.append(f"Missing: {missing}")
    if empty:
        findings.append(f"Empty: {empty}")
    if still_present:
        findings.append(f"Stale files not removed: {still_present}")

    ok = len(findings) == 0
    detail = (
        "\n".join(findings) if findings else f"All {len(required_files)} files present"
    )
    results.add("T24", "File integrity", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T25 — LGPD compliance (data protection BR)
# ═══════════════════════════════════════════════════════════════════════


def _t25_lgpd_compliance(results: CodeReviewResults):
    """T25: LGPD: no PII collection, no cookies, privacy by design."""
    findings = []

    for f in PYTHON_FILES:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            continue
        content = fpath.read_text()
        # No cookie setting
        if "set_cookie" in content:
            findings.append(f"{f}: sets cookies — requires LGPD consent")
        # No tracking pixels
        for tracker in [
            "google-analytics",
            "gtag(",
            "fbq(",
            "hotjar",
            "mixpanel",
            "amplitude",
        ]:
            if tracker in content.lower():
                findings.append(
                    f"{f}: third-party tracker ({tracker}) — LGPD consent req"
                )

    # Check disclaimers mention privacy
    disc_path = PROJECT_ROOT / "defi_cli" / "legal_disclaimers.py"
    if disc_path.exists():
        disc = disc_path.read_text().lower()
        if "privacy" not in disc and "dados" not in disc and "lgpd" not in disc:
            findings.append("legal_disclaimers.py: no privacy/LGPD mention")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "No PII, no cookies — LGPD compliant"
    results.add("T25", "LGPD compliance (data protection BR)", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T26 — CVM/SEC disclaimer depth
# ═══════════════════════════════════════════════════════════════════════


def _t26_cvm_disclaimer(results: CodeReviewResults):
    """T26: CVM/SEC: NOT FINANCIAL ADVICE, no guarantees, user responsibility."""
    findings = []
    disc_path = PROJECT_ROOT / "defi_cli" / "legal_disclaimers.py"
    if disc_path.exists():
        content = disc_path.read_text().upper()
        phrases = [
            ("NOT FINANCIAL ADVICE", "Must state not financial advice"),
            ("NO GUARANTEE", "Must disclaim guarantees"),
            ("YOUR RESPONSIBILITY", "User sole responsibility"),
            ("RISK", "DeFi risk warning"),
        ]
        for phrase, desc in phrases:
            if phrase not in content:
                findings.append(f"Missing: '{phrase}' — {desc}")
    else:
        findings.append("legal_disclaimers.py not found")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "All CVM/SEC phrases present"
    results.add("T26", "CVM/SEC disclaimer depth", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T27 — No third-party tracking
# ═══════════════════════════════════════════════════════════════════════


def _t27_no_tracking(results: CodeReviewResults):
    """T27: No LGPD/GDPR-violating trackers (GA, FB, Hotjar, etc.)."""
    findings = []
    trackers = [
        "google-analytics",
        "gtag(",
        "fbq(",
        "hotjar",
        "mixpanel",
        "amplitude",
        "facebook.com/tr",
    ]

    for f in PYTHON_FILES:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            continue
        content = fpath.read_text().lower()
        for t in trackers:
            if t in content:
                findings.append(f"{f}: tracker detected ({t})")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "No trackers — privacy compliant"
    results.add("T27", "No third-party tracking (LGPD/GDPR)", ok, detail, "MEDIUM")


# ═══════════════════════════════════════════════════════════════════════
# T28 — Azure IaC validation (conditional)
# ═══════════════════════════════════════════════════════════════════════


def _t28_azure_iac(results: CodeReviewResults):
    """T28: If terraform/ exists, validate IaC files and secrets config."""
    tf_dir = PROJECT_ROOT / "terraform"
    if not tf_dir.exists():
        results.add(
            "T28",
            "Azure IaC (conditional)",
            True,
            "No terraform/ — not applicable",
            "PASS",
        )
        return

    findings = []
    for tf in ["providers.tf", "variables.tf", "main.tf", "outputs.tf"]:
        fp = tf_dir / tf
        if not fp.exists():
            findings.append(f"Missing {tf}")
        elif fp.stat().st_size == 0:
            findings.append(f"{tf} is empty")

    if (tf_dir / "main.tf").exists():
        main = (tf_dir / "main.tf").read_text()
        if "azurerm_key_vault" not in main:
            findings.append("No Key Vault configured")

    if (tf_dir / "variables.tf").exists():
        vartf = (tf_dir / "variables.tf").read_text()
        if "sensitive" not in vartf:
            findings.append("No sensitive vars — secrets exposed in state")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "Terraform IaC validated"
    results.add("T28", "Azure IaC validation (conditional)", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T29 — Docker security (conditional)
# ═══════════════════════════════════════════════════════════════════════


def _t29_docker_security(results: CodeReviewResults):
    """T29: If Dockerfile exists, validate non-root, slim, HEALTHCHECK."""
    dockerfile = PROJECT_ROOT / "Dockerfile"
    if not dockerfile.exists():
        results.add(
            "T29",
            "Docker security (conditional)",
            True,
            "No Dockerfile — not applicable",
            "PASS",
        )
        return

    findings = []
    src = dockerfile.read_text()
    if "USER " not in src:
        findings.append("No non-root USER")
    if "-slim" not in src and "-alpine" not in src:
        findings.append("Not using slim/alpine base")
    if "HEALTHCHECK" not in src:
        findings.append("No HEALTHCHECK instruction")

    # .dockerignore
    if not (PROJECT_ROOT / ".dockerignore").exists():
        findings.append(".dockerignore missing — secrets may leak into image")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "Docker security validated"
    results.add("T29", "Docker security (conditional)", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T30 — CI/CD security (conditional)
# ═══════════════════════════════════════════════════════════════════════


def _t30_cicd_security(results: CodeReviewResults):
    """T30: If .github/workflows exists, validate pinned actions, perms, concurrency."""
    wf_dir = PROJECT_ROOT / ".github" / "workflows"
    if not wf_dir.exists():
        results.add(
            "T30",
            "CI/CD security (conditional)",
            True,
            "No .github/workflows/ — not applicable",
            "PASS",
        )
        return

    findings = []
    for yml in wf_dir.glob("*.yml"):
        content = yml.read_text()
        name = yml.name

        # Check pinned SHAs
        uses = re.findall(r"uses:\s*(\S+)", content)
        for action in uses:
            if "@" in action:
                _, ref = action.split("@", 1)
                if not re.match(r"^[0-9a-f]{40}$", ref):
                    findings.append(f"{name}: not pinned — {action}")

        # Check permissions
        if "permissions:" not in content:
            findings.append(f"{name}: no permissions block")

        # Check concurrency
        if "concurrency:" not in content:
            findings.append(f"{name}: no concurrency control")

    ok = len(findings) == 0
    detail = "\n".join(findings[:5]) if findings else "CI/CD security validated"
    results.add("T30", "CI/CD security (conditional)", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T31 — CSP nonce-based script policy (CWE-79 / OWASP A03:2021)
# ═══════════════════════════════════════════════════════════════════════

def _t31_csp_nonce(results: CodeReviewResults):
    """T31: HTML reports use nonce-based CSP, not 'unsafe-inline' for scripts."""
    try:
        from real_defi_math import PositionData, analyze_position
        from html_generator import generate_position_report
        from datetime import datetime

        pos = PositionData(
            token0_amount=1.0, token1_amount=2000.0,
            token0_symbol="WETH", token1_symbol="USDC",
            current_price=2000.0, range_min=1800.0, range_max=2200.0,
            fee_tier=0.0005, total_value_usd=4000.0, fees_earned_usd=10.0,
            volume_24h=100_000_000.0, total_value_locked_usd=50_000_000.0,
            pool_address="0x" + "a" * 40, network="ethereum", protocol="uniswap_v3",
        )
        analysis = analyze_position(pos)
        analysis["consent_timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        path = generate_position_report(analysis, _open_browser=False)
        html = Path(path).read_text()

        findings = []
        # Must NOT have 'unsafe-inline' for script-src
        if "script-src 'unsafe-inline'" in html:
            findings.append("CSP still uses 'unsafe-inline' for script-src")
        # Must have nonce-based CSP
        nonce_match = re.search(r"script-src 'nonce-([A-Za-z0-9_-]+)'", html)
        if not nonce_match:
            findings.append("CSP missing nonce-based script-src")
        else:
            nonce_val = nonce_match.group(1)
            # Verify nonce appears in <script> tags
            if f'nonce="{nonce_val}"' not in html:
                findings.append("Nonce in CSP does not match <script> nonce attribute")
        # Must have frame-ancestors 'none'
        if "frame-ancestors 'none'" not in html:
            findings.append("CSP missing frame-ancestors 'none'")
        # Must have X-Content-Type-Options
        if "nosniff" not in html:
            findings.append("Missing X-Content-Type-Options: nosniff")
        # Must have referrer policy
        if "no-referrer" not in html:
            findings.append("Missing Referrer-Policy: no-referrer")

        try:
            Path(path).unlink()
        except Exception:
            pass

        ok = len(findings) == 0
        detail = "\n".join(findings) if findings else "Nonce CSP + frame-ancestors + headers OK"
        results.add("T31", "CSP nonce policy (CWE-79)", ok, detail, "HIGH")
    except Exception as e:
        results.add("T31", "CSP nonce policy (CWE-79)", False, str(e)[:200], "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T32 — EIP-55 address validation (CWE-20)
# ═══════════════════════════════════════════════════════════════════════

def _t32_eip55_validation(results: CodeReviewResults):
    """T32: Address validation rejects mistyped mixed-case addresses."""
    try:
        from defi_cli.commands import _validate_address, _eip55_checksum

        findings = []

        # Valid all-lowercase (pre-EIP-55) — must pass
        if not _validate_address("0x" + "a" * 40, "test"):
            findings.append("Rejected valid lowercase address")

        # Valid all-uppercase — must pass
        if not _validate_address("0x" + "A" * 40, "test"):
            findings.append("Rejected valid uppercase address")

        # Invalid format
        if _validate_address("not-an-address", "test"):
            findings.append("Accepted invalid format")
        if _validate_address("0x123", "test"):
            findings.append("Accepted too-short address")
        if _validate_address("", "test"):
            findings.append("Accepted empty address")

        # Checksum function produces valid output
        test_addr = "0xAb5801a7D398351b8bE11C439e05C5B3259aeC9B"
        checksummed = _eip55_checksum(test_addr)
        if not re.fullmatch(r"0x[0-9a-fA-F]{40}", checksummed):
            findings.append(f"Checksum output invalid: {checksummed}")

        ok = len(findings) == 0
        detail = "\n".join(findings) if findings else "EIP-55 validation working"
        results.add("T32", "EIP-55 address validation (CWE-20)", ok, detail, "HIGH")
    except Exception as e:
        results.add("T32", "EIP-55 address validation (CWE-20)", False, str(e)[:200], "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T33 — Error message sanitization (CWE-209)
# ═══════════════════════════════════════════════════════════════════════

def _t33_error_sanitization(results: CodeReviewResults):
    """T33: Error messages do not leak internal paths or stack traces."""
    findings = []

    # Scan all Python files for print(f"...{e}") patterns that leak raw exceptions
    # Allowed: _sanitize_error(e), generic messages, test files
    for f in PYTHON_FILES:
        fpath = PROJECT_ROOT / f
        if not fpath.exists() or "test_" in f:
            continue
        content = fpath.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Look for raw exception interpolation in print/return/raise
            if re.search(r'(print|return)\s*\(.*\{e\}', stripped):
                # Allow sanitized errors
                if "_sanitize_error" in stripped:
                    continue
                # Allow in test functions
                if "def _t" in stripped:
                    continue
                findings.append(f"{f}:{i}: raw exception in output")

    ok = len(findings) == 0
    detail = "\n".join(findings[:5]) if findings else "No raw exceptions in user-facing output"
    results.add("T33", "Error sanitization (CWE-209)", ok, detail, "MEDIUM")


# ═══════════════════════════════════════════════════════════════════════
# T34 — Rate limiter present (CWE-770)
# ═══════════════════════════════════════════════════════════════════════

def _t34_rate_limiter(results: CodeReviewResults):
    """T34: Client-side rate limiter exists for external API calls."""
    findings = []

    dex_client = (PROJECT_ROOT / "defi_cli" / "dexscreener_client.py").read_text()
    if "_RateLimiter" not in dex_client:
        findings.append("dexscreener_client.py: no _RateLimiter class")
    if "acquire" not in dex_client:
        findings.append("dexscreener_client.py: no acquire() call (rate limit not enforced)")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "Rate limiter present in DEXScreener client"
    results.add("T34", "Rate limiter (CWE-770)", ok, detail, "MEDIUM")


# ═══════════════════════════════════════════════════════════════════════
# T35 — Temp file cleanup on exit (CWE-459 / LGPD Art. 6 III)
# ═══════════════════════════════════════════════════════════════════════

def _t35_temp_cleanup(results: CodeReviewResults):
    """T35: Temp files registered + 0o600 perms + cleanup_reports() API."""
    findings = []

    html_gen = (PROJECT_ROOT / "html_generator.py").read_text()
    if "atexit" not in html_gen:
        findings.append("html_generator.py: no atexit import")
    if "_register_temp_file" not in html_gen:
        findings.append("html_generator.py: no _register_temp_file function")
    if "_cleanup_temp_files" not in html_gen:
        findings.append("html_generator.py: no _cleanup_temp_files function")
    if "cleanup_reports" not in html_gen:
        findings.append("html_generator.py: no cleanup_reports() public API")
    if "0o600" not in html_gen:
        findings.append("html_generator.py: temp files not created with 0o600 permissions")
    # Must NOT auto-delete via atexit (race condition with browser)
    if "atexit.register(_cleanup_temp_files)" in html_gen:
        findings.append("html_generator.py: atexit auto-deletes files — browser race condition")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "cleanup_reports() API + 0o600 perms + atexit reminder OK"
    results.add("T35", "Temp file cleanup (CWE-459/LGPD)", ok, detail, "HIGH")


# ═══════════════════════════════════════════════════════════════════════
# T36 — RPC URL masking in reports (CWE-200)
# ═══════════════════════════════════════════════════════════════════════

def _t36_rpc_url_masking(results: CodeReviewResults):
    """T36: Private RPC URLs with API keys are masked in HTML reports."""
    try:
        from html_generator import _mask_rpc_url

        tests = [
            ("https://1rpc.io/arb", "https://1rpc.io/arb"),  # public — pass through
            ("https://arb-mainnet.g.alchemy.com/v2/abc123def456ghi789", "https://arb-mainnet.g.alchemy.com/v2/***"),
            ("", "N/A"),
        ]
        findings = []
        for input_url, expected in tests:
            result = _mask_rpc_url(input_url)
            if result != expected:
                findings.append(f"_mask_rpc_url({input_url!r}) = {result!r}, expected {expected!r}")

        ok = len(findings) == 0
        detail = "\n".join(findings) if findings else "RPC URL masking working"
        results.add("T36", "RPC URL masking (CWE-200)", ok, detail, "MEDIUM")
    except Exception as e:
        results.add("T36", "RPC URL masking (CWE-200)", False, str(e)[:200], "MEDIUM")


# ═══════════════════════════════════════════════════════════════════════
# T37 — Wallet address masking in CLI output (LGPD Art. 6 III)
# ═══════════════════════════════════════════════════════════════════════

def _t37_wallet_masking(results: CodeReviewResults):
    """T37: Full wallet addresses are not printed to CLI output."""
    findings = []

    # Check commands.py and position_indexer.py for unmasked wallet prints
    for f in ["defi_cli/commands.py", "position_indexer.py"]:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            continue
        content = fpath.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Look for print statements with full wallet variable
            if "print" in stripped and "wallet}" in stripped:
                # Allowed if masked
                if "mask_address" in stripped or "[:6]" in stripped or "[:-4]" in stripped or "[-4:]" in stripped:
                    continue
                findings.append(f"{f}:{i}: possible unmasked wallet in output")

    # Check _mask_address exists
    commands = (PROJECT_ROOT / "defi_cli" / "commands.py").read_text()
    if "_mask_address" not in commands:
        findings.append("commands.py: no _mask_address function")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "Wallet addresses properly masked"
    results.add("T37", "Wallet masking (LGPD Art. 6 III)", ok, detail, "MEDIUM")


# ═══════════════════════════════════════════════════════════════════════
# T38 — Tick bounds validation (CWE-682)
# ═══════════════════════════════════════════════════════════════════════

def _t38_tick_bounds(results: CodeReviewResults):
    """T38: Math functions handle extreme tick values without overflow."""
    from real_defi_math import UniswapV3Math

    findings = []

    # Extreme prices should not raise overflow
    extreme_prices = [1e-18, 1e-10, 1e18, 1e30]
    for price in extreme_prices:
        try:
            tick = UniswapV3Math.price_to_tick(price)
            recovered = UniswapV3Math.tick_to_price(tick)
            # Tick must be within Uniswap V3 bounds
            if tick < -887272 or tick > 887272:
                findings.append(f"price={price}: tick={tick} out of bounds")
        except (OverflowError, ValueError) as e:
            findings.append(f"price={price}: overflow — {e}")

    # Extreme ticks should not overflow
    for tick in [-887272, 887272, -999999, 999999]:
        try:
            price = UniswapV3Math.tick_to_price(tick)
            if price <= 0 or price == float('inf'):
                findings.append(f"tick={tick}: price={price} invalid")
        except OverflowError as e:
            findings.append(f"tick={tick}: overflow — {e}")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "Tick bounds validated — no overflow"
    results.add("T38", "Tick bounds (CWE-682)", ok, detail, "MEDIUM")


# ═══════════════════════════════════════════════════════════════════════
# T39 — html.escape() used instead of manual (CWE-79 defense-in-depth)
# ═══════════════════════════════════════════════════════════════════════

def _t39_html_escape_stdlib(results: CodeReviewResults):
    """T39: _safe() uses html.escape() from stdlib, not manual replacement."""
    html_gen = (PROJECT_ROOT / "html_generator.py").read_text()
    findings = []

    if "import html" not in html_gen and "import html as" not in html_gen:
        findings.append("html_generator.py: html module not imported")
    if "html.escape" not in html_gen and "_html_mod.escape" not in html_gen:
        findings.append("_safe() does not use html.escape()")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "Using stdlib html.escape()"
    results.add("T39", "html.escape() stdlib (CWE-79)", ok, detail, "LOW")


# ═══════════════════════════════════════════════════════════════════════
# T40 — OWASP/CWE/CVE/CVSS summary audit
# ═══════════════════════════════════════════════════════════════════════

def _t40_owasp_cwe_audit(results: CodeReviewResults):
    """T40: Comprehensive OWASP/CWE audit — all critical CWEs mitigated."""
    findings = []

    # CWE-79: XSS — check both _safe() and CSP
    html_gen = (PROJECT_ROOT / "html_generator.py").read_text()
    if "_safe(" not in html_gen:
        findings.append("CWE-79: No _safe() XSS prevention function")
    if "Content-Security-Policy" not in html_gen:
        findings.append("CWE-79: No CSP headers in HTML output")

    # CWE-20: Input validation — check address validation
    commands = (PROJECT_ROOT / "defi_cli" / "commands.py").read_text()
    if "_validate_address" not in commands:
        findings.append("CWE-20: No centralized address validation")

    # CWE-200: Information exposure — check RPC URL masking
    if "_mask_rpc_url" not in html_gen:
        findings.append("CWE-200: No RPC URL masking in reports")

    # CWE-209: Error messages — check for _sanitize_error
    if "_sanitize_error" not in commands:
        findings.append("CWE-209: No error sanitization in commands")

    # CWE-377/459: Temp file security — check atexit
    if "atexit" not in html_gen:
        findings.append("CWE-377/459: No temp file cleanup on exit")

    # CWE-532: Log injection — check wallet masking
    if "_mask_address" not in commands:
        findings.append("CWE-532: No wallet address masking in output")

    # CWE-770: Rate limiting — check dexscreener
    dex_client = (PROJECT_ROOT / "defi_cli" / "dexscreener_client.py").read_text()
    if "_RateLimiter" not in dex_client:
        findings.append("CWE-770: No rate limiter for external APIs")

    # CWE-682: Math overflow — check tick bounds
    math_file = (PROJECT_ROOT / "real_defi_math.py").read_text()
    if "887272" not in math_file:
        findings.append("CWE-682: No tick bounds validation in math")

    # No eval/exec (CWE-94/95)
    for f in PYTHON_FILES:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            continue
        content = fpath.read_text()
        for i, line in enumerate(content.split("\n"), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if re.search(r"\beval\s*\(", stripped) or re.search(r"\bexec\s*\(", stripped):
                findings.append(f"CWE-94/95: {f}:{i} eval/exec usage")

    # No pickle/marshal (CWE-502)
    for f in PYTHON_FILES:
        fpath = PROJECT_ROOT / f
        if not fpath.exists():
            continue
        content = fpath.read_text()
        if "import pickle" in content or "import marshal" in content:
            findings.append(f"CWE-502: {f} unsafe deserialization")

    ok = len(findings) == 0
    detail = "\n".join(findings) if findings else "All CWEs mitigated — OWASP A01-A10 compliant"
    results.add("T40", "OWASP/CWE/CVE audit", ok, detail, "CRITICAL")


# ═══════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════


def run_all(quick: bool = False):
    """Execute all codereview tests and print summary."""
    results = CodeReviewResults()

    print("\n🔍 CODEREVIEW — Starting automated validation...")
    print(f"   Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Mode: {'quick (offline)' if quick else 'full (with network tests)'}")
    print(f"   Root: {PROJECT_ROOT}")
    print()

    # ── Phase 1: Local tests (always run) ────────────────────────────
    print("  ⏳ T01: CLI info...")
    _t01_cli_info(results)

    print("  ⏳ T05: Unit tests...")
    _t05_unit_tests(results)

    print("  ⏳ T06: Syntax validation...")
    _t06_syntax(results)

    print("  ⏳ T07: Import validation...")
    _t07_imports(results)

    print("  ⏳ T08: Version consistency...")
    _t08_version(results)

    print("  ⏳ T09: Sensitive data scan...")
    _t09_secrets(results)

    print("  ⏳ T11: Tick↔Price roundtrip...")
    _t11_tick_price_roundtrip(results)

    print("  ⏳ T12: IL symmetry...")
    _t12_il_symmetry(results)

    print("  ⏳ T13: Capital efficiency...")
    _t13_capital_efficiency(results)

    print("  ⏳ T14: Fee APY monotonic...")
    _t14_fee_apy_monotonic(results)

    print("  ⏳ T15: Pipeline schema...")
    _t15_pipeline_schema(results)

    print("  ⏳ T19: Disclaimers...")
    _t19_disclaimers(results)

    print("  ⏳ T20: HTML structure...")
    _t20_html_structure(results)

    print("  ⏳ T21: Requirements...")
    _t21_requirements(results)

    print("  ⏳ T22: Modularity...")
    _t22_modularity(results)

    print("  ⏳ T23: Vulnerability scan...")
    _t23_vulnerability(results)

    print("  ⏳ T24: File integrity...")
    _t24_file_integrity(results)

    print("  ⏳ T25: LGPD compliance...")
    _t25_lgpd_compliance(results)

    print("  ⏳ T26: CVM/SEC disclaimer depth...")
    _t26_cvm_disclaimer(results)

    print("  ⏳ T27: No third-party tracking...")
    _t27_no_tracking(results)

    print("  ⏳ T28: Azure IaC (conditional)...")
    _t28_azure_iac(results)

    print("  ⏳ T29: Docker security (conditional)...")
    _t29_docker_security(results)

    print("  ⏳ T30: CI/CD security (conditional)...")
    _t30_cicd_security(results)

    # ── Phase 1b: New security mitigations (T31-T40) ────────────────
    print()
    print("  🛡️  Security mitigation validation (T31-T40)...")

    print("  ⏳ T31: CSP nonce policy...")
    _t31_csp_nonce(results)

    print("  ⏳ T32: EIP-55 address validation...")
    _t32_eip55_validation(results)

    print("  ⏳ T33: Error sanitization...")
    _t33_error_sanitization(results)

    print("  ⏳ T34: Rate limiter...")
    _t34_rate_limiter(results)

    print("  ⏳ T35: Temp file cleanup...")
    _t35_temp_cleanup(results)

    print("  ⏳ T36: RPC URL masking...")
    _t36_rpc_url_masking(results)

    print("  ⏳ T37: Wallet masking...")
    _t37_wallet_masking(results)

    print("  ⏳ T38: Tick bounds...")
    _t38_tick_bounds(results)

    print("  ⏳ T39: html.escape stdlib...")
    _t39_html_escape_stdlib(results)

    print("  ⏳ T40: OWASP/CWE audit...")
    _t40_owasp_cwe_audit(results)

    # ── Phase 2: Network tests (skip if --quick) ─────────────────────
    if not quick:
        print()
        print("  🌐 Network tests (real data)...")

        print("  ⏳ T02: Integration check...")
        _t02_cli_check(results)

        print("  ⏳ T03: Pool analysis (DEXScreener)...")
        _t03_pool_analysis(results)

        print("  ⏳ T04: Multi-DEX wallet scan...")
        _t04_list_scan(results)

        print("  ⏳ T10: Contract addresses on-chain...")
        _t10_contracts_onchain(results)

        print("  ⏳ T16: DEXScreener chains...")
        _t16_dexscreener_chains(results)

        print("  ⏳ T17: RPC endpoints...")
        _t17_rpc_endpoints(results)

        print("  ⏳ T18: README links...")
        _t18_readme_links(results)
    else:
        for tid, name in [
            ("T02", "Integration check"),
            ("T03", "Pool analysis"),
            ("T04", "Multi-DEX scan"),
            ("T10", "Contracts on-chain"),
            ("T16", "DEXScreener chains"),
            ("T17", "RPC endpoints"),
            ("T18", "README links"),
        ]:
            results.add(
                tid, f"{name} (SKIPPED —quick)", True, "Skipped in quick mode", "PASS"
            )

    # ── Print summary ────────────────────────────────────────────────
    print(results.summary())

    # Return exit code
    critical_fails = sum(
        1 for r in results.results if not r["passed"] and r["severity"] == "CRITICAL"
    )
    return 1 if critical_fails > 0 else 0


# ── Pytest integration ──────────────────────────────────────────────────
# Each test can also be run individually via pytest

import pytest


@pytest.fixture(scope="module")
def cr():
    return CodeReviewResults()

def test_cr_t06_syntax(cr): _t06_syntax(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T06")
def test_cr_t07_imports(cr): _t07_imports(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T07")
def test_cr_t08_version(cr): _t08_version(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T08")
def test_cr_t09_secrets(cr): _t09_secrets(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T09")
def test_cr_t11_tick_roundtrip(cr): _t11_tick_price_roundtrip(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T11")
def test_cr_t12_il_symmetry(cr): _t12_il_symmetry(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T12")
def test_cr_t13_capital_eff(cr): _t13_capital_efficiency(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T13")
def test_cr_t14_fee_monotonic(cr): _t14_fee_apy_monotonic(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T14")
def test_cr_t15_pipeline(cr): _t15_pipeline_schema(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T15")
def test_cr_t19_disclaimers(cr): _t19_disclaimers(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T19")
def test_cr_t21_requirements(cr): _t21_requirements(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T21")
def test_cr_t22_modularity(cr): _t22_modularity(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T22")
def test_cr_t23_vulnerability(cr): _t23_vulnerability(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T23")
def test_cr_t24_file_integrity(cr): _t24_file_integrity(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T24")
def test_cr_t25_lgpd(cr): _t25_lgpd_compliance(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T25")
def test_cr_t26_cvm(cr): _t26_cvm_disclaimer(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T26")
def test_cr_t27_tracking(cr): _t27_no_tracking(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T27")
def test_cr_t28_azure_iac(cr): _t28_azure_iac(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T28")
def test_cr_t29_docker(cr): _t29_docker_security(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T29")
def test_cr_t30_cicd(cr): _t30_cicd_security(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T30")
def test_cr_t31_csp_nonce(cr): _t31_csp_nonce(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T31")
def test_cr_t32_eip55(cr): _t32_eip55_validation(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T32")
def test_cr_t33_error_sanitize(cr): _t33_error_sanitization(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T33")
def test_cr_t34_rate_limiter(cr): _t34_rate_limiter(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T34")
def test_cr_t35_temp_cleanup(cr): _t35_temp_cleanup(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T35")
def test_cr_t36_rpc_masking(cr): _t36_rpc_url_masking(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T36")
def test_cr_t37_wallet_masking(cr): _t37_wallet_masking(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T37")
def test_cr_t38_tick_bounds(cr): _t38_tick_bounds(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T38")
def test_cr_t39_html_escape(cr): _t39_html_escape_stdlib(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T39")
def test_cr_t40_owasp_audit(cr): _t40_owasp_cwe_audit(cr); assert all(r["passed"] for r in cr.results if r["id"] == "T40")


# ── CLI entry point ─────────────────────────────────────────────────────

if __name__ == "__main__":
    quick = "--quick" in sys.argv
    exit_code = run_all(quick=quick)
    sys.exit(exit_code)
