# Compliance Framework — DeFi CLI

> Priority-ordered compliance framework for educational DeFi software.
> Every category maps to specific code, tests, and documentation.

---

## Priority Hierarchy (P1 → P7)

Ordered by **potential harm** — higher priority = greater damage if violated.

| Priority | Domain | Harm if Violated | Owner |
|----------|--------|-----------------|-------|
| **P1** | **Security** | Total loss of user funds, private key exposure | SECURITY.md, T09, T23 |
| **P2** | **Privacy & Data Protection** | Identity exposure, regulatory fines (LGPD/GDPR) | SECURITY.md §Privacy, T09, T17 |
| **P3** | **Informed Consent** | Developer civil liability, invalid waiver | commands.py, T19, T20 |
| **P4** | **Liability Disclaimer** | Lawsuits, financial claims against developer | LICENSE, legal_disclaimers.py, T19 |
| **P5** | **Data Accuracy** | User decisions based on incorrect calculations | real_defi_math.py, T05, T11-T14 |
| **P6** | **Regulatory Compliance** | Classification as investment advisor / money transmitter | legal_disclaimers.py, LICENSE |
| **P7** | **Versioning & Integrity** | Inconsistency, non-reproducibility, loss of trust | T08, T24, CHANGELOG.md |

---

## P1 — Security

### Standards Applied
- **OWASP Top 10** (2021) — https://owasp.org/Top10/
- **CWE/SANS Top 25** — https://cwe.mitre.org/top25/
- **ISO/IEC 27001:2022** — Information security management (controls subset)

### Implementation Matrix

| Control | Implementation | Verification |
|---------|---------------|-------------|
| No private key access | Read-only design — zero write operations | T23: grep for `private_key`, `secret`, `mnemonic` |
| No `eval`/`exec`/`pickle`/`subprocess` | Forbidden patterns | T23: AST scan of all .py files |
| Input validation | `re.fullmatch(r"0x[0-9a-fA-F]{40}", addr)` | T06: syntax, T15: pipeline |
| XSS prevention | `html.escape()` via `_safe()` for all user data | T20: HTML structure, T23 |
| CSP headers | `default-src 'none'` in HTML reports | T20: HTML report |
| HTTPS only | All external calls via `https://` | T23: grep for `http://` (must be zero) |
| Minimal dependencies | 1 runtime dep (`httpx`), 7 transitive | T21: requirements, T24: file integrity |
| Supply chain | Dependabot enabled, version pinning in pyproject.toml | GitHub Dependabot alerts |

### Code References
- Input validation: `commands.py` → `_prompt_address()` (regex)
- XSS: `html_generator.py` → `_safe()`, `safe_num()`
- Vulnerability scan: `tests/test_codereview.py` → T23

---

## P2 — Privacy & Data Protection

### Standards Applied
- **LGPD** — Lei 13.709/2018 (Brazil General Data Protection Law)
- **GDPR** — Regulation (EU) 2016/679
- **Privacy by Design** — Ann Cavoukian, 7 Foundational Principles (ISO 31700:2023)
- **1RPC.io TEE Relay** — Automata Network, burn-after-relay architecture

### Implementation Matrix

| LGPD/GDPR Principle | Implementation | Verification |
|---------------------|---------------|-------------|
| **Data minimization** (LGPD Art. 6 III / GDPR Art. 5(1)(c)) | Only public on-chain data read; no PII | T09: sensitive data scan |
| **Purpose limitation** (LGPD Art. 6 I / GDPR Art. 5(1)(b)) | Educational analysis only | Disclaimers in all output (T19) |
| **Storage limitation** (LGPD Art. 6 V / GDPR Art. 5(1)(e)) | Zero persistence — temp files only, no DB/cache | T24: no `reports/` dir, no `.db` files |
| **Integrity & confidentiality** (LGPD Art. 6 VII / GDPR Art. 5(1)(f)) | HTTPS + 1RPC.io TEE relay | T17: RPC connectivity, T23: HTTPS-only |
| **Right to erasure** (LGPD Art. 18 VI / GDPR Art. 17) | Trivial — no remote data stored | By design |
| **Consent** (LGPD Art. 7 I / GDPR Art. 6(1)(a)) | Explicit opt-in before any data-accessing command | T19: disclaimers present |

### Data Flow Per Command

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          DATA FLOW DIAGRAM                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  User Input         Validation          Network               Local         │
│  ─────────         ──────────          ───────               ─────         │
│                                                                             │
│  report             hex regex    ──→   1RPC.io (TEE)   ──→  V3 Math   ──→  │
│  --position 123     0x + 40 hex        ├── positions()       tick↔price     │
│  --network arb      enum check         ├── slot0()           IL formula     │
│                                        ├── Factory.getPool() fee calc       │
│                                        └── feeGrowth*()      efficiency     │
│                                                                    │        │
│                                  ──→   DEXScreener API             │        │
│                                        ├── /pairs/{addr}      ┌────┘        │
│                                        └── volume, TVL        │             │
│                                                                ▼            │
│                                                           HTML escape       │
│                                                           CSP headers       │
│                                                           temp file         │
│                                                           browser open      │
│                                                           (discarded)       │
│                                                                             │
│  pool               hex regex    ──→   DEXScreener only  ──→ CLI stdout     │
│  --pool 0x…         0x + 40 hex        /pairs/{addr}                        │
│                                                                             │
│  list               hex regex    ──→   1RPC.io (TEE)     ──→ CLI stdout     │
│  <wallet>           0x + 40 hex        ├── balanceOf()                      │
│  --network arb                         └── tokenOfOwnerByIndex()            │
│                                                                             │
│  scout              pair parse   ──→   DefiLlama API     ──→ CLI stdout     │
│  WETH/USDC          token names        yields.llama.fi                      │
│                                        (no user data sent)                  │
│                                                                             │
│  info, check        (none)       ──→   (none)            ──→ CLI stdout     │
│                                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### What Leaves Your Machine (Privacy Matrix)

| # | Destination | Data Sent | Purpose | Privacy Level |
|---|-------------|-----------|---------|--------------|
| 1 | **1RPC.io** TEE → blockchain RPC | Contract addresses, position NFT IDs, wallet (list only) | On-chain state reads | **Maximum** — TEE relay, burn-after-relay, metadata masking |
| 2 | **DEXScreener** API | Pool/token address (**no wallet**) | Market data (volume, TVL) | **High** — only pool address + your IP |
| 3 | **DefiLlama** API | **Nothing user-specific** (GET request) | Pool yield comparison | **Maximum** — only your IP, no query params |

### What We Do NOT Do

| Category | Status | Verification |
|----------|--------|-------------|
| Telemetry / Analytics | None | T23 |
| Private key access | Never | T09, T23 |
| User-Agent fingerprinting | Default httpx only | Source inspection |
| Tracking pixels / external resources | None — CSP enforced | T20, T23 |
| Phone-home / update checks | None | T23 |
| Persistent identifiers / cookies | None | T24 (no DB/cache files) |
| Personal data storage | None | By design |

### Code References
- RPC relay: `defi_cli/rpc_helpers.py` → `RPC_URLS` (all 1RPC.io)
- Temp reports: `html_generator.py` → `tempfile.NamedTemporaryFile(delete=False)`
- Privacy documentation: `SECURITY.md` → §Privacy & Data Transparency

---

## P3 — Informed Consent

### Standards Applied
- **Informed consent doctrine** — common law consumer protection
- **LGPD Art. 7 I / Art. 8** — consent must be free, informed, unambiguous
- **GDPR Art. 6(1)(a) / Art. 7** — conditions for consent

### Consent Matrix

| Command | Consent Level | Mechanism | Reason |
|---------|--------------|-----------|--------|
| `report` | **Full** — "I agree" | `_require_consent()` — must type exact phrase | Generates financial analysis; highest risk of misinterpretation |
| `pool` | **Simple** — "y/N" | `_simple_disclaimer()` — y or yes | Shows pool metrics; lower risk |
| `list` | **Simple** — "y/N" | `_simple_disclaimer()` — y or yes | Scans wallet (sends wallet to RPC) |
| `scout` | **None** | — | DefiLlama only, no user data sent |
| `check` | **None** | — | Internal validation, no user data |
| `info` | **None** | — | Static text, no network calls |

### Consent Properties
- **Timestamped** — `consent_timestamp` saved in report (visible in HTML Session 5)
- **Session-scoped** — consent valid only for current execution; no persistence
- **Non-transferable** — cannot be inherited from a previous run
- **Revocable** — user can Ctrl+C at any point to cancel

### Code References
- Full consent: `defi_cli/commands.py` → `_require_consent()`
- Simple consent: `defi_cli/commands.py` → `_simple_disclaimer()`
- Consent routing: `run.py` → `main()` function
- Timestamp recording: `defi_cli/commands.py` → `cmd_report()` line 389

---

## P4 — Liability Disclaimer

### Standards Applied
- **MIT License** — OSI-approved, "AS IS" without warranty (USC Title 17)
- **UCC §2-316** (USA) — disclaimer of implied warranties
- **Brazilian Civil Code Art. 927** — liability requires fault + causation (excluded via disclaimers)
- **Consumer Contracts Unfair Terms Directive 93/13/EEC** (EU)

### Disclaimer Locations (Defense in Depth)

| Layer | Location | Content |
|-------|----------|---------|
| 1. License | `LICENSE` | MIT AS-IS + extended financial disclaimers + jurisdictional notices |
| 2. Source code | `defi_cli/legal_disclaimers.py` | `REGULATORY_COMPLIANCE` (~150 lines), `CLI_DISCLAIMER`, `get_jurisdiction_specific_warning()` |
| 3. CLI runtime | Every consent prompt | "NOT financial advice", "HIGH RISK", "Developer NOT LIABLE" |
| 4. HTML report | Session 5: Legal Compliance | Full mandatory disclaimer, risk warnings, regulatory notices |
| 5. README | Badge + first paragraph | "Educational DeFi Analyzer" |

### Code References
- License: `LICENSE` (80 lines, MIT + financial extensions)
- Legal text module: `defi_cli/legal_disclaimers.py`
- CLI disclaimer: `defi_cli/commands.py` → consent functions
- HTML disclaimer: `html_generator.py` → Session 5
- T19 validates disclaimers present in output

---

## P5 — Data Accuracy

### Standards Applied
- **Uniswap V3 Whitepaper** — https://uniswap.org/whitepaper-v3.pdf (§6.1-§6.3)
- **Pintail IL Formula** — https://pintail.medium.com/uniswap-a-good-deal-for-liquidity-providers-104c0b6816f2
- **DEXScreener API** — https://docs.dexscreener.com/api/reference
- **DefiLlama Yields API** — https://defillama.com/docs/api

### Formula Traceability

| Calculation | Formula | Source | Test |
|-------------|---------|--------|------|
| Tick → Price | $p(i) = 1.0001^i$ | Whitepaper §6.1 | T11: roundtrip 15 scales |
| Liquidity | $L = \Delta x \cdot \sqrt{P_a} \cdot \sqrt{P_b} / (\sqrt{P_b} - \sqrt{P_a})$ | Whitepaper §6.2 | T05: 83 unit tests |
| Impermanent Loss | $IL = 2\sqrt{r} / (1 + r) - 1$ | Pintail 2019 | T12: symmetry IL(2x) = IL(0.5x) |
| Capital Efficiency | $CE = 1 / (1 - \sqrt{P_a / P_b})$ | Whitepaper §2 | T13: CE ≥ 1.0 |
| Uncollected Fees | $fees = (feeGrowthGlobal - feeGrowthOutside) \times L / 2^{128}$ | Tick Library | T15: pipeline schema |
| Fee APY | $(fees_{24h} \times 365) / position\_value$ | Standard finance | T14: monotonic |
| Range Width | $(P_{upper} - P_{lower}) / P_{current} \times 100$ | Derived | T05 |

### Known Accuracy Limitations

| Metric | Variance | Cause | Documented In |
|--------|----------|-------|--------------|
| **Uncollected fees** | **±2-5%** until actual collection | Rounding in feeGrowth accumulation, block timing | LICENSE, HTML report |
| **Fee projections (APR/APY)** | **±20-30%** | Based on 24h volume snapshot, not historical average | HTML report Session 4 |
| **Position value (USD)** | **±1-2%** | Price derived from sqrtPriceX96 at single block | HTML report audit trail |

### Audit Trail (Reproducibility)
Every HTML report generated from on-chain data includes:
- **Block number** — exact block the data was read at
- **RPC endpoint** — which 1RPC.io relay was used
- **Contract addresses** — PositionManager, Factory, Pool
- **Raw eth_call data** — selector + calldata for each call
- **Decoded results** — parsed values with labels
- **Formulas applied** — which Whitepaper section was used

An auditor can independently reproduce every number by replaying the same `eth_call` at the same block.

### Code References
- Formula docstrings: `real_defi_math.py` lines 1-37 (6 numbered sources with URLs)
- Audit trail builder: `html_generator.py` → `_build_audit_trail()`
- Math tests: `tests/test_math.py` (83 tests)
- Pipeline test: `tests/test_codereview.py` → T15

---

## P6 — Regulatory Compliance

### Classification

This tool is an **educational, read-only, open-source analysis tool**. It does NOT:
- Provide investment advice or recommendations
- Manage, custody, or transmit user funds
- Execute on-chain transactions
- Require authentication, KYC, or registration
- Charge fees for usage

### Regulatory Matrix

| Jurisdiction | Regulator | Regulation | Classification | Compliance Measure |
|-------------|-----------|------------|---------------|-------------------|
| 🇧🇷 Brazil | **CVM** | Instrução CVM 598/2018 (investment advisors) | Not an investment advisor — educational tool | Explicit disclaimer in LICENSE, CLI, HTML |
| 🇧🇷 Brazil | **CVM** | Resolução CVM 175/2022 (investment funds) | Not a fund — no custody, no management | By design (read-only) |
| 🇧🇷 Brazil | **Receita Federal** | IN RFB 1888/2019, IN RFB 2164/2023 | User responsible for crypto tax reporting | Disclaimer in legal_disclaimers.py |
| 🇧🇷 Brazil | **Bacen** | Lei 14.478/2022 (crypto framework) | Not a virtual asset service provider (VASP) | By design (no transactions) |
| 🇧🇷 Brazil | **LGPD** | Lei 13.709/2018 | No personal data processed | Privacy by design (P2) |
| 🇺🇸 USA | **SEC** | Investment Advisers Act of 1940, §202(a)(11)(A) | Educational tool exemption | Disclaimer in LICENSE |
| 🇺🇸 USA | **FinCEN** | Bank Secrecy Act (BSA) | Not a money transmitter (no fund movement) | By design (read-only) |
| 🇺🇸 USA | **IRS** | Notice 2014-21, Rev. Rul. 2019-24 | User responsible for reporting | Disclaimer in legal_disclaimers.py |
| 🇪🇺 EU | **ESMA** | MiCA — Regulation (EU) 2023/1114 | Does not provide crypto-asset services per Art. 3(1)(16) | Disclaimer in LICENSE, CLI |
| 🇪🇺 EU | **GDPR** | Regulation (EU) 2016/679 | No personal data processing | Privacy by design (P2) |
| 🇬🇧 UK | **FCA** | FCA PS22/10 (crypto marketing) | Not a financial promotion (educational/open-source) | Disclaimers |
| 🌍 Global | **FATF** | FATF Recommendations (2012, updated 2021) | Not a VASP — no asset transfer/exchange | By design |
| 🌍 Global | **Basel** | Basel Committee crypto guidelines (2022) | Not applicable (not a financial institution) | N/A |

### Code References
- Regulatory text: `defi_cli/legal_disclaimers.py` → `REGULATORY_COMPLIANCE`
- Jurisdictional warnings: `defi_cli/legal_disclaimers.py` → `get_jurisdiction_specific_warning()`
- License disclaimers: `LICENSE` lines 23-80
- Automated check: `tests/test_codereview.py` → T19 (disclaimers in output)

---

## P7 — Versioning & Integrity

### Standards Applied
- **Semantic Versioning 2.0.0** — https://semver.org/
- **Keep a Changelog 1.1.0** — https://keepachangelog.com/

### Version Synchronization Points

| Location | Variable/Field | Automated Check |
|----------|---------------|----------------|
| `pyproject.toml` | `version = "X.Y.Z"` | T08 |
| `defi_cli/central_config.py` | `PROJECT_VERSION = "X.Y.Z"` | T08 |
| `defi_cli/__init__.py` | `__version__ = "X.Y.Z"` | T08 |
| `run.py` | Docstring `vX.Y.Z` | T08 |
| `html_generator.py` | Footer version | T20 |
| `defi_cli/legal_disclaimers.py` | `Version: X.Y.Z` | Manual |
| `CHANGELOG.md` | `[X.Y.Z]` heading | Manual |
| `README.md` | Badge `vX.Y.Z` | Manual |

### Versioning Policy
- **MAJOR** (X): Breaking changes to CLI interface, data format, or formula corrections
- **MINOR** (Y): New features (commands, DEX support, networks)
- **PATCH** (Z): Bug fixes, documentation, test improvements

### File Integrity
T24 validates that all 25 expected project files exist and no stale artifacts remain.

### Code References
- Version check: `tests/test_codereview.py` → T08
- File integrity: `tests/test_codereview.py` → T24
- Changelog: `CHANGELOG.md`

---

## Codereview Category → Priority Mapping

Each of the 50 codereview categories in `.codereview.md` maps to a priority level:

| Priority | Categories (from .codereview.md) |
|----------|--------------------------------|
| **P1 Security** | #02 Pen Test, #18 Security, #19 Sensitive Data, #23 OWASP, #24 Supply Chain |
| **P2 Privacy** | #20 PII, #21 ISO 27001, #22 ISO 27701, #43 GDPR/LGPD Cross-border |
| **P3 Consent** | #25 User Consent, #13 User Interface (consent UX) |
| **P4 Liability** | #35 General Compliance, #40 Civil Liability, #41 IP, #42 Terms of Use |
| **P5 Accuracy** | #01 Code Review, #04 Bug Check, #10 Schema, #14 Info Sufficiency, #49 Math Formulas, #50 Transparency |
| **P6 Regulatory** | #26 CVM, #27 Receita Federal, #28 LGPD, #29 Bacen, #30 SEC, #31 FinCEN, #32 MiCA, #33 FCA, #34 FATF, #36-#39 Fiscal |
| **P7 Versioning** | #03 Best Practices, #08 Dead Code, #11 Metadata, #12 Links, #17 GitHub Impact |

---

## Automated Verification Summary

| Priority | Automated Tests | Coverage |
|----------|----------------|----------|
| P1 Security | T09, T23, T30 | Secrets scan, vuln scan (eval/exec/http), CSP, CI/CD security (pinned SHAs, permissions, concurrency) |
| P2 Privacy | T09, T17, T24, T25, T27 | No PII, RPC connectivity (1RPC.io), no persistence, LGPD compliance, no tracking |
| P3 Consent | T19, T20 | Disclaimers in output, HTML sections present |
| P4 Liability | T19, T24, T26 | Disclaimers present, LICENSE file exists, CVM disclaimer |
| P5 Accuracy | T05, T11, T12, T13, T14, T15 | 83 formula tests, roundtrip, symmetry, pipeline |
| P6 Regulatory | T19, T26 | Disclaimer text includes regulatory notices, CVM compliance |
| P7 Versioning | T08, T21, T24 | Version consistency, requirements, file integrity |

---

## Third-Party Service Audit

| Service | URL | What They Receive | Privacy | Free Tier | Rate Limit |
|---------|-----|-------------------|---------|-----------|------------|
| [1RPC.io](https://1rpc.io) | `https://*.1rpc.io` | RPC calls (TEE-protected) | Zero-tracking, burn-after-relay | 10K req/day | 10,000/day |
| [DEXScreener](https://dexscreener.com) | `api.dexscreener.com` | Pool/token address (no wallet) | IP + address only | Unlimited | 300 req/min |
| [DefiLlama](https://defillama.com) | `yields.llama.fi` | Nothing user-specific | IP only | Unlimited | ~30 req/min |

All services are accessed via **HTTPS only**, verified by T23 (no `http://` in codebase).

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.1.0 | 2026-02-08 | Added T25–T30 (LGPD, CVM, tracking, Azure IaC, Docker, CI/CD). CI pipeline added. |
| 1.0.0 | 2026-02-07 | Initial P1–P7 compliance framework |

*This document is part of the project's compliance infrastructure and is reviewed during every codereview cycle.*
