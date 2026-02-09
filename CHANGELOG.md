# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/).

---

## [1.1.1] — 2026-02-09

### Security
- **CWE-79**: Nonce-based Content-Security-Policy (`script-src 'nonce-…'`), `html.escape()` stdlib, `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`
- **CWE-20**: EIP-55 address checksum validation (sha3-256)
- **CWE-200**: RPC URL masking — API keys hidden in audit trail
- **CWE-209**: Error message sanitization — maps internal exception types to generic messages
- **CWE-377/459**: Temp files created with `0o600` permissions + cleanup registry (`cleanup_reports()` API, LGPD Art. 6 III)
- **CWE-532**: Wallet address masking in console output (`0xAbCd…EfGh`)
- **CWE-682**: Tick bounds clamping to `[-887272, +887272]` (Uniswap V3 limits)
- **CWE-770**: Token-bucket rate limiter (250 req/min) for DEXScreener API
- **10 new codereview tests** (T31–T40): CSP nonce, EIP-55, error sanitization, rate limiter, temp cleanup, RPC masking, wallet masking, tick bounds, html.escape, OWASP/CWE audit
- Test count: 307 total (83 math + 194 unit + 30 codereview)

### Added
- **CI/CD pipeline** (`.github/workflows/ci.yml`) — 3-job GitHub Actions workflow:
  - Lint & Security: ruff check + format, secrets scan, dangerous functions scan, HTTPS-only validation
  - Test Matrix: Python 3.10 / 3.11 / 3.12 with full offline test suite
  - Codereview Report: T06–T30 validation uploaded as 30-day artifact
  - T30 compliant: pinned SHA actions, least-privilege permissions, concurrency control
- **CI badge** + **Security badge** (T09|T23|T25) added to README
- **CI/CD Security section** added to SECURITY.md
- **30 automated codereview checks** (T01–T30) — expanded from 24
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
- Test count: 297 total (83 math + 194 unit + 20 codereview)
- SECURITY.md version reference updated to v1.1.1
- `cmd_info()` version label: "New in v1.1.0" → "New in v1.1.x"

- **Single-source version** — `pyproject.toml` is the sole source of truth; `central_config.py`, `__init__.py`, `html_generator.py`, and `run.py` derive version via `importlib.metadata` with pyproject.toml fallback
- **Automated release workflow** (`.github/workflows/release.yml`) — validates tag↔pyproject.toml version match, verifies CHANGELOG entry, runs full test suite + lint, creates GitHub Release with extracted notes

### Fixed
- HTML report footer showed "v1.1.0" instead of "v1.1.1" (hardcoded)
- Docstring example in `estimate_fee_tier("WETH","USDC")` returned wrong value (0.003 → 0.0005)
- Unused import `DEX_REGISTRY` in position_reader.py
- Unused import `Optional` in html_generator.py
- Ruff lint + format enforced: removed unused imports (F401), f-strings without placeholders (F541), unused variables (F841), ambiguous names (E741)
- `per-file-ignores` configured in `pyproject.toml` for intentional test patterns (E402, E702)

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
- CLI commands restructured: `list`, `scout`, `pool`, `report`, `check`, `info`
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
