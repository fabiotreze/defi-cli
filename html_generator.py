"""
HTML report generator for DeFi CLI v1.0.0
Generates comprehensive position analysis with 5 structured sessions as requested by user.

This module creates detailed HTML reports from Uniswap V3 position data,
including risk assessment, alternative strategies, and legal disclaimers.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

try:
    from defi_cli.legal_disclaimers import BTC_DONATION, ETH_DONATION
except ImportError:
    BTC_DONATION = "See source code"
    ETH_DONATION = "See source code"

# Constants
REPORTS_DIR = Path("reports")

def _safe(value: Any, fallback: str = "Unknown") -> str:
    """Escape a value for safe HTML embedding (XSS prevention)."""
    if value is None:
        return fallback
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")

def _safe_filename(value: str) -> str:
    """Strip any character not safe for filenames (path traversal prevention).""" 
    return re.sub(r'[^a-zA-Z0-9._-]', '_', str(value))

def _explorer(network: str) -> Dict[str, str]:
    """Get explorer info for a network."""
    explorers = {
        "ethereum": {"name": "Etherscan", "base": "https://etherscan.io"},
        "arbitrum": {"name": "Arbiscan", "base": "https://arbiscan.io"},
        "polygon": {"name": "PolygonScan", "base": "https://polygonscan.com"},
        "base": {"name": "BaseScan", "base": "https://basescan.org"},
        "optimism": {"name": "Optimistic Etherscan", "base": "https://optimistic.etherscan.io"},
    }
    return explorers.get(network.lower(), {"name": "Explorer", "base": "#"})

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
        "CRV": "Curve DAO Token"
    }
    return tokens.get(symbol.upper(), symbol or "Unknown Token")

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
            <h2 class="session-title">🔍 Audit Trail</h2>
            <div style="background: #fefce8; border: 1px solid #eab308; border-radius: 8px; padding: 1rem;">
                <p style="margin: 0 0 0.5rem 0;">⚠️ <strong>Simulated data</strong> — no on-chain audit trail available.</p>
                <p style="margin: 0; font-size: 0.85rem; color: #92400e;">For the <strong>full experience</strong> (on-chain data, audit trail, and working cross-validation links), run with:<br>
                <code style="background: #fef3c7; padding: 2px 6px; border-radius: 4px;">python run.py report &lt;pool&gt; --position &lt;id&gt; --wallet &lt;addr&gt; --network &lt;net&gt;</code></p>
            </div>
        </div>
        """

    block = audit.get("block_number", 0)
    rpc = _safe(audit.get("rpc_endpoint", ""))
    contracts = audit.get("contracts", {})
    raw_calls = audit.get("raw_calls", [])
    formulas = audit.get("formulas_applied", [])
    net = _safe((data.get("network") or "arbitrum").lower())
    
    # Build explorer links
    explorer_base = _explorer(net).get("base", "")
    block_link = f'{explorer_base}/block/{block}' if explorer_base and block else "#"

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
        to_link = f'<a href="{explorer_base}/address/{to_addr}" target="_blank" style="color: #2563eb;">{to_short}</a>' if explorer_base else to_short
        
        call_rows += f"""
        <tr style="{bg}">
            <td style="padding: 6px 8px; font-weight: 600;">{i+1}. {label}</td>
            <td style="padding: 6px 8px; font-family: monospace; font-size: 0.8rem;">{to_link}</td>
            <td style="padding: 6px 8px; font-family: monospace; font-size: 0.75rem; word-break: break-all;">{calldata}</td>
            <td style="padding: 6px 8px; font-size: 0.8rem;">{decoded_str}</td>
        </tr>
        """
    
    # Build formulas list
    formula_items = "".join(
        f'<li style="margin: 4px 0;"><code>{_safe(f)}</code></li>'
        for f in formulas
    )

    # Contract addresses
    pm_addr = _safe(contracts.get("position_manager", ""))
    pool_addr = _safe(contracts.get("pool", ""))
    t0_addr = _safe(contracts.get("token0", ""))
    t1_addr = _safe(contracts.get("token1", ""))

    return f"""
        <div class="session">
            <h2 class="session-title">🔍 Audit Trail — Independent Verification</h2>
            
            <div style="background: #eff6ff; border: 2px solid #3b82f6; border-radius: 12px; padding: 1.5rem; margin: 0 0 1.5rem 0;">
                <h3 style="color: #1d4ed8; margin-top: 0;">📋 How to Audit This Report</h3>
                <p style="font-size: 0.9rem; line-height: 1.6; margin-bottom: 0.5rem;">
                    Every number in this report can be independently verified by replaying the <strong>exact same 
                    blockchain queries</strong> listed below. An auditor needs:
                </p>
                <ol style="font-size: 0.875rem; line-height: 1.7; margin: 0.5rem 0;">
                    <li><strong>Connect</strong> to the RPC endpoint: <code>{rpc}</code></li>
                    <li><strong>Query</strong> at block <a href="{block_link}" target="_blank" style="color: #1d4ed8;"><strong>#{block:,}</strong></a> 
                        — all data was read at this exact block height</li>
                    <li><strong>Execute</strong> each <code>eth_call</code> listed below with the same <code>to</code> + <code>calldata</code></li>
                    <li><strong>Decode</strong> responses and apply the Whitepaper formulas shown</li>
                    <li><strong>Compare</strong> your results with the "Decoded Value" column — they must match exactly</li>
                </ol>
                <p style="font-size: 0.8rem; color: #1e40af; margin-bottom: 0;">
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
                    <div style="font-size: 0.8rem; word-break: break-all;">{rpc}</div>
                </div>
                <div class="metric-card">
                    <div><strong>Data Source:</strong></div>
                    <div>Direct on-chain <code>eth_call</code></div>
                </div>
            </div>
            
            <h3>📝 Smart Contract Addresses</h3>
            <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin: 1rem 0; font-size: 0.85rem;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 4px 8px; font-weight: 600;">PositionManager:</td>
                        <td style="padding: 4px 8px; font-family: monospace; font-size: 0.8rem;">
                            <a href="{explorer_base}/address/{pm_addr}" target="_blank" style="color: #2563eb;">{pm_addr}</a>
                        </td>
                    </tr>
                    <tr style="background: #f0f6ff;">
                        <td style="padding: 4px 8px; font-weight: 600;">Pool:</td>
                        <td style="padding: 4px 8px; font-family: monospace; font-size: 0.8rem;">
                            <a href="{explorer_base}/address/{pool_addr}" target="_blank" style="color: #2563eb;">{pool_addr}</a>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 4px 8px; font-weight: 600;">Token0:</td>
                        <td style="padding: 4px 8px; font-family: monospace; font-size: 0.8rem;">
                            <a href="{explorer_base}/address/{t0_addr}" target="_blank" style="color: #2563eb;">{t0_addr}</a>
                        </td>
                    </tr>
                    <tr style="background: #f0f6ff;">
                        <td style="padding: 4px 8px; font-weight: 600;">Token1:</td>
                        <td style="padding: 4px 8px; font-family: monospace; font-size: 0.8rem;">
                            <a href="{explorer_base}/address/{t1_addr}" target="_blank" style="color: #2563eb;">{t1_addr}</a>
                        </td>
                    </tr>
                </table>
            </div>
            
            <h3>📡 Raw On-Chain Calls (Reproducible)</h3>
            <p style="font-size: 0.8rem; color: var(--text-light);">
                Each row = one <code>eth_call</code>. Copy the <code>calldata</code> and <code>to</code> address to replay with any RPC client.
            </p>
            <div style="overflow-x: auto;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem; border: 1px solid var(--border);">
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
                <p style="font-size: 0.8rem; color: #15803d; margin-top: 0;">
                    Each formula below transforms raw on-chain values into the human-readable numbers shown in this report.
                    Verify against <a href="https://uniswap.org/whitepaper-v3.pdf" target="_blank" style="color: #15803d;">Uniswap V3 Whitepaper</a> §6.1-6.3.
                </p>
                <ol style="font-family: monospace; font-size: 0.8rem; line-height: 1.8;">
                    {formula_items}
                </ol>
            </div>
            
            <div style="background: #fefce8; border: 1px solid #eab308; border-radius: 8px; padding: 1rem; margin: 1rem 0;">
                <h4 style="color: #854d0e; margin-top: 0;">🛠️ Verification Example (curl)</h4>
                <pre style="background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 6px; overflow-x: auto; font-size: 0.75rem; line-height: 1.5;"><code>curl -X POST {rpc} \\
  -H "Content-Type: application/json" \\
  -d '{{"jsonrpc":"2.0","id":1,"method":"eth_call","params":[{{"to":"{pool_addr}","data":"{_safe(raw_calls[0].get('selector', '') if raw_calls else '')}"}},"{hex(block) if block else 'latest'}"]}}'</code></pre>
                <p style="font-size: 0.75rem; color: #92400e; margin-bottom: 0;">
                    Replace <code>"latest"</code> with <code>"{hex(block) if block else '0x0'}"</code> to query the exact same block state.
                </p>
            </div>
        </div>
    """


def _build_html(data: Dict) -> str:
    """Build HTML with 5 structured sessions as requested by user."""
    
    # Basic data extraction
    t0 = _safe(data.get("token0_symbol", "Token0"))
    t1 = _safe(data.get("token1_symbol", "Token1"))
    current_price = data.get("current_price", 0)
    total_value = data.get("total_value_usd", 0)
    in_range = data.get("in_range", False)
    consent_ts = _safe(data.get("consent_timestamp", "Unknown"))
    generated = _safe(data.get("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    net = _safe((data.get("network") or "arbitrum").title())
    
    # Helper for safe number formatting
    def safe_num(val, decimals=2, default=0):
        """Format a number with fixed decimals (no thousands separator). Use for token amounts, percentages, etc."""
        try:
            return f"{float(val or default):.{decimals}f}"
        except (ValueError, TypeError):
            return f"{default:.{decimals}f}"

    def safe_usd(val, decimals=2, default=0):
        """Format a number as USD with thousands separator ($1,234.56). Use for all dollar values."""
        try:
            return f"{float(val or default):,.{decimals}f}"
        except (ValueError, TypeError):
            return f"{default:,.{decimals}f}"
    
    # Status formatting
    status_text_color = "#15803d" if in_range else "#dc2626"
    status_bg = "#f0fdf4" if in_range else "#fef2f2" 
    status_border = "#bbf7d0" if in_range else "#fecaca"
    status_text = "● In Range" if in_range else "● Out of Range"
    
    # Pool info
    pool_addr = _safe(data.get("pool_address", ""))
    t0_info = _token_info(data.get("token0_symbol", ""))
    t1_info = _token_info(data.get("token1_symbol", ""))
    
    # Generate strategies section
    strategies = []
    if total_value > 0:
        for strategy_name in ["conservative", "moderate", "aggressive"]:
            strategy_data = data.get("strategies", {}).get(strategy_name, {})
            if strategy_data:
                strategies.append(f"""
                <div class="strategy-card">
                    <h4>{strategy_name.title()}</h4>
                    <div class="strategy-details">
                        <div><strong>Range:</strong> ${safe_usd(strategy_data.get('lower_price'), 2)} - ${safe_usd(strategy_data.get('upper_price'), 2)}</div>
                        <div><strong>Initial Investment:</strong> ${safe_usd(strategy_data.get('total_value_usd'))}</div>
                        <div><strong>Estimated APY:</strong> {safe_num(strategy_data.get('apr_estimate', 0) * 100, 1)}%</div>
                        <div><strong>Risk Level:</strong> {strategy_data.get('risk_level', 'Unknown')}</div>
                        <div><strong>Description:</strong> {strategy_data.get('description', 'No description')}</div>
                    </div>
                </div>
                """)

    strategies_html = "".join(strategies) if strategies else "<p>Loading strategy data...</p>"
    
    # Generate strategies section with visual elements
    def _render_strategies_visual(strategies_dict):
        """Render strategies with visual gauges and comparison bars."""
        if not strategies_dict:
            return '<div class="tile"><p>Processing strategies...</p></div>'
        
        strategy_html = ""
        colors = {
            "conservative": {"primary": "#059669", "bg": "#dcfce7"},  
            "moderate": {"primary": "#3b82f6", "bg": "#dbeafe"},
            "aggressive": {"primary": "#dc2626", "bg": "#fee2e2"}
        }
        
        risk_icons = {
            "conservative": "🛡️",
            "moderate": "⚖️", 
            "aggressive": "🚀"
        }
        
        for strategy_name in ["conservative", "moderate", "aggressive"]:
            strategy_data = strategies_dict.get(strategy_name, {})
            if not strategy_data:
                continue
                
            color = colors[strategy_name]
            icon = risk_icons[strategy_name]
            apy = strategy_data.get('apr_estimate', 0) * 100
            range_min = strategy_data.get('lower_price', 0)  
            range_max = strategy_data.get('upper_price', 0)
            investment = data.get('total_value_usd', 0) if data.get('total_value_usd', 0) > 0 else strategy_data.get('total_value_usd', 10000)
            risk_level = strategy_data.get('risk_level', 'Unknown')
            description = strategy_data.get('description', 'No description')
            range_width = strategy_data.get('range_width_pct', 0)
            s_t0 = _safe(strategy_data.get('token0_symbol', t0))
            s_t1 = _safe(strategy_data.get('token1_symbol', t1))
            daily_est = strategy_data.get('daily_fees_est', 0)
            weekly_est = strategy_data.get('weekly_fees_est', 0)
            monthly_est = strategy_data.get('monthly_fees_est', 0)
            annual_est = strategy_data.get('annual_fees_est', 0)
            
            # Calculate gauge width based on APY (relative to max 15%)
            gauge_width = min((apy / 15.0) * 100, 100)
            
            strategy_html += f'''
            <div class="tile" style="border-left: 4px solid {color["primary"]};">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, {color["primary"]}, {color["primary"]}cc);">{icon}</div>
                    <div>
                        <div class="tile-title">{strategy_name.title()} Strategy</div>
                        <div style="font-size: 0.875rem; color: var(--text-light);">{description}</div>
                    </div>
                </div>
                
                <!-- Price Range with min/max descriptions -->
                <div style="background: {color["bg"]}; padding: 1rem; border-radius: 8px; margin: 1rem 0;">
                    <div style="display: grid; grid-template-columns: 1fr auto 1fr; gap: 0.5rem; align-items: center;">
                        <div style="text-align: left;">
                            <div style="font-size: 0.7rem; color: var(--text-light); text-transform: uppercase;">Min Price</div>
                            <div style="font-weight: 700; color: #ef4444;">${safe_usd(range_min, 2)}</div>
                            <div style="font-size: 0.7rem; color: var(--text-light);">Below → 100% {s_t0}</div>
                        </div>
                        <div style="text-align: center; font-size: 0.8rem; color: var(--text-light);">
                            ±{range_width:.0f}%
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 0.7rem; color: var(--text-light); text-transform: uppercase;">Max Price</div>
                            <div style="font-weight: 700; color: #16a34a;">${safe_usd(range_max, 2)}</div>
                            <div style="font-size: 0.7rem; color: var(--text-light);">Above → 100% {s_t1}</div>
                        </div>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin: 0.5rem 0;">
                    <div>
                        <div style="font-size: 0.875rem; color: var(--text-light); margin-bottom: 0.25rem;">Investment</div>
                        <div style="font-weight: 600; color: var(--text);">${safe_usd(investment, 0)}</div>
                    </div>
                    <div>
                        <div style="font-size: 0.875rem; color: var(--text-light); margin-bottom: 0.25rem;">Capital Efficiency</div>
                        <div style="font-weight: 600; color: var(--text);">{strategy_data.get("capital_efficiency", 0):.1f}× vs V2</div>
                    </div>
                </div>
                
                <div style="margin: 1rem 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                        <span style="font-size: 0.875rem; color: var(--text-light);">Estimated APY</span>
                        <span style="font-weight: 600; color: {color["primary"]};">{apy:.1f}%</span>
                    </div>
                    <div class="strategy-gauge">
                        <div class="gauge-fill" data-width="{gauge_width}" style="background: linear-gradient(135deg, {color["primary"]}, {color["primary"]}dd);"></div>
                        <div class="gauge-label">{risk_level} Risk</div>
                    </div>
                </div>
                
                <!-- Earnings Projections -->
                <div style="background: #f8fafc; padding: 0.75rem; border-radius: 8px; margin-top: 0.5rem;">
                    <div style="font-size: 0.75rem; color: var(--text-light); text-transform: uppercase; margin-bottom: 0.5rem;">Projected Earnings</div>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 0.5rem; text-align: center;">
                        <div>
                            <div style="font-size: 0.7rem; color: var(--text-light);">Daily</div>
                            <div style="font-weight: 600; color: {color["primary"]}; font-size: 0.9rem;">${safe_usd(daily_est, 2)}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.7rem; color: var(--text-light);">Weekly</div>
                            <div style="font-weight: 600; color: {color["primary"]}; font-size: 0.9rem;">${safe_usd(weekly_est, 2)}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.7rem; color: var(--text-light);">Monthly</div>
                            <div style="font-weight: 600; color: {color["primary"]}; font-size: 0.9rem;">${safe_usd(monthly_est, 2)}</div>
                        </div>
                        <div>
                            <div style="font-size: 0.7rem; color: var(--text-light);">Annual</div>
                            <div style="font-weight: 600; color: {color["primary"]}; font-size: 0.9rem;">${safe_usd(annual_est, 2)}</div>
                        </div>
                    </div>
                </div>
            </div>
            '''
        
        return strategy_html

    # Generate visual strategies HTML
    strategies_visual_html = _render_strategies_visual(data.get("strategies", {}))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:;">
    <title>Position Report: {t0}/{t1} — DeFi CLI</title>
    <style>
        :root {{
            --primary: #2563eb;
            --success: #16a34a; 
            --warning: #d97706;
            --danger: #dc2626;
            --bg: #f8fafc;
            --card: #ffffff;
            --border: #e2e8f0;
            --text: #1e293b;
            --text-light: #64748b;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            margin: 0;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, #1d4ed8 100%);
            color: white;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            text-align: center;
        }}
        
        .session {{
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        
        .session-title {{
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--primary);
            margin-bottom: 1rem;
            border-bottom: 2px solid var(--border);
            padding-bottom: 0.5rem;
        }}
        
        .metric-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin: 1rem 0;
        }}
        
        .metric-card {{
            padding: 1rem;
            border: 1px solid var(--border);
            border-radius: 8px;
            background: #fafbfc;
            position: relative;
            overflow: hidden;
        }}
        
        .metric-value {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--primary);
        }}
        
        .price-range-bar {{
            position: relative;
            width: 100%;
            height: 8px;
            background: linear-gradient(90deg, #ef4444 0%, #f59e0b 50%, #22c55e 100%);
            border-radius: 4px;
            margin: 1rem 0;
        }}
        
        .current-price-indicator {{
            position: absolute;
            top: -4px;
            width: 16px;
            height: 16px;
            background: white;
            border: 3px solid var(--primary);
            border-radius: 50%;
            transform: translateX(-50%);
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        }}
        
        .range-labels {{
            display: flex;
            justify-content: space-between;
            margin-top: 0.5rem;
            font-size: 0.75rem;
            color: var(--text-light);
        }}
        
        .strategy-gauge {{
            position: relative;
            width: 100%;
            height: 80px;
            background: #f1f5f9;
            border-radius: 8px;
            overflow: hidden;
            margin: 0.5rem 0;
        }}
        
        .gauge-fill {{
            height: 100%;
            background: linear-gradient(135deg, var(--primary), #3b82f6);
            transition: width 0.3s ease;
            border-radius: 8px;
        }}
        
        .gauge-label {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-weight: 600;
            color: white;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }}
        
        .tile {{
            background: linear-gradient(135deg, white 0%, #f8fafc 100%);
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 1.5rem;
            margin: 1rem 0;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            transition: all 0.2s ease;
        }}
        
        .tile:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}
        
        .tile-header {{
            display: flex;
            align-items: center;
            margin-bottom: 1rem;
        }}
        
        .tile-icon {{
            width: 40px;
            height: 40px;
            background: linear-gradient(135deg, var(--primary), #3b82f6);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            margin-right: 1rem;
            font-size: 1.25rem;
        }}
        
        .tile-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: var(--text);
        }}
        
        .progress-bar {{
            width: 100%;
            height: 6px;
            background: #e2e8f0;
            border-radius: 3px;
            overflow: hidden;
            margin: 0.5rem 0;
        }}
        
        .progress-fill {{
            height: 100%;
            background: linear-gradient(90deg, var(--primary), #3b82f6);
            border-radius: 3px;
            transition: width 0.5s ease;
        }}
        
        .status-indicator {{
            display: inline-flex;
            align-items: center;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-size: 0.875rem;
            font-weight: 600;
            margin: 0.5rem 0;
        }}
        
        .status-in-range {{
            background: linear-gradient(135deg, #dcfce7, #bbf7d0);
            color: #15803d;
            border: 1px solid #86efac;
        }}
        
        .status-out-range {{
            background: linear-gradient(135deg, #fef2f2, #fecaca);
            color: #dc2626;
            border: 1px solid #fca5a5;
        }}
        
        .apy-display {{
            background: linear-gradient(135deg, #fef3c7, #fde68a);
            border: 1px solid #facc15;
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            margin: 1rem 0;
        }}
        
        .apy-value {{
            font-size: 2rem;
            font-weight: 700;
            color: #d97706;
        }}
        
        .comparison-bars {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 1rem;
            margin: 1rem 0;
        }}
        
        .comparison-item {{
            text-align: center;
            padding: 1rem;
            background: white;
            border: 1px solid var(--border);
            border-radius: 8px;
        }}
        
        .comparison-value {{
            font-size: 1.5rem;
            font-weight: 600;
            margin: 0.5rem 0;
        }}
        
        .comparison-label {{
            font-size: 0.875rem;
            color: var(--text-light);
        }}
        
        .strategy-card {{
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
            margin: 1rem 0;
            background: #f8fafc;
        }}
        
        .strategy-details div {{
            margin: 0.5rem 0;
        }}
        
        .status-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
            background: {status_bg};
            border: 1px solid {status_border};
            color: {status_text_color};
        }}
        
        .footer {{
            text-align: center;
            padding: 2rem;
            color: var(--text-light);
            border-top: 1px solid var(--border);
            margin-top: 2rem;
        }}
        
        .consent-info {{
            background: linear-gradient(135deg, #fefce8, #fef9c3);
            border: 3px solid #f59e0b;
            border-radius: 12px;
            padding: 1.25rem;
            margin: 1.5rem 0;
            font-size: 0.95rem;
            box-shadow: 0 2px 8px rgba(245, 158, 11, 0.15);
        }}
    </style>
    
    <script>
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
            const rangeMin = {safe_num(data.get('range_min', 0), 6)};
            const rangeMax = {safe_num(data.get('range_max', 0), 6)};
            
            document.querySelectorAll('.current-price-indicator').forEach(indicator => {{
                const position = calculatePricePosition(currentPrice, rangeMin, rangeMax);
                indicator.style.left = position + '%';
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
        </div>

        <!-- ═══════════════════ SESSION 1: YOUR POSITION ═══════════════════ -->
        <div class="session">
            <h2 class="session-title">📊 Session 1: Your Position</h2>
            
            {'<div style="background: #dbeafe; border: 1px solid #93c5fd; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.9rem;"><strong>🔗 Data Source:</strong> Real on-chain data via Arbitrum RPC · Position NFT #{}</div>'.format(data.get('position_id', '')) if data.get('data_source') == 'on-chain' else '<div style="background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.9rem;"><strong>⚠️ Data Source:</strong> Simulated position ($10K capital). Use <code>--position &lt;id&gt;</code> for real data.</div>'}

            <!-- Position Value Card -->
            <div class="tile" style="border-left: 4px solid var(--primary);">
                <div class="tile-header">
                    <div class="tile-icon">💰</div>
                    <div>
                        <div class="tile-title">Position Value</div>
                        <div style="font-size: 0.875rem; color: var(--text-light);">{'On-chain balances' if data.get('data_source') == 'on-chain' else 'Simulated balances'}</div>
                    </div>
                </div>
                <div class="comparison-value" style="color: var(--primary); font-size: 2rem;">${safe_usd(total_value)}</div>
                
                <!-- Token Composition -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                    <div style="background: #f0f9ff; padding: 1rem; border-radius: 8px; border: 1px solid #bfdbfe;">
                        <div style="font-size: 0.8rem; color: var(--text-light);">{t0}</div>
                        <div style="font-size: 1.25rem; font-weight: 600;">{safe_num(data.get('token0_amount', 0), 6)}</div>
                        <div style="display: flex; justify-content: space-between; margin-top: 0.25rem;">
                            <span style="color: var(--primary); font-weight: 500;">${safe_usd(data.get('token0_value_usd', 0))}</span>
                            <span style="color: var(--text-light);">{safe_num(data.get('token0_pct', 0), 1)}%</span>
                        </div>
                        <div class="progress-bar" style="margin-top: 0.5rem;"><div class="progress-fill" data-width="{safe_num(data.get('token0_pct', 0), 0)}"></div></div>
                    </div>
                    <div style="background: #fefce8; padding: 1rem; border-radius: 8px; border: 1px solid #fef08a;">
                        <div style="font-size: 0.8rem; color: var(--text-light);">{t1}</div>
                        <div style="font-size: 1.25rem; font-weight: 600;">{safe_num(data.get('token1_amount', 0), 6)}</div>
                        <div style="display: flex; justify-content: space-between; margin-top: 0.25rem;">
                            <span style="color: #d97706; font-weight: 500;">${safe_usd(data.get('token1_value_usd', 0))}</span>
                            <span style="color: var(--text-light);">{safe_num(data.get('token1_pct', 0), 1)}%</span>
                        </div>
                        <div class="progress-bar" style="margin-top: 0.5rem;"><div class="progress-fill" data-width="{safe_num(data.get('token1_pct', 0), 0)}" style="background: #d97706;"></div></div>
                    </div>
                </div>
            </div>

            <!-- Fees Earned Card -->
            <div class="tile" style="border-left: 4px solid #16a34a;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #16a34a, #15803d);">💸</div>
                    <div>
                        <div class="tile-title">Uncollected Fees</div>
                        <div style="font-size: 0.875rem; color: var(--text-light);">{'Computed from on-chain feeGrowth data' if data.get('data_source') == 'on-chain' else 'Estimated from pool volume'}</div>
                    </div>
                </div>
                <div class="comparison-value" style="color: #16a34a; font-size: 1.5rem;">${safe_usd(data.get('fees_earned_usd', 0), 2)}</div>
            </div>

            <!-- Earnings Projections Card -->
            <div class="tile" style="border-left: 4px solid #8b5cf6;">
                <div class="tile-header">
                    <div class="tile-icon" style="background: linear-gradient(135deg, #8b5cf6, #6d28d9);">📅</div>
                    <div>
                        <div class="tile-title">Fee Earnings Projections (Current Position)</div>
                        <div style="font-size: 0.875rem; color: var(--text-light);">Based on Pool APR ({safe_num(data.get('pool_apr_estimate', 0), 1)}%) applied to your position value</div>
                    </div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                    <div style="background: #f5f3ff; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #ddd6fe;">
                        <div style="font-size: 0.75rem; color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Daily</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: #8b5cf6;">${safe_usd(data.get('daily_fees_est', 0), 2)}</div>
                    </div>
                    <div style="background: #f5f3ff; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #ddd6fe;">
                        <div style="font-size: 0.75rem; color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Weekly</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: #8b5cf6;">${safe_usd(data.get('weekly_fees_est', 0), 2)}</div>
                    </div>
                    <div style="background: #f5f3ff; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #ddd6fe;">
                        <div style="font-size: 0.75rem; color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Monthly</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: #7c3aed;">${safe_usd(data.get('monthly_fees_est', 0), 2)}</div>
                    </div>
                    <div style="background: #f5f3ff; padding: 1rem; border-radius: 8px; text-align: center; border: 1px solid #ddd6fe;">
                        <div style="font-size: 0.75rem; color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Annual</div>
                        <div style="font-size: 1.25rem; font-weight: 700; color: #6d28d9;">${safe_usd(data.get('annual_fees_est', 0), 2)}</div>
                    </div>
                </div>
                
                <div style="background: #fef2f2; padding: 0.75rem; border-radius: 8px; margin-top: 0.75rem; font-size: 0.8rem; color: #991b1b; border: 1px solid #fecaca;">
                    <strong>⚠️ THEORETICAL estimate based on today's 24h volume snapshot.</strong> 
                    Actual avg daily fees may differ by 20–30% due to volume fluctuations. 
                    Fee APR does NOT account for <strong>impermanent loss (IL)</strong> — your total PnL may be negative even with high fee earnings.
                    Position APR (fees only): <strong>{safe_num(data.get('position_apr_est', data.get('annual_apy_est', 0)), 1)}%</strong>
                </div>
                
                <div style="background: #f0fdf4; padding: 0.75rem; border-radius: 8px; margin-top: 0.5rem; font-size: 0.8rem; color: #166534; border: 1px solid #bbf7d0;">
                    <strong>🔍 Cross-validate your data:</strong> 
                    <a href="https://revert.finance/#/account/{_safe(data.get('wallet_address', ''))}" target="_blank" style="color: #15803d; font-weight: 600;">Revert.finance</a> 
                    shows real historical fees, PnL, divergence loss, and invested amounts for your position.
                    Compare their <em>avg daily fees</em> and <em>total PnL</em> with these projections.
                </div>
            </div>

            <!-- Key Metrics -->
            <div class="comparison-bars">
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon">⚡</div>
                        <div class="tile-title">Liquidity (L)</div>
                    </div>
                    <div class="comparison-value" style="color: #22c55e;">{safe_num(data.get('liquidity', 0), 0)}</div>
                    <div class="comparison-label">Whitepaper §6.2: L = Δx·√(Pa·Pb)/(√Pb−√Pa)</div>
                </div>
                
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon">🎯</div>
                        <div class="tile-title">Fee Tier</div>
                    </div>
                    <div class="comparison-value" style="color: #f59e0b;">{data.get('fee_tier_label', safe_num(data.get('fee_tier', 3000)))}</div>
                    <div class="comparison-label"><a href="https://docs.uniswap.org/concepts/protocol/fees" style="color: var(--text-light);">Uniswap Fee Tiers</a></div>
                </div>
                
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon">📐</div>
                        <div class="tile-title">Capital Efficiency</div>
                    </div>
                    <div class="comparison-value" style="color: #dc2626;">{safe_num(data.get('capital_efficiency_vs_v2', 1), 1)}× vs V2</div>
                    <div class="comparison-label">Whitepaper §2: 1/(1−√(Pa/Pb))</div>
                </div>
            </div>
        </div>

        <!-- ═══════════════════ SESSION 2: POOL OVERVIEW & STATS ═══════════════════ -->
        <div class="session">
            <h2 class="session-title">📈 Session 2: Pool Overview & Stats</h2>
            <p style="color: var(--text-light); margin-top: -0.5rem;">Source: <a href="https://docs.dexscreener.com/api/reference" style="color: var(--primary);">DEXScreener API</a> · Real-time on-chain data</p>
            
            <!-- Pool APR Highlight -->
            <div class="apy-display">
                <h3 style="margin-top: 0; color: #d97706;">Pool APR (Estimated)</h3>
                <div class="apy-value">{safe_num(data.get('pool_apr_estimate', data.get('annual_apy_est', 0)), 1)}%</div>
                <p style="margin-bottom: 0; color: #78350f;">Formula: (Volume 24h × Fee Tier × 365) / TVL × 100<br>
                <span style="font-size: 0.8rem;">Ref: <a href="https://docs.uniswap.org/concepts/protocol/fees" style="color: #92400e;">Uniswap V3 Fee Distribution</a></span></p>
            </div>
            
            <!-- Pool Stats Grid -->
            <div class="comparison-bars">
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon" style="background: linear-gradient(135deg, #3b82f6, #1d4ed8);">📊</div>
                        <div class="tile-title">24h Volume</div>
                    </div>
                    <div class="comparison-value" style="color: #3b82f6;">${safe_usd(data.get('volume_24h', 0))}</div>
                    <div class="comparison-label">On-chain swap transactions (24h)</div>
                </div>
                
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon" style="background: linear-gradient(135deg, #059669, #047857);">🏦</div>
                        <div class="tile-title">Pool TVL</div>
                    </div>
                    <div class="comparison-value" style="color: #059669;">${safe_usd(data.get('total_value_locked_usd', 0))}</div>
                    <div class="comparison-label">Total Value Locked (pool reserves)</div>
                </div>
                
                <div class="tile">
                    <div class="tile-header">
                        <div class="tile-icon" style="background: linear-gradient(135deg, #d97706, #b45309);">💸</div>
                        <div class="tile-title">24h Fees (Pool)</div>
                    </div>
                    <div class="comparison-value" style="color: #d97706;">${safe_usd(data.get('pool_24h_fees_est', 0))}</div>
                    <div class="comparison-label">Volume × Fee Tier ({data.get('fee_tier_label', '0.05%')})</div>
                </div>
            </div>
            
            <div style="background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 8px; padding: 1rem; margin: 1rem 0; font-size: 0.875rem;">
                <strong>📋 Data Pipeline:</strong>
                <ol style="margin: 0.5rem 0 0 0; padding-left: 1.5rem; color: var(--text-light);">
                    <li>DEXScreener API → pool volume, TVL, price (300 req/min, public)</li>
                    <li>APR = (Volume₂₄h × Fee Tier × 365) / TVL — annualized estimate</li>
                    <li>Fees₂₄h = Volume₂₄h × Fee Tier — distributed pro-rata to in-range LPs</li>
                </ol>
            </div>
        </div>

        <!-- ═══════════════════ SESSION 3: PRICE RANGE, STRATEGIES & RISK ═══════════════════ -->
        <div class="session">
            <h2 class="session-title">🎯 Session 3: Price Range, Strategies & Risk</h2>
            
            <!-- Price Range with clear min/max descriptions -->
            <div class="tile" style="border-left: 4px solid var(--primary);">
                <div class="tile-header">
                    <div class="tile-icon">📈</div>
                    <div class="tile-title">Price Range</div>
                </div>
                
                <div class="price-range-bar">
                    <div class="current-price-indicator"></div>
                </div>
                
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; margin-top: 1rem;">
                    <div style="text-align: left;">
                        <div style="font-size: 0.75rem; color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Min Price (Lower Bound)</div>
                        <div style="font-size: 1.2rem; font-weight: 700; color: #ef4444;">${safe_usd(data.get('range_min'), 2)}</div>
                        <div style="font-size: 0.8rem; color: var(--text-light);">{t1} per {t0}</div>
                        <div style="font-size: 0.75rem; color: var(--text-light); margin-top: 0.25rem;">Below this → 100% {t0}, 0% {t1}</div>
                    </div>
                    <div style="text-align: center;">
                        <div style="font-size: 0.75rem; color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Market Price (Current)</div>
                        <div style="font-size: 1.2rem; font-weight: 700; color: var(--primary);">${safe_usd(current_price, 2)}</div>
                        <div style="font-size: 0.8rem; color: var(--text-light);">{t1} per {t0}</div>
                        <div class="status-indicator {'status-in-range' if in_range else 'status-out-range'}" style="margin-top: 0.5rem; font-size: 0.75rem;">{status_text}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 0.75rem; color: var(--text-light); text-transform: uppercase; letter-spacing: 0.05em;">Max Price (Upper Bound)</div>
                        <div style="font-size: 1.2rem; font-weight: 700; color: #16a34a;">${safe_usd(data.get('range_max'), 2)}</div>
                        <div style="font-size: 0.8rem; color: var(--text-light);">{t1} per {t0}</div>
                        <div style="font-size: 0.75rem; color: var(--text-light); margin-top: 0.25rem;">Above this → 0% {t0}, 100% {t1}</div>
                    </div>
                </div>
                
                <div style="background: #f8fafc; padding: 0.75rem; border-radius: 8px; margin-top: 1rem; font-size: 0.8rem; color: var(--text-light);">
                    <strong>📐 Range Analysis:</strong>
                    Downside buffer: {safe_num(data.get('downside_buffer_pct', 0), 1)}% · 
                    Upside buffer: {safe_num(data.get('upside_buffer_pct', 0), 1)}% · 
                    Range width: ${safe_usd(data.get('range_max', 0) - data.get('range_min', 0), 2)} · 
                    Strategy: <strong>{_safe(data.get('current_strategy', 'moderate')).title()}</strong> · 
                    Source: <a href="https://uniswap.org/whitepaper-v3.pdf" style="color: var(--primary);">Whitepaper §6.1 (Tick-Price)</a>
                </div>
            </div>
            
            <h3>🎯 Strategy Comparison:</h3>
            <div style="background: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 1rem; font-size: 0.85rem; color: #78350f;">
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
                        <div style="font-size: 0.8rem; color: var(--text-light);">Each risk is linked to your position's specific parameters</div>
                    </div>
                </div>
                
                <div style="background: white; padding: 1rem; border-radius: 8px;">
                    <div class="comparison-bars">
                        <div class="comparison-item" style="border-left: 4px solid #ef4444;">
                            <div style="color: #ef4444; font-weight: 600;">1. Impermanent Loss (IL) — Divergence Loss</div>
                            <div class="progress-bar">
                                <div class="progress-fill" data-width="75" style="background: #ef4444;"></div>
                            </div>
                            <div class="comparison-label" style="line-height: 1.5;">
                                <strong>What:</strong> Price divergence between {t0} and {t1} causes value loss vs holding. In concentrated V3 positions, this is called <em>divergence loss</em> and can be much larger than V2 IL.<br>
                                <strong>Your exposure:</strong> Concentrated range ({safe_num(data.get('range_min'), 0)}–{safe_num(data.get('range_max'), 0)}) amplifies IL by {safe_num(data.get('capital_efficiency_vs_v2', 1), 1)}×. <strong style="color: #dc2626;">Divergence loss often exceeds fee earnings — total PnL can be NEGATIVE even with high fee APR.</strong><br>
                                <strong>Verify:</strong> Check your real PnL on <a href="https://revert.finance/#/account/{_safe(data.get('wallet_address', ''))}" style="color: var(--primary);">Revert.finance</a> (shows divergence loss, total PnL, fees vs IL).<br>
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
                                <strong>Your exposure:</strong> Downside {safe_num(data.get('downside_buffer_pct', 0), 1)}% buffer, upside {safe_num(data.get('upside_buffer_pct', 0), 1)}% buffer from current price.<br>
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

        <!-- ═══════════════════ SESSION 4: TECHNICAL DETAILS ═══════════════════ -->
        <div class="session">
            <h2 class="session-title">🔍 Session 4: Technical Details & Transparency</h2>
            
            <div style="background: #eff6ff; border: 2px solid #3b82f6; border-radius: 12px; padding: 1.5rem; margin: 0 0 2rem 0;">
                <h3 style="color: #1d4ed8; margin-top: 0;">🔗 Our Data Sources — Direct from Official Contracts</h3>
                <p style="font-size: 0.9rem; line-height: 1.6; margin-bottom: 1rem;">
                    This report reads data <strong>directly from the blockchain</strong> via official Uniswap V3 smart contract calls 
                    and the DEXScreener public API. No third-party aggregator intermediaries. Values are computed using the 
                    <strong>exact formulas from the <a href="https://uniswap.org/whitepaper-v3.pdf" target="_blank" style="color: #1d4ed8;">Uniswap V3 Whitepaper</a></strong>
                    and the <a href="https://docs.uniswap.org/contracts/v3/reference/core/UniswapV3Pool" target="_blank" style="color: #1d4ed8;">official Uniswap V3 SDK/Contract documentation</a>.
                </p>
                <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
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
                    </tbody>
                </table>
            </div>
            
            <div style="background: #fefce8; border: 2px solid #eab308; border-radius: 12px; padding: 1.5rem; margin: 0 0 2rem 0;">
                <h3 style="color: #854d0e; margin-top: 0;">🔍 Cross-Validation with Third-Party Dashboards</h3>
                <p style="font-size: 0.85rem; color: #854d0e; margin-bottom: 1rem;">
                    We recommend verifying this report against independent dashboards. In our testing, on-chain reads
                    typically matched Revert.finance within small margins for position value and uncollected fees.
                    Results may vary depending on market conditions, RPC latency, and block timing.
                </p>
                <table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                    <thead>
                        <tr style="background: #fef9c3;">
                            <th style="text-align: left; padding: 6px 8px; border-bottom: 2px solid #facc15;">Dashboard</th>
                            <th style="text-align: left; padding: 6px 8px; border-bottom: 2px solid #facc15;">What It Shows</th>
                            <th style="text-align: left; padding: 6px 8px; border-bottom: 2px solid #facc15;">Link</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr><td style="padding: 5px 8px;">🟢 <strong>Revert.finance</strong></td><td style="padding: 5px 8px;">V3 position PnL, divergence loss, historical fees, APR</td><td style="padding: 5px 8px;"><a href="https://revert.finance/#/account/{_safe(data.get('wallet_address', ''))}" target="_blank" style="color: #2563eb;">Open →</a></td></tr>
                        <tr style="background: #fffef0;"><td style="padding: 5px 8px;">🟡 <strong>Zerion</strong></td><td style="padding: 5px 8px;">Full wallet balance, all DeFi positions, P&L</td><td style="padding: 5px 8px;"><a href="https://app.zerion.io/{_safe(data.get('wallet_address', ''))}/overview" target="_blank" style="color: #2563eb;">Open →</a></td></tr>
                        <tr><td style="padding: 5px 8px;">🟡 <strong>Zapper</strong></td><td style="padding: 5px 8px;">Portfolio tracker, DeFi positions, yields</td><td style="padding: 5px 8px;"><a href="https://zapper.xyz/account/{_safe(data.get('wallet_address', ''))}?tab=apps" target="_blank" style="color: #2563eb;">Open →</a></td></tr>
                        <tr style="background: #fffef0;"><td style="padding: 5px 8px;">🟡 <strong>DeBank</strong></td><td style="padding: 5px 8px;">Multi-chain portfolio, protocol breakdown</td><td style="padding: 5px 8px;"><a href="https://debank.com/profile/{_safe(data.get('wallet_address', ''))}" target="_blank" style="color: #2563eb;">Open →</a></td></tr>
                        <tr><td style="padding: 5px 8px;">🔵 <strong>Uniswap App</strong></td><td style="padding: 5px 8px;">Official interface — manage, collect fees, rebalance</td><td style="padding: 5px 8px;"><a href="https://app.uniswap.org/positions/v3/{net.lower()}/{_safe(str(data.get('position_id', '')))}" target="_blank" style="color: #2563eb;">Open →</a></td></tr>
                    </tbody>
                </table>
                <p style="font-size: 0.8rem; color: #92400e; margin-bottom: 0; margin-top: 0.75rem;">
                    ⚠️ <strong>Note:</strong> Dashboard values may differ slightly due to caching, data freshness, and fee computation methods.
                    Our tool reads on-chain data in real-time via <code>eth_call</code> — the most accurate method available.
                </p>
            </div>
            
            <h3>📋 Data Schema & Sources:</h3>
            <div class="metric-grid">
                <div class="metric-card">
                    <div><strong>DEXScreener API Schema:</strong></div>
                    <div style="font-size: 0.875rem;">
                        • <code>priceUsd</code>: Current USD price<br>
                        • <code>volume.h24</code>: Volume 24h<br>
                        • <code>liquidity.usd</code>: Pool TVL<br>
                        • <code>txns.h24</code>: Transactions 24h<br>
                        • <code>pairCreatedAt</code>: Creation date
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Uniswap V3 Formulas:</strong></div>
                    <div style="font-size: 0.875rem;">
                        • Tick ↔ Price: <code>p(i) = 1.0001^i</code><br>
                        • Liquidity: <code>L = Δx√(Pa·Pb)/(√Pb-√Pa)</code><br>
                        • IL: <code>2√(r)/(1+r) - 1</code><br>
                        • Capital Efficiency: <code>1/(1-√(Pa/Pb))</code>
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Blockchain Endpoints:</strong></div>
                    <div style="font-size: 0.875rem;">
                        • <strong>{net}:</strong> Official RPC<br>
                        • <strong>Explorer:</strong> {_explorer(net.lower()).get('name', 'Scanner')}<br>
                        • <strong>Graph Protocol:</strong> On-chain indexing<br>
                        • <strong>IPFS:</strong> Decentralized metadata
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Data Validation:</strong></div>
                    <div style="font-size: 0.875rem;">
                        • Addresses: Regex hex validation<br>
                        • Prices: Multi-source cross-check<br>
                        • Ranges: Boundary math validation<br>
                        • Fees: Historical fee tracking
                    </div>
                </div>
            </div>
            
            <h3>🏗️ Technical Architecture:</h3>
            <div class="metric-grid">
                <div class="metric-card">
                    <div><strong>Pool Address:</strong></div>
                    <div style="font-family: monospace; word-break: break-all; font-size: 0.875rem;">{pool_addr}</div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Token0 ({t0}):</strong></div>
                    <div>{t0_info} • Decimals: 18<br>ERC-20 Standard</div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Token1 ({t1}):</strong></div>
                    <div>{t1_info} • Decimals: 6/18<br>ERC-20 Standard</div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Fee Tier:</strong></div>
                    <div>{data.get('fee_tier_label', safe_num(data.get('fee_tier', 3000)))} • Protocol Fee Split<br>LP Fee Distribution</div>
                </div>
            </div>
            
            <h3>🔗 Official APIs & Contract Integrations:</h3>
            <div style="background: #f8fafc; border: 1px solid var(--border); border-radius: 8px; padding: 1rem; margin: 1rem 0;">
                <h4>📊 DEXScreener API (Pool Market Data)</h4>
                <ul style="margin: 0.5rem 0; font-size: 0.875rem;">
                    <li><strong>Endpoint:</strong> <code>https://api.dexscreener.com/latest/dex/pairs/&#123;chainId&#125;/&#123;pairAddress&#125;</code></li>
                    <li><strong>Rate Limit:</strong> 300 requests/min (<a href="https://docs.dexscreener.com/api/reference" target="_blank">officially documented</a>)</li>
                    <li><strong>Authentication:</strong> Public (no API key required)</li>
                    <li><strong>Data Used:</strong> <code>volume.h24</code>, <code>liquidity.usd</code>, <code>priceUsd</code>, <code>txns.h24</code></li>
                    <li><strong>Limitation:</strong> Volume is a 24h snapshot — may not represent average daily volume</li>
                </ul>
                
                <h4>⛓️ On-Chain RPC — Direct Contract Reads (Most Accurate)</h4>
                <ul style="margin: 0.5rem 0; font-size: 0.875rem;">
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
                
                <h4>🦄 Uniswap V3 Core — Mathematical References</h4>
                <ul style="margin: 0.5rem 0; font-size: 0.875rem;">
                    <li><strong>Whitepaper:</strong> <a href="https://uniswap.org/whitepaper-v3.pdf" target="_blank">uniswap.org/whitepaper-v3.pdf</a> — §2 Concentrated Liquidity, §6.1-6.3 Tick Math</li>
                    <li><strong>SDK Source:</strong> <a href="https://github.com/Uniswap/v3-sdk" target="_blank">github.com/Uniswap/v3-sdk</a> — reference implementation</li>
                    <li><strong>Deployments:</strong> <a href="https://docs.uniswap.org/contracts/v3/reference/deployments/" target="_blank">docs.uniswap.org/contracts/v3/reference/deployments</a></li>
                    {'<li><strong>Your Position:</strong> <a href="https://app.uniswap.org/positions/v3/{}/{}" target="_blank">app.uniswap.org/positions/v3/{}/{}</a></li>'.format(net.lower(), data.get('position_id', ''), net.lower(), data.get('position_id', '')) if data.get('position_id') else ''}
                    <li><strong>Pool:</strong> <a href="https://app.uniswap.org/explore/pools/{net.lower()}/{pool_addr}" target="_blank">app.uniswap.org/explore/pools/{pool_addr[:16]}…</a></li>
                </ul>
            </div>
            
            <h3>🔄 Detailed Calculation Methodology:</h3>
            <div class="metric-card">
                <div style="font-size: 0.875rem; line-height: 1.6;">
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
                        <li><strong>Divergence loss:</strong> Not computed (requires historical mint event indexing)</li>
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
            
            <div class="consent-info">
                <div style="font-size: 1.3rem; margin-bottom: 0.5rem;">✅ <strong style="font-size: 1.05rem;">CONSENT RECORDED</strong></div>
                <div style="margin-bottom: 0.25rem;"><strong>User Agreement:</strong> Legal disclaimer accepted on <strong>{consent_ts}</strong></div>
                <div><strong>🔒 Compliance:</strong> Educational report per DeFi regulations</div>
            </div>
        </div>

        <!-- ═══════════════════ AUDIT TRAIL ═══════════════════ -->
        {_build_audit_trail(data)}

        <!-- ═══════════════════ SESSION 5: LEGAL COMPLIANCE ═══════════════════ -->
        <div class="session">
            <h2 class="session-title">⚖️ Session 5: Legal Compliance</h2>
            
            <div style="background: #fef2f2; border: 2px solid #dc2626; border-radius: 12px; padding: 2rem; margin: 2rem 0;">
                <h3 style="color: #991b1b; margin-top: 0;">🚨 MANDATORY DISCLAIMER</h3>
                <div style="color: #991b1b; font-weight: 600; line-height: 1.8;">
                    <p><strong>This tool performs EXCLUSIVELY EDUCATIONAL analysis of DeFi pools.</strong></p>
                    <p><strong>This is NOT financial, investment, tax, or legal advice.</strong></p>
                    <p><strong>Strategy comparisons in this report are HYPOTHETICAL mathematical examples — NOT investment recommendations.</strong></p>
                    
                    <div style="background: #fecaca; padding: 1rem; border-radius: 8px; margin: 1rem 0;">
                        <h4 style="margin-top: 0;">⚠️ INHERENT RISKS OF DeFi PROTOCOLS:</h4>
                        <ul style="margin-bottom: 0;">
                            <li><strong>Total Loss:</strong> DeFi protocols can result in total loss of deposited funds</li>
                            <li><strong>Impermanent Loss:</strong> Losses can significantly exceed displayed estimates</li>
                            <li><strong>Smart Contract Risk:</strong> Exploits and vulnerabilities may occur without warning</li>
                            <li><strong>Volatility:</strong> Crypto markets are extremely volatile and unpredictable</li>
                            <li><strong>Estimates Only:</strong> All calculations are estimates that may diverge from reality</li>
                            <li><strong>Projections:</strong> Daily/monthly earning projections assume constant pool volume and in-range status — not guaranteed</li>
                            <li><strong>No Recommendation:</strong> Strategy comparisons are mathematical examples, not advice to rebalance or reposition</li>
                        </ul>
                    </div>
                    
                    <p><strong style="font-size: 1.1rem;">⚖️ LEGAL RESPONSIBILITY:</strong></p>
                    <p>The developer assumes <strong>NO RESPONSIBILITY</strong> for losses, direct, indirect, incidental or consequential damages arising from the use of this tool.</p>
                </div>
            </div>
            
            <h3>📚 Legal Structure & Compliance:</h3>
            <div class="metric-grid">
                <div class="metric-card">
                    <div><strong>Licensing:</strong></div>
                    <div style="font-size: 0.875rem;">
                        • <strong>License:</strong> MIT License<br>
                        • <strong>Open Source:</strong> Public GitHub<br>
                        • <strong>Audit:</strong> Code available for inspection<br>
                        • <strong>Distribution:</strong> Free for educational use
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Jurisdiction & Compliance:</strong></div>
                    <div style="font-size: 0.875rem;">
                        • <strong>US/SEC:</strong> Educational tool, not a security<br>
                        • <strong>BR/CVM:</strong> Not authorized advisory<br>
                        • <strong>EU/MiCA:</strong> Crypto regulation compliance<br>
                        • <strong>Disclaimer:</strong> Mandatory legal disclaimers
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Appropriate Use:</strong></div>
                    <div style="font-size: 0.875rem;">
                        • <strong>Purpose:</strong> Educational only<br>
                        • <strong>Audience:</strong> Developers, researchers<br>
                        • <strong>Limitation:</strong> Not for financial decisions<br>
                        • <strong>Validation:</strong> Always verify data independently
                    </div>
                </div>
                
                <div class="metric-card">
                    <div><strong>Documented Consent:</strong></div>
                    <div style="font-size: 0.875rem;">
                        • <strong>Timestamp:</strong> {consent_ts}<br>
                        • <strong>Action:</strong> User typed "I agree"<br>
                        • <strong>IP:</strong> [Not recorded for privacy]<br>
                        • <strong>Valid:</strong> Current session only
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
                    <div>• <a href="{_explorer(net.lower()).get('base', '#')}" target="_blank" style="color: #2563eb;">{_explorer(net.lower()).get('name', 'Blockchain')} Explorer</a></div>
                    <div>• <a href="https://github.com" target="_blank" style="color: #2563eb;">Open Source Repository</a></div>
                </div>
                
                <h4 style="color: #15803d;">💡 Scientific Research</h4>
                <div class="metric-grid" style="gap: 0.5rem;">
                    <div>• <a href="https://pintail.medium.com/uniswap-a-good-deal-for-liquidity-providers-104c0b6816f2" target="_blank" style="color: #2563eb;">Pintail Research - Impermanent Loss</a></div>
                    <div>• <a href="https://web.archive.org/web/20230000000000*/uniswapv3book.com" target="_blank" style="color: #2563eb;">Uniswap V3 Development Book</a></div>
                    <div>• <a href="https://arxiv.org/search/?query=automated+market+makers" target="_blank" style="color: #2563eb;">Academic Papers on AMMs</a></div>
                </div>
            </div>
            
            <h3>💰 Development Support (Optional):</h3>
            <div style="background: #fffbeb; border: 1px solid #fbbf24; border-radius: 8px; padding: 1rem; margin: 1rem 0;">
                <p style="margin-top: 0; font-size: 0.875rem;"><strong>🎯 Voluntary Contributions:</strong> If this educational tool was useful, consider supporting continued development.</p>
                
                <div class="metric-grid">
                    <div class="metric-card" style="background: white;">
                        <div><strong>Bitcoin (BTC):</strong></div>
                        <div style="font-family: monospace; font-size: 0.8rem; word-break: break-all;">
                            {BTC_DONATION}
                        </div>
                    </div>
                    
                    <div class="metric-card" style="background: white;">
                        <div><strong>Ethereum/EVM:</strong></div>
                        <div style="font-family: monospace; font-size: 0.8rem; word-break: break-all;">
                            {ETH_DONATION}
                        </div>
                    </div>
                </div>
                
                <p style="font-size: 0.8rem; color: #78350f; margin-bottom: 0;">
                    <strong>⚖️ Legal Notice:</strong> Donations are 100% voluntary and do not constitute investment, service purchase, or equity. 
                    The tool remains free regardless. See full terms in source code.
                </p>
            </div>
        </div>

        <!-- ═══════════════════ FOOTER ═══════════════════ -->
        <div class="footer">
            <p><strong>DeFi CLI v1.0.0</strong> · Report generated on {generated}</p>
            <p>Sources: Uniswap V3 Whitepaper, DEXScreener API</p>
            <p style="font-size: 0.875rem; color: var(--text-light);">
                This report was generated for educational purposes. Always verify data independently.
            </p>
        </div>
    </div>
</body>
</html>"""


def generate_position_report(data: Dict, output_dir: Optional[Path] = None) -> Path:
    """Generate HTML report from position analysis data."""
    if output_dir is None:
        output_dir = REPORTS_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Generate filename
    t0 = _safe_filename(data.get("token0_symbol", "TOKEN0"))
    t1 = _safe_filename(data.get("token1_symbol", "TOKEN1"))
    network = _safe_filename(data.get("network", "ethereum"))
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{t0}_{t1}_{network}_{timestamp}.html"
    
    filepath = output_dir / filename
    html_content = _build_html(data)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    return filepath


# Test function for CLI usage
def main():
    """Test function: generate a sample report from a live pool.

    Usage:
        python html_generator.py <pool_address>
    """
    import sys
    import asyncio
    from real_defi_math import PositionData, analyze_position
    from defi_cli.dexscreener_client import analyze_pool_real

    address = sys.argv[1] if len(sys.argv) > 1 else None
    if not address:
        print("Usage: python html_generator.py <pool_address>")
        sys.exit(1)

    async def _generate():
        print(f"Fetching pool data for {address[:16]}...")
        result = await analyze_pool_real(address)
        if result["status"] != "success":
            print(f"❌ {result['message']}")
            return
        pos = PositionData.from_pool_data(result["data"])
        path = generate_position_report(analyze_position(pos))
        print(f"✅ {path}")

    asyncio.run(_generate())


if __name__ == "__main__":
    main()