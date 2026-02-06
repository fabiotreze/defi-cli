#!/usr/bin/env python3
"""
On-Chain Position Reader for Uniswap V3
========================================

Reads REAL position data directly from the blockchain via public JSON-RPC.
No API key required. No web3.py dependency — uses httpx for raw eth_call.

Data Sources (per RPC call):
─────────────────────────────
1. NonfungiblePositionManager.positions(tokenId)
   Contract: 0xC36442b4a4522E871399CD717aBDD847Ab11FE88
   Returns: token0, token1, fee, tickLower, tickUpper, liquidity,
            feeGrowthInside0LastX128, feeGrowthInside1LastX128,
            tokensOwed0, tokensOwed1
   Ref: https://github.com/Uniswap/v3-periphery/blob/main/contracts/NonfungiblePositionManager.sol

2. Pool.slot0()
   Returns: sqrtPriceX96, tick (current price state)
   Ref: https://github.com/Uniswap/v3-core/blob/main/contracts/UniswapV3Pool.sol

3. Pool.liquidity()
   Returns: Current in-range liquidity (for fee share calculation)

4. Pool.feeGrowthGlobal0X128(), feeGrowthGlobal1X128()
   Pool.ticks(int24) → feeGrowthOutside0X128, feeGrowthOutside1X128
   Used to compute uncollected fees per Uniswap V3 Core logic.

5. ERC-20.decimals(), ERC-20.symbol()
   Token metadata for human-readable formatting.

Price Formulas (Uniswap V3 Whitepaper):
───────────────────────────────────────
  Current price: p = (sqrtPriceX96 / 2^96)^2 × 10^(d0 − d1)   [§6.1]
  Tick → price:  p(i) = 1.0001^i × 10^(d0 − d1)               [§6.1]
  Token amounts: From liquidity L and sqrt prices               [§6.2]
  Fees:          feeGrowthInside × L / 2^128                    [Pool.sol]
"""

import asyncio
import httpx
from typing import Dict


# ── Public RPC Endpoints (no API key) ────────────────────────────────────

RPC_URLS = {
    "arbitrum": "https://arb1.arbitrum.io/rpc",
    "ethereum": "https://eth.llamarpc.com",
    "polygon": "https://polygon-rpc.com",
    "base": "https://mainnet.base.org",
    "optimism": "https://mainnet.optimism.io",
}

# Uniswap V3 NonfungiblePositionManager (same address on all EVM L2s)
# Ref: https://docs.uniswap.org/contracts/v3/reference/deployments/
POSITION_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"


# ── ABI Function Selectors ──────────────────────────────────────────────
# First 4 bytes of keccak256(function_signature)

SELECTORS = {
    "positions":              "0x99fbab88",  # positions(uint256)
    "slot0":                  "0x3850c7bd",  # slot0()
    "liquidity":              "0x1a686502",  # liquidity()
    "decimals":               "0x313ce567",  # decimals()
    "symbol":                 "0x95d89b41",  # symbol()
    "feeGrowthGlobal0X128":   "0xf3058399",  # feeGrowthGlobal0X128()
    "feeGrowthGlobal1X128":   "0x46141319",  # feeGrowthGlobal1X128()
    "ticks":                  "0xf30dba93",  # ticks(int24)
}

Q96 = 2 ** 96
Q128 = 2 ** 128
Q256 = 2 ** 256

# Common token symbol normalization (on-chain symbols can be non-standard)
SYMBOL_MAP = {
    "USD₮0": "USDT",
    "USD₮": "USDT",
    "USDT0": "USDT",
    "WETH": "WETH",
    "USDC.e": "USDC.e",
}


def _normalize_symbol(raw_symbol: str) -> str:
    """Normalize on-chain token symbol to common name."""
    cleaned = raw_symbol.strip().strip("\x00")
    return SYMBOL_MAP.get(cleaned, cleaned)


# ── ABI Encoding / Decoding Helpers ─────────────────────────────────────

def _encode_uint256(value: int) -> str:
    """ABI-encode a uint256 as 32-byte hex (no 0x prefix)."""
    return format(value, '064x')


def _encode_int24(value: int) -> str:
    """ABI-encode an int24 sign-extended to int256."""
    if value < 0:
        value = Q256 + value
    return format(value, '064x')


def _decode_uint(hex_data: str, slot: int = 0) -> int:
    """Decode uint256 from ABI response at 32-byte slot offset."""
    start = slot * 64
    return int(hex_data[start:start + 64], 16)


def _decode_int(hex_data: str, slot: int = 0) -> int:
    """Decode int256 (two's complement) from ABI response."""
    val = _decode_uint(hex_data, slot)
    if val >= (1 << 255):
        return val - Q256
    return val


def _decode_address(hex_data: str, slot: int = 0) -> str:
    """Decode address (last 20 bytes of 32-byte slot)."""
    start = slot * 64
    return "0x" + hex_data[start + 24:start + 64]


def _decode_string(hex_data: str) -> str:
    """Decode ABI-encoded dynamic string return value."""
    try:
        offset = _decode_uint(hex_data, 0)
        word_offset = offset // 32
        length = _decode_uint(hex_data, word_offset)
        start_byte = (word_offset + 1) * 64
        hex_str = hex_data[start_byte:start_byte + length * 2]
        return bytes.fromhex(hex_str).decode("utf-8").strip("\x00")
    except Exception:
        # Fallback: Some tokens return bytes32 instead of string
        try:
            raw = bytes.fromhex(hex_data[:64])
            return raw.decode("utf-8").strip("\x00").strip()
        except Exception:
            return "UNK"


# ── JSON-RPC Client ─────────────────────────────────────────────────────

async def _eth_call(rpc_url: str, to: str, data: str, timeout: int = 20) -> str:
    """
    Execute eth_call on an EVM node.

    Args:
        rpc_url: JSON-RPC endpoint URL
        to: Contract address (0x...)
        data: ABI-encoded calldata (0x + selector + params)

    Returns:
        Hex response string (without 0x prefix).

    Raises:
        RuntimeError: If RPC returns an error.
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
            raise RuntimeError("Empty response — position may not exist")
        return raw[2:]  # strip 0x prefix


async def _eth_call_batch(rpc_url: str, calls: list, timeout: int = 20) -> list:
    """
    Batch multiple eth_call requests into a single HTTP request.

    Args:
        calls: List of (to, data) tuples.

    Returns:
        List of hex result strings.
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


# ── Position Reader ─────────────────────────────────────────────────────

class PositionReader:
    """
    Reads Uniswap V3 position data directly from the blockchain.

    Usage:
        reader = PositionReader("arbitrum")
        data = await reader.read_position(1234567, "0x...pool_addr...")
    """

    def __init__(self, network: str = "arbitrum"):
        if network not in RPC_URLS:
            raise ValueError(
                f"Unsupported network: {network}. "
                f"Available: {list(RPC_URLS.keys())}"
            )
        self.network = network
        self.rpc_url = RPC_URLS[network]

    async def _get_block_number(self) -> int:
        """Fetch current block number for audit trail reproducibility."""
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "eth_blockNumber", "params": [],
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.rpc_url, json=payload)
                return int(resp.json().get("result", "0x0"), 16)
        except Exception:
            return 0

    async def read_position(self, position_id: int, pool_address: str) -> Dict:
        """
        Read complete position data from the blockchain.

        Args:
            position_id: NFT token ID (integer)
            pool_address: Pool contract address (0x...)

        Returns:
            Dict with position data, pool state, token amounts, fees,
            and audit trail (block number, raw calldata, RPC endpoint).
        """
        # ── Step 0: Validate inputs ────────────────────────────────
        if position_id < 0:
            raise ValueError(f"position_id must be non-negative, got {position_id}")
        if not pool_address or not pool_address.startswith("0x") or len(pool_address) != 42:
            raise ValueError(f"Invalid pool address: {pool_address}")

        # ── Step 0b: Capture block number for audit ──────────────────
        block_number = await self._get_block_number()

        # ── Step 1: Read position NFT ────────────────────────────────
        print(f"  📖 Reading position #{position_id} from {self.network}...")
        pos = await self._read_position_nft(position_id)

        if pos["liquidity"] == 0:
            print("  ⚠️  Position has zero liquidity (may be closed)")

        # ── Step 2: Batch read pool state + token info ───────────────
        print(f"  📊 Reading pool & token state...")

        # Batch: slot0, liquidity, feeGrowthGlobal0, feeGrowthGlobal1,
        #         decimals0, decimals1, symbol0, symbol1
        batch_calls = [
            (pool_address, SELECTORS["slot0"]),
            (pool_address, SELECTORS["liquidity"]),
            (pool_address, SELECTORS["feeGrowthGlobal0X128"]),
            (pool_address, SELECTORS["feeGrowthGlobal1X128"]),
            (pos["token0"], SELECTORS["decimals"]),
            (pos["token1"], SELECTORS["decimals"]),
            (pos["token0"], SELECTORS["symbol"]),
            (pos["token1"], SELECTORS["symbol"]),
        ]

        try:
            batch_results = await _eth_call_batch(self.rpc_url, batch_calls)
        except Exception:
            # Fallback to sequential calls if batch not supported
            batch_results = []
            for to, data in batch_calls:
                try:
                    r = await _eth_call(self.rpc_url, to, data)
                    batch_results.append(r)
                except Exception:
                    batch_results.append("")

        # Parse batch results
        slot0_data        = batch_results[0]
        pool_liq_data     = batch_results[1]
        fg0_global_data   = batch_results[2]
        fg1_global_data   = batch_results[3]
        dec0_data         = batch_results[4]
        dec1_data         = batch_results[5]
        sym0_data         = batch_results[6]
        sym1_data         = batch_results[7]

        # Decode pool state
        sqrtPriceX96 = _decode_uint(slot0_data, 0) if slot0_data else 0
        current_tick = _decode_int(slot0_data, 1) if slot0_data else 0
        pool_liquidity = _decode_uint(pool_liq_data, 0) if pool_liq_data else 0

        # Decode token info
        decimals0 = _decode_uint(dec0_data, 0) if dec0_data else 18
        decimals1 = _decode_uint(dec1_data, 0) if dec1_data else 6
        symbol0 = _normalize_symbol(_decode_string(sym0_data)) if sym0_data else "TOKEN0"
        symbol1 = _normalize_symbol(_decode_string(sym1_data)) if sym1_data else "TOKEN1"

        # Decode fee growth globals
        fg0_global = _decode_uint(fg0_global_data, 0) if fg0_global_data else 0
        fg1_global = _decode_uint(fg1_global_data, 0) if fg1_global_data else 0

        # ── Step 3: Read tick data for fee computation ───────────────
        print(f"  💰 Computing uncollected fees...")

        tick_lower_call = SELECTORS["ticks"] + _encode_int24(pos["tickLower"])
        tick_upper_call = SELECTORS["ticks"] + _encode_int24(pos["tickUpper"])

        try:
            tick_batch = await _eth_call_batch(self.rpc_url, [
                (pool_address, tick_lower_call),
                (pool_address, tick_upper_call),
            ])
        except Exception:
            tick_batch = ["", ""]
            try:
                tick_batch[0] = await _eth_call(self.rpc_url, pool_address, tick_lower_call)
            except Exception:
                pass
            try:
                tick_batch[1] = await _eth_call(self.rpc_url, pool_address, tick_upper_call)
            except Exception:
                pass

        # ── Step 4: Compute token amounts ────────────────────────────
        amounts = self._compute_token_amounts(
            pos["liquidity"], sqrtPriceX96, current_tick,
            pos["tickLower"], pos["tickUpper"],
            decimals0, decimals1,
        )

        # ── Step 5: Compute uncollected fees ─────────────────────────
        fees = self._compute_fees(
            pos, current_tick,
            fg0_global, fg1_global,
            tick_batch[0], tick_batch[1],
            decimals0, decimals1,
        )

        # ── Step 6: Compute prices ───────────────────────────────────
        current_price = self._sqrtPriceX96_to_price(sqrtPriceX96, decimals0, decimals1)
        price_lower = self._tick_to_price(pos["tickLower"], decimals0, decimals1)
        price_upper = self._tick_to_price(pos["tickUpper"], decimals0, decimals1)

        # ── Step 7: Compute USD values ───────────────────────────────
        # Assumption: token1 is the quote (stablecoin like USDT/USDC)
        # If not, we'd need an external price oracle — but for ETH/USDT this works
        token0_value_usd = amounts["amount0"] * current_price
        token1_value_usd = amounts["amount1"]  # token1 ≈ $1 for stablecoins
        total_value_usd = token0_value_usd + token1_value_usd

        fee0_value_usd = fees["fees0"] * current_price
        fee1_value_usd = fees["fees1"]
        total_fees_usd = fee0_value_usd + fee1_value_usd

        # Composition percentages
        t0_pct = (token0_value_usd / total_value_usd * 100) if total_value_usd > 0 else 0
        t1_pct = (token1_value_usd / total_value_usd * 100) if total_value_usd > 0 else 0

        in_range = pos["tickLower"] <= current_tick < pos["tickUpper"]

        # ── Step 8: Position share of pool liquidity ─────────────────
        position_share = (pos["liquidity"] / pool_liquidity) if pool_liquidity > 0 else 0

        fee_tier = pos["fee"] / 1_000_000  # e.g., 500 → 0.0005

        print(f"  ✅ Position data loaded: ${total_value_usd:,.2f} | "
              f"{'In Range' if in_range else 'OUT OF RANGE'}")

        return {
            # Identity
            "position_id": position_id,
            "pool_address": pool_address,
            "network": self.network,

            # Tokens
            "token0_address": pos["token0"],
            "token1_address": pos["token1"],
            "token0_symbol": symbol0,
            "token1_symbol": symbol1,
            "token0_decimals": decimals0,
            "token1_decimals": decimals1,

            # Fee tier
            "fee_raw": pos["fee"],         # 500 = 0.05%
            "fee_tier": fee_tier,          # 0.0005

            # On-chain position state
            "liquidity_raw": pos["liquidity"],
            "tickLower": pos["tickLower"],
            "tickUpper": pos["tickUpper"],
            "in_range": in_range,

            # Prices (token1 per token0, e.g., USDT per WETH)
            "current_price": round(current_price, 6),
            "price_lower": round(price_lower, 6),
            "price_upper": round(price_upper, 6),

            # Token amounts (human-readable)
            "amount0": round(amounts["amount0"], 8),
            "amount1": round(amounts["amount1"], 8),
            "token0_value_usd": round(token0_value_usd, 2),
            "token1_value_usd": round(token1_value_usd, 2),
            "total_value_usd": round(total_value_usd, 2),

            # Composition
            "token0_pct": round(t0_pct, 2),
            "token1_pct": round(t1_pct, 2),

            # Uncollected fees
            "fees0": round(fees["fees0"], 8),
            "fees1": round(fees["fees1"], 8),
            "fee0_value_usd": round(fee0_value_usd, 2),
            "fee1_value_usd": round(fee1_value_usd, 2),
            "total_fees_usd": round(total_fees_usd, 2),

            # Pool state
            "pool_liquidity": pool_liquidity,
            "position_share": round(position_share * 100, 6),  # percentage
            "sqrtPriceX96": sqrtPriceX96,
            "pool_tick": current_tick,

            # Data source & audit trail
            "data_source": "on-chain",
            "rpc_endpoint": self.rpc_url,
            "block_number": block_number,

            # Audit trail: raw on-chain values for independent verification
            "audit_trail": {
                "block_number": block_number,
                "rpc_endpoint": self.rpc_url,
                "contracts": {
                    "position_manager": POSITION_MANAGER,
                    "pool": pool_address,
                    "token0": pos["token0"],
                    "token1": pos["token1"],
                },
                "raw_calls": [
                    {
                        "label": "positions(uint256)",
                        "to": POSITION_MANAGER,
                        "selector": SELECTORS["positions"],
                        "calldata": SELECTORS["positions"] + hex(position_id)[2:].zfill(64),
                        "decoded": {
                            "liquidity": pos["liquidity"],
                            "tickLower": pos["tickLower"],
                            "tickUpper": pos["tickUpper"],
                            "fee": pos["fee"],
                            "token0": pos["token0"],
                            "token1": pos["token1"],
                        },
                    },
                    {
                        "label": "slot0()",
                        "to": pool_address,
                        "selector": SELECTORS["slot0"],
                        "decoded": {
                            "sqrtPriceX96": sqrtPriceX96,
                            "tick": current_tick,
                        },
                    },
                    {
                        "label": "liquidity()",
                        "to": pool_address,
                        "selector": SELECTORS["liquidity"],
                        "decoded": {"liquidity": pool_liquidity},
                    },
                    {
                        "label": "feeGrowthGlobal0X128()",
                        "to": pool_address,
                        "selector": SELECTORS["feeGrowthGlobal0X128"],
                        "decoded": {"value": fg0_global},
                    },
                    {
                        "label": "feeGrowthGlobal1X128()",
                        "to": pool_address,
                        "selector": SELECTORS["feeGrowthGlobal1X128"],
                        "decoded": {"value": fg1_global},
                    },
                ],
                "formulas_applied": [
                    f"current_price = (sqrtPriceX96 / 2^96)^2 × 10^({decimals0}-{decimals1}) = {current_price:.6f}",
                    f"price_lower = 1.0001^{pos['tickLower']} × 10^({decimals0}-{decimals1}) = {price_lower:.6f}",
                    f"price_upper = 1.0001^{pos['tickUpper']} × 10^({decimals0}-{decimals1}) = {price_upper:.6f}",
                    f"token0_amount = L × (1/√P - 1/√Pu) / 10^{decimals0} = {amounts['amount0']:.8f}",
                    f"token1_amount = L × (√P - √Pl) / 10^{decimals1} = {amounts['amount1']:.8f}",
                    f"fees0 = (feeGrowthInside0 × L) / 2^128 / 10^{decimals0} = {fees['fees0']:.8f}",
                    f"fees1 = (feeGrowthInside1 × L) / 2^128 / 10^{decimals1} = {fees['fees1']:.8f}",
                    f"position_share = {pos['liquidity']} / {pool_liquidity} = {position_share:.8f}",
                ],
            },
        }

    # ── Internal: Read position NFT ──────────────────────────────────

    async def _read_position_nft(self, token_id: int) -> Dict:
        """
        Call NonfungiblePositionManager.positions(uint256 tokenId).

        Returns 12 fields per the contract ABI:
          (nonce, operator, token0, token1, fee, tickLower, tickUpper,
           liquidity, feeGrowthInside0LastX128, feeGrowthInside1LastX128,
           tokensOwed0, tokensOwed1)
        """
        calldata = SELECTORS["positions"] + _encode_uint256(token_id)
        result = await _eth_call(self.rpc_url, POSITION_MANAGER, calldata)

        return {
            "nonce":                       _decode_uint(result, 0),
            "operator":                    _decode_address(result, 1),
            "token0":                      _decode_address(result, 2),
            "token1":                      _decode_address(result, 3),
            "fee":                         _decode_uint(result, 4),
            "tickLower":                   _decode_int(result, 5),
            "tickUpper":                   _decode_int(result, 6),
            "liquidity":                   _decode_uint(result, 7),
            "feeGrowthInside0LastX128":    _decode_uint(result, 8),
            "feeGrowthInside1LastX128":    _decode_uint(result, 9),
            "tokensOwed0":                 _decode_uint(result, 10),
            "tokensOwed1":                 _decode_uint(result, 11),
        }

    # ── Internal: Compute token amounts ──────────────────────────────

    def _compute_token_amounts(
        self,
        liquidity: int,
        sqrtPriceX96: int,
        current_tick: int,
        tick_lower: int,
        tick_upper: int,
        decimals0: int,
        decimals1: int,
    ) -> Dict:
        """
        Compute token amounts from position liquidity and current price.

        Formula (Whitepaper §6.2):
          In range:  amount0 = L × (1/√P − 1/√P_upper)
                     amount1 = L × (√P − √P_lower)
          Below:     amount0 = L × (1/√P_lower − 1/√P_upper), amount1 = 0
          Above:     amount0 = 0, amount1 = L × (√P_upper − √P_lower)
        """
        if liquidity == 0 or sqrtPriceX96 == 0:
            return {"amount0": 0.0, "amount1": 0.0}

        sqrtP = sqrtPriceX96 / Q96
        sqrtPl = 1.0001 ** (tick_lower / 2)
        sqrtPu = 1.0001 ** (tick_upper / 2)

        if current_tick < tick_lower:
            amount0_raw = liquidity * (1 / sqrtPl - 1 / sqrtPu)
            amount1_raw = 0
        elif current_tick >= tick_upper:
            amount0_raw = 0
            amount1_raw = liquidity * (sqrtPu - sqrtPl)
        else:
            amount0_raw = liquidity * (1 / sqrtP - 1 / sqrtPu)
            amount1_raw = liquidity * (sqrtP - sqrtPl)

        return {
            "amount0": amount0_raw / (10 ** decimals0),
            "amount1": amount1_raw / (10 ** decimals1),
        }

    # ── Internal: Compute uncollected fees ───────────────────────────

    def _compute_fees(
        self,
        pos: Dict,
        current_tick: int,
        fg0_global: int,
        fg1_global: int,
        tick_lower_data: str,
        tick_upper_data: str,
        decimals0: int,
        decimals1: int,
    ) -> Dict:
        """
        Compute uncollected fees from on-chain feeGrowth data.

        Logic mirrors Uniswap V3 Core Pool.sol::_getFeeGrowthInside().

        Steps:
          1. Determine feeGrowthBelow from tickLower's feeGrowthOutside
          2. Determine feeGrowthAbove from tickUpper's feeGrowthOutside
          3. feeGrowthInside = global − below − above  (mod 2^256)
          4. fees = liquidity × (inside_current − inside_last) / 2^128
        """
        try:
            if not tick_lower_data or not tick_upper_data:
                raise ValueError("Missing tick data")

            # ticks() returns: liquidityGross[0], liquidityNet[1],
            #   feeGrowthOutside0X128[2], feeGrowthOutside1X128[3], ...
            fg0_outside_lower = _decode_uint(tick_lower_data, 2)
            fg1_outside_lower = _decode_uint(tick_lower_data, 3)
            fg0_outside_upper = _decode_uint(tick_upper_data, 2)
            fg1_outside_upper = _decode_uint(tick_upper_data, 3)

            # feeGrowthBelow (lower tick)
            if current_tick >= pos["tickLower"]:
                fg0_below = fg0_outside_lower
                fg1_below = fg1_outside_lower
            else:
                fg0_below = (fg0_global - fg0_outside_lower) % Q256
                fg1_below = (fg1_global - fg1_outside_lower) % Q256

            # feeGrowthAbove (upper tick)
            if current_tick < pos["tickUpper"]:
                fg0_above = fg0_outside_upper
                fg1_above = fg1_outside_upper
            else:
                fg0_above = (fg0_global - fg0_outside_upper) % Q256
                fg1_above = (fg1_global - fg1_outside_upper) % Q256

            # feeGrowthInside
            fg0_inside = (fg0_global - fg0_below - fg0_above) % Q256
            fg1_inside = (fg1_global - fg1_below - fg1_above) % Q256

            # Uncollected fees
            liq = pos["liquidity"]
            fees0_raw = (liq * ((fg0_inside - pos["feeGrowthInside0LastX128"]) % Q256)) // Q128
            fees1_raw = (liq * ((fg1_inside - pos["feeGrowthInside1LastX128"]) % Q256)) // Q128

            # Add tokensOwed (fees already checkpointed but not yet collected)
            fees0_raw += pos.get("tokensOwed0", 0)
            fees1_raw += pos.get("tokensOwed1", 0)

            return {
                "fees0": fees0_raw / (10 ** decimals0),
                "fees1": fees1_raw / (10 ** decimals1),
            }

        except Exception as e:
            print(f"  ⚠️  Fee computation fallback (tokensOwed only): {e}")
            fees0 = pos.get("tokensOwed0", 0) / (10 ** decimals0)
            fees1 = pos.get("tokensOwed1", 0) / (10 ** decimals1)
            return {"fees0": fees0, "fees1": fees1}

    # ── Internal: Price conversions ──────────────────────────────────

    def _sqrtPriceX96_to_price(
        self, sqrtPriceX96: int, decimals0: int, decimals1: int
    ) -> float:
        """
        Convert sqrtPriceX96 to human-readable price (token1 per token0).

        Formula (Whitepaper §6.1):
          raw_price = (sqrtPriceX96 / 2^96)^2
          human_price = raw_price × 10^(decimals0 − decimals1)

        Example: WETH(18)/USDT(6) → multiply by 10^12
        """
        if sqrtPriceX96 == 0:
            return 0.0
        sqrtP = sqrtPriceX96 / Q96
        raw_price = sqrtP * sqrtP
        return raw_price * (10 ** (decimals0 - decimals1))

    def _tick_to_price(
        self, tick: int, decimals0: int, decimals1: int
    ) -> float:
        """
        Convert tick index to human-readable price.

        Formula (Whitepaper §6.1):
          p(i) = 1.0001^i × 10^(decimals0 − decimals1)
        """
        raw_price = 1.0001 ** tick
        return raw_price * (10 ** (decimals0 - decimals1))


# ── Standalone Test ──────────────────────────────────────────────────────

async def _test_position(
    position_id: int,
    pool_address: str,
    network: str = "arbitrum",
):
    """Quick test: read a real position from chain.

    Usage:
        python position_reader.py <position_id> <pool_address> [network]
    """
    reader = PositionReader(network)
    data = await reader.read_position(position_id, pool_address)

    print("\n" + "=" * 60)
    print(f"  Position #{data['position_id']} — {data['token0_symbol']}/{data['token1_symbol']}")
    print(f"  Network: {data['network'].title()} | Pool: {data['pool_address'][:16]}...")
    print("=" * 60)
    print(f"  Status     : {'🟢 In Range' if data['in_range'] else '🔴 Out of Range'}")
    print(f"  Fee Tier   : {data['fee_tier']*100:.2f}%")
    print(f"  Price Now  : {data['current_price']:,.2f} {data['token1_symbol']}/{data['token0_symbol']}")
    print(f"  Range      : {data['price_lower']:,.2f} – {data['price_upper']:,.2f}")
    print()
    print(f"  Position Value: ${data['total_value_usd']:,.2f}")
    print(f"    {data['token0_symbol']}: {data['amount0']:.6f} (${data['token0_value_usd']:,.2f} · {data['token0_pct']:.1f}%)")
    print(f"    {data['token1_symbol']}: {data['amount1']:.6f} (${data['token1_value_usd']:,.2f} · {data['token1_pct']:.1f}%)")
    print()
    print(f"  Uncollected Fees: ${data['total_fees_usd']:,.2f}")
    print(f"    {data['token0_symbol']}: {data['fees0']:.8f} (${data['fee0_value_usd']:,.2f})")
    print(f"    {data['token1_symbol']}: {data['fees1']:.8f} (${data['fee1_value_usd']:,.2f})")
    print()
    print(f"  Pool Share : {data['position_share']:.4f}%")
    print(f"  Data Source: {data['data_source']}")
    print("=" * 60)

    return data


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python position_reader.py <position_id> <pool_address> [network]")
        print("  position_id  : Uniswap V3 NFT token ID (integer)")
        print("  pool_address : Pool contract address (0x...)")
        print("  network      : arbitrum | ethereum | polygon | base | optimism")
        sys.exit(1)
    pos_id = int(sys.argv[1])
    pool = sys.argv[2]
    net = sys.argv[3] if len(sys.argv) > 3 else "arbitrum"
    asyncio.run(_test_position(pos_id, pool, net))
