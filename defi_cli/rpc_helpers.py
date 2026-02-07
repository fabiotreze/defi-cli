#!/usr/bin/env python3
"""
RPC Helpers — Shared ABI Encoding/Decoding and JSON-RPC Client
===============================================================

Consolidates low-level EVM interaction primitives used by both
position_reader.py and position_indexer.py:

  • ABI encoding/decoding (uint256, int256, address, uint24, int24, string)
  • JSON-RPC client (eth_call, eth_call_batch, eth_blockNumber)
  • Named constants for ABI word sizes and Q-values

All constants reference the Ethereum ABI specification:
  https://docs.soliditylang.org/en/latest/abi-spec.html

Terminology:
  • Word:  32 bytes = 256 bits = 64 hex characters
  • Slot:  Position of a 32-byte word in an ABI response
  • Q96:   2^96  — fixed-point denominator for sqrtPriceX96
  • Q128:  2^128 — fixed-point denominator for feeGrowthX128
  • Q256:  2^256 — two's complement boundary for int256
"""

import httpx
from typing import List, Tuple

# ── ABI Word Constants ──────────────────────────────────────────────────
# Ethereum ABI spec: https://docs.soliditylang.org/en/latest/abi-spec.html

ABI_WORD_BYTES = 32          # 1 ABI word = 32 bytes
ABI_WORD_HEX = 64            # 32 bytes × 2 hex chars = 64 hex characters
ADDRESS_BYTES = 20            # Ethereum address = 20 bytes
ADDRESS_HEX = 40              # 20 bytes × 2 = 40 hex characters
ADDRESS_PAD_HEX = 24          # Left padding in a 32-byte slot = 64 - 40 = 24 hex chars
SIGN_BIT = 1 << 255           # Two's complement sign bit for int256

# ── Uniswap V3 Fixed-Point Constants ───────────────────────────────────
# Ref: Uniswap V3 Whitepaper §6.1 — https://uniswap.org/whitepaper-v3.pdf

Q96 = 2 ** 96                # sqrtPriceX96 denominator (FixedPoint96.RESOLUTION)
Q128 = 2 ** 128              # feeGrowthGlobalX128 denominator (FixedPoint128.Q128)
Q256 = 2 ** 256              # int256 overflow boundary (two's complement wrap)

# ── Common Token Symbol Normalization ───────────────────────────────────
# Some on-chain symbols use non-standard Unicode or suffixes.

SYMBOL_MAP = {
    "USD₮0": "USDT",
    "USD₮": "USDT",
    "USDT0": "USDT",
    "WETH": "WETH",
    "USDC.e": "USDC.e",
}


def normalize_symbol(raw_symbol: str) -> str:
    """Normalize on-chain token symbol to common name."""
    cleaned = raw_symbol.strip().strip("\x00")
    return SYMBOL_MAP.get(cleaned, cleaned)


# ── Privacy-Preserving RPC Endpoints via 1RPC.io ────────────────────────
# 1RPC is a TEE-attested relay by Automata Network that protects user
# privacy: zero-tracking, metadata masking, random dispatching.
# Free tier: 10,000 req/day — no API key required.
# Docs: https://docs.1rpc.io/web3-relay/overview
# Networks: https://docs.1rpc.io/using-the-web3-api/networks

RPC_URLS: dict[str, str] = {
    "arbitrum": "https://1rpc.io/arb",
    "ethereum": "https://1rpc.io/eth",
    "polygon": "https://1rpc.io/matic",
    "base": "https://1rpc.io/base",
    "optimism": "https://1rpc.io/op",
    "bsc": "https://1rpc.io/bnb",
}


# ── ABI Function Selectors ──────────────────────────────────────────────
# First 4 bytes of keccak256(function_signature).
# Shared across position_reader.py and position_indexer.py.

SELECTORS: dict[str, str] = {
    # NonfungiblePositionManager (ERC-721 Enumerable)
    "balanceOf":              "0x70a08231",  # balanceOf(address)
    "tokenOfOwnerByIndex":    "0x2f745c59",  # tokenOfOwnerByIndex(address,uint256)
    "positions":              "0x99fbab88",  # positions(uint256)

    # UniswapV3Pool (read-only state)
    "slot0":                  "0x3850c7bd",  # slot0()
    "liquidity":              "0x1a686502",  # liquidity()
    "feeGrowthGlobal0X128":   "0xf3058399",  # feeGrowthGlobal0X128()
    "feeGrowthGlobal1X128":   "0x46141319",  # feeGrowthGlobal1X128()
    "ticks":                  "0xf30dba93",  # ticks(int24)

    # UniswapV3Factory
    "getPool":                "0x1698ee82",  # getPool(address,address,uint24)

    # ERC-20 metadata
    "symbol":                 "0x95d89b41",  # symbol()
    "decimals":               "0x313ce567",  # decimals()
}


# ── ABI Encoding ────────────────────────────────────────────────────────

def encode_uint256(value: int) -> str:
    """ABI-encode a uint256 as 32-byte hex (no 0x prefix).

    >>> encode_uint256(1)
    '0000000000000000000000000000000000000000000000000000000000000001'
    """
    return format(value, f'0{ABI_WORD_HEX}x')


def encode_address(addr: str) -> str:
    """ABI-encode an address as 32 bytes (left-padded, no 0x prefix).

    >>> encode_address('0xC36442b4a4522E871399CD717aBDD847Ab11FE88')
    '000000000000000000000000c36442b4a4522e871399cd717abdd847ab11fe88'
    """
    return addr.lower().replace("0x", "").zfill(ABI_WORD_HEX)


def encode_uint24(val: int) -> str:
    """ABI-encode a uint24 as 32 bytes (for fee tier parameter).

    >>> encode_uint24(3000)
    '0000000000000000000000000000000000000000000000000000000000000bb8'
    """
    return format(val, f'0{ABI_WORD_HEX}x')


def encode_int24(value: int) -> str:
    """ABI-encode an int24 sign-extended to int256 (for ticks).

    >>> encode_int24(-887220)
    'fffffffffffffffffffffffffffffffffffffffffffffffffffffffffff27e8c'
    """
    if value < 0:
        value = Q256 + value
    return format(value, f'0{ABI_WORD_HEX}x')


# ── ABI Decoding ────────────────────────────────────────────────────────

def decode_uint(hex_data: str, slot: int = 0) -> int:
    """Decode uint256 from ABI response at 32-byte slot offset.

    Args:
        hex_data: Hex string (without 0x prefix).
        slot: Which 32-byte word to read (0-indexed).
    """
    start = slot * ABI_WORD_HEX
    return int(hex_data[start:start + ABI_WORD_HEX], 16)


def decode_int(hex_data: str, slot: int = 0) -> int:
    """Decode int256 (two's complement) from ABI response.

    Args:
        hex_data: Hex string (without 0x prefix).
        slot: Which 32-byte word to read (0-indexed).
    """
    val = decode_uint(hex_data, slot)
    if val >= SIGN_BIT:
        return val - Q256
    return val


def decode_address(hex_data: str, slot: int = 0) -> str:
    """Decode address (last 20 bytes of 32-byte slot).

    Args:
        hex_data: Hex string (without 0x prefix).
        slot: Which 32-byte word to read (0-indexed).
    """
    start = slot * ABI_WORD_HEX
    return "0x" + hex_data[start + ADDRESS_PAD_HEX:start + ABI_WORD_HEX]


def decode_string(hex_data: str) -> str:
    """Decode ABI-encoded dynamic string return value.

    Handles both standard dynamic strings (offset + length + data)
    and non-standard bytes32 returns from some token contracts.
    """
    try:
        offset = decode_uint(hex_data, 0)
        word_offset = offset // ABI_WORD_BYTES
        length = decode_uint(hex_data, word_offset)
        start_byte = (word_offset + 1) * ABI_WORD_HEX
        hex_str = hex_data[start_byte:start_byte + length * 2]
        return bytes.fromhex(hex_str).decode("utf-8").strip("\x00")
    except Exception:
        # Fallback: Some tokens return bytes32 instead of string
        try:
            raw = bytes.fromhex(hex_data[:ABI_WORD_HEX])
            return raw.decode("utf-8").strip("\x00").strip()
        except Exception:
            return "UNK"


# ── JSON-RPC Client ─────────────────────────────────────────────────────

async def eth_call(rpc_url: str, to: str, data: str, timeout: int = 20) -> str:
    """
    Execute eth_call on an EVM node.

    Args:
        rpc_url: JSON-RPC endpoint URL (e.g. https://1rpc.io/arb)
        to: Contract address (0x...)
        data: ABI-encoded calldata (0x + selector + params)
        timeout: HTTP timeout in seconds

    Returns:
        Hex response string (without 0x prefix).

    Raises:
        RuntimeError: If RPC returns an error or empty response.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(rpc_url, json=payload)
        result = resp.json()
        if "error" in result:
            raise RuntimeError(f"RPC error: {result['error'].get('message', result['error'])}")
        raw = result.get("result", "0x")
        if raw == "0x" or len(raw) < 4:
            raise RuntimeError("Empty response — contract may not exist at this address")
        return raw[2:]  # strip 0x prefix


async def eth_call_batch(rpc_url: str, calls: List[Tuple[str, str]], timeout: int = 20) -> List[str]:
    """
    Batch multiple eth_call requests into a single HTTP request.

    Args:
        rpc_url: JSON-RPC endpoint URL
        calls: List of (contract_address, calldata) tuples
        timeout: HTTP timeout in seconds

    Returns:
        List of hex result strings (without 0x prefix), in same order as calls.
    """
    payloads = []
    for i, (to, data) in enumerate(calls):
        payloads.append({
            "jsonrpc": "2.0",
            "id": i + 1,
            "method": "eth_call",
            "params": [{"to": to, "data": data}, "latest"],
        })

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(rpc_url, json=payloads)
        results = resp.json()

    # Sort by id and extract results
    if isinstance(results, list):
        results.sort(key=lambda r: r.get("id", 0))
        return [r.get("result", "0x")[2:] if "result" in r else "" for r in results]
    else:
        # Single result (some RPCs don't support batch)
        return [results.get("result", "0x")[2:]]


async def eth_block_number(rpc_url: str, timeout: int = 10) -> int:
    """
    Get the latest block number from an EVM node.

    Args:
        rpc_url: JSON-RPC endpoint URL
        timeout: HTTP timeout in seconds

    Returns:
        Latest block number as integer.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_blockNumber",
        "params": [],
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(rpc_url, json=payload)
        result = resp.json()
        if "error" in result:
            raise RuntimeError(f"RPC error: {result['error']}")
        return int(result["result"], 16)
