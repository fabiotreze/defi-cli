# Security Policy

> For the full compliance framework (P1–P7 priority hierarchy, regulatory matrix,
> consent matrix, data flow diagram), see [`COMPLIANCE.md`](COMPLIANCE.md).

## Scope

DeFi CLI is a **read-only, educational** tool. It does not:

- Handle, store, or transmit private keys
- Manage or custody any funds
- Execute on-chain transactions
- Require authentication or KYC

It **only** reads public blockchain data and performs mathematical calculations locally.

## Reporting a Vulnerability

If you discover a security issue, please open a GitHub Issue at:

https://github.com/fabiotreze/defi-cli/issues

For sensitive disclosures, include `[SECURITY]` in the title.

## Security Measures

### Input Validation
- **Hex address validation** — regex `0x[0-9a-fA-F]{40}` enforced before any API call
- **EIP-55 checksum validation** — mixed-case addresses verified against EIP-55 checksum to detect typos (CWE-20)
- **Filename sanitization** — report filenames stripped to `[a-zA-Z0-9_-]` only (path traversal prevention)
- **Tick bounds clamping** — Uniswap V3 tick values clamped to [-887272, +887272] to prevent math overflow (CWE-682)

### Output Security
- **XSS prevention** — all user-supplied data is escaped via `html.escape()` (stdlib) in `_safe()` before embedding in reports (CWE-79)
- **JavaScript sanitization** — all numeric values in `<script>` blocks use `safe_num()` to guarantee fixed-format output
- **Nonce-based CSP** — `script-src 'nonce-<random>'` with cryptographic nonce per report; `frame-ancestors 'none'`; `X-Content-Type-Options: nosniff`; `Referrer-Policy: no-referrer` (CWE-79)
- **No dynamic code** — no `eval()`, `exec()`, `os.system()`, or `subprocess` calls anywhere
- **Error sanitization** — all user-facing error messages stripped of internal paths, stack traces, and implementation details (CWE-209)

### Privacy & Data Minimization (LGPD Art. 6 III)
- **Wallet masking** — wallet addresses displayed as `0xAbCd…EfGh` in CLI output (CWE-532)
- **RPC URL masking** — private RPC URLs with API keys masked in HTML reports (CWE-200)
- **Temp file cleanup** — all report files registered for automatic deletion on process exit via `atexit` (CWE-459)
- **Secure temp permissions** — report files created with `0o600` (owner read/write only) (CWE-377)

### Transport
- **HTTPS only** — all external requests use HTTPS
- **RPC privacy** — all blockchain reads via 1RPC.io TEE relay (zero-tracking, metadata masking)
- **No secrets** — no API keys, tokens, or credentials stored or transmitted

### Rate Limiting
- **Client-side rate limiter** — token-bucket limiter enforced on DEXScreener API calls (250 req/min, safety margin under 300 limit) (CWE-770)
- Respects DEXScreener API limits: 300 req/min (pairs), 60 req/min (general)
- Built-in 0.3s delay between requests during integration checks

## Dependencies

| Package | Purpose | Risk |
|---------|---------|------|
| `httpx` | Async HTTP client for DEXScreener API | Low — well-maintained, no native extensions |

All other imports are Python standard library (`math`, `asyncio`, `pathlib`, `argparse`, `dataclasses`, `html`, `re`).

## Data Flow

```
User CLI input → hex validate → 1RPC.io (TEE) → blockchain / DEXScreener API (HTTPS) → parse JSON → local math → HTML escape → temp file → browser → discarded
```

Reports are opened as temporary files in the browser. **Nothing is saved to disk.**
Financial data in reports is ephemeral by default — the user must explicitly save from the browser (Ctrl+S) if desired.

## Privacy & Data Transparency

### What leaves your machine

| # | Destination | Data Sent | Purpose | Privacy |
|---|-------------|-----------|---------|---------|
| 1 | **1RPC.io** (TEE relay) → Arbitrum/ETH/Polygon/Base/OP/BSC RPC | Contract addresses, position NFT IDs, wallet address (only in `list` command) | Read on-chain state (positions, prices, fees) | TEE-attested: zero-tracking, metadata masking, random dispatching |
| 2 | **DEXScreener API** (`api.dexscreener.com`) | Pool/token contract address (**no wallet**) | Pool market data (volume, TVL, price) | IP + pool address only |
| 3 | **DefiLlama API** (`yields.llama.fi`) | **Nothing user-specific** (plain GET request) | Pool comparison data (Scout) | IP only |

### What stays on your machine

- All mathematical calculations (Uniswap V3 formulas, IL, APR, fee projections)
- Generated HTML reports (temporary, opened in browser — user saves manually if desired)
- No databases, no caches, no cookies, no persistent state files
- No logging framework — only `print()` for CLI output (not persisted)

### What we do NOT do

| Check | Status |
|-------|--------|
| Telemetry / Analytics | ✅ None |
| Private key access | ✅ Never requested or transmitted |
| User-Agent fingerprinting | ✅ Default httpx User-Agent only |
| Tracking pixels in reports | ✅ None |
| External JS/CSS/fonts in reports | ✅ None — fully self-contained, CSP enforced |
| Phone-home behavior | ✅ None |
| Persistent identifiers | ✅ None |

### RPC Privacy (1RPC.io by Automata Network)

All blockchain reads are routed through [1RPC.io](https://1rpc.io), a TEE-attested relay:

- **Zero tracking** — user metadata is not retained after relay (burn after relaying)
- **Metadata masking** — your IP/device info replaced with 1RPC's own
- **Random dispatching** — requests dispatched randomly to break wallet linkage
- **TEE attested** — relay runs inside a Trusted Execution Environment, [verifiable on-chain](https://github.com/automata-network/automata-dcap-attestation)
- **Free tier** — 10,000 req/day, no API key required
- **64+ networks** — covers all chains we support plus future expansion
- **Docs** — https://docs.1rpc.io/web3-relay/overview

### Third-Party Services

| Service | What They Receive | Docs | Free? | Rate Limit |
|---------|-------------------|------|-------|------------|
| [1RPC.io](https://1rpc.io) | Relayed RPC calls (TEE-protected) | [docs.1rpc.io](https://docs.1rpc.io/web3-relay/overview) | ✅ 10K req/day | 10,000/day |
| [DEXScreener](https://dexscreener.com) | Pool/token addresses (no wallet) | [docs.dexscreener.com](https://docs.dexscreener.com/api/reference) | ✅ No key | 300 req/min |
| [DefiLlama](https://defillama.com) | Nothing user-specific | [defillama.com/docs/api](https://defillama.com/docs/api) | ✅ No key | ~30 req/min |

### LGPD / GDPR Compliance

- **Data minimization** — only requests data strictly necessary for analysis
- **No personal data storage** — no database, no user profiles, no login
- **Right to erasure** — trivial: no remote data to erase
- **Consent mechanism** — explicit "I agree" prompt before report generation
- **Pseudonymous data** — wallet addresses are public on-chain data; tool does not link them to identity

## Architecture (v1.1.1)

```
run.py                     CLI entry point (6 commands: list, pool, report, check, info, scout)
real_defi_math.py          Uniswap V3 math (stdlib only, no network calls)
html_generator.py          HTML reports (XSS-safe, CSP headers)
position_reader.py         On-chain reader via public JSON-RPC (no API key)
position_indexer.py        Multi-DEX V3 position scanner (list command)
defi_cli/
├── central_config.py      API config (endpoints, networks, rate limits)
├── dex_registry.py        Multi-DEX contract address registry
├── dexscreener_client.py  Async HTTP client (httpx)
└── legal_disclaimers.py   Legal text, disclaimers
```

## CI/CD Security (T30)

The project uses GitHub Actions with the following security controls:

| Control | Implementation |
|---------|----------------|
| **Pinned Actions** | All third-party actions pinned by full SHA (not mutable tags) |
| **Least Privilege** | `permissions: contents: read` — no write access |
| **Concurrency** | `cancel-in-progress: true` — prevents resource abuse on stale runs |
| **Lint + Format** | `ruff check` + `ruff format --check` enforced on every push/PR |
| **Security Scans** | Hardcoded secrets (T09), dangerous functions (`eval`/`exec`/`pickle`), HTTPS-only URLs |
| **Test Matrix** | Python 3.10 / 3.11 / 3.12 — math, unit, and codereview tests |
| **Codereview Report** | Full T06–T30 validation suite uploaded as artifact (30-day retention) |

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml) for the full pipeline definition.