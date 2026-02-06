# Security Policy

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
- **Filename sanitization** — report filenames stripped to `[a-zA-Z0-9_-]` only (path traversal prevention)

### Output Security
- **XSS prevention** — all user-supplied data is HTML-escaped via `_safe()` (entity encoding for `& < > " '`) before embedding in reports
- **JavaScript sanitization** — all numeric values in `<script>` blocks use `safe_num()` to guarantee fixed-format output
- **Content Security Policy** — `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src data:;">` blocks external resource loading in reports
- **No dynamic code** — no `eval()`, `exec()`, `os.system()`, or `subprocess` calls anywhere

### Transport
- **HTTPS only** — all external requests use HTTPS to `api.dexscreener.com`
- **No secrets** — no API keys, tokens, or credentials stored or transmitted

### Rate Limiting
- Respects DEXScreener API limits: 300 req/min (pairs), 60 req/min (general)
- Built-in 0.3s delay between requests during integration checks

## Dependencies

| Package | Purpose | Risk |
|---------|---------|------|
| `httpx` | Async HTTP client for DEXScreener API | Low — well-maintained, no native extensions |

All other imports are Python standard library (`math`, `asyncio`, `pathlib`, `argparse`, `dataclasses`, `html`, `re`).

## Data Flow

```
User CLI input → hex validate → DEXScreener API (HTTPS) → parse JSON → local math → HTML escape → file
```

No user data leaves the machine. Reports are saved locally to `./reports/`.

## Architecture (v1.0.0)

```
run.py                     CLI entry point (5 commands: pool, report, check, donate, info)
real_defi_math.py          Uniswap V3 math (stdlib only, no network calls)
html_generator.py          HTML reports (XSS-safe, CSP headers)
position_reader.py         On-chain reader via public JSON-RPC (no API key)
defi_cli/
├── central_config.py      API config (endpoints, chains, rate limits)
├── dexscreener_client.py  Async HTTP client (httpx)
└── legal_disclaimers.py   Legal text, donation addresses
```