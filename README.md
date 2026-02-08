# DeFi CLI

<p>
<a href="https://github.com/fabiotreze/defi-cli/actions/workflows/ci.yml"><img src="https://github.com/fabiotreze/defi-cli/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-≥3.10-3776AB?logo=python&logoColor=white" alt="Python"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green" alt="License"></a>
<a href="CHANGELOG.md"><img src="https://img.shields.io/badge/version-1.1.1-blue" alt="Version"></a>
<a href="SECURITY.md"><img src="https://img.shields.io/badge/security-T09%20%7C%20T23%20%7C%20T25-blueviolet" alt="Security"></a>
</p>

**Educational** multi-DEX V3 concentrated-liquidity analyzer.  
Supports **Uniswap V3** 🦄, **PancakeSwap V3** 🥞, and **SushiSwap V3** 🍣.  
Reads real on-chain data, generates HTML reports, and performs risk analysis.

> ⚠️ **Not financial advice.** DeFi = **HIGH RISK** including **total loss of capital**. Use at your own risk. DYOR.

---

## Install

**macOS / Linux**

```bash
git clone https://github.com/fabiotreze/defi-cli.git
cd defi-cli
python3 -m venv defi_env && source defi_env/bin/activate
pip install -r requirements.txt && pip install -e .
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/fabiotreze/defi-cli.git
cd defi-cli
python -m venv defi_env; defi_env\Scripts\activate
pip install -r requirements.txt; pip install -e .
```

---

## Commands

> **Tip:** Run `python run.py --help` to see all available commands, options, and examples.

### `report` — Generate HTML Report

```bash
python run.py report \
  --pool <POOL_ADDRESS> \
  --position <POSITION_ID> \
  --wallet <WALLET_ADDRESS> \
  --network <NETWORK> \
  --dex <DEX>
```

| Parameter | Required For | Without It |
|-----------|-------------|------------|
| `--pool` | Target pool | Required (or auto-detected from `--position`) |
| `--position` | Real on-chain data + audit trail | Simulated data |
| `--wallet` | Cross-validation links (Revert, Zerion, DeBank) | Links won't work |
| `--network` | Correct RPC + explorer links | Defaults to `arbitrum` |
| `--dex` | Non-Uniswap positions | Defaults to `uniswap_v3` |

### `list` — Scan Wallet for V3 Positions

```bash
python run.py list <WALLET_ADDRESS> --network <NETWORK> --dex <DEX>
```

### `pool` — Analyze Any Pool

```bash
python run.py pool --pool <POOL_ADDRESS>
```

### `scout` — Compare Pools for a Token Pair

```bash
python run.py scout <PAIR> --network <NETWORK> --dex <DEX> --sort <apy|tvl|volume|efficiency>
```

### `check` · `info`

| Command | Description |
|---------|-------------|
| `python run.py check` | Integration tests against live pools |
| `python run.py info` | System info + supported DEXes |

---

## Full Example — Best Experience

> **All parameters = full report with real on-chain data, audit trail, and cross-validation links.**

```bash
python run.py report \
  --pool 0x641C00A822e8b671738d32a431a4Fb6074E5c79d \
  --position 5260106 \
  --wallet 0x4819A678A5Ba46A5108765FE3db9Ab522543F3d4 \
  --network arbitrum \
  --dex uniswap_v3
```

```bash
python run.py list 0x4819A678A5Ba46A5108765FE3db9Ab522543F3d4 --network arbitrum
```

```bash
python run.py scout WETH/USDT --network arbitrum --sort apy --limit 5
```

### How to Find Your Position ID

1. [app.uniswap.org](https://app.uniswap.org) → **Pool** → click your position  
2. URL: `/positions/v3/<network>/<position_id>`  
3. Pool link (e.g. "WETH/USDT 0.05%") → contains the pool address  

---

## Parameters

| Parameter | Values | Default |
|-----------|--------|---------|
| `--network` | `arbitrum` · `ethereum` · `polygon` · `base` · `optimism` · `bsc` | `arbitrum` |
| `--dex` | `uniswap_v3` · `pancakeswap_v3` · `sushiswap_v3` | `uniswap_v3` |
| `--sort` | `apy` · `tvl` · `volume` · `efficiency` | `apy` |
| `--limit` | Integer | `15` |
| `--min-tvl` | USD (e.g. `50000`) | `50000` |

---

## Supported Networks & DEXes

| DEX | Networks | Position Manager |
|-----|----------|-----------------|
| 🦄 Uniswap V3 | ETH, ARB, POLY, BASE, OP | `0xC364…FE88` (Base: `0x03a5…4f1`) |
| 🥞 PancakeSwap V3 | ETH, BSC, ARB, BASE | `0x46A1…4364` (ARB: `0x427b…96c1`) |
| 🍣 SushiSwap V3 | ETH, ARB, POLY, BASE, OP | Per-chain ([dex_registry.py](defi_cli/dex_registry.py)) |

All RPC calls go through [1RPC.io](https://docs.1rpc.io/web3-relay/overview) — privacy-preserving TEE relay (no API keys, no tracking).

| Network | RPC | Explorer |
|---------|-----|----------|
| Arbitrum | `1rpc.io/arb` | [arbiscan.io](https://arbiscan.io) |
| Ethereum | `1rpc.io/eth` | [etherscan.io](https://etherscan.io) |
| Polygon | `1rpc.io/matic` | [polygonscan.com](https://polygonscan.com) |
| Base | `1rpc.io/base` | [basescan.org](https://basescan.org) |
| Optimism | `1rpc.io/op` | [optimistic.etherscan.io](https://optimistic.etherscan.io) |
| BSC | `1rpc.io/bnb` | [bscscan.com](https://bscscan.com) |

Pool data via [DEXScreener API](https://docs.dexscreener.com/api/reference) — supports all DEXes on 50+ networks. **No API keys required.**

---

## Report Preview

<p align="center">
<a href="docs/screenshots/01_header.png"><img src="docs/screenshots/01_header.png" width="600"></a>
</p>

<details>
<summary><strong>View all report sections (6 more)</strong></summary>
<br>

| Section | Preview |
|---------|---------|
| Your Position | <a href="docs/screenshots/02_position.png"><img src="docs/screenshots/02_position.png" width="500"></a> |
| Pool Stats | <a href="docs/screenshots/03_pool_stats.png"><img src="docs/screenshots/03_pool_stats.png" width="500"></a> |
| Strategies & Risk | <a href="docs/screenshots/04_strategies.png"><img src="docs/screenshots/04_strategies.png" width="500"></a> |
| Technical Details | <a href="docs/screenshots/05_technical.png"><img src="docs/screenshots/05_technical.png" width="500"></a> |
| Audit Trail | <a href="docs/screenshots/06_audit_trail.png"><img src="docs/screenshots/06_audit_trail.png" width="500"></a> |
| Legal Compliance | <a href="docs/screenshots/07_legal.png"><img src="docs/screenshots/07_legal.png" width="500"></a> |

</details>

Reports are **temporary by design** — opened in your browser, then discarded. Press **Ctrl+S** / **⌘+S** to save.

---

## Known Limitations

| Limitation | Impact |
|-----------|--------|
| **IL not calculated** | Fee APR ≠ Total PnL — use [Revert.finance](https://revert.finance) for real PnL |
| **24h snapshot** | Projections may differ 20–30% from actual averages |
| **No historical data** | Cross-validate with [Revert](https://revert.finance), [Zerion](https://zerion.io), [DeBank](https://debank.com) |
| **Mathematical examples** | Strategies are formulas, not investment recommendations |

---

## Data Sources

| Source | Provides | Docs |
|--------|----------|------|
| Uniswap V3 Contracts | Position data, prices, fees | [Whitepaper](https://uniswap.org/whitepaper-v3.pdf) |
| PancakeSwap V3 Contracts | Position data (same ABI) | [Addresses](https://developer.pancakeswap.finance/contracts/v3/addresses) |
| SushiSwap V3 Contracts | Position data (same ABI) | [Addresses](https://docs.sushi.com/docs/Products/V3%20AMM/Periphery/Deployment%20Addresses) |
| DEXScreener API | Pool metrics, volume, TVL | [API Docs](https://docs.dexscreener.com/api/reference) |
| 1RPC.io TEE Relay | Privacy-preserving RPC | [Docs](https://docs.1rpc.io/web3-relay/overview) |

---

## Testing

```bash
pip install pytest
python -m pytest tests/ -v --tb=short
```

> `pytest` is a dev-only dependency. The command above runs all 292 tests.

| Suite | Tests | Scope |
|-------|-------|-------|
| `test_math.py` | 83 | V3 math formulas, metrics, edge cases |
| `test_units.py` | 195 | CLI commands, HTML output, mocked integration |
| `test_codereview.py` | 14 | Code quality + 10 live network checks |

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Python | ≥ 3.10 | Runtime |
| httpx | ≥ 0.25.0 | HTTP client (API + JSON-RPC) |
| pytest | ≥ 8.0 | Testing (dev only) |

| OS | Python | Status |
|----|--------|--------|
| macOS Sequoia 15.3 (ARM64) | 3.14 | ✅ |
| Windows 11 (x64) | 3.11 | ✅ |
| Ubuntu 24.04 (x64) | 3.12 | ✅ |

---

## Uninstall

**macOS / Linux**

```bash
deactivate && cd .. && rm -rf defi-cli/
```

**Windows (PowerShell)**

```powershell
deactivate; cd ..; Remove-Item -Recurse -Force defi-cli\
```

> **Zero residue.** Everything lives inside the project folder — nothing touches your system.

---

## Legal

**MIT License** ([LICENSE](LICENSE)) · Not financial advice · No warranty · No liability  
See [SECURITY.md](SECURITY.md) · [COMPLIANCE.md](COMPLIANCE.md)

---

## Support

If you find this tool useful, consider giving it a ⭐ on GitHub!
