#!/usr/bin/env python3
"""
DEX Registry — Multi-Protocol V3 Contract Address Configuration
================================================================

Maps each supported V3-compatible DEX to its NonfungiblePositionManager
and Factory contract addresses per network.

Compatibility Rules:
  ✅ Compatible (same positions() ABI as Uniswap V3):
     - Uniswap V3
     - PancakeSwap V3
     - SushiSwap V3

Contract Address Sources:
  Uniswap V3  : https://docs.uniswap.org/contracts/v3/reference/deployments/
  PancakeSwap : https://developer.pancakeswap.finance/contracts/v3/addresses
  SushiSwap   : https://docs.sushi.com/docs/Products/V3%20AMM/Periphery/Deployment%20Addresses

SDK & Protocol Documentation:
  Uniswap V3 SDK     : https://docs.uniswap.org/sdk/v3/overview
  Uniswap V3 Core    : https://github.com/Uniswap/v3-core
  PancakeSwap V3 SDK : https://developer.pancakeswap.finance/contracts/v3/overview
  SushiSwap V3 Core  : https://docs.sushi.com/docs/Products/V3%20AMM/Core/Overview
"""

from typing import Dict, List, Optional

# ── DEX Registry ────────────────────────────────────────────────────────
#
# Structure:
#   DEX_REGISTRY[dex_slug] = {
#       "name": str,                       # Display name
#       "icon": str,                       # Emoji for CLI
#       "compatible": bool,                # True = same ABI as Uniswap V3
#       "networks": {
#           "network_slug": {
#               "position_manager": "0x...",
#               "factory": "0x...",
#           }
#       }
#   }

DEX_REGISTRY: Dict[str, dict] = {
    # ── Uniswap V3 ─────────────────────────────────────────────────
    # The original. Same contract on most EVM chains via CREATE2.
    # Ref: https://docs.uniswap.org/contracts/v3/reference/deployments/
    "uniswap_v3": {
        "name": "Uniswap V3",
        "icon": "🦄",
        "compatible": True,
        "networks": {
            "ethereum": {
                "position_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            },
            "arbitrum": {
                "position_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            },
            "polygon": {
                "position_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            },
            "optimism": {
                "position_manager": "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
                "factory": "0x1F98431c8aD98523631AE4a59f267346ea31F984",
            },
            "base": {
                "position_manager": "0x03a520b32C04BF3bEEf7BEb72E919cf822Ed34f1",
                "factory": "0x33128a8fC17869897dcE68Ed026d694621f6FDfD",
            },
        },
    },
    # ── PancakeSwap V3 ──────────────────────────────────────────────
    # Fork of Uniswap V3 with identical positions() ABI.
    # Deployed on: ETH, BSC, Arbitrum, Base (NOT on Polygon or Optimism).
    # Ref: https://developer.pancakeswap.finance/contracts/v3/addresses
    "pancakeswap_v3": {
        "name": "PancakeSwap V3",
        "icon": "🥞",
        "compatible": True,
        "networks": {
            "ethereum": {
                "position_manager": "0x46A15B0b27311cedF172AB29E4f4766fbE7F4364",
                "factory": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
            },
            "bsc": {
                "position_manager": "0x46A15B0b27311cedF172AB29E4f4766fbE7F4364",
                "factory": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
            },
            "arbitrum": {
                "position_manager": "0x427bF5b37357632377eCbEC9de3626C71A5396c1",
                "factory": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
            },
            "base": {
                "position_manager": "0x46A15B0b27311cedF172AB29E4f4766fbE7F4364",
                "factory": "0x0BFbCF9fa4f9C56B0F40a671Ad40E0805A091865",
            },
        },
    },
    # ── SushiSwap V3 ────────────────────────────────────────────────
    # Fork of Uniswap V3 with identical positions() ABI.
    # DIFFERENT addresses per chain — verified from sushi-labs/sushi source.
    # Ref: https://github.com/sushi-labs/sushi (src/evm/config/features/sushiswap-v3.ts)
    "sushiswap_v3": {
        "name": "SushiSwap V3",
        "icon": "🍣",
        "compatible": True,
        "networks": {
            "ethereum": {
                "position_manager": "0x2214A42d8e2A1d20635C2cb0664422c528b6A432",
                "factory": "0xbACEB8eC6b9355Dfc0269C18bac9d6E2Bdc29C4F",
            },
            "arbitrum": {
                "position_manager": "0xF0cBce1942a68BEB3d1b73F0dd86c8DCc363eF49",
                "factory": "0x1af415a1EbA07a4986a52B6f2e7dE7003D82231e",
            },
            "polygon": {
                "position_manager": "0xb7402ee99F0A008e461098AC3a27F4957Df89a40",
                "factory": "0x917933899c6a5f8E37F31E19f92CdbFf7e8ff0e2",
            },
            "base": {
                "position_manager": "0x80C7DD17B01855a6D2347444a0FCC36136a314de",
                "factory": "0xc35DADB65012eC5796536bD9864eD8773aBc74C4",
            },
            "optimism": {
                "position_manager": "0x1af415a1EbA07a4986a52B6f2e7dE7003D82231e",
                "factory": "0x9c6522117e2ed1fE5bdb72bb0eD5E3f2bdE7DBe0",
            },
        },
    },
}


# ── Helper Functions ────────────────────────────────────────────────────


def get_dexes_for_network(network: str) -> List[dict]:
    """
    Get all compatible DEXes available on a given network.

    Returns:
        List of dicts: [{slug, name, icon, position_manager, factory}, ...]
    """
    dexes = []
    for slug, dex in DEX_REGISTRY.items():
        if not dex["compatible"]:
            continue
        if network in dex["networks"]:
            addrs = dex["networks"][network]
            dexes.append(
                {
                    "slug": slug,
                    "name": dex["name"],
                    "icon": dex["icon"],
                    "position_manager": addrs["position_manager"],
                    "factory": addrs["factory"],
                }
            )
    return dexes


def get_all_position_managers(network: str) -> List[dict]:
    """
    Get all NonfungiblePositionManager addresses for a network.

    Returns:
        List of dicts: [{slug, name, icon, address}, ...]
    """
    managers = []
    for slug, dex in DEX_REGISTRY.items():
        if not dex["compatible"]:
            continue
        if network in dex["networks"]:
            managers.append(
                {
                    "slug": slug,
                    "name": dex["name"],
                    "icon": dex["icon"],
                    "address": dex["networks"][network]["position_manager"],
                }
            )
    return managers


def get_factory_address(dex_slug: str, network: str) -> Optional[str]:
    """Get the Factory address for a specific DEX + network."""
    dex = DEX_REGISTRY.get(dex_slug)
    if not dex or network not in dex.get("networks", {}):
        return None
    return dex["networks"][network]["factory"]


def get_position_manager_address(dex_slug: str, network: str) -> Optional[str]:
    """Get the NonfungiblePositionManager address for a specific DEX + network."""
    dex = DEX_REGISTRY.get(dex_slug)
    if not dex or network not in dex.get("networks", {}):
        return None
    return dex["networks"][network]["position_manager"]


def get_dex_display_name(dex_slug: str) -> str:
    """Get display name for a DEX slug."""
    dex = DEX_REGISTRY.get(dex_slug)
    return dex["name"] if dex else dex_slug


def get_dex_icon(dex_slug: str) -> str:
    """Get emoji icon for a DEX slug."""
    dex = DEX_REGISTRY.get(dex_slug)
    return dex["icon"] if dex else "🔄"
