# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

---

## [1.1.1] — 2026-02-07

### Added
- **24 automated codereview checks** (T01–T24) — expanded from 20
  - T21: Requirements validation (dependencies importable, version constraints)
  - T22: Modularity check (no circular imports, proper package isolation)
  - T23: Vulnerability scan (eval/exec/pickle, HTTPS-only, minimal deps)
  - T24: File integrity (all 25 expected files present, stale files removed)
- `defi_cli/rpc_helpers.py` — shared ABI encoding/decoding and JSON-RPC client (extracted from 2 files)
- `defi_cli/stablecoins.py` — stablecoin detection, pair classification, fee tier estimation
- `defi_cli/html_styles.py` — CSS extracted from html_generator.py for maintainability
- `defi_cli/commands.py` — CLI command handlers extracted from run.py
- `tests/test_units.py` — 195 unit tests covering all extracted modules
- `COMPLIANCE.md` — P1–P7 compliance priority framework
- `.codereview.md` — 50-category audit checklist with 5-phase execution procedure

### Changed
- **RPC helpers consolidated** — position_reader.py and position_indexer.py now import from shared `rpc_helpers.py` (was ~200 lines duplicated)
- **Screenshots updated** — 7 report screenshots regenerated at 1200px with current Arbitrum position data (WETH/USDT, $768.49)
- Test count: 292 total (83 unit + 195 integration + 14 codereview)
- SECURITY.md version reference updated to v1.1.1
- `cmd_info()` version label: "New in v1.1.0" → "New in v1.1.x"

### Fixed
- HTML report footer showed "v1.1.0" instead of "v1.1.1" (hardcoded)
- Docstring example in `estimate_fee_tier("WETH","USDC")` returned wrong value (0.003 → 0.0005)
- Unused import `DEX_REGISTRY` in position_reader.py
- Unused import `Optional` in html_generator.py
- Stale `.github/workflows/` directory removed (user manages CI separately)

---

## [1.1.0] — 2026-02-07

### Added
- **Multi-DEX Support**: PancakeSwap V3 and SushiSwap V3 alongside Uniswap V3
- **Pool Scout**: Search and compare V3 pools across DEXes via DefiLlama Yields API
- **Wallet Scanner** (`list` command): Discover all V3 positions across multiple DEXes
- **Auto Pool Detection**: Resolve pool address from position NFT via Factory.getPool()
- **V3 Impermanent Loss**: Boundary IL estimates with V3 amplification (IL_v3 = IL_v2 × CE)
- **Range Width %**: Range width as percentage of current price
- **Vol/TVL Ratio**: Capital efficiency indicator with color-coded progress bar
- **HODL Comparison**: Fees vs IL at range boundaries (net P&L snapshot)
- **DEX Registry**: Centralized contract address management per DEX per network
- **On-Chain Verification**: Full audit trail with raw calldata, block number, and reproducible curl commands
- **BSC network support** in RPC endpoints and DEX registry
- `.codereview.md` — 50-category audit checklist with automated test definitions

### Changed
- **CLI parameters aligned with on-chain documentation** — positional `address` renamed to `--pool` (named parameter). Matches Uniswap V3 `Factory.getPool()` and DEXScreener `pairAddress` conventions. `--position` help text now references `tokenId (uint256)` per NonfungiblePositionManager spec.
- **RPC endpoints migrated to 1RPC.io** — TEE-attested privacy relay (zero-tracking, metadata masking, random dispatching). Docs: https://docs.1rpc.io
- **Reports are now temporary only** — opened in browser, never saved to disk. User saves from browser (Ctrl+S) if desired. Privacy by design: no persistence, no cookies, no retention.
- **Auto-detect network** — `--network` is now optional. When only `--position` is given, all 6 networks are scanned in parallel to find the position.
- **SECURITY.md expanded** — full data transparency section: every external endpoint documented, LGPD/GDPR compliance, third-party services matrix, privacy guarantees
- CLI commands restructured: `list`, `scout`, `pool`, `report`, `check`, `info`, `donate`
- HTML report now includes V3 IL tile, HODL comparison tile, Vol/TVL progress bar
- Strategy projections scale relative to current position's capital efficiency
- Position APR computed from on-chain liquidity share (most accurate method)
- All Portuguese text translated to English

### Removed
- `AUDIT_REPORT.md`, `TEST_REPORT.md`, `API_MAP.md` (stale point-in-time snapshots)
- Unused code: `ComplianceInfo` class, `compare_with_position()`, dead constants

### Fixed
- HTML dict-in-f-string bug in HODL comparison tile
- Test naming conflict (`test_t01_*` → `_t01_*`) preventing pytest fixture errors

---

## [1.0.0] — 2026-02-06

### Initial Release

**Core Features**
- Uniswap V3 concentrated-liquidity position analyzer
- On-chain data reading via Ethereum JSON-RPC (no API keys required)
- DEXScreener API integration for real-time pool data
- Comprehensive HTML report generation with 5 structured sessions
- 65 unit tests covering core mathematical formulas

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
- `pool --pool <0x…>` — Analyze any pool via DEXScreener
- `report --pool <0x…>` — Generate HTML report (simulated or real position)
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
- Legal disclaimers embedded in CLI and HTML reports

---

_For future releases, new entries will be added above this line._
