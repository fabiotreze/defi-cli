"""
OFFICIAL DEXSCREENER CONFIGURATION — Based on official documentation
====================================================================
Source: https://docs.dexscreener.com/api/reference

Official DEXScreener API for universal DeFi pool analysis.
"""
from dataclasses import dataclass

# Version
PROJECT_VERSION = "1.0.0"
PROJECT_NAME = "DeFi CLI"

@dataclass(frozen=True)
class DexScreenerAPI:
    """Official DEXScreener API configuration."""
    
    # Official base URL
    BASE_URL: str = "https://api.dexscreener.com"
    
    # Official endpoints
    PAIRS_ENDPOINT: str = "/latest/dex/pairs"          # For specific pools
    SEARCH_ENDPOINT: str = "/latest/dex/search"        # General search
    TOKENS_ENDPOINT: str = "/tokens/v1"                # Token data
    
    # Official rate limits (from documentation)
    PAIRS_RATE_LIMIT: int = 300   # requests/minute
    GENERAL_RATE_LIMIT: int = 60  # requests/minute  
    
    # Recommended timeout
    TIMEOUT_SECONDS: int = 15
    
    # Supported chains (ALL major networks)
    SUPPORTED_CHAINS = {
        # Ethereum & L2s
        'ethereum': 'ethereum',
        'arbitrum': 'arbitrum', 
        'optimism': 'optimism',
        'base': 'base',
        'polygon': 'polygon',
        
        # Other major chains
        'bsc': 'bsc',           # Binance Smart Chain
        'avalanche': 'avalanche', # Avalanche C-Chain  
        'fantom': 'fantom',     # Fantom
        'solana': 'solana',     # Solana
        'cronos': 'cronos',     # Cronos
        'moonbeam': 'moonbeam', # Moonbeam
        'celo': 'celo',         # Celo
        'harmony': 'harmony',   # Harmony ONE
        'kcc': 'kcc',           # KuCoin Community Chain
        
        # Additional networks (aliases)
        'eth': 'ethereum',
        'arb': 'arbitrum',
        'matic': 'polygon',
        'ftm': 'fantom',
        'avax': 'avalanche',
        'bnb': 'bsc'
    }
    
    # Priority chains for auto-detection (by volume/popularity)
    PRIORITY_CHAINS = ['ethereum', 'arbitrum', 'polygon', 'base', 'optimism']
    
    @classmethod
    def get_pair_url(cls, chain_id: str, pair_address: str) -> str:
        """URL to fetch a specific pool."""
        return f"{cls.BASE_URL}{cls.PAIRS_ENDPOINT}/{chain_id}/{pair_address}"
    
    @classmethod
    def get_auto_detect_urls(cls, address: str) -> list:
        """Generate URLs for auto-detection across priority chains."""
        urls = []
        for chain in cls.PRIORITY_CHAINS:
            urls.append((chain, cls.get_pair_url(chain, address)))
        return urls
    
    @classmethod
    def get_token_search_url(cls, chain_id: str, token_address: str) -> str:
        """URL to search pools for a specific token."""
        return f"{cls.BASE_URL}/token-pairs/v1/{chain_id}/{token_address}"
    @classmethod
    def get_token_url(cls, chain_id: str, token_address: str) -> str:
        """URL for specific token data."""
        return f"{cls.BASE_URL}{cls.TOKENS_ENDPOINT}/{chain_id}/{token_address}"

@dataclass(frozen=True)  
class ComplianceInfo:
    """Compliance information based on DEXScreener."""
    
    # Official data source
    DATA_SOURCE: str = "DEX Screener"
    DATA_SOURCE_URL: str = "https://dexscreener.com"
    API_DOCS_URL: str = "https://docs.dexscreener.com/api/reference"
    
    # Official disclaimer  
    OFFICIAL_DISCLAIMER: str = (
        "Data provided by DEX Screener aggregates information from multiple DEXs. "
        "Always verify data independently and understand the risks of DeFi trading."
    )
    
    # Rate limits for compliance
    RATE_LIMITS: str = (
        "API Rate Limits: 300 req/min for pairs, 60 req/min for general endpoints. "
        "Excessive usage may result in temporary blocks."
    )

# Unified configuration
class DexScreenerConfig:
    """Unified configuration based on DEXScreener."""
    
    api = DexScreenerAPI()
    compliance = ComplianceInfo()

# Global instance
config = DexScreenerConfig()