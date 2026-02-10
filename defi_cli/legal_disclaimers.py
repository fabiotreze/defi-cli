"""
GLOBAL LEGAL DISCLAIMERS & REGULATORY COMPLIANCE
===============================================

🚨 CRITICAL LEGAL NOTICE 🚨

This software is provided for EDUCATIONAL and INFORMATIONAL purposes ONLY.

⚠️ NOT FINANCIAL ADVICE:
• This tool does NOT provide financial, investment, or trading advice
• All information is for educational and analytical purposes only
• No recommendations or investment suggestions are provided
• Past performance does NOT indicate future results
• DeFi protocols carry HIGH RISK including total loss of capital

🛡️ USER RESPONSIBILITY:
• Users assume 100% responsibility for their financial decisions
• Developer(s) disclaim ALL LIABILITY for financial losses
• Users must conduct their own research (DYOR) before any transactions
• Independent professional advice is recommended for financial decisions
"""

# Full regulatory compliance text (assigned to a constant — not a dead string literal)
REGULATORY_COMPLIANCE = """
🔗 DATA SOURCE COMPLIANCE:
• Primary data source: DEX Screener (https://dexscreener.com)
• API documentation: https://docs.dexscreener.com/api/reference
• Rate limits: 300 req/min for pairs, 60 req/min general
• Data aggregated from multiple decentralized exchanges
• Real-time pricing and liquidity information
• Always verify data independently before transactions

⚖️ REGULATORY COMPLIANCE:

�🇸 UNITED STATES (SEC/CFTC):
- Not a registered investment advisor under Investment Advisers Act of 1940
- Educational tool exemption under Section 202(a)(11)(A)
- Does not constitute investment advice per SEC guidance
- Not a money transmitter per FinCEN Bank Secrecy Act (BSA)

🇪🇺 EUROPEAN UNION (MiCA/GDPR):
- Does not provide crypto-asset services per MiCA Regulation (EU) 2023/1114 Art. 3(1)(16)
- GDPR Regulation (EU) 2016/679 — no personal data processed (privacy by design)
- Right to data portability and erasure — trivially satisfied (no data stored)

🇧🇷 BRAZIL (CVM/LGPD):
- Not an investment advisor per Instrução CVM 598/2018
- Not a fund manager per Resolução CVM 175/2022
- LGPD Lei 13.709/2018 — data minimization (Art. 6 III), no personal data processed
- User responsible for Receita Federal reporting per IN RFB 1888/2019
- Not a virtual asset service provider per Lei 14.478/2022 (Bacen)

🌍 GLOBAL STANDARDS:
- OWASP security standards compliance
- ISO 27001 information security management
- Financial Action Task Force (FATF) guidelines awareness
- Basel Committee crypto asset guidelines consideration

🔒 DATA PROTECTION:
• No private keys stored, transmitted, or accessed
• Public blockchain data only - no personal financial information
• Transport Layer Security (TLS/HTTPS) for all external API communications
• Audit trails maintained for transparency and compliance
• Data retention limited to operational necessity

📊 DATA SOURCES:
• Official protocol smart contracts and subgraphs only
• DEXScreener official universal API
• Verified on-chain data exclusively
• No third-party price manipulation or estimates
• Mathematical formulas from official protocol documentation

🔗 TRANSPARENCY COMMITMENT:
• Complete source code transparency
• Open mathematical formulas based on protocol whitepapers
• Verifiable on-chain data only
• No hidden fees, commissions, or financial incentives
• Community-driven development with public audit trails

⚡ TECHNICAL DISCLAIMER:
• Software provided "AS IS" without warranty of any kind
• No guarantee of uptime, accuracy, or continued functionality  
• Blockchain data may be delayed or temporarily unavailable
• Network congestion may affect real-time data accuracy
• Smart contract risks are inherent to DeFi protocols

� FINANCIAL LOSS DISCLAIMER:
• DEVELOPER IS NOT LIABLE FOR ANY FINANCIAL LOSSES WHATSOEVER
• NO WARRANTY OR GUARANTEE of profit, return, or capital preservation
• Users assume 100% FINANCIAL RESPONSIBILITY for all trading decisions
• Past performance NEVER indicates future results
• DeFi protocols may suffer TOTAL LOSS due to hacks, exploits, or market crashes  
• BY USING THIS SOFTWARE, YOU WAIVE ALL CLAIMS against developer for financial losses

�🔥 HIGH RISK WARNING:
DeFi protocols involve EXTREME RISKS including but not limited to:
• Total loss of capital
• Smart contract exploits and vulnerabilities
• Impermanent loss in liquidity provision
• Network congestion and failed transactions
• Regulatory changes affecting protocol availability
• Market manipulation and extreme volatility

BY USING THIS SOFTWARE, YOU ACKNOWLEDGE:
✅ You have read and understood these disclaimers
✅ You accept full responsibility for your financial decisions
✅ You will not hold developers liable for any losses
✅ You understand DeFi risks and will proceed cautiously
✅ You will seek professional advice for significant decisions
✅ You are legally permitted to use crypto analysis tools
✅ You will comply with all applicable laws and regulations

For questions regarding compliance or legal matters, 
consult qualified legal and financial professionals in your jurisdiction.
ALL decisions are YOUR RESPONSIBILITY — use at your own risk.

⭐ OPEN SOURCE:
• MIT License: Copy, modify, distribute freely
• Community encouraged to fork and improve
• Star us on GitHub: github.com/fabiotreze/defi-cli

Last Updated: 2026-02-09
Version: 1.1.2
License: MIT (Software) / CC BY-SA 4.0 (Documentation)
"""

# CLI disclaimer for user acceptance prompt
CLI_DISCLAIMER = """
🚨 CRITICAL LEGAL WARNING 🚨

⚠️  NOT FINANCIAL ADVICE - EDUCATIONAL TOOL ONLY
🔥 HIGH RISK - DeFi can result in TOTAL LOSS of capital
📚 DO YOUR OWN RESEARCH (DYOR) before any decisions
⚡ USE AT YOUR OWN RISK - DEVELOPER NOT LIABLE FOR LOSSES
⚖️ CHECK LOCAL LAWS - Crypto may be prohibited in your jurisdiction
💰 FINANCIAL DISCLAIMER - Developer WAIVES ALL LIABILITY for financial losses

By continuing, you ACCEPT total responsibility for your financial decisions.
"""


def get_jurisdiction_specific_warning(jurisdiction: str = "GLOBAL") -> str:
    """Returns jurisdiction-specific warning with enhanced liability protection."""

    warnings = {
        "BR": """
🇧🇷 BRAZIL: Per CVM regulations, this tool does not offer investment advisory services.
Cryptocurrencies are not regulated by Central Bank. High-risk investment.
DEVELOPER NOT LIABLE for financial losses. Use at own risk.
        """,
        "US": """
🇺🇸 USA: Not registered investment advisor. Educational tool only per SEC guidance.
Crypto investments are highly speculative and involve substantial risk of loss.
DEVELOPER DISCLAIMS ALL LIABILITY for trading losses or financial damages.
        """,
        "EU": """
🇪🇺 EU: Compliant with MiCA regulation. No investment advice per ESMA guidelines.
Crypto-assets are unregulated and highly volatile. Capital at risk.
DEVELOPER WAIVES LIABILITY for financial losses under EU law.
        """,
        "GLOBAL": """
🌍 GLOBAL: Educational analysis only. No financial advice. High-risk activity.
Verify local regulations. User assumes all responsibility.
DEVELOPER NOT RESPONSIBLE for any financial losses or damages.
        """,
    }

    return warnings.get(jurisdiction, warnings["GLOBAL"])
