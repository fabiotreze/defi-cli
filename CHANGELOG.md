# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

---

## [1.0.0] — 2026-02-06

### Initial Release

**Core Features**
- Uniswap V3 concentrated-liquidity position analyzer
- On-chain data reading via Ethereum JSON-RPC (no API keys required)
- DEXScreener API integration for real-time pool data
- Comprehensive HTML report generation with 5 structured sessions
- 65 unit tests covering all mathematical formulas

**Analysis Capabilities**
- Impermanent Loss calculation (V3 concentrated liquidity formula)
- Capital Efficiency ratio (vs. full-range V2)
- Fee APR projections with volatility scaling
- Range proximity analysis (in-range / out-of-range detection)
- 3 strategy suggestions (Conservative, Moderate, Aggressive)
- Risk classification based on range width

**Supported Networks**
- Ethereum, Arbitrum, Base, Polygon, Optimism

**CLI Commands**
- `pool <address>` — Analyze any pool via DEXScreener
- `report <address>` — Generate HTML report (simulated or real position)
- `check` — Validate app against live Uniswap pools
- `info` — System & architecture overview
- `donate` — Show donation addresses

**Technical Stack**
- Python ≥ 3.10 (stdlib + httpx only)
- Zero API keys required
- 100% local execution — no data leaves the machine
- Tested on macOS (ARM64) and Windows 11 (x64)

**Documentation**
- README with Quick Start, Known Limitations, and full CLI reference
- SECURITY.md — Security policy and architecture overview
- AUDIT_REPORT.md — 101-check comprehensive audit (all passed)
- TEST_REPORT.md — Full end-to-end test results
- Legal disclaimers embedded in CLI and HTML reports

---

_For future releases, new entries will be added above this line._
