"""
Project Configuration — API endpoints, version, constants
==========================================================

Contains DEXScreener API configuration and project metadata.
Source: https://docs.dexscreener.com/api/reference
"""

import re
from dataclasses import dataclass
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from types import MappingProxyType

# Version — single source of truth is pyproject.toml
try:
    PROJECT_VERSION = version("defi-cli")
except PackageNotFoundError:
    # Dev / CI: package not installed — read pyproject.toml directly
    _toml = Path(__file__).resolve().parent.parent / "pyproject.toml"
    _m = (
        re.search(r'version\s*=\s*"([^"]+)"', _toml.read_text())
        if _toml.exists()
        else None
    )
    PROJECT_VERSION = _m.group(1) if _m else "0.0.0-dev"
PROJECT_NAME = "DeFi CLI"


@dataclass(frozen=True)
class DexScreenerAPI:
    """Official DEXScreener API configuration."""

    # Official base URL
    BASE_URL: str = "https://api.dexscreener.com"

    # Official endpoints
    PAIRS_ENDPOINT: str = "/latest/dex/pairs"  # For specific pools
    TOKENS_ENDPOINT: str = "/tokens/v1"  # Token data

    # Recommended timeout
    TIMEOUT_SECONDS: int = 15

    # Supported chains (ALL major networks) — immutable mapping
    SUPPORTED_CHAINS = MappingProxyType(
        {
            # Ethereum & L2s
            "ethereum": "ethereum",
            "arbitrum": "arbitrum",
            "optimism": "optimism",
            "base": "base",
            "polygon": "polygon",
            # Other major chains
            "bsc": "bsc",  # Binance Smart Chain
            "avalanche": "avalanche",  # Avalanche C-Chain
            "fantom": "fantom",  # Fantom
            "solana": "solana",  # Solana
            "cronos": "cronos",  # Cronos
            "moonbeam": "moonbeam",  # Moonbeam
            "celo": "celo",  # Celo
            "harmony": "harmony",  # Harmony ONE
            "kcc": "kcc",  # KuCoin Community Chain
            # Additional networks (aliases)
            "eth": "ethereum",
            "arb": "arbitrum",
            "matic": "polygon",
            "ftm": "fantom",
            "avax": "avalanche",
            "bnb": "bsc",
        }
    )

    # Priority chains for auto-detection (by volume/popularity)
    PRIORITY_CHAINS = ["ethereum", "arbitrum", "polygon", "base", "optimism"]

    @classmethod
    def get_pair_url(cls, chain_id: str, pair_address: str) -> str:
        """URL to fetch a specific pool."""
        return f"{cls.BASE_URL}{cls.PAIRS_ENDPOINT}/{chain_id}/{pair_address}"

    @classmethod
    def get_auto_detect_urls(cls, address: str) -> list[tuple[str, str]]:
        """Generate URLs for auto-detection across priority chains."""
        urls = []
        for chain in cls.PRIORITY_CHAINS:
            urls.append((chain, cls.get_pair_url(chain, address)))
        return urls

    @classmethod
    def get_token_search_url(cls, chain_id: str, token_address: str) -> str:
        """URL to search pools for a specific token."""
        return f"{cls.BASE_URL}/token-pairs/v1/{chain_id}/{token_address}"


# Unified configuration
class DexScreenerConfig:
    """Unified configuration based on DEXScreener."""

    api = DexScreenerAPI()


# Global instance
config = DexScreenerConfig()
