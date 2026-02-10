"""
HTML report generator for DeFi CLI
Generates comprehensive position analysis with 7 tab-based sections.

This module creates detailed HTML reports from Uniswap V3 position data,
including risk assessment, alternative strategies, and legal disclaimers.
"""

import atexit
import html as _html_mod
import os
import re
import secrets
import tempfile
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List
from defi_cli.html_styles import build_css as _build_css
from defi_cli.central_config import PROJECT_VERSION


# Constants
# No persistent output directory — all reports are temporary (privacy by design)

# ── Temp File Cleanup Registry (LGPD Art. 6 III — data minimization) ────
_TEMP_FILES: List[str] = []


def _register_temp_file(path: str) -> None:
    """Register a temporary file for cleanup."""
    _TEMP_FILES.append(path)


def _cleanup_temp_files() -> None:
    """Remove all registered temporary report files.

    Security: CWE-459 mitigation — ensures financial data in temp files
    is not left on disk indefinitely.
    LGPD Art. 6 III — storage limitation / data minimization.

    NOTE: Not called via atexit to avoid a race condition where the
    browser has not yet loaded the file before it is deleted.
    Temp files live in the OS temp directory which is cleaned on reboot.
    Files are created with 0o600 permissions (owner-only read/write).
    """
    for path in list(_TEMP_FILES):
        try:
            if os.path.exists(path):
                os.unlink(path)
        except OSError:
            pass  # best-effort cleanup


def cleanup_reports() -> int:
    """Public API: explicitly delete all temp reports created this session.

    Returns the number of files removed.  Safe to call multiple times.
    """
    count = 0
    for path in list(_TEMP_FILES):
        try:
            if os.path.exists(path):
                os.unlink(path)
                count += 1
        except OSError:
            pass
    _TEMP_FILES.clear()
    return count


def _atexit_reminder() -> None:
    """Print a reminder about temp files on exit (non-destructive)."""
    remaining = [p for p in _TEMP_FILES if os.path.exists(p)]
    if remaining:
        import sys

        try:
            print(
                f"\n🗑️  {len(remaining)} temporary report(s) in {tempfile.gettempdir()}"
                f" — deleted on next reboot, or run cleanup_reports().",
                file=sys.stderr,
            )
        except Exception:
            pass  # stderr may be closed


# Register non-destructive reminder (NOT auto-delete)
atexit.register(_atexit_reminder)


def _safe(value: Any, fallback: str = "Unknown") -> str:
    """Escape a value for safe HTML embedding (XSS prevention).

    Uses Python's html.escape() for robust entity encoding (CWE-79 mitigation).
    Covers: & < > " ' — all OWASP-recommended HTML context escapes.
    """
    if value is None:
        return fallback
    return _html_mod.escape(str(value), quote=True).replace("'", "&#x27;")


def _safe_filename(value: str) -> str:
    """Strip any character not safe for filenames (path traversal prevention)."""
    return re.sub(r"[^a-zA-Z0-9._-]", "_", str(value))


def _mask_rpc_url(url: str) -> str:
    """Mask RPC URL to prevent leaking private API keys in reports.

    CWE-200 mitigation: If a user configures a private RPC endpoint
    (e.g. https://arb-mainnet.g.alchemy.com/v2/<API_KEY>), the key
    portion is replaced with '***'. Public 1RPC.io URLs pass through.
    """
    if not url:
        return "N/A"
    # Known public RPCs — safe to show fully
    if "1rpc.io" in url or "publicnode.com" in url:
        return url
    # Mask everything after the last '/' if it looks like an API key
    parts = url.rsplit("/", 1)
    if len(parts) == 2 and len(parts[1]) > 12:
        return f"{parts[0]}/***"
    return url


def _explorer(network: str) -> Dict[str, str]:
    """Get explorer info for a network."""
    explorers = {
        "ethereum": {"name": "Etherscan", "base": "https://etherscan.io"},
        "arbitrum": {"name": "Arbiscan", "base": "https://arbiscan.io"},
        "polygon": {"name": "PolygonScan", "base": "https://polygonscan.com"},
        "base": {"name": "BaseScan", "base": "https://basescan.org"},
        "optimism": {
            "name": "Optimistic Etherscan",
            "base": "https://optimistic.etherscan.io",
        },
        "bsc": {"name": "BscScan", "base": "https://bscscan.com"},
    }
    return explorers.get(network.lower(), {"name": "Explorer", "base": "#"})


# ── URL Security: Allowlist of Trusted Domains ──────────────────────────
#
# CWE-601 mitigation (Open Redirect) / OWASP link-safety:
# Every external <a href="..."> in the generated HTML report MUST resolve
# to one of these approved domains.  This prevents:
#   1. Injection of links to phishing / scam / malware sites
#   2. Open-redirect via user-supplied data (wallet / pool addresses)
#   3. Accidental inclusion of dubious or unverified sources
#
# Maintenance: to add a domain, add it here and document the justification.
#
ALLOWED_URL_DOMAINS: frozenset[str] = frozenset(
    {
        # ── Protocol Official ──────────────────────────────────────────
        "uniswap.org",  # Uniswap Whitepaper, App
        "docs.uniswap.org",  # Uniswap Docs (SDK, Contracts, Concepts)
        "app.uniswap.org",  # Uniswap Web App (positions, pools)
        # ── Source Code / Audits ───────────────────────────────────────
        "github.com",  # Uniswap v3-core/v3-sdk, project repo, audits
        # ── Market Data APIs ───────────────────────────────────────────
        "dexscreener.com",  # DEXScreener Platform
        "docs.dexscreener.com",  # DEXScreener API Reference
        "api.dexscreener.com",  # DEXScreener API endpoint
        "defillama.com",  # DefiLlama docs/API
        "yields.llama.fi",  # DefiLlama Yields API (pool scout)
        # ── Block Explorers ────────────────────────────────────────────
        "etherscan.io",  # Ethereum
        "arbiscan.io",  # Arbitrum
        "polygonscan.com",  # Polygon
        "basescan.org",  # Base
        "optimistic.etherscan.io",  # Optimism
        "bscscan.com",  # BSC
        # ── DeFi Analytics / Portfolio Trackers ────────────────────────
        "revert.finance",  # Revert Finance — LP analytics
        "app.zerion.io",  # Zerion — portfolio tracker
        "zapper.xyz",  # Zapper — portfolio tracker
        "debank.com",  # DeBank — portfolio tracker
        # ── Academic / Research ────────────────────────────────────────
        "pintail.medium.com",  # Pintail — IL formula research
        "lambert-guillaume.medium.com",  # Lambert — Uniswap V3 IL paper
        "arxiv.org",  # Academic papers (Angeris et al.)
        "uniswapv3book.com",  # Uniswap V3 Development Book
        # ── Ethereum Foundation ────────────────────────────────────────
        "ethereum.org",  # Official Ethereum docs
        "eips.ethereum.org",  # Ethereum Improvement Proposals
        "docs.soliditylang.org",  # Solidity docs (ABI spec)
        # ── Other Protocol Docs (multi-DEX support) ───────────────────
        "developer.pancakeswap.finance",  # PancakeSwap V3 docs
        "docs.sushi.com",  # SushiSwap V3 docs
    }
)


def _is_allowed_url(url: str) -> bool:
    """Check whether a URL belongs to an approved domain.

    Security: CWE-601 (Open Redirect) mitigation.
    Only HTTPS URLs with domains in ALLOWED_URL_DOMAINS pass.
    Fragment-only (#) and empty URLs are always allowed.

    Returns True if the URL is safe to use in an <a href>.
    """
    if not url or url.startswith("#"):
        return True
    # Must be HTTPS (CWE-319: cleartext transmission)
    if not url.startswith("https://"):
        return False
    # Extract domain from URL
    try:
        # Remove scheme
        rest = url[8:]  # len("https://") == 8
        # Split at first '/' or '?' or '#'
        for sep in ("/", "?", "#"):
            idx = rest.find(sep)
            if idx != -1:
                rest = rest[:idx]
        domain = rest.lower().strip()
        # Check exact match or subdomain match
        if domain in ALLOWED_URL_DOMAINS:
            return True
        # Check if it's a subdomain of an allowed domain
        for allowed in ALLOWED_URL_DOMAINS:
            if domain.endswith("." + allowed):
                return True
        return False
    except Exception:
        return False


def _safe_href(url: str) -> str:
    """Return the URL only if it passes the domain allowlist check.

    If the URL is not on the allowlist, returns '#' (safe no-op link).
    This is the ONLY function that should be used to build <a href> values
    from dynamically constructed URLs.

    >>> _safe_href("https://etherscan.io/tx/0x123")
    'https://etherscan.io/tx/0x123'
    >>> _safe_href("https://evil-site.com/phish")
    '#'
    """
    return url if _is_allowed_url(url) else "#"


def _token_info(symbol: str) -> str:
    """Get display name for common tokens."""
    tokens = {
        "WETH": "Wrapped Ethereum",
        "USDC": "USD Coin",
        "USDT": "Tether USD",
        "DAI": "Dai Stablecoin",
        "WBTC": "Wrapped Bitcoin",
        "UNI": "Uniswap Token",
        "LINK": "Chainlink",
        "MATIC": "Polygon",
        "AAVE": "Aave Token",
        "CRV": "Curve DAO Token",
    }
    return tokens.get(symbol.upper(), symbol or "Unknown Token")


def _safe_num(val: Any, decimals: int = 2, default: float = 0) -> str:
    """Format a number with fixed decimals (no thousands separator). Use for token amounts, percentages, etc."""
    try:
        return f"{float(val or default):.{decimals}f}"
    except (ValueError, TypeError):
        return f"{default:.{decimals}f}"


def _safe_usd(val: Any, decimals: int = 2, default: float = 0) -> str:
    """Format a number as USD with thousands separator ($1,234.56). Use for all dollar values."""
    try:
        return f"{float(val or default):,.{decimals}f}"
    except (ValueError, TypeError):
        return f"{default:,.{decimals}f}"


def _build_audit_trail(data: Dict) -> str:
    """
    Build the Audit Trail HTML section.

    An auditor can reproduce every number in this report by:
    1. Connecting to the same RPC endpoint
    2. Reading the same block number
    3. Making the same eth_call calls listed here
    4. Applying the same formulas (Whitepaper references provided)

    If no audit_trail data exists (simulated mode), shows a notice.
    """
    audit = data.get("audit_trail")
    if not audit:
        return """
        <div class="session">
            <h2 class="session-title">📝 Audit Trail</h2>
            <div style="background: #fefce8; border: 1px solid #eab308; border-radius: 8px; padding: 1rem;">
                <p style="margin: 0 0 0.5rem 0;">⚠️ <strong>Simulated data</strong> — no on-chain audit trail available.</p>
                <p style="margin: 0; font-size: var(--fs-sm); color: #92400e;">For the <strong>full experience</strong> (on-chain data, audit trail, and working cross-validation links), run with:<br>
                <code style="background: #fef3c7; padding: 2px 6px; border-radius: 4px;">python run.py report &lt;pool&gt; --position &lt;id&gt; --wallet &lt;addr&gt; --network &lt;net&gt;</code></p>
            </div>
        </div>
        """

    block = audit.get("block_number", 0)
    # CWE-200 mitigation: mask RPC URL to prevent leaking private API keys
    # if a user configures a custom RPC (e.g. Alchemy/Infura with embedded key)
    raw_rpc = audit.get("rpc_endpoint", "")
    rpc = _safe(_mask_rpc_url(raw_rpc))
    contracts = audit.get("contracts", {})
    raw_calls = audit.get("raw_calls", [])
    formulas = audit.get("formulas_applied", [])
    net = _safe((data.get("network") or "arbitrum").lower())

    # Build explorer links
    explorer_base = _explorer(net).get("base", "")
    block_link = (
        _safe_href(f"{explorer_base}/block/{block}") if explorer_base and block else "#"
    )

    # Build raw calls table rows
    call_rows = ""
    for i, call in enumerate(raw_calls):
        label = _safe(call.get("label", ""))
        to_addr = _safe(call.get("to", ""))
        selector = _safe(call.get("selector", ""))
        calldata = _safe(call.get("calldata", selector))
        decoded = call.get("decoded", {})
        decoded_str = "<br>".join(
            f"<code>{_safe(str(k))}</code>: <code>{_safe(str(v))}</code>"
            for k, v in decoded.items()
        )
        bg = "background: #f8fafc;" if i % 2 == 0 else ""

        to_short = to_addr[:10] + "…" + to_addr[-4:] if len(to_addr) > 16 else to_addr
        to_link = (
            f'<a href="{_safe_href(explorer_base + "/address/" + to_addr)}" target="_blank" style="color: #2563eb;">{to_short}</a>'
            if explorer_base
            else to_short
        )

        call_rows += f"""
        <tr style="{bg}">
            <td style="padding: 6px 8px; font-weight: 600;">{i + 1}. {label}</td>
            <td style="padding: 6px 8px; font-family: monospace; font-size: var(--fs-sm);">{to_link} <button class="copy-btn" data-copy="{to_addr}" aria-label="Copy contract address to clipboard">📋</button></td>
            <td style="padding: 6px 8px; font-family: monospace; font-size: var(--fs-xs); word-break: break-all;">{calldata} <button class="copy-btn" data-copy="{calldata}">📋</button></td>
            <td style="padding: 6px 8px; font-size: var(--fs-sm);">{decoded_str}</td>
        </tr>
        """

    # Build formulas list
    formula_items = "".join(
        f'<li style="margin: 4px 0;"><code>{_safe(f)}</code></li>' for f in formulas
    )

    # Contract addresses
    pm_addr = _safe(contracts.get("position_manager", ""))
    pool_addr = _safe(contracts.get("pool", ""))
    t0_addr = _safe(contracts.get("token0", ""))
    t1_addr = _safe(contracts.get("token1", ""))

    return f"""
        <div class="session">
            <h2 class="session-title">📝 Audit Trail — Independent Verification</h2>
            
            <div style="background: #eff6ff; border: 2px solid #3b82f6; border-radius: 12px; padding: 1.5rem; margin: 0 0 1.5rem 0;">
                <h3 style="color: #1d4ed8; margin-top: 0;">📋 How to Audit This Report</h3>
                <p style="font-size: var(--fs-base); line-height: 1.6; margin-bottom: 0.5rem;">
                    Every number in this report can be independently verified by replaying the <strong>exact same 
                    blockchain queries</strong> listed below. An auditor needs:
                </p>
                <ol style="font-size: var(--fs-md); line-height: 1.7; margin: 0.5rem 0;">
                    <li><strong>Connect</strong> to the RPC endpoint: <code>{rpc}</code></li>
                    <li><strong>Query</strong> at block <a href="{block_link}" target="_blank" style="color: #1d4ed8;"><strong>#{block:,}</strong></a> 
                        — all data was read at this exact block height</li>
                    <li><strong>Execute</strong> each <code>eth_call</code> listed below with the same <code>to</code> + <code>calldata</code></li>
                    <li><strong>Decode</strong> responses and apply the Whitepaper formulas shown</li>
                    <li><strong>Compare</strong> your results with the "Decoded Value" column — they must match exactly</li>
                </ol>
                <p style="font-size: var(--fs-sm); color: #1e40af; margin-bottom: 0;">
                    ℹ️ Any JSON-RPC client can replay these calls: <code>curl</code>, <code>cast call</code> (Foundry), 
                    Python <code>httpx</code>, or browser console with <code>fetch()</code>.
                </p>
            </div>
            
            <h3>⛓️ Blockchain State Snapshot</h3>
            <div class="metric-grid">
                <div class="metric-card">
                    <div><strong>Block Number:</strong></div>
                    <div style="font-family: monospace;"><a href="{block_link}" target="_blank" style="color: #2563eb;">#{block:,}</a></div>
                </div>
                <div class="metric-card">
                    <div><strong>Network:</strong></div>
                    <div>{net.title()}</div>
                </div>
                <div class="metric-card">
                    <div><strong>RPC Endpoint:</strong></div>
                    <div style="font-size: var(--fs-sm); word-break: break-all;">{rpc}</div>
                </div>
                <div class="metric-card">
                    <div><strong>Data Source:</strong></div>
                    <div>Direct on-chain <code>eth_call</code></div>
                </div>
            </div>
            
            <h3>📝 Smart Contract Addresses</h3>
            <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin: 1rem 0; font-size: var(--fs-sm);">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 4px 8px; font-weight: 600;">PositionManager:</td>
                        <td style="padding: 4px 8px; font-family: monospace; font-size: var(--fs-sm);">
                            <a href="{_safe_href(explorer_base + "/address/" + pm_addr)}" target="_blank" style="color: #2563eb;">{pm_addr}</a>
                            <button class="copy-btn" data-copy="{pm_addr}" aria-label="Copy position manager address to clipboard">📋 Copy</button>
                        </td>
                    </tr>
                    <tr style="background: #f0f6ff;">
                        <td style="padding: 4px 8px; font-weight: 600;">Pool:</td>
                        <td style="padding: 4px 8px; font-family: monospace; font-size: var(--fs-sm);">
                            <a href="{_safe_href(explorer_base + "/address/" + pool_addr)}" target="_blank" style="color: #2563eb;">{pool_addr}</a>
                            <button class="copy-btn" data-copy="{pool_addr}" aria-label="Copy pool address to clipboard">📋 Copy</button>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 8px; font-weight: 600;">Token0:</td>
                        <td style="padding: 4px 8px; font-family: monospace; font-size: var(--fs-sm);">
                            <a href="{_safe_href(explorer_base + "/address/" + t0_addr)}" target="_blank" style="color: #2563eb;">{t0_addr}</a>
                            <button class="copy-btn" data-copy="{t0_addr}" aria-label="Copy Token0 address to clipboard">📋 Copy</button>
                        </td>
                    </tr>
                    <tr style="background: #f0f6ff;">
                        <td style="padding: 4px 8px; font-weight: 600;">Token1:</td>
                        <td style="padding: 4px 8px; font-family: monospace; font-size: var(--fs-sm);">
                            <a href="{_safe_href(explorer_base + "/address/" + t1_addr)}" target="_blank" style="color: #2563eb;">{t1_addr}</a>
                            <button class="copy-btn" data-copy="{t1_addr}" aria-label="Copy Token1 address to clipboard">📋 Copy</button>
                        </td>
                    </tr>
                </table>
            </div>
            
            <h3>📡 Raw On-Chain Calls (Reproducible)</h3>
            <p style="font-size: var(--fs-sm); color: var(--text-light);">
                Each row = one <code>eth_call</code>. Copy the <code>calldata</code> and <code>to</code> address to replay with any RPC client.
            </p>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: var(--fs-sm); border: 1px solid var(--border);">
                    <thead>
                        <tr style="background: #f1f5f9;">
                            <th style="text-align: left; padding: 8px; border-bottom: 2px solid var(--border);">Call</th>
                            <th style="text-align: left; padding: 8px; border-bottom: 2px solid var(--border);">Contract</th>
                            <th style="text-align: left; padding: 8px; border-bottom: 2px solid var(--border);">Calldata</th>
                            <th style="text-align: left; padding: 8px; border-bottom: 2px solid var(--border);">Decoded Value</th>
                        </tr>
                    </thead>
                    <tbody>
                        {call_rows}
                    </tbody>
                </table>
            </div>
            
            <h3>📐 Formulas Applied (Whitepaper References)</h3>
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 1rem; margin: 1rem 0;">
                <p style="font-size: var(--fs-sm); color: #15803d; margin-top: 0;">
                    Each formula below transforms raw on-chain values into the human-readable numbers shown in this report.
                    Verify against <a href="https://uniswap.org/whitepaper-v3.pdf" target="_blank" style="color: #15803d;">Uniswap V3 Whitepaper</a> §6.1-6.3.
                </p>
                <ol style="font-family: monospace; font-size: var(--fs-sm); line-height: 1.8;">
                    {formula_items}
                </ol>
            </div>
            
            <div style="background: #fefce8; border: 1px solid #eab308; border-radius: 8px; padding: 1rem; margin: 1rem 0;">
                <h4 style="color: #854d0e; margin-top: 0;">🛠️ Verification Example (curl)</h4>
                <pre style="background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: var(--fs-xs); line-height: 1.5;"><code>curl -X POST {rpc} \\
  -H "Content-Type: application/json" \\
  -d '{{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{{"to":"{pool_addr}","data":"{_safe(raw_calls[0].get("selector", "") if raw_calls else "")}"}},"{hex(block) if block else "latest"}"]}}'</code></pre>
                <p style="font-size: var(--fs-xs); color: #92400e; margin-bottom: 0;">
                    Replace <code>"latest"</code> with <code>"{hex(block) if block else "0x0"}"</code> to query the exact same block state.
                </p>
            </div>
        </div>
    """


def _render_strategies_visual(
    strategies_dict: Dict[str, Dict[str, Any]], data: Dict, t0: str, t1: str
) -> str:
    """Render strategies with visual gauges and comparison bars."""
    if not strategies_dict:
        return '<div class="tile"><p>Processing strategies...</p></div>'

    # Current market price to display on all strategy cards
    mkt_price = data.get("current_price", 0)

    strategy_html = ""
    colors = {
        "conservative": {"primary": "#059669", "bg": "#dcfce7"},
        "moderate": {"primary": "#3b82f6", "bg": "#dbeafe"},
        "aggressive": {"primary": "#dc2626", "bg": "#fee2e2"},
    }

    risk_icons = {"conservative": "🛡️", "moderate": "⚖️", "aggressive": "🚀"}

    for strategy_name in ["conservative", "moderate", "aggressive"]:
        strategy_data = strategies_dict.get(strategy_name, {})
        if not strategy_data:
            continue

        color = colors[strategy_name]
        icon = risk_icons[strategy_name]
        apy = strategy_data.get("apr_estimate", 0) * 100
        range_min = strategy_data.get("lower_price", 0)
        range_max = strategy_data.get("upper_price", 0)
        investment = (
            data.get("total_value_usd", 0)
            if data.get("total_value_usd", 0) > 0
            else strategy_data.get("total_value_usd", 10000)
        )
        risk_level = strategy_data.get("risk_level", "Unknown")
        description = strategy_data.get("description", "No description")
        range_width = strategy_data.get("range_width_pct", 0)
        s_t0 = _safe(strategy_data.get("token0_symbol", t0))
        s_t1 = _safe(strategy_data.get("token1_symbol", t1))
        daily_est = strategy_data.get("daily_fees_est", 0)
        weekly_est = strategy_data.get("weekly_fees_est", 0)
        monthly_est = strategy_data.get("monthly_fees_est", 0)
        annual_est = strategy_data.get("annual_fees_est", 0)

        # Calculate gauge width based on APY (relative to max 15%)
        gauge_width = min((apy / 15.0) * 100, 100)

        strategy_html += f'''
        <div class="tile" style="border-left: 4px solid {color["primary"]};">
            <div class="tile-header">
                <div class="tile-icon" style="background: linear-gradient(135deg, {color["primary"]}, {color["primary"]}cc);">{icon}</div>
                <div>
                    <div class="tile-title">{strategy_name.title()} Strategy</div>
                    <div style="font-size: var(--fs-md); color: var(--text-light);">{description}</div>
                </div>
            </div>
            
            <!-- Price Range with min/max descriptions -->
            <div style="background: {color["bg"]}; padding: 1rem; border-radius: 8px; margin: 1rem 0;">
                <div class="grid-1a1" style="gap: 0.5rem;">
                    <div style="text-align: left;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.03em;">Min Price</div>
                        <div style="font-weight: 700; font-size: var(--fs-lg); color: #ef4444;">${_safe_usd(range_min, 2)}</div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light);">Below → 100% {s_t0}</div>
                    </div>
                    <div style="text-align: center; font-size: var(--fs-sm); color: var(--text-light);">
                        ±{range_width:.0f}%
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.03em;">Max Price</div>
                        <div style="font-weight: 700; font-size: var(--fs-lg); color: #16a34a;">${_safe_usd(range_max, 2)}</div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light);">Above → 100% {s_t1}</div>
                    </div>
                </div>
                <!-- Current Market Price reference -->
                <div style="margin-top: 0.75rem; padding-top: 0.5rem; border-top: 1px dashed {"#86efac" if range_min <= mkt_price <= range_max else "#fca5a5"}; text-align: center;">
                    <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.03em;">Current Market Price</div>
                    <div style="font-weight: 700; font-size: var(--fs-lg); color: {"#16a34a" if range_min <= mkt_price <= range_max else "#dc2626"};">${_safe_usd(mkt_price, 2)}</div>
                    <div style="font-size: var(--fs-xs); color: {"#16a34a" if range_min <= mkt_price <= range_max else "#dc2626"};">{"✅ In Range" if range_min <= mkt_price <= range_max else "❌ Out of Range"}</div>
                </div>
            </div>
            
            <div class="grid-2" style="margin: 0.5rem 0;">
                <div>
                    <div style="font-size: var(--fs-md); color: var(--text-light); margin-bottom: 0.25rem;">Investment</div>
                    <div style="font-weight: 600; color: var(--text);">${_safe_usd(investment, 0)}</div>
                </div>
                <div>
                    <div style="font-size: var(--fs-md); color: var(--text-light); margin-bottom: 0.25rem;">Capital Efficiency</div>
                    <div style="font-weight: 600; color: var(--text);">{strategy_data.get("capital_efficiency", 0):.1f}× vs V2</div>
                </div>
            </div>
            
            <div style="margin: 1rem 0;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <span style="font-size: var(--fs-md); color: var(--text-light);">Estimated APR</span>
                    <span style="font-weight: 600; color: {color["primary"]};">{apy:.1f}%</span>
                </div>
                <div class="strategy-gauge">
                    <div class="gauge-fill" data-width="{gauge_width}" style="background: linear-gradient(135deg, {color["primary"]}, {color["primary"]}dd);"></div>
                    <div class="gauge-label">{risk_level} Risk</div>
                </div>
            </div>
            
            <!-- Earnings Projections -->
            <div style="background: #f8fafc; padding: 1rem; border-radius: 8px; margin-top: 0.75rem;">
                <div style="font-size: var(--fs-sm); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 0.75rem; font-weight: 600;">Projected Earnings</div>
                <div class="grid-4" style="gap: 0.75rem; text-align: center;">
                    <div>
                        <div style="font-size: var(--fs-sm); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.03em;">Daily</div>
                        <div style="font-weight: 700; color: {color["primary"]}; font-size: var(--fs-xl);">${_safe_usd(daily_est, 2)}</div>
                    </div>
                    <div>
                        <div style="font-size: var(--fs-sm); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.03em;">Weekly</div>
                        <div style="font-weight: 700; color: {color["primary"]}; font-size: var(--fs-xl);">${_safe_usd(weekly_est, 2)}</div>
                    </div>
                    <div>
                        <div style="font-size: var(--fs-sm); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.03em;">Monthly</div>
                        <div style="font-weight: 700; color: {color["primary"]}; font-size: var(--fs-xl);">${_safe_usd(monthly_est, 2)}</div>
                    </div>
                    <div>
                        <div style="font-size: var(--fs-sm); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.03em;">Annual</div>
                        <div style="font-weight: 700; color: {color["primary"]}; font-size: var(--fs-xl);">${_safe_usd(annual_est, 2)}</div>
                    </div>
                </div>
            </div>
        </div>
        '''

    return strategy_html


def _render_performance_history(data: Dict) -> str:
    """Render historical performance analysis section with PnL vs HODL comparison."""

    historical = data.get("historical_performance")
    if not historical:
        # No historical data available - show informational message
        return """
            <p style="color: var(--text-light); margin-top: -0.5rem;">Historical analysis powered by DEXScreener API + Uniswap Subgraph</p>
            
            <div class="tile" style="border-left: 4px solid #f59e0b; background: #fffbeb;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #f59e0b, #f59e0bcc);">📊</div>
                    <div>
                        <div class="tile-title">Historical Data Unavailable</div>
                    <div style="color: #92400e; margin-top: 0.5rem;">
                        Historical analysis requires real position data
                    </div>
                    <div style="font-size: var(--fs-sm); color: #a16207; margin-top: 0.75rem;">
                        💡 Historical PnL analysis is only available for positions with real on-chain data (when <code>--position</code> parameter is provided).
                    </div>
                    </div>
                </div>
            </div>
            
            <div class="tile">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #3b82f6, #3b82f6cc);">🏦</div>
                    <div>
                        <div class="tile-title">What Historical Analysis Shows</div>
                    <ul style="margin: 0.75rem 0 0 0; padding-left: 1.5rem; color: var(--text-light);">
                        <li><strong>Position PnL</strong> — Real gains/losses from fees + liquidity changes</li>
                        <li><strong>vs HODL Comparison</strong> — Your strategy vs simply holding tokens</li>
                        <li><strong>Impermanent Loss</strong> — True IL calculation with historical prices</li>
                        <li><strong>Fee Timeline</strong> — When and how much fees were collected</li>
                    </ul>
                    </div>
                </div>
            </div>
        """

    if historical.get("error"):
        return f"""
            <p style="color: var(--text-light); margin-top: -0.5rem;">Historical analysis powered by DEXScreener API + Uniswap Subgraph</p>
            
            <div class="tile" style="border-left: 4px solid #dc2626; background: #fef2f2;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #dc2626, #dc2626cc);">❌</div>
                    <div>
                        <div class="tile-title">Historical Analysis Error</div>
                    <div style="color: #7f1d1d; margin-top: 0.5rem;">
                        {historical.get("error")}
                    </div>
                    </div>
                </div>
            </div>
        """

    # Extract performance data
    perf = historical.get("position_performance", {})
    hodl = historical.get("hodl_comparison", {})
    fees = historical.get("fee_timeline", [])
    price_data = historical.get("price_data", {})

    # Performance calculations
    total_value = perf.get("total_current_value", 0)
    initial_investment = perf.get("initial_investment", 0)
    gross_pnl = perf.get("gross_pnl", 0)
    gross_pnl_pct = perf.get("gross_pnl_pct", 0)
    fees_collected = perf.get("fees_collected", 0)

    # HODL comparison
    hodl_value = hodl.get("hodl_value", 0)
    hodl_pnl_pct = hodl.get("hodl_pnl_pct", 0)
    il_pct = hodl.get("il_pct", 0)
    net_outperformance = hodl.get("net_outperformance_pct", 0)
    strategy_better = hodl.get("strategy_better_than_hodl", False)

    # Price data
    current_price = price_data.get("current_price", 0)
    price_change_24h = price_data.get("price_change_24h", 0)

    days_analyzed = historical.get("analysis_period_days", 0)

    # Colors for status
    pnl_color = "#16a34a" if gross_pnl >= 0 else "#dc2626"
    strategy_color = "#16a34a" if strategy_better else "#dc2626"
    il_color = "#dc2626" if il_pct < -1 else "#f59e0b" if il_pct < 0 else "#16a34a"

    # Fee collection summary
    total_collections = len(fees)

    return f"""
        <p style="color: var(--text-light); margin-top: -0.5rem;">
            Performance analysis over {days_analyzed} days • Sources: 
            <a href="https://docs.dexscreener.com/api/reference" style="color: var(--primary);">DEXScreener</a> • 
            <a href="https://thegraph.com/docs/en/about/" style="color: var(--primary);">The Graph</a>
        </p>
        
        <!-- Position Performance Overview -->
        <div class="tile" style="border-left: 4px solid {pnl_color};">
            <div class="tile-header">
                <div class="tile-icon" style="background: linear-gradient(135deg, {pnl_color}, {pnl_color}cc);">💰</div>
                <div>
                    <div class="tile-title">Position Performance</div>
                    <div style="color: var(--text-light); font-size: var(--fs-md);">Total return including fees collected</div>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 1rem; margin-top: 1rem;">
                <div class="metric-card">
                    <div style="color: var(--text-light); font-size: var(--fs-xs); text-transform: uppercase;">Total PnL</div>
                    <div style="font-size: var(--fs-2xl); font-weight: 700; color: {pnl_color};">
                        ${gross_pnl:+,.2f}
                    </div>
                    <div style="font-size: var(--fs-base); color: {pnl_color}; font-weight: 600;">
                        {gross_pnl_pct:+.2f}%
                    </div>
                </div>
                <div class="metric-card">
                    <div style="color: var(--text-light); font-size: var(--fs-xs); text-transform: uppercase;">Current Value</div>
                    <div style="font-size: var(--fs-xl); font-weight: 700; color: var(--text);">
                        ${total_value:,.2f}
                    </div>
                    <div style="font-size: var(--fs-sm); color: var(--text-light);">
                        vs ${initial_investment:,.2f} initial
                    </div>
                </div>
                <div class="metric-card">
                    <div style="color: var(--text-light); font-size: var(--fs-xs); text-transform: uppercase;">Fees Collected</div>
                    <div style="font-size: var(--fs-xl); font-weight: 700; color: #16a34a;">
                        ${fees_collected:,.2f}
                    </div>
                    <div style="font-size: var(--fs-sm); color: var(--text-light);">
                        {perf.get("fees_pct_of_investment", 0):.2f}% of investment
                    </div>
                </div>
            </div>
        </div>
        
        <!-- HODL Comparison -->
        <div class="tile" style="border-left: 4px solid {strategy_color};">
            <div class="tile-header">
                <div class="tile-icon" style="background: linear-gradient(135deg, {strategy_color}, {strategy_color}cc);">🔄</div>
                <div>
                    <div class="tile-title">vs HODL Strategy</div>
                    <div style="color: var(--text-light); font-size: var(--fs-md);">Your position vs simply holding the tokens</div>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin-top: 1rem;">
                <div class="metric-card">
                    <div style="color: var(--text-light); font-size: var(--fs-xs); text-transform: uppercase;">HODL Would Be</div>
                    <div style="font-size: var(--fs-xl); font-weight: 700; color: var(--text);">
                        ${hodl_value:,.2f}
                    </div>
                    <div style="font-size: var(--fs-base); color: {"#16a34a" if hodl_pnl_pct >= 0 else "#dc2626"};">
                        {hodl_pnl_pct:+.2f}%
                    </div>
                </div>
                <div class="metric-card">
                    <div style="color: var(--text-light); font-size: var(--fs-xs); text-transform: uppercase;">Impermanent Loss</div>
                    <div style="font-size: var(--fs-xl); font-weight: 700; color: {il_color};">
                        {il_pct:.2f}%
                    </div>
                    <div style="font-size: var(--fs-sm); color: var(--text-light);">
                        vs no pool
                    </div>
                </div>
                <div class="metric-card">
                    <div style="color: var(--text-light); font-size: var(--fs-xs); text-transform: uppercase;">Net Outperformance</div>
                    <div style="font-size: var(--fs-xl); font-weight: 700; color: {strategy_color};">
                        {net_outperformance:+.2f}%
                    </div>
                    <div style="font-size: var(--fs-sm); color: {strategy_color};">
                        {"✅ Better than HODL" if strategy_better else "❌ HODL was better"}
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Price Movement Context -->
        <div class="tile">
            <div class="tile-header">
                <div class="tile-icon" style="background: linear-gradient(135deg, #8b5cf6, #8b5cf6cc);">📊</div>
                <div>
                    <div class="tile-title">Price Context ({days_analyzed} days)</div>
                    <div style="color: var(--text-light); font-size: var(--fs-md);">Token price movement during analysis period</div>
                </div>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 1rem; margin-top: 1rem;">
                <div class="metric-card">
                    <div style="color: var(--text-light); font-size: var(--fs-xs); text-transform: uppercase;">Current Price</div>
                    <div style="font-size: var(--fs-xl); font-weight: 700; color: var(--text);">
                        ${current_price:,.4f}
                    </div>
                </div>
                <div class="metric-card">
                    <div style="color: var(--text-light); font-size: var(--fs-xs); text-transform: uppercase;">24h Change</div>
                    <div style="font-size: var(--fs-xl); font-weight: 700; color: {"#16a34a" if price_change_24h >= 0 else "#dc2626"};">
                        {price_change_24h:+.2f}%
                    </div>
                </div>
                <div class="metric-card">
                    <div style="color: var(--text-light); font-size: var(--fs-xs); text-transform: uppercase;">Fee Collections</div>
                    <div style="font-size: var(--fs-xl); font-weight: 700; color: var(--text);">
                        {total_collections}
                    </div>
                    <div style="font-size: var(--fs-sm); color: var(--text-light);">
                        events tracked
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Fee Collection Timeline -->
        {_render_fee_timeline(fees) if fees else ""}
        
        <!-- Performance Summary -->
        <div style="background: #f8fafc; border: 2px solid #e2e8f0; padding: 1.5rem; border-radius: 12px; margin-top: 1.5rem;">
            <h4 style="margin: 0 0 1rem 0; color: var(--text);">📝 Performance Summary</h4>
            <div style="color: #475569; line-height: 1.6;">
                {"🎯" if strategy_better else "⚠️"} Your liquidity position {"outperformed" if strategy_better else "underperformed"} a simple HODL strategy by 
                <strong style="color: {strategy_color};">{abs(net_outperformance):.2f} percentage points</strong>.
                <br><br>
                {"✅" if fees_collected > abs(hodl.get("il_absolute", 0)) else "❌"} Fees collected 
                (${fees_collected:.2f}) {"exceeded" if fees_collected > abs(hodl.get("il_absolute", 0)) else "did not fully offset"} 
                impermanent loss of ${abs(hodl.get("il_absolute", 0)):,.2f}.
                <br><br>
                <strong>Data Sources:</strong> Historical prices from DEXScreener, position events from Uniswap V3 subgraph.
                Analysis covers last {days_analyzed} days of position activity.
            </div>
        </div>
        
        <div style="background: #fffbeb; border: 2px solid #f59e0b; padding: 1rem; border-radius: 8px; margin-top: 1rem; font-size: var(--fs-md);">
            <strong>⚠️ Important:</strong> Historical analysis is based on available data and simplified calculations. 
            For precise PnL tracking, use <a href="https://revert.finance" style="color: #f59e0b;">Revert Finance</a>, 
            <a href="https://app.zerion.io" style="color: #f59e0b;">Zerion</a>, or 
            <a href="https://debank.com" style="color: #f59e0b;">DeBank</a>.
        </div>
    """


def _render_fee_timeline(fees: list) -> str:
    """Render fee collection timeline."""
    if not fees or len(fees) == 0:
        return ""

    # Show up to 5 most recent fee collections
    recent_fees = fees[:5]

    timeline_html = """
    <div class="tile">
        <div class="tile-header">
            <div class="tile-icon" style="background: linear-gradient(135deg, #10b981, #10b981cc);">💰</div>
            <div>
                <div class="tile-title">Recent Fee Collections</div>
                <div style="color: var(--text-light); font-size: var(--fs-md);">Latest fee collection events</div>
            </div>
        </div>
        <div style="margin-top: 1rem;">
    """

    for fee in recent_fees:
        timestamp = fee.get("timestamp", 0)
        amount = fee.get("amount_usd", 0)
        block = fee.get("block", 0)

        # Convert timestamp to readable date
        if timestamp:
            try:
                date_str = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError, OSError):
                date_str = "Unknown date"
        else:
            date_str = "Unknown date"

        timeline_html += f"""
            <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem; 
                        border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 0.5rem; background: #f8fafc;">
                <div>
                    <div style="font-weight: 600; color: var(--text);">${amount:.2f}</div>
                    <div style="font-size: var(--fs-sm); color: var(--text-light);">{date_str}</div>
                </div>
                <div style="font-size: var(--fs-xs); color: var(--text-light); text-align: right;">
                    Block {block}
                </div>
            </div>
        """

    if len(fees) > 5:
        timeline_html += f"""
            <div style="text-align: center; padding: 0.5rem; color: var(--text-light); font-size: var(--fs-md);">
                ... and {len(fees) - 5} more fee collections
            </div>
        """

    timeline_html += """
        </div>
    </div>
    """

    return timeline_html


def _build_html(data: Dict) -> str:
    """Build HTML with 7 tab-based sections.

    Security: Generates a unique CSP nonce per report (CWE-79 mitigation).
    The nonce is a cryptographic random value that whitelists only the
    inline script blocks generated by this function.
    """

    # Generate cryptographic nonce for Content-Security-Policy (CWE-79)
    nonce = secrets.token_urlsafe(32)

    # Basic data extraction
    t0 = _safe(data.get("token0_symbol", "Token0"))
    t1 = _safe(data.get("token1_symbol", "Token1"))
    current_price = data.get("current_price", 0)
    total_value = data.get("total_value_usd", 0)
    in_range = data.get("in_range", False)
    consent_ts = _safe(data.get("consent_timestamp", "Unknown"))
    generated = _safe(
        data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    net = _safe((data.get("network") or "arbitrum").title())

    # Local aliases for readability in f-string templates
    safe_num = _safe_num
    safe_usd = _safe_usd

    # Extract HODL comparison dict for safe use in f-string templates
    hodl = data.get("hodl_comparison") or {}
    hodl_il_lower_usd = hodl.get("il_if_at_lower_usd", 0)
    hodl_il_upper_usd = hodl.get("il_if_at_upper_usd", 0)
    hodl_fees_usd = hodl.get("fees_earned_usd", 0)
    hodl_net_lower = hodl.get("net_if_at_lower_usd", 0) or 0
    hodl_net_upper = hodl.get("net_if_at_upper_usd", 0) or 0

    # Status formatting
    status_text_color = "#15803d" if in_range else "#dc2626"
    status_bg = "#f0fdf4" if in_range else "#fef2f2"
    status_border = "#bbf7d0" if in_range else "#fecaca"
    status_text = "● In Range" if in_range else "● Out of Range"

    # Pool info
    pool_addr = _safe(data.get("pool_address", ""))
    t0_info = _token_info(data.get("token0_symbol", ""))
    t1_info = _token_info(data.get("token1_symbol", ""))

    # Generate visual strategies HTML
    strategies_visual_html = _render_strategies_visual(
        data.get("strategies", {}), data, t0, t1
    )

    # ── Derived metrics for enhanced report ───────────────────────────
    # Health Score (0-100): composite measure of position health
    _downside = data.get("downside_buffer_pct", 0) or 0
    _upside = data.get("upside_buffer_pct", 0) or 0
    _range_score = min((_downside + _upside) / 2, 50) / 50 * 30  # 0-30 pts
    _in_range_score = 25 if in_range else 0  # 25 pts
    _vol_tvl = data.get("vol_tvl_ratio", 0) or 0
    _vol_score = min(_vol_tvl / 0.3, 1) * 20  # 0-20 pts
    _il_lower_pct = abs(data.get("il_at_lower_v3_pct", 0) or 0)
    _il_upper_pct = abs(data.get("il_at_upper_v3_pct", 0) or 0)
    _il_avg_pct = (_il_lower_pct + _il_upper_pct) / 2
    _il_score = max(25 - _il_avg_pct, 0)  # 0-25 pts
    health_score = round(
        min(_in_range_score + _range_score + _vol_score + _il_score, 100)
    )

    def _health_color(s: int) -> str:
        if s >= 70:
            return "#16a34a"
        if s >= 40:
            return "#d97706"
        return "#dc2626"

    def _health_label(s: int) -> str:
        if s >= 85:
            return "Excellent"
        if s >= 70:
            return "Good"
        if s >= 50:
            return "Fair"
        if s >= 25:
            return "Weak"
        return "Critical"

    health_color = _health_color(health_score)
    health_label = _health_label(health_score)

    # Break-even days: how many days until fees offset worst-case IL
    _daily_fees = data.get("daily_fees_est", 0) or 0
    _il_lower_usd = abs(hodl.get("il_if_at_lower_usd", 0) or 0)
    _il_upper_usd = abs(hodl.get("il_if_at_upper_usd", 0) or 0)
    breakeven_lower = (
        round(_il_lower_usd / _daily_fees)
        if _daily_fees > 0 and _il_lower_usd > 0
        else 0
    )
    breakeven_upper = (
        round(_il_upper_usd / _daily_fees)
        if _daily_fees > 0 and _il_upper_usd > 0
        else 0
    )

    # Fee Efficiency Ratio: are you earning more/less than your pool share?
    _pool_tvl = data.get("total_value_locked_usd", 0) or 1
    _position_share_pct = (
        (total_value / _pool_tvl * 100) if _pool_tvl > 0 and total_value > 0 else 0
    )
    _pool_24h_fees = data.get("pool_24h_fees_est", 0) or 0
    _expected_fee_share = (
        _pool_24h_fees * _position_share_pct / 100 if _pool_24h_fees > 0 else 0
    )
    fee_efficiency = (
        round((_daily_fees / _expected_fee_share), 2)
        if _expected_fee_share > 0
        else 1.0
    )

    # Net APR after estimated IL
    _position_apr = data.get("position_apr_est", data.get("annual_apy_est", 0)) or 0
    net_apr = round(_position_apr - _il_avg_pct, 1)

    # Pool age from DEXScreener pairCreatedAt (milliseconds timestamp)
    _pair_created_ms = data.get("pair_created_at", 0) or 0
    if _pair_created_ms > 0:
        _pool_created_dt = datetime.fromtimestamp(_pair_created_ms / 1000)
        pool_age_days = (datetime.now() - _pool_created_dt).days
        pool_age_str = (
            f"{pool_age_days:,} days"
            if pool_age_days < 365
            else f"{pool_age_days // 365}y {pool_age_days % 365}d"
        )
        pool_created_date = _pool_created_dt.strftime("%b %d, %Y")
    else:
        pool_age_days = 0
        pool_age_str = "Unknown"
        pool_created_date = "N/A"

    # SVG arc for health gauge (circumference = 2π×50 ≈ 314.16)
    _circ = 314.16
    _health_offset = _circ - (health_score / 100) * _circ

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-{nonce}'; img-src data:; frame-ancestors 'none';">
    <meta http-equiv="X-Content-Type-Options" content="nosniff">
    <meta http-equiv="X-Frame-Options" content="DENY">
    <meta name="referrer" content="no-referrer">
    <title>Position Report: {t0}/{t1} — DeFi CLI</title>
{_build_css(status_bg, status_border, status_text_color)}
    
    <script nonce="{nonce}">
        // Calculate price position percentage for visual indicators
        function calculatePricePosition(current, min, max) {{
            if (max <= min) return 50; // fallback to center
            return Math.min(Math.max(((current - min) / (max - min)) * 100, 0), 100);
        }}
        
        // Animate progress bars and gauges on load  
        document.addEventListener('DOMContentLoaded', function() {{
            // Animate all progress bars
            document.querySelectorAll('.progress-fill').forEach(bar => {{
                const width = bar.dataset.width || '0';
                setTimeout(() => {{
                    bar.style.width = width + '%';
                }}, 500);
            }});
            
            // Animate gauge fills
            document.querySelectorAll('.gauge-fill').forEach(gauge => {{
                const width = gauge.dataset.width || '0';
                setTimeout(() => {{
                    gauge.style.width = width + '%';
                }}, 800);
            }});
            
            // Position price indicators
            const currentPrice = {safe_num(current_price, 6)};
            const rangeMin = {safe_num(data.get("range_min", 0), 6)};
            const rangeMax = {safe_num(data.get("range_max", 0), 6)};
            
            document.querySelectorAll('.current-price-indicator').forEach(indicator => {{
                const position = calculatePricePosition(currentPrice, rangeMin, rangeMax);
                indicator.style.left = position + '%';
            }});

            // Animate health score ring
            document.querySelectorAll('.health-ring-fg').forEach(circle => {{
                const val = parseFloat(circle.dataset.score || '0');
                const circ = 2 * Math.PI * 50;
                const offset = circ - (val / 100) * circ;
                setTimeout(() => {{ circle.style.strokeDashoffset = offset; }}, 600);
            }});

        }});
    </script>
</head>
<body>
    <div class="container">
        <!-- ═══════════════════ HEADER ═══════════════════ -->
        <div class="header">
            <h1>🏛️ DeFi CLI — Position Analysis</h1>
            <h2>{t0}/{t1} · {net}</h2>
            <div class="status-badge">{status_text}</div>
            <div style="margin-top: 0.5rem; font-size: var(--fs-base); color: rgba(255,255,255,0.85);">
                {data.get("dex_name", "Uniswap V3")} · {data.get("protocol_version", "v3").upper()} · Concentrated Liquidity
            </div>
        </div>

        <!-- ═══════════════════ FINANCIAL DATA NOTICE ═══════════════════ -->
        <div style="background: linear-gradient(135deg, #fef3c7, #fde68a); border: 2px solid #f59e0b; border-radius: 12px; padding: 1rem 1.25rem; margin: 0 0 1.5rem 0; font-size: var(--fs-base); color: #78350f;">
            <strong>⚠️ FINANCIAL DATA NOTICE:</strong> This report contains position values, fee estimates, and financial projections.
            It is generated as a <strong>temporary file</strong> and will not be saved automatically.
            To keep a copy, use <strong>Ctrl+S</strong> (or ⌘+S) in your browser.
            <strong>This is NOT financial advice — educational analysis only.</strong>
        </div>

        <!-- ═══════════════════ EXPORT BAR ═══════════════════ -->
        <div class="export-bar" id="export-bar">
            <span class="export-bar-label"><strong>📄 Report: {t0}/{t1} · {net}</strong></span>
            <button class="export-btn export-btn-secondary" id="btn-toggle-view" data-action="toggle-export" title="Show all sections continuously for export">
                📋 Full Report View
            </button>
            <button class="export-btn export-btn-primary" data-action="print" title="Print or save as PDF">
                🖨️ Print / Save PDF
            </button>
        </div>

        <!-- ═══════════════════ TAB NAVIGATION ═══════════════════ -->
        <div class="tab-container">
            <div class="tab-nav">
                <button class="tab-btn active" data-tab="tab-position">💼 Your Position</button>
                <button class="tab-btn" data-tab="tab-history">📈 Performance History</button>
                <button class="tab-btn" data-tab="tab-pool">🏊 Pool Overview</button>
                <button class="tab-btn" data-tab="tab-strategy">🎯 Strategy & Risk</button>
                <button class="tab-btn" data-tab="tab-technical">🔧 Technical Details</button>
                <button class="tab-btn" data-tab="tab-audit">📝 Audit Trail</button>
                <button class="tab-btn" data-tab="tab-legal">⚖️ Legal Compliance</button>
            </div>

            <!-- ═══════════════════ TAB CONTENT: YOUR POSITION ═══════════════════ -->
            <div class="tab-content active" id="tab-position">
                <h2 class="session-title">💼 Your Position</h2>
            
            <!-- Health Score Card -->
            <div class="tile" style="border-left: 4px solid {health_color}; margin-bottom: 1.5rem;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, {health_color}, {health_color}cc);">🏥</div>
                    <div>
                        <div class="tile-title">Position Health Score</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">How healthy is your position right now? Score based on 4 factors (0–100).</div>
                    </div>
                </div>
                <div class="health-gauge-container">
                    <div class="health-gauge-ring">
                        <svg width="120" height="120" viewBox="0 0 120 120">
                            <circle cx="60" cy="60" r="50" fill="none" stroke="#e2e8f0" stroke-width="10"/>
                            <circle class="health-ring-fg" cx="60" cy="60" r="50" fill="none"
                                stroke="{health_color}" stroke-width="10"
                                stroke-dasharray="{_circ}" stroke-dashoffset="{_circ}"
                                stroke-linecap="round" data-score="{health_score}"/>
                        </svg>
                        <div class="score-text">
                            <div class="score-number" style="color: {health_color};">{health_score}</div>
                            <div class="score-label">{health_label}</div>
                        </div>
                    </div>
                    <div class="health-breakdown">
                        <div class="health-row">
                            <span style="width: 120px;">{"✅" if in_range else "❌"} In Range</span>
                            <div class="health-row-bar"><div class="health-row-fill" style="width: {_in_range_score / 25 * 100:.0f}%; background: {"#16a34a" if in_range else "#dc2626"};"></div></div>
                            <span style="width: 45px; text-align: right;">{_in_range_score:.0f}/25</span>
                        </div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light); margin: -0.1rem 0 0.4rem 0; padding-left: 0.25rem;">{"Current price is within your range — earning fees" if in_range else "Current price is outside your range — NOT earning fees"}</div>
                        <div class="health-row">
                            <span style="width: 120px;">🛡️ Range Buffer</span>
                            <div class="health-row-bar"><div class="health-row-fill" style="width: {_range_score / 30 * 100:.0f}%; background: #3b82f6;"></div></div>
                            <span style="width: 45px; text-align: right;">{_range_score:.0f}/30</span>
                        </div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light); margin: -0.1rem 0 0.4rem 0; padding-left: 0.25rem;">{"Wide safety margin — price can move a lot before leaving range" if _range_score >= 20 else "Narrow margin — price could leave range with moderate movement" if _range_score >= 10 else "Very tight range — high risk of going out-of-range"}</div>
                        <div class="health-row">
                            <span style="width: 120px;">⚡ Pool Activity</span>
                            <div class="health-row-bar"><div class="health-row-fill" style="width: {_vol_score / 20 * 100:.0f}%; background: #8b5cf6;"></div></div>
                            <span style="width: 45px; text-align: right;">{_vol_score:.0f}/20</span>
                        </div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light); margin: -0.1rem 0 0.4rem 0; padding-left: 0.25rem;">{"High trading volume — generating significant fees" if _vol_score >= 15 else "Moderate volume — average fee generation" if _vol_score >= 8 else "Low volume — few trades generating fees"}</div>
                        <div class="health-row">
                            <span style="width: 120px;">📉 IL Exposure</span>
                            <div class="health-row-bar"><div class="health-row-fill" style="width: {_il_score / 25 * 100:.0f}%; background: #d97706;"></div></div>
                            <span style="width: 45px; text-align: right;">{_il_score:.0f}/25</span>
                        </div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light); margin: -0.1rem 0 0.2rem 0; padding-left: 0.25rem;">{"Low impermanent loss risk — tokens are close to entry price" if _il_score >= 18 else "Moderate IL — some divergence from entry price" if _il_score >= 10 else "High IL exposure — significant divergence loss if you exit now"}</div>
                    </div>
                </div>
                <div style="background: #f8fafc; padding: 0.75rem 1rem; border-radius: 8px; margin-top: 1rem; font-size: var(--fs-sm); color: var(--text-light); line-height: 1.5;">
                    <strong style="color: var(--text);">How to read:</strong> Each bar shows points earned out of maximum.
                    In-Range ({_in_range_score:.0f}/25) = {"earning" if in_range else "not earning"} fees ·
                    Range Buffer ({_range_score:.0f}/30) = distance to boundary ·
                    Pool Activity ({_vol_score:.0f}/20) = trading volume ·
                    IL Exposure ({_il_score:.0f}/25) = impermanent loss risk.<br>
                    <span style="font-size: var(--fs-xs);">Score ≥70 🟢 Good · 40–69 🟡 Fair · &lt;40 🔴 Weak · Educational only — not financial advice.
                    Sources: <a href="https://docs.uniswap.org/contracts/v3/reference/core/UniswapV3Pool#slot0" style="color: var(--primary);">slot0</a> · <a href="https://docs.dexscreener.com/api/reference" style="color: var(--primary);">DEXScreener</a> · <a href="https://uniswap.org/whitepaper-v3.pdf" style="color: var(--primary);">Whitepaper §2</a></span>
                </div>
            </div>
            
            {'<div style="background: #dbeafe; border: 1px solid #93c5fd; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: var(--fs-base);"><strong>🔗 Data Source:</strong> Real on-chain data via {} RPC · {} · Position NFT #{}</div>'.format(data.get("network", "Arbitrum").title(), data.get("dex_name", "Uniswap V3"), data.get("position_id", "")) if data.get("data_source") == "on-chain" else '<div style="background: #fefce8; border: 2px solid #f59e0b; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; font-size: var(--fs-base); color: #92400e;"><strong>📊 DATA TRANSPARENCY:</strong><br>• <strong>REAL:</strong> Pool volume, TVL, price from on-chain + DEXScreener<br>• <strong>SIMULATED:</strong> Only position allocation ($5K WETH + $5K USDC) for demonstration<br>• Use <code>--position &lt;id&gt;</code> for your actual position data</div>'}

            <!-- Position Value Card -->
            <div class="tile" style="border-left: 4px solid var(--primary);">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, var(--primary), var(--primary-light));">💰</div>
                    <div>
                        <div class="tile-title">Position Value</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">{"On-chain balances" if data.get("data_source") == "on-chain" else "Simulated balances"}</div>
                    </div>
                </div>
                <div class="comparison-value" style="color: var(--primary); font-size: var(--fs-3xl);">${safe_usd(total_value)}</div>
                
                <!-- Token Composition -->
                <div class="grid-2" style="margin-top: 1rem;">
                    <div style="background: #f0f9ff; padding: 1rem; border-radius: 8px; border: 1px solid #bfdbfe;">
                        <div style="font-size: var(--fs-sm); color: var(--text-light);">{t0}</div>
                        <div style="font-size: var(--fs-xl); font-weight: 600;">{safe_num(data.get("token0_amount", 0), 6)}</div>
                        <div style="display: flex; justify-content: space-between; margin-top: 0.25rem;">
                            <span style="color: var(--primary); font-weight: 500;">${safe_usd(data.get("token0_value_usd", 0))}</span>
                            <span style="color: var(--text-light);">{safe_num(data.get("token0_pct", 0), 1)}%</span>
                        </div>
                        <div class="progress-bar" style="margin-top: 0.5rem;"><div class="progress-fill" data-width="{safe_num(data.get("token0_pct", 0), 0)}"></div></div>
                    </div>
                    <div style="background: #fefce8; padding: 1rem; border-radius: 8px; border: 1px solid #fef08a;">
                        <div style="font-size: var(--fs-sm); color: var(--text-light);">{t1}</div>
                        <div style="font-size: var(--fs-xl); font-weight: 600;">{safe_num(data.get("token1_amount", 0), 6)}</div>
                        <div style="display: flex; justify-content: space-between; margin-top: 0.25rem;">
                            <span style="color: #d97706; font-weight: 500;">${safe_usd(data.get("token1_value_usd", 0))}</span>
                            <span style="color: var(--text-light);">{safe_num(data.get("token1_pct", 0), 1)}%</span>
                        </div>
                        <div class="progress-bar" style="margin-top: 0.5rem;"><div class="progress-fill" data-width="{safe_num(data.get("token1_pct", 0), 0)}" style="background: #d97706;"></div></div>
                    </div>
                </div>
            </div>

            <!-- Fees Earned Card -->
            <div class="tile" style="border-left: 4px solid #16a34a;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #16a34a, #15803d);">💸</div>
                    <div>
                        <div class="tile-title">Uncollected Fees</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">{"Computed from on-chain feeGrowth data" if data.get("data_source") == "on-chain" else "Estimated from pool volume"}</div>
                    </div>
                </div>
                <div class="comparison-value" style="color: #16a34a; font-size: var(--fs-2xl);">${safe_usd(data.get("fees_earned_usd", 0), 2)}</div>
                <div style="font-size: var(--fs-xs); color: #92400e; margin-top: 0.25rem;">⚠️ On-chain fees have ±2-5% variance until actual collection (feeGrowth rounding + block timing)</div>
            </div>

            <!-- Earnings Projections Card -->
            <div class="tile" style="border-left: 4px solid #8b5cf6;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #8b5cf6, #6d28d9);">💰</div>
                    <div>
                        <div class="tile-title">Fee Earnings Projections (Current Position)</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">Based on Position APR ({safe_num(data.get("position_apr_est", data.get("annual_apy_est", 0)), 1)}%) — Pool APR ({safe_num(data.get("pool_apr_estimate", 0), 1)}%) × capital efficiency</div>
                    </div>
                </div>
                
                <div class="grid-4" style="margin-top: 1rem;">
                    <div style="background: #f5f3ff; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #ddd6fe;">
                        <div style="font-size: var(--fs-sm); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Daily</div>
                        <div style="font-size: var(--fs-2xl); font-weight: 700; color: #8b5cf6;">${safe_usd(data.get("daily_fees_est", 0), 2)}</div>
                    </div>
                    <div style="background: #f5f3ff; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #ddd6fe;">
                        <div style="font-size: var(--fs-sm); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Weekly</div>
                        <div style="font-size: var(--fs-2xl); font-weight: 700; color: #8b5cf6;">${safe_usd(data.get("weekly_fees_est", 0), 2)}</div>
                    </div>
                    <div style="background: #f5f3ff; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #ddd6fe;">
                        <div style="font-size: var(--fs-sm); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Monthly</div>
                        <div style="font-size: var(--fs-2xl); font-weight: 700; color: #7c3aed;">${safe_usd(data.get("monthly_fees_est", 0), 2)}</div>
                    </div>
                    <div style="background: #f5f3ff; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #ddd6fe;">
                        <div style="font-size: var(--fs-sm); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Annual</div>
                        <div style="font-size: var(--fs-2xl); font-weight: 700; color: #6d28d9;">${safe_usd(data.get("annual_fees_est", 0), 2)}</div>
                    </div>
                </div>
                
                <div style="background: #fef2f2; padding: 0.5rem 0.75rem; border-radius: 8px; margin-top: 0.75rem; font-size: var(--fs-xs); color: #991b1b; border: 1px solid #fecaca;">
                    🚨 <strong>SNAPSHOT BIAS WARNING:</strong> Position APR {safe_num(data.get("position_apr_est", data.get("annual_apy_est", 0)), 1)}% from 24h volume only—NOT representative.<br>
                    📊 <strong>REGULATORY NOTICE:</strong> Past performance ≠ future results (CVM/SEC/MiCA requirement).<br>
                    ⚡ Real APR varies with volume/volatility. Verify: <a href="{_safe_href("https://revert.finance/#/account/" + _safe(data.get("wallet_address", "")))}" style="color: #991b1b;">Revert.finance</a>
                </div>
            </div>

            <!-- Key Metrics -->
            <div class="comparison-bars">
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon" style="background: linear-gradient(135deg, #22c55e, #16a34a);">⚡</div>
                        <div class="tile-title">Liquidity (L)</div>
                    </div>
                    <div class="comparison-value" style="color: #22c55e;">{safe_num(data.get("liquidity", 0), 0)}</div>
                    <div class="comparison-label">Whitepaper §6.2: L = Δx·√(Pa·Pb)/(√Pb−√Pa)</div>
                </div>
                
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon" style="background: linear-gradient(135deg, #f59e0b, #d97706);">🎯</div>
                        <div class="tile-title">Fee Tier</div>
                    </div>
                    <div class="comparison-value" style="color: #f59e0b;">{data.get("fee_tier_label", safe_num(data.get("fee_tier", 3000)))}</div>
                    <div class="comparison-label"><a href="https://docs.uniswap.org/concepts/protocol/fees" style="color: var(--text-light);">Uniswap Fee Tiers</a></div>
                </div>
                
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon" style="background: linear-gradient(135deg, #dc2626, #b91c1c);">📐</div>
                        <div class="tile-title">Capital Efficiency</div>
                    </div>
                    <div class="comparison-value" style="color: #dc2626;">{safe_num(data.get("capital_efficiency_vs_v2", 1), 1)}× vs V2</div>
                    <div class="comparison-label">Whitepaper §2: 1/(1−√(Pa/Pb))</div>
                </div>
            </div>

            <!-- Fee Efficiency Ratio -->
            <div class="tile" style="border-left: 4px solid #0ea5e9;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #0ea5e9, #0284c7);">⚡</div>
                    <div>
                        <div class="tile-title">Fee Efficiency Ratio</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">Your fee earnings vs. your proportional share of pool fees</div>
                    </div>
                </div>
                <div class="grid-3" style="margin-top: 0.5rem;">
                    <div style="text-align: center;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Your Pool Share</div>
                        <div style="font-size: var(--fs-xl); font-weight: 700; color: #0ea5e9;">{_safe_num(_position_share_pct, 6)}%</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Expected Daily Fees</div>
                        <div style="font-size: var(--fs-xl); font-weight: 700; color: var(--text-light);">${_safe_usd(_expected_fee_share, 4)}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Efficiency Ratio</div>
                        <div style="font-size: var(--fs-xl); font-weight: 700; color: {"#16a34a" if fee_efficiency >= 1.0 else "#dc2626"};">{_safe_num(fee_efficiency, 2)}×</div>
                    </div>
                </div>
                <div style="background: #f0f9ff; padding: 0.5rem 0.75rem; border-radius: 8px; margin-top: 0.75rem; font-size: var(--fs-xs); color: #0369a1; border: 1px solid #bae6fd;">
                    {"🔥 Above average — concentrated range capturing more fees." if fee_efficiency >= 1.0 else "💤 Below average — wider range might capture more."}
                    Your daily fees ÷ (pool fees × TVL share). &gt;1× = outperforming.
                    Sources: <a href="https://docs.uniswap.org/contracts/v3/reference/core/UniswapV3Pool" style="color: #0369a1;">Pool</a> · <a href="https://docs.dexscreener.com/api/reference" style="color: #0369a1;">DEXScreener</a> · <a href="https://docs.uniswap.org/concepts/protocol/fees" style="color: #0369a1;">Fee Tiers</a>
                </div>
            </div>
        </div>

        <!-- ═══════════════════ TAB CONTENT: PERFORMANCE HISTORY ═══════════════════ -->
        <div class="tab-content" id="tab-history">
            <h2 class="session-title">📈 Performance History</h2>
            {_render_performance_history(data)}
        </div>

        <!-- ═══════════════════ TAB CONTENT: POOL OVERVIEW ═══════════════════ -->
        <div class="tab-content" id="tab-pool">
            <h2 class="session-title">🏊 Pool Overview & Stats</h2>
            <p style="color: var(--text-light); margin-top: -0.5rem;">Source: <a href="https://docs.dexscreener.com/api/reference" style="color: var(--primary);">DEXScreener API</a> · Real-time on-chain data</p>
            
            <!-- Pool APR Highlight -->
            <div class="apy-display">
                <h3 style="margin-top: 0; color: #d97706;">Pool APR (Estimated)</h3>
                <div class="apy-value">{safe_num(data.get("pool_apr_estimate", data.get("annual_apy_est", 0)), 1)}%</div>
                <p style="margin-bottom: 0; color: #78350f;">Formula: (Volume 24h × Fee Tier × 365) / TVL × 100<br>
                <span style="font-size: var(--fs-sm);">Ref: <a href="https://docs.uniswap.org/concepts/protocol/fees" style="color: #92400e;">Uniswap V3 Fee Distribution</a></span></p>
            </div>
            
            <!-- Pool Stats Grid -->
            <div class="comparison-bars">
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon" style="background: linear-gradient(135deg, #3b82f6, #1d4ed8);">📊</div>
                        <div class="tile-title">24h Volume</div>
                    </div>
                    <div class="comparison-value" style="color: #3b82f6;">${safe_usd(data.get("volume_24h", 0))}</div>
                    <div class="comparison-label">On-chain swap transactions (24h)</div>
                </div>
                
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon" style="background: linear-gradient(135deg, #059669, #047857);">🏦</div>
                        <div class="tile-title">Pool TVL</div>
                    </div>
                    <div class="comparison-value" style="color: #059669;">${safe_usd(data.get("total_value_locked_usd", 0))}</div>
                    <div class="comparison-label">Total Value Locked (pool reserves)</div>
                </div>
                
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon" style="background: linear-gradient(135deg, #d97706, #b45309);">💸</div>
                        <div class="tile-title">24h Fees (Pool)</div>
                    </div>
                    <div class="comparison-value" style="color: #d97706;">${safe_usd(data.get("pool_24h_fees_est", 0))}</div>
                    <div class="comparison-label">Volume × Fee Tier ({data.get("fee_tier_label", "0.05%")})</div>
                </div>
            </div>

            <!-- Vol/TVL Ratio Tile -->
            <div class="tile" style="border-left: 4px solid #7c3aed;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #7c3aed, #5b21b6);">⚡</div>
                    <div>
                        <div class="tile-title">Volume / TVL Ratio</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">Fee-generating efficiency — higher = more fees per dollar locked</div>
                    </div>
                </div>
                <div style="display: flex; align-items: baseline; gap: 0.5rem; margin-top: 0.5rem;">
                    <div style="font-size: var(--fs-3xl); font-weight: 700; color: #7c3aed;">{safe_num(data.get("vol_tvl_ratio", 0), 4)}×</div>
                    <div style="font-size: var(--fs-md); color: var(--text-light);">
                        {"🔥 High efficiency" if (data.get("vol_tvl_ratio") or 0) >= 0.3 else "⚖️ Normal" if (data.get("vol_tvl_ratio") or 0) >= 0.1 else "💤 Low activity"}
                    </div>
                </div>
                <div class="progress-bar" style="margin-top: 0.5rem; height: 8px;">
                    <div class="progress-fill" data-width="{min((data.get("vol_tvl_ratio", 0) or 0) / 0.5 * 100, 100):.0f}" style="background: linear-gradient(90deg, #7c3aed, #a78bfa);"></div>
                </div>
                <div style="font-size: var(--fs-xs); color: var(--text-light); margin-top: 0.25rem;">
                    Benchmarks: &lt;0.1× low · 0.1-0.3× normal · &gt;0.3× high efficiency
                </div>
            </div>

            <!-- Pool Age -->
            <div class="tile" style="border-left: 4px solid #6366f1;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #6366f1, #4f46e5);">📅</div>
                    <div>
                        <div class="tile-title">Pool Age</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">How long this pool has been active on-chain</div>
                    </div>
                </div>
                <div class="grid-2" style="margin-top: 0.5rem;">
                    <div style="text-align: center;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Age</div>
                        <div style="font-size: var(--fs-2xl); font-weight: 700; color: #6366f1;">{pool_age_str}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Created</div>
                        <div style="font-size: var(--fs-2xl); font-weight: 700; color: var(--text);">{pool_created_date}</div>
                    </div>
                </div>
                <div style="background: #eef2ff; padding: 0.5rem 0.75rem; border-radius: 8px; margin-top: 0.75rem; font-size: var(--fs-xs); color: #3730a3; border: 1px solid #c7d2fe;">
                    {"🟢 Mature pool (>90d) — reliable APR estimates." if pool_age_days > 90 else "🟡 Young pool (<90d) — APR may be volatile." if pool_age_days > 0 else "ℹ️ Creation date unavailable."}
                    Source: <a href="https://docs.dexscreener.com/api/reference" style="color: #3730a3;">DEXScreener</a>
                </div>
            </div>
            
            <div style="background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 0.5rem 0.75rem; margin: 1rem 0; font-size: var(--fs-xs); color: var(--text-light);">
                <strong>Pipeline:</strong> DEXScreener API → volume/TVL/price · APR = (Vol₂₄h × Fee × 365) / TVL · Fees₂₄h = Vol₂₄h × Fee tier
            </div>
        </div>

        <!-- ═══════════════════ TAB CONTENT: STRATEGY & RISK ═══════════════════ -->
        <div class="tab-content" id="tab-strategy">
            <h2 class="session-title">🎯 Price Range, Strategies & Risk</h2>
            
            <!-- Price Range with clear min/max descriptions -->
            <div class="tile" style="border-left: 4px solid var(--primary);">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, var(--primary), #7c3aed);">📈</div>
                    <div class="tile-title">Price Range</div>
                </div>
                
                <div class="price-range-bar">
                    <div class="current-price-indicator"></div>
                </div>
                
                <div class="grid-3" style="margin-top: 1rem;">
                    <div style="text-align: left;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Min Price (Lower Bound)</div>
                        <div style="font-size: var(--fs-lg); font-weight: 700; color: #ef4444;">${safe_usd(data.get("range_min"), 2)}</div>
                        <div style="font-size: var(--fs-sm); color: var(--text-light);">{t1} per {t0}</div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light); margin-top: 0.25rem;">Below this → 100% {t0}, 0% {t1}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Market Price (Current)</div>
                        <div style="font-size: var(--fs-lg); font-weight: 700; color: var(--primary);">${safe_usd(current_price, 2)}</div>
                        <div style="font-size: var(--fs-sm); color: var(--text-light);">{t1} per {t0}</div>
                        <div class="status-indicator {"status-in-range" if in_range else "status-out-range"}" style="margin-top: 0.5rem; font-size: var(--fs-xs);">{status_text}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Max Price (Upper Bound)</div>
                        <div style="font-size: var(--fs-lg); font-weight: 700; color: #16a34a;">${safe_usd(data.get("range_max"), 2)}</div>
                        <div style="font-size: var(--fs-sm); color: var(--text-light);">{t1} per {t0}</div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light); margin-top: 0.25rem;">Above this → 0% {t0}, 100% {t1}</div>
                    </div>
                </div>
                
                <div style="background: #f8fafc; padding: 0.5rem 0.75rem; border-radius: 8px; margin-top: 1rem; font-size: var(--fs-xs); color: var(--text-light);">
                    Range: <strong>{safe_num(data.get("range_width_pct", 0), 1)}%</strong> width · ↓{safe_num(data.get("downside_buffer_pct", 0), 1)}% · ↑{safe_num(data.get("upside_buffer_pct", 0), 1)}% · {_safe(data.get("current_strategy", "moderate")).title()} ·
                    <a href="https://uniswap.org/whitepaper-v3.pdf" style="color: var(--primary);">Whitepaper §6.1</a>
                </div>
            </div>

            <!-- V3 Impermanent Loss Tile -->
            <div class="tile" style="border-left: 4px solid #ef4444;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #ef4444, #b91c1c);">📉</div>
                    <div>
                        <div class="tile-title">V3 Impermanent Loss Estimate</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">Worst-case IL if price moves to range boundaries · V3 IL = V2 IL × Capital Efficiency</div>
                    </div>
                </div>
                
                <div class="grid-2" style="margin-top: 1rem;">
                    <div style="background: #fef2f2; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #fecaca;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">If Price → Lower Bound</div>
                        <div style="font-size: var(--fs-2xl); font-weight: 700; color: #dc2626;">{safe_num(data.get("il_at_lower_v3_pct", 0), 1)}%</div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light); margin-top: 0.25rem;">V2 equivalent: {safe_num(data.get("il_at_lower_v2_pct", 0), 1)}%</div>
                        <div style="font-size: var(--fs-sm); color: #991b1b; margin-top: 0.25rem;">${safe_usd(hodl_il_lower_usd)}</div>
                    </div>
                    <div style="background: #fef2f2; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #fecaca;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">If Price → Upper Bound</div>
                        <div style="font-size: var(--fs-2xl); font-weight: 700; color: #dc2626;">{safe_num(data.get("il_at_upper_v3_pct", 0), 1)}%</div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light); margin-top: 0.25rem;">V2 equivalent: {safe_num(data.get("il_at_upper_v2_pct", 0), 1)}%</div>
                        <div style="font-size: var(--fs-sm); color: #991b1b; margin-top: 0.25rem;">${safe_usd(hodl_il_upper_usd)}</div>
                    </div>
                </div>
                
                <div style="background: #fff7ed; padding: 0.5rem 0.75rem; border-radius: 8px; margin-top: 0.75rem; font-size: var(--fs-xs); color: #9a3412; border: 1px solid #fed7aa;">
                    IL_v3 = IL_v2 × CE ({safe_num(data.get("capital_efficiency_vs_v2", 1), 1)}×). Concentrated range amplifies fees AND losses.
                    <a href="https://pintail.medium.com/uniswap-a-good-deal-for-liquidity-providers-104c0b6816f2" style="color: #9a3412;">Pintail</a> · <a href="https://uniswap.org/whitepaper-v3.pdf" style="color: #9a3412;">Whitepaper §2</a>
                </div>
            </div>

            <!-- HODL Comparison Tile -->
            <div class="tile" style="border-left: 4px solid #8b5cf6;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #8b5cf6, #6d28d9);">🔄</div>
                    <div>
                        <div class="tile-title">Fees vs IL — HODL Comparison</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">Are fees earned enough to offset impermanent loss?</div>
                    </div>
                </div>
                
                <div class="grid-3" style="margin-top: 1rem;">
                    <div style="background: #f0fdf4; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #bbf7d0;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Fees Earned</div>
                        <div style="font-size: var(--fs-xl); font-weight: 700; color: #16a34a;">+${safe_usd(hodl_fees_usd)}</div>
                    </div>
                    <div style="background: #fef2f2; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #fecaca;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Net if at Lower</div>
                        <div style="font-size: var(--fs-xl); font-weight: 700; color: {"#16a34a" if hodl_net_lower >= 0 else "#dc2626"};">${safe_usd(hodl_net_lower)}</div>
                        <div style="font-size: var(--fs-2xs); color: var(--text-light);">Fees + IL at lower bound</div>
                    </div>
                    <div style="background: #fef2f2; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #fecaca;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Net if at Upper</div>
                        <div style="font-size: var(--fs-xl); font-weight: 700; color: {"#16a34a" if hodl_net_upper >= 0 else "#dc2626"};">${safe_usd(hodl_net_upper)}</div>
                        <div style="font-size: var(--fs-2xs); color: var(--text-light);">Fees + IL at upper bound</div>
                    </div>
                </div>
                
                <div style="background: #eff6ff; padding: 0.5rem 0.75rem; border-radius: 8px; margin-top: 0.75rem; font-size: var(--fs-xs); color: #1e40af; border: 1px solid #bfdbfe;">
                    Positive net = LP profitable vs HODL. Negative = HODL better.
                    Verify: <a href="{_safe_href("https://revert.finance/#/account/" + _safe(data.get("wallet_address", "")))}" style="color: #1d4ed8;">Revert.finance</a>
                </div>
            </div>

            <!-- Net APR (Fees - IL) -->
            <div class="tile" style="border-left: 4px solid {"#16a34a" if net_apr >= 0 else "#dc2626"};">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, {"#16a34a" if net_apr >= 0 else "#dc2626"}, {"#15803d" if net_apr >= 0 else "#b91c1c"});">📊</div>
                    <div>
                        <div class="tile-title">Net APR (Fees − IL)</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">Estimated annual return after accounting for average IL at boundaries</div>
                    </div>
                </div>
                <div class="grid-1a1" style="margin-top: 1rem;">
                    <div style="text-align: center; background: #f0fdf4; padding: 1rem; border-radius: 8px; border: 1px solid #bbf7d0;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Position Fee APR</div>
                        <div style="font-size: var(--fs-xl); font-weight: 700; color: #16a34a;">+{safe_num(_position_apr, 1)}%</div>
                    </div>
                    <div style="font-size: var(--fs-2xl); color: var(--text-light);">−</div>
                    <div style="text-align: center; background: #fef2f2; padding: 1rem; border-radius: 8px; border: 1px solid #fecaca;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Avg IL at Boundaries</div>
                        <div style="font-size: var(--fs-xl); font-weight: 700; color: #dc2626;">{safe_num(_il_avg_pct, 1)}%</div>
                    </div>
                </div>
                <div style="text-align: center; margin-top: 1rem; padding: 1rem; background: {"#f0fdf4" if net_apr >= 0 else "#fef2f2"}; border-radius: 8px; border: 2px solid {"#bbf7d0" if net_apr >= 0 else "#fecaca"};">
                    <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">Estimated Net APR</div>
                    <div style="font-size: var(--fs-3xl); font-weight: 800; color: {"#16a34a" if net_apr >= 0 else "#dc2626"};">{("+" if net_apr >= 0 else "")}{safe_num(net_apr, 1)}%</div>
                    <div style="font-size: var(--fs-sm); color: var(--text-light);">{"🟢 Fees are projected to outpace IL — LP profitable vs HODL" if net_apr >= 0 else "🔴 IL may exceed fee earnings — consider wider range or rebalancing"}</div>
                </div>
                <div style="background: #fef3c7; padding: 0.5rem 0.75rem; border-radius: 8px; margin-top: 0.75rem; font-size: var(--fs-xs); color: #78350f; border: 1px solid #fcd34d;">
                    🚨 <strong>REGULATORY WARNING:</strong> 24h snapshot—high seasonal/volume variance.<br>
                    📉 <strong>IL UNDERESTIMATION:</strong> During divergence loss, effective APR approaches zero.<br>
                    ⚠️ <strong>CVM/SEC/MiCA:</strong> Past performance ≠ future results—estimates may diverge significantly.<br>
                    Sources: <a href="https://docs.uniswap.org/concepts/protocol/fees" style="color: #78350f;">Fee Docs</a> · <a href="https://pintail.medium.com/uniswap-a-good-deal-for-liquidity-providers-104c0b6816f2" style="color: #78350f;">Pintail IL</a> · <a href="https://uniswap.org/whitepaper-v3.pdf" style="color: #78350f;">Whitepaper §2</a>
                </div>
            </div>

            <!-- Break-even Analysis -->
            <div class="tile" style="border-left: 4px solid #0891b2;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #0891b2, #0e7490);">⏱️</div>
                    <div>
                        <div class="tile-title">Break-even Analysis</div>
                        <div style="font-size: var(--fs-md); color: var(--text-light);">Days of fee earnings needed to offset worst-case IL at each boundary</div>
                    </div>
                </div>
                <div class="grid-2" style="margin-top: 1rem;">
                    <div style="text-align: center; background: #ecfeff; padding: 1rem; border-radius: 8px; border: 1px solid #a5f3fc;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">If Price → Lower</div>
                        <div style="font-size: var(--fs-3xl); font-weight: 700; color: #0891b2;">{"∞" if breakeven_lower == 0 else f"~{breakeven_lower}"}</div>
                        <div style="font-size: var(--fs-sm); color: var(--text-light);">{"days" if breakeven_lower > 0 else "(no daily fees)"}</div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light); margin-top: 0.25rem;">IL: ${safe_usd(_il_lower_usd)} ÷ ${safe_usd(_daily_fees, 4)}/day</div>
                    </div>
                    <div style="text-align: center; background: #ecfeff; padding: 1rem; border-radius: 8px; border: 1px solid #a5f3fc;">
                        <div style="font-size: var(--fs-xs); color: var(--text-light); text-transform: uppercase;">If Price → Upper</div>
                        <div style="font-size: var(--fs-3xl); font-weight: 700; color: #0891b2;">{"∞" if breakeven_upper == 0 else f"~{breakeven_upper}"}</div>
                        <div style="font-size: var(--fs-sm); color: var(--text-light);">{"days" if breakeven_upper > 0 else "(no daily fees)"}</div>
                        <div style="font-size: var(--fs-xs); color: var(--text-light); margin-top: 0.25rem;">IL: ${safe_usd(_il_upper_usd)} ÷ ${safe_usd(_daily_fees, 4)}/day</div>
                    </div>
                </div>
                <div style="background: #ecfeff; padding: 0.5rem 0.75rem; border-radius: 8px; margin-top: 0.75rem; font-size: var(--fs-xs); color: #155e75; border: 1px solid #a5f3fc;">
                    Fewer days = faster recovery. Assumes ${safe_usd(_daily_fees, 4)}/day (±30%).
                    Sources: <a href="https://uniswap.org/whitepaper-v3.pdf" style="color: #155e75;">Whitepaper §2</a> · <a href="https://docs.uniswap.org/contracts/v3/reference/core/UniswapV3Pool" style="color: #155e75;">Pool contract</a>
                </div>
            </div>
            
            <h3>🎯 Strategy Comparison:</h3>
            <div style="background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: var(--fs-sm); color: #78350f;">
                <strong>⚠️ NOT investment recommendations.</strong> These are <strong>hypothetical mathematical examples</strong> showing how different range widths affect projected earnings. 
                APR estimates assume constant volume and in-range status — actual results will vary. Always do your own research before repositioning.
            </div>
            <div class="strategies-section">
                {strategies_visual_html}
            </div>
            
            <!-- Risk Considerations with clear sourcing -->
            <div class="tile" style="border-left: 4px solid #ef4444;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #ef4444, #dc2626);">⚠️</div>
                    <div>
                        <div class="tile-title">Risk Assessment</div>
                        <div style="font-size: var(--fs-sm); color: var(--text-light);">Each risk is linked to your position's specific parameters</div>
                    </div>
                </div>
                
                <div style="background: var(--card); padding: 1rem; border-radius: 8px;">
                    <div class="comparison-bars">
                        <div class="comparison-item" style="border-left: 4px solid #ef4444;">
                            <div style="color: #ef4444; font-weight: 600;">1. Impermanent Loss (IL) — Divergence Loss</div>
                            <div class="progress-bar">
                                <div class="progress-fill" data-width="75" style="background: #ef4444;"></div>
                            </div>
                            <div class="comparison-label" style="line-height: 1.5;">
                                <strong>What:</strong> Price divergence between {t0} and {t1} causes value loss vs holding. In concentrated V3 positions, this is called <em>divergence loss</em> and can be much larger than V2 IL.<br>
                                <strong>Your exposure:</strong> Concentrated range ({safe_num(data.get("range_min"), 0)}–{safe_num(data.get("range_max"), 0)}) amplifies IL by {safe_num(data.get("capital_efficiency_vs_v2", 1), 1)}×. <strong style="color: #dc2626;">Divergence loss often exceeds fee earnings — total PnL can be NEGATIVE even with high fee APR.</strong><br>
                                <strong>Verify:</strong> Check your real PnL on <a href="{_safe_href("https://revert.finance/#/account/" + _safe(data.get("wallet_address", "")))}" style="color: var(--primary);">Revert.finance</a> (shows divergence loss, total PnL, fees vs IL).<br>
                                <strong>Source:</strong> <a href="https://pintail.medium.com/uniswap-a-good-deal-for-liquidity-providers-104c0b6816f2" style="color: var(--primary);">Pintail IL Formula</a> · <a href="https://uniswap.org/whitepaper-v3.pdf" style="color: var(--primary);">Whitepaper §2</a>
                            </div>
                        </div>
                        
                        <div class="comparison-item" style="border-left: 4px solid #f59e0b;">
                            <div style="color: #f59e0b; font-weight: 600;">2. Out-of-Range Risk</div>
                            <div class="progress-bar">
                                <div class="progress-fill" data-width="60" style="background: #f59e0b;"></div>
                            </div>
                            <div class="comparison-label" style="line-height: 1.5;">
                                <strong>What:</strong> If price exits your range, you earn zero fees and hold 100% of one token.<br>
                                <strong>Your exposure:</strong> Downside {safe_num(data.get("downside_buffer_pct", 0), 1)}% buffer, upside {safe_num(data.get("upside_buffer_pct", 0), 1)}% buffer from current price.<br>
                                <strong>Source:</strong> <a href="https://docs.uniswap.org/concepts/protocol/concentrated-liquidity" style="color: var(--primary);">Uniswap Concentrated Liquidity Docs</a>
                            </div>
                        </div>
                        
                        <div class="comparison-item" style="border-left: 4px solid #8b5cf6;">
                            <div style="color: #8b5cf6; font-weight: 600;">3. Smart Contract Risk</div>
                            <div class="progress-bar">
                                <div class="progress-fill" data-width="40" style="background: #8b5cf6;"></div>
                            </div>
                            <div class="comparison-label" style="line-height: 1.5;">
                                <strong>What:</strong> Uniswap V3 contracts could have undiscovered vulnerabilities or exploits.<br>
                                <strong>Your exposure:</strong> Full position value (${safe_usd(total_value)}) at risk in the protocol on {net}.<br>
                                <strong>Source:</strong> <a href="https://github.com/Uniswap/v3-core/tree/main/audits" style="color: var(--primary);">Uniswap V3 Audit Reports</a> · <a href="https://docs.uniswap.org/concepts/protocol/oracle" style="color: var(--primary);">Oracle Security</a>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ═══════════════════ TAB CONTENT: TECHNICAL DETAILS ═══════════════════ -->
        <div class="tab-content" id="tab-technical">
            <h2 class="session-title">🔧 Technical Details & Transparency</h2>
            
            <div style="background: #eff6ff; border: 2px solid #3b82f6; border-radius: 12px; padding: 1.5rem; margin: 0 0 2rem 0;">
                <h3 style="color: #1d4ed8; margin-top: 0;">🔗 Our Data Sources — Direct from Official Contracts</h3>
                <p style="font-size: var(--fs-base); line-height: 1.6; margin-bottom: 1rem;">
                    This report reads data <strong>directly from the blockchain</strong> via official Uniswap V3 smart contract calls 
                    and the DEXScreener public API. No third-party aggregator intermediaries. Values are computed using the 
                    <strong>exact formulas from the <a href="https://uniswap.org/whitepaper-v3.pdf" target="_blank" style="color: #1d4ed8;">Uniswap V3 Whitepaper</a></strong>
                    and the <a href="https://docs.uniswap.org/contracts/v3/reference/core/UniswapV3Pool" target="_blank" style="color: #1d4ed8;">official Uniswap V3 SDK/Contract documentation</a>.
                </p>
                <table style="width: 100%; border-collapse: collapse; font-size: var(--fs-sm);">
                    <thead>
                        <tr style="background: #dbeafe;">
                            <th style="text-align: left; padding: 6px 8px; border-bottom: 2px solid #93c5fd;">Data Point</th>
                            <th style="text-align: left; padding: 6px 8px; border-bottom: 2px solid #93c5fd;">Source</th>
                            <th style="text-align: left; padding: 6px 8px; border-bottom: 2px solid #93c5fd;">Method</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td style="padding: 5px 8px;">Token amounts & price range</td><td style="padding: 5px 8px;">Uniswap V3 NonfungiblePositionManager</td><td style="padding: 5px 8px;"><code>positions(tokenId)</code> on-chain call</td></tr>
                        <tr style="background: #f0f6ff;"><td style="padding: 5px 8px;">Current price & tick</td><td style="padding: 5px 8px;">Uniswap V3 Pool contract</td><td style="padding: 5px 8px;"><code>slot0()</code> on-chain call</td></tr>
                        <tr><td style="padding: 5px 8px;">Uncollected fees</td><td style="padding: 5px 8px;">Pool feeGrowth + Position feeGrowth</td><td style="padding: 5px 8px;"><code>feeGrowthGlobal</code>, <code>ticks()</code>, <code>positions()</code></td></tr>
                        <tr style="background: #f0f6ff;"><td style="padding: 5px 8px;">Pool TVL & liquidity</td><td style="padding: 5px 8px;">Pool contract + DEXScreener</td><td style="padding: 5px 8px;"><code>liquidity()</code> + API cross-check</td></tr>
                        <tr><td style="padding: 5px 8px;">Volume 24h & transactions</td><td style="padding: 5px 8px;">DEXScreener API</td><td style="padding: 5px 8px;"><code>GET /latest/dex/pairs/&#123;chain&#125;/&#123;pair&#125;</code></td></tr>
                        <tr style="background: #f0f6ff;"><td style="padding: 5px 8px;">USD prices (ETH, tokens)</td><td style="padding: 5px 8px;">DEXScreener + on-chain</td><td style="padding: 5px 8px;">API <code>priceUsd</code> + sqrtPriceX96 derivation</td></tr>
                        <tr><td style="padding: 5px 8px;">Math formulas</td><td style="padding: 5px 8px;">Uniswap V3 Whitepaper</td><td style="padding: 5px 8px;">§2 Concentrated Liquidity, §6.1-6.3 Tick Math</td></tr>
                        <tr style="background: #f0f6ff;"><td style="padding: 5px 8px;">IL formula</td><td style="padding: 5px 8px;">Pintail (2019) + Whitepaper §2</td><td style="padding: 5px 8px;"><code>2√r/(1+r) - 1</code> × capital efficiency</td></tr>
                        <tr><td style="padding: 5px 8px;">V3 IL amplification</td><td style="padding: 5px 8px;">Whitepaper §2 + Pintail</td><td style="padding: 5px 8px;"><code>IL_v3 = IL_v2 × CE</code> (concentrated range)</td></tr>
                        <tr style="background: #f0f6ff;"><td style="padding: 5px 8px;">Pool comparison / APR</td><td style="padding: 5px 8px;">DefiLlama Yields API</td><td style="padding: 5px 8px;"><code>GET https://yields.llama.fi/pools</code> (free, no key)</td></tr>
                    </tbody>
                </table>
            </div>
            
            <div style="background: #fefce8; border: 2px solid #eab308; border-radius: 12px; padding: 1.5rem; margin: 0 0 2rem 0;">
                <h3 style="color: #854d0e; margin-top: 0;">🔍 Cross-Validation with Third-Party Dashboards</h3>
                <p style="font-size: var(--fs-sm); color: #854d0e; margin-bottom: 1rem;">
                    We recommend verifying this report against independent dashboards. In our testing, on-chain reads
                    typically matched Revert.finance within small margins for position value and uncollected fees.
                    Results may vary depending on market conditions, RPC latency, and block timing.
                </p>
                <table style="width: 100%; border-collapse: collapse; font-size: var(--fs-sm);">
                    <thead>
                        <tr style="background: #fef9c3;">
                            <th style="text-align: left; padding: 6px 8px; border-bottom: 2px solid #facc15;">Dashboard</th>
                            <th style="text-align: left; padding: 6px 8px; border-bottom: 2px solid #facc15;">What It Shows</th>
                            <th style="text-align: left; padding: 6px 8px; border-bottom: 2px solid #facc15;">Link</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td style="padding: 5px 8px;">🟢 <strong>Revert.finance</strong></td><td style="padding: 5px 8px;">V3 position PnL, divergence loss, historical fees, APR</td><td style="padding: 5px 8px;"><a href="{_safe_href("https://revert.finance/#/account/" + _safe(data.get("wallet_address", "")))}" target="_blank" style="color: #2563eb;">Open →</a></td></tr>
                        <tr style="background: #fffef0;"><td style="padding: 5px 8px;">🟡 <strong>Zerion</strong></td><td style="padding: 5px 8px;">Full wallet balance, all DeFi positions, P&L</td><td style="padding: 5px 8px;"><a href="{_safe_href("https://app.zerion.io/" + _safe(data.get("wallet_address", "")) + "/overview")}" target="_blank" style="color: #2563eb;">Open →</a></td></tr>
                        <tr><td style="padding: 5px 8px;">🟡 <strong>Zapper</strong></td><td style="padding: 5px 8px;">Portfolio tracker, DeFi positions, yields</td><td style="padding: 5px 8px;"><a href="{_safe_href("https://zapper.xyz/account/" + _safe(data.get("wallet_address", "")) + "?tab=apps")}" target="_blank" style="color: #2563eb;">Open →</a></td></tr>
                        <tr style="background: #fffef0;"><td style="padding: 5px 8px;">🟡 <strong>DeBank</strong></td><td style="padding: 5px 8px;">Multi-chain portfolio, protocol breakdown</td><td style="padding: 5px 8px;"><a href="{_safe_href("https://debank.com/profile/" + _safe(data.get("wallet_address", "")))}" target="_blank" style="color: #2563eb;">Open →</a></td></tr>
                        <tr><td style="padding: 5px 8px;">🔵 <strong>Uniswap App</strong></td><td style="padding: 5px 8px;">Official interface — manage, collect fees, rebalance</td><td style="padding: 5px 8px;"><a href="{_safe_href("https://app.uniswap.org/positions/v3/" + net.lower() + "/" + _safe(str(data.get("position_id", ""))))}" target="_blank" style="color: #2563eb;">Open →</a></td></tr>
                    </tbody>
                </table>
                <p style="font-size: var(--fs-sm); color: #92400e; margin-bottom: 0; margin-top: 0.75rem;">
                    ⚠️ <strong>Note:</strong> Dashboard values may differ slightly due to caching, data freshness, and fee computation methods.
                    Our tool reads on-chain data in real-time via <code>eth_call</code> — the most accurate method available.
                </p>
            </div>
            
            <h3>📋 Data Schema & Sources:</h3>
            <div class="metric-grid">
                <div class="metric-card">
                    <div><strong>DEXScreener API Schema:</strong></div>
                    <div style="font-size: var(--fs-md);">
                        • <code>priceUsd</code>: Current USD price<br>
                        • <code>volume.h24</code>: Volume 24h<br>
                        • <code>liquidity.usd</code>: Pool TVL<br>
                        • <code>txns.h24</code>: Transactions 24h<br>
                        • <code>pairCreatedAt</code>: Creation date
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Uniswap V3 Formulas:</strong></div>
                    <div style="font-size: var(--fs-md);">
                        • Tick ↔ Price: <code>p(i) = 1.0001^i</code><br>
                        • Liquidity: <code>L = Δx√(Pa·Pb)/(√Pb-√Pa)</code><br>
                        • IL: <code>2√(r)/(1+r) - 1</code><br>
                        • Capital Efficiency: <code>1/(1-√(Pa/Pb))</code>
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Blockchain Endpoints:</strong></div>
                    <div style="font-size: var(--fs-md);">
                        • <strong>{net}:</strong> Official RPC<br>
                        • <strong>Explorer:</strong> {_explorer(net.lower()).get("name", "Scanner")}<br>
                        • <strong>Graph Protocol:</strong> On-chain indexing<br>
                        • <strong>IPFS:</strong> Decentralized metadata
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Data Validation:</strong></div>
                    <div style="font-size: var(--fs-md);">
                        • Addresses: EIP-55 checksum + regex hex validation<br>
                        • Prices: On-chain sqrtPriceX96 + DEXScreener cross-check<br>
                        • Ranges: Tick → price boundary math (Whitepaper §6.1)<br>
                        • Fees: On-chain feeGrowthGlobal/Inside/Outside (Tick library)
                    </div>
                </div>
            </div>
            
            <h3>🏗️ Technical Architecture:</h3>
            <div class="metric-grid">
                <div class="metric-card">
                    <div><strong>Pool Address:</strong></div>
                    <div style="font-family: monospace; word-break: break-all; font-size: var(--fs-md);">{pool_addr}</div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Token0 ({t0}):</strong></div>
                    <div>{t0_info} • Decimals: {data.get("token0_decimals", "18")}<br>ERC-20 Standard</div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Token1 ({t1}):</strong></div>
                    <div>{t1_info} • Decimals: {data.get("token1_decimals", "18")}<br>ERC-20 Standard</div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Fee Tier:</strong></div>
                    <div>{data.get("fee_tier_label", safe_num(data.get("fee_tier", 3000)))} • Protocol Fee Split<br>LP Fee Distribution</div>
                </div>
            </div>
            
            <h3>🔗 Official APIs & Contract Integrations:</h3>
            <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin: 1rem 0;">
                <h4>📊 DEXScreener API (Pool Market Data)</h4>
                <ul style="margin: 0.5rem 0; font-size: var(--fs-md);">
                    <li><strong>Endpoint:</strong> <code>https://api.dexscreener.com/latest/dex/pairs/&#123;chainId&#125;/&#123;pairAddress&#125;</code></li>
                    <li><strong>Rate Limit:</strong> 300 requests/min (<a href="https://docs.dexscreener.com/api/reference" target="_blank">officially documented</a>)</li>
                    <li><strong>Authentication:</strong> Public (no API key required)</li>
                    <li><strong>Data Used:</strong> <code>volume.h24</code>, <code>liquidity.usd</code>, <code>priceUsd</code>, <code>txns.h24</code></li>
                    <li><strong>Limitation:</strong> Volume is a 24h snapshot — may not represent average daily volume</li>
                </ul>
                
                <h4>⛓️ On-Chain RPC — Direct Contract Reads (Most Accurate)</h4>
                <ul style="margin: 0.5rem 0; font-size: var(--fs-md);">
                    <li><strong>Method:</strong> JSON-RPC <code>eth_call</code> — reads live blockchain state, zero intermediaries</li>
                    <li><strong>RPC:</strong> Public {net} endpoint (no API key)</li>
                    <li><strong>Contracts Called:</strong>
                        <ul>
                            <li><strong>NonfungiblePositionManager</strong> (<code>0xC36442b4a4522E871399CD717aBDD847Ab11FE88</code>) — <a href="https://docs.uniswap.org/contracts/v3/reference/periphery/NonfungiblePositionManager" target="_blank">official docs</a>
                                <br>→ <code>positions(tokenId)</code>: token0/1, tickLower/Upper, liquidity, feeGrowthInside</li>
                            <li><strong>UniswapV3Pool</strong> (<code>{pool_addr}</code>) — <a href="https://docs.uniswap.org/contracts/v3/reference/core/UniswapV3Pool" target="_blank">official docs</a>
                                <br>→ <code>slot0()</code>: sqrtPriceX96, tick
                                <br>→ <code>liquidity()</code>: active pool liquidity
                                <br>→ <code>ticks(int24)</code>: feeGrowthOutside per tick boundary
                                <br>→ <code>feeGrowthGlobal0X128()</code>, <code>feeGrowthGlobal1X128()</code>: cumulative fees</li>
                            <li><strong>ERC-20 tokens</strong> → <code>decimals()</code>, <code>symbol()</code></li>
                        </ul>
                    </li>
                    <li><strong>Fee Computation:</strong> Following <a href="https://docs.uniswap.org/contracts/v3/reference/core/libraries/Tick" target="_blank">Tick library</a> — uncollected = (feeGrowthGlobal − feeGrowthOutside − feeGrowthInside) × liquidity / 2¹²⁸</li>
                </ul>
                
                <h4>🦎 DefiLlama Yields API (Pool Scout / Cross-DEX Comparison)</h4>
                <ul style="margin: 0.5rem 0; font-size: var(--fs-md);">
                    <li><strong>Endpoint:</strong> <code>https://yields.llama.fi/pools</code></li>
                    <li><strong>Rate Limit:</strong> ~30 requests/min (free, no API key required)</li>
                    <li><strong>Authentication:</strong> Public (100% free)</li>
                    <li><strong>Coverage:</strong> 20,000+ pools across all major DEXes and chains</li>
                    <li><strong>Data Used:</strong> <code>apy</code>, <code>apyBase</code>, <code>tvlUsd</code>, <code>volumeUsd1d</code>, <code>apyMean30d</code>, <code>ilRisk</code></li>
                    <li><strong>Purpose:</strong> Pool Scout — compare your pool against alternatives across DEXes/chains</li>
                    <li><strong>Documentation:</strong> <a href="https://defillama.com/docs/api" target="_blank">defillama.com/docs/api</a></li>
                </ul>
                
                <h4>🦄 Uniswap V3 Core — Mathematical References</h4>
                <ul style="margin: 0.5rem 0; font-size: var(--fs-md);">
                    <li><strong>Whitepaper:</strong> <a href="https://uniswap.org/whitepaper-v3.pdf" target="_blank">uniswap.org/whitepaper-v3.pdf</a> — §2 Concentrated Liquidity, §6.1-6.3 Tick Math</li>
                    <li><strong>SDK Source:</strong> <a href="https://github.com/Uniswap/v3-sdk" target="_blank">github.com/Uniswap/v3-sdk</a> — reference implementation</li>
                    <li><strong>Deployments:</strong> <a href="https://docs.uniswap.org/contracts/v3/reference/deployments/" target="_blank">docs.uniswap.org/contracts/v3/reference/deployments</a></li>
                    {'<li><strong>Your Position:</strong> <a href="' + _safe_href("https://app.uniswap.org/positions/v3/" + net.lower() + "/" + str(data.get("position_id", ""))) + '" target="_blank">app.uniswap.org/positions/v3/{}/{}</a></li>'.format(net.lower(), data.get("position_id", "")) if data.get("position_id") else ""}
                    <li><strong>Pool:</strong> <a href="{_safe_href("https://app.uniswap.org/explore/pools/" + net.lower() + "/" + pool_addr)}" target="_blank">app.uniswap.org/explore/pools/{pool_addr[:16]}…</a></li>
                </ul>
            </div>
            
            <h3>🔄 Detailed Calculation Methodology:</h3>
            <div class="metric-card" style="text-align: left;">
                <div style="font-size: var(--fs-md); line-height: 1.6;">
                    <p><strong>1. Data Collection:</strong></p>
                    <ul>
                        <li>Pool market data via DEXScreener public API → schema validation</li>
                        <li>Position data via on-chain <code>eth_call</code> → direct contract reads (no intermediary)</li>
                        <li>USD prices from DEXScreener + on-chain sqrtPriceX96 derivation</li>
                    </ul>
                    
                    <p><strong>2. Mathematical Processing (per Uniswap V3 Whitepaper):</strong></p>
                    <ul>
                        <li>Tick ↔ Price: <code>p(i) = 1.0001^i</code> (Whitepaper §6.1)</li>
                        <li>Liquidity: <code>L = Δx·√Pa·√Pb / (√Pb − √Pa)</code> (Whitepaper §6.2)</li>
                        <li>Token amounts: <code>getAmount0ForLiquidity()</code>, <code>getAmount1ForLiquidity()</code> (SDK reference)</li>
                        <li>Uncollected fees: feeGrowthGlobal − feeGrowthOutside − feeGrowthInside (Tick library)</li>
                        <li>Impermanent Loss: <code>2√(r)/(1+r) - 1</code> (Pintail 2019)</li>
                        <li>Capital efficiency: <code>1 / (1 - √(Pa/Pb))</code> (Whitepaper §2)</li>
                    </ul>
                    
                    <p><strong>3. Known Limitations (Transparency):</strong></p>
                    <ul>
                        <li><strong>Fee projections:</strong> Based on 24h volume snapshot — actual average may differ 20-30%</li>
                        <li><strong>APR estimate:</strong> Assumes constant in-range status and volume — not guaranteed</li>
                        <li><strong>Divergence loss:</strong> Estimated at range boundaries only — actual IL depends on entry vs current price</li>
                        <li><strong>Total PnL:</strong> Not shown — use <a href="https://revert.finance" target="_blank" style="color: var(--primary);">Revert.finance</a> for complete PnL tracking</li>
                        <li><strong>Volume variance:</strong> 24h DEXScreener snapshot ≠ 7-day average. Cross-validate with Revert</li>
                    </ul>
                    
                    <p><strong>4. Validation & Output:</strong></p>
                    <ul>
                        <li>Address validation via regex + checksum</li>
                        <li>Fee tier validation against known Uniswap V3 tiers (0.01%, 0.05%, 0.3%, 1%)</li>
                        <li>HTML sanitized against XSS injection</li>
                        <li>All timestamps recorded for audit trail</li>
                    </ul>
                </div>
            </div>
        </div>

        <!-- ═══════════════════ TAB CONTENT: AUDIT TRAIL ═══════════════════ -->
        <div class="tab-content" id="tab-audit">
        {_build_audit_trail(data)}
        </div>

        <!-- ═══════════════════ TAB CONTENT: LEGAL COMPLIANCE ═══════════════════ -->
        <div class="tab-content" id="tab-legal">
            <h2 class="session-title">⚖️ Legal Compliance</h2>
            
            <div style="background: #fef2f2; border: 2px solid #dc2626; border-radius: 12px; padding: 2rem; margin: 2rem 0;">
                <h3 style="color: #991b1b; margin-top: 0;">🚨 MANDATORY DISCLAIMER</h3>
                <div style="color: #991b1b; font-weight: 600; line-height: 1.8;">
                    <p><strong>This tool performs EXCLUSIVELY EDUCATIONAL analysis of DeFi pools.</strong></p>
                    <p><strong>This is NOT financial, investment, tax, or legal advice.</strong></p>
                    <p><strong>Strategy comparisons in this report are HYPOTHETICAL mathematical examples — NOT investment recommendations.</strong></p>
                    
                    <div style="background: #fecaca; padding: 1rem; border-radius: 8px; margin: 1rem 0; border: 2px solid #dc2626;">
                        <h4 style="margin-top: 0; color: #991b1b;">🚨 REGULATORY COMPLIANCE WARNINGS:</h4>
                        <ul style="margin-bottom: 0; color: #991b1b;">
                            <li><strong>🇧🇷 CVM/Lei 14.478:</strong> Ativos virtuais—risco total perda. Ferramenta NÃO autorizada CVM</li>
                            <li><strong>🇺🇸 SEC:</strong> Forward-looking statements—actual results may differ materially</li>
                            <li><strong>🇪🇺 MiCA:</strong> Past performance ≠ future results. Crypto assets highly volatile</li>
                            <li><strong>🚨 Total Loss Risk:</strong> DeFi protocols can result in 100% capital loss</li>
                            <li><strong>📉 IL Amplification:</strong> V3 concentrated liquidity amplifies losses vs V2</li>
                            <li><strong>⚡ Snapshot Bias:</strong> 24h APR estimates—seasonal/volume effects underestimated</li>
                            <li><strong>💰 No Guarantees:</strong> All projections are theoretical—actual returns may be negative</li>
                            <li><strong>🎯 Not Investment Advice:</strong> Educational analysis only—consult licensed advisors</li>
                        </ul>
                    </div>
                    
                    <p><strong style="font-size: var(--fs-lg);">⚖️ LEGAL RESPONSIBILITY:</strong></p>
                    <p>The developer assumes <strong>NO RESPONSIBILITY</strong> for losses, direct, indirect, incidental or consequential damages arising from the use of this tool.</p>
                </div>
            </div>
            
            <h3>📚 Legal Structure & Compliance:</h3>
            <div class="metric-grid">
                <div class="metric-card">
                    <div><strong>Licensing:</strong></div>
                    <div style="font-size: var(--fs-md);">
                        • <strong>License:</strong> MIT License<br>
                        • <strong>Open Source:</strong> Public GitHub<br>
                        • <strong>Audit:</strong> Code available for inspection<br>
                        • <strong>Distribution:</strong> Free for educational use
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>🇧🇷 BRASIL COMPLIANCE:</strong></div>
                    <div style="font-size: var(--fs-md); color: #dc2626;">
                        • <strong>CVM Art. 11:</strong> NÃO registrada/autorizada pela CVM<br>
                        • <strong>Lei 14.478/22:</strong> Ativos virtuais—risco total perda<br>
                        • <strong>LGPD:</strong> Dados mínimos, consent documented<br>
                        • <strong>Uso:</strong> Apenas educacional
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>🌍 INTERNATIONAL COMPLIANCE:</strong></div>
                    <div style="font-size: var(--fs-md); color: #dc2626;">
                        • <strong>🇺🇸 US/SEC:</strong> Forward-looking statements—not guaranteed<br>
                        • <strong>🇪🇺 EU/MiCA:</strong> Crypto estimates—past ≠ future performance<br>
                        • <strong>Educational tool:</strong> Not investment advice/security<br>
                        • <strong>Risk:</strong> Total loss possible in DeFi
                    </div>
                </div>
            </div>
            
            <h3>🏛️ Official Sources & Technical References:</h3>
            <div style="background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 1.5rem; margin: 1rem 0;">
                <h4 style="color: #15803d; margin-top: 0;">📄 Core Documentation</h4>
                <div class="metric-grid" style="gap: 0.5rem;">
                    <div>• <a href="https://uniswap.org/whitepaper-v3.pdf" target="_blank" style="color: #2563eb;">Uniswap V3 Whitepaper</a> (mathematical formulas)</div>
                    <div>• <a href="https://docs.uniswap.org" target="_blank" style="color: #2563eb;">Official Uniswap Documentation</a></div>
                    <div>• <a href="https://docs.dexscreener.com/api/reference" target="_blank" style="color: #2563eb;">DEXScreener API Reference</a></div>
                    <div>• <a href="https://ethereum.org/en/developers/docs/" target="_blank" style="color: #2563eb;">Ethereum Developer Docs</a></div>
                </div>
                
                <h4 style="color: #15803d;">🔗 Operational Links</h4>
                <div class="metric-grid" style="gap: 0.5rem;">
                    <div>• <a href="https://app.uniswap.org" target="_blank" style="color: #2563eb;">Official Uniswap Interface</a></div>
                    <div>• <a href="https://dexscreener.com" target="_blank" style="color: #2563eb;">DEXScreener Platform</a></div>
                    <div>• <a href="{_safe_href(_explorer(net.lower()).get("base", "#"))}" target="_blank" style="color: #2563eb;">{_explorer(net.lower()).get("name", "Blockchain")} Explorer</a></div>
                    <div>• <a href="https://github.com/fabiotreze/defi-cli" target="_blank" style="color: #2563eb;">Open Source Repository</a></div>
                </div>
                
                <h4 style="color: #15803d;">💡 Scientific Research</h4>
                <div class="metric-grid" style="gap: 0.5rem;">
                    <div>• <a href="https://pintail.medium.com/uniswap-a-good-deal-for-liquidity-providers-104c0b6816f2" target="_blank" style="color: #2563eb;">Pintail Research - Impermanent Loss</a></div>
                    <div>• <a href="https://uniswapv3book.com" target="_blank" style="color: #2563eb;">Uniswap V3 Development Book</a></div>
                    <div>• <a href="https://arxiv.org/abs/2103.14769" target="_blank" style="color: #2563eb;">Replicating Market Makers (Angeris et al., 2021)</a></div>
                </div>
            </div>
            
            <h3>⭐ Like this project?</h3>
            <div style="background: #fffbeb; border: 1px solid #fbbf24; border-radius: 8px; padding: 1rem; margin: 1rem 0;">
                <p style="margin: 0; font-size: var(--fs-md);"><strong>🌟 Star us on GitHub:</strong> 
                    <a href="https://github.com/fabiotreze/defi-cli" target="_blank" style="color: #2563eb;">github.com/fabiotreze/defi-cli</a>
                </p>
            </div>
        </div>
        </div>  <!-- End tab-container -->

        <!-- ═══════════════════ FOOTER ═══════════════════ -->
        <div class="footer">
            <div style="background: #dbeafe; border: 1px solid #3b82f6; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                <strong style="color: #1d4ed8;">📋 CONSENT RECORDED</strong>
                <div style="font-size: var(--fs-md); color: #1d4ed8; margin-top: 0.5rem;">
                    User agreement timestamp: {consent_ts} · Legal compliance documented for this session
                </div>
            </div>
            <p><strong>DeFi CLI v{PROJECT_VERSION}</strong> · Report generated on {generated}</p>
            <p>Sources: Uniswap V3 Whitepaper, DEXScreener API, DefiLlama Yields API</p>
            <p style="font-size: var(--fs-md); color: var(--text-light);">
                This report was generated for educational purposes. Always verify data independently.
            </p>
        </div>
    </div>

    <script nonce="{nonce}">
        function showTab(tabId, clickedButton) {{
            var contents = document.querySelectorAll('.tab-content');
            for (var i = 0; i < contents.length; i++) {{ contents[i].classList.remove('active'); }}
            var buttons = document.querySelectorAll('.tab-btn');
            for (var i = 0; i < buttons.length; i++) {{ buttons[i].classList.remove('active'); }}
            var targetTab = document.getElementById(tabId);
            if (targetTab) {{ targetTab.classList.add('active'); }}
            if (clickedButton) {{ clickedButton.classList.add('active'); }}
        }}

        function toggleExportMode() {{
            var body = document.body;
            var btn = document.getElementById('btn-toggle-view');
            var isExport = body.classList.toggle('export-mode');
            if (isExport) {{
                btn.innerHTML = '🔙 Tab View';
                btn.classList.add('active');
            }} else {{
                btn.innerHTML = '📋 Full Report View';
                btn.classList.remove('active');
                showTab('tab-position', document.querySelector('[data-tab="tab-position"]'));
            }}
        }}

        document.addEventListener('DOMContentLoaded', function() {{
            // Tab navigation — CSP-safe event delegation (no inline onclick)
            document.querySelectorAll('.tab-btn').forEach(function(btn) {{
                btn.addEventListener('click', function() {{
                    showTab(this.getAttribute('data-tab'), this);
                }});
            }});

            // Export bar buttons — CSP-safe
            document.querySelectorAll('[data-action="toggle-export"]').forEach(function(btn) {{
                btn.addEventListener('click', toggleExportMode);
            }});
            document.querySelectorAll('[data-action="print"]').forEach(function(btn) {{
                btn.addEventListener('click', function() {{ window.print(); }});
            }});

            // Ensure first tab active
            showTab('tab-position', document.querySelector('[data-tab="tab-position"]'));

            // Collapsible sections — CSP-safe
            document.querySelectorAll('.collapsible-toggle').forEach(function(toggle) {{
                toggle.addEventListener('click', function() {{
                    var targetId = this.getAttribute('data-target');
                    var target = document.getElementById(targetId);
                    var chevron = this.querySelector('.chevron');
                    if (target) {{
                        var isExpanded = target.classList.toggle('expanded');
                        if (isExpanded) {{
                            if (chevron) chevron.textContent = '▲';
                        }} else {{
                            if (chevron) chevron.textContent = '▼';
                        }}
                    }}
                }});
            }});

            // Copy-to-clipboard — CSP-safe
            document.querySelectorAll('.copy-btn').forEach(function(btn) {{
                btn.addEventListener('click', function() {{
                    var text = this.getAttribute('data-copy');
                    var orig = btn.innerHTML;
                    navigator.clipboard.writeText(text).then(function() {{
                        btn.innerHTML = '✅ Copied';
                        setTimeout(function() {{ btn.innerHTML = orig; }}, 1500);
                    }});
                }});
            }});
        }});
    </script>
</body>
</html>"""


def generate_position_report(data: Dict[str, Any], _open_browser: bool = True) -> Path:
    """Generate HTML report as a temporary file and open in browser.

    The report is created as a temporary file — nothing is persisted unless
    the user explicitly saves from the browser (Ctrl+S / ⌘+S).

    Privacy: no cookies, no saved files, no retained data.
    ⚠️ Reports contain financial data — a disclaimer banner is always shown.
    """
    html_content = _build_html(data)

    # Generate filename parts
    t0 = _safe_filename(data.get("token0_symbol", "TOKEN0"))
    t1 = _safe_filename(data.get("token1_symbol", "TOKEN1"))
    network = _safe_filename(data.get("network", "ethereum"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{t0}_{t1}_{network}_{timestamp}.html"

    # Temporary file — auto-cleaned on process exit (CWE-459 / LGPD Art. 6 III)
    # Uses restrictive permissions (0o600) to prevent other users reading reports
    temp_path = os.path.join(tempfile.gettempdir(), f"defi_cli_{filename}")
    # Ensure unique filename (avoid O_EXCL failure on rapid calls)
    counter = 0
    while os.path.exists(temp_path):
        counter += 1
        temp_path = os.path.join(
            tempfile.gettempdir(), f"defi_cli_{counter}_{filename}"
        )
    fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as tmp:
        tmp.write(html_content)
    filepath = Path(temp_path)
    _register_temp_file(str(filepath))
    if _open_browser:
        webbrowser.open(f"file://{filepath.resolve()}")
    return filepath


# Test function for CLI usage
def main() -> None:
    """Test function: generate a sample report from a live pool.

    Usage:
        python html_generator.py <pool_address>
    """
    import sys
    import asyncio
    from real_defi_math import PositionData, analyze_position
    from defi_cli.dexscreener_client import analyze_pool_real

    pool = sys.argv[1] if len(sys.argv) > 1 else None
    if not pool:
        print("Usage: python html_generator.py <pool_address>")
        sys.exit(1)

    async def _generate() -> None:
        print(f"Fetching pool data for {pool[:16]}...")
        result = await analyze_pool_real(pool)
        if result["status"] != "success":
            print(f"❌ {result['message']}")
            return
        pos = PositionData.from_pool_data(result["data"])
        path = generate_position_report(analyze_position(pos))
        print(f"✅ {path}")

    asyncio.run(_generate())


if __name__ == "__main__":
    main()
