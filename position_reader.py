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
from typing import Any, Dict

from defi_cli.rpc_helpers import (
    # Constants
    Q96, Q128, Q256, SYMBOL_MAP, ABI_WORD_HEX,
    # Shared definitions (single source of truth)
    RPC_URLS, SELECTORS,
    # Encoding
    encode_uint256 as _encode_uint256,
    encode_address as _encode_address,
    encode_uint24 as _encode_uint24,
    encode_int24 as _encode_int24,
    # Decoding
    decode_uint as _decode_uint,
    decode_int as _decode_int,
    decode_address as _decode_address,
    decode_string as _decode_string,
    # RPC
    eth_call as _eth_call,
    eth_call_batch as _eth_call_batch,
    eth_block_number as _eth_block_number,
    # Symbol normalization
    normalize_symbol as _normalize_symbol,
)
from defi_cli.stablecoins import is_stablecoin, stablecoin_side


# RPC_URLS and SELECTORS are imported from defi_cli.rpc_helpers (single source of truth).

# ── DEX Registry (multi-DEX support) ────────────────────────────────────
try:
    from defi_cli.dex_registry import (
        get_position_manager_address, get_factory_address,
        get_dex_display_name, get_dex_icon,
    )
    _HAS_REGISTRY = True
except ImportError:
    _HAS_REGISTRY = False

# Fallback: Uniswap V3 defaults (if registry not available)
# These MUST match dex_registry.py uniswap_v3 → ethereum entries.
# Ref: https://docs.uniswap.org/contracts/v3/reference/deployments/
_FALLBACK_POSITION_MANAGER = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
_FALLBACK_FACTORY = "0x1F98431c8aD98523631AE4a59f267346ea31F984"


# ABI function selectors, encoding/decoding, and RPC client
# are all imported from defi_cli.rpc_helpers (shared with position_indexer.py).


# ── Position Reader ─────────────────────────────────────────────────────

class PositionReader:
    """
    Reads V3-compatible position data directly from the blockchain.
    Supports multiple DEXes: Uniswap V3, PancakeSwap V3, SushiSwap V3.

    Usage:
        reader = PositionReader("arbitrum")                           # Uniswap V3 default
        reader = PositionReader("arbitrum", dex_slug="pancakeswap_v3") # PancakeSwap V3
        data = await reader.read_position(1234567)                    # auto-detect pool
        data = await reader.read_position(1234567, "0x...pool_addr")  # explicit pool
    """

    def __init__(self, network: str = "arbitrum", dex_slug: str = "uniswap_v3"):
        if network not in RPC_URLS:
            raise ValueError(
                f"Unsupported network: {network}. "
                f"Available: {list(RPC_URLS.keys())}"
            )
        self.network = network
        self.rpc_url = RPC_URLS[network]
        self.dex_slug = dex_slug

        # Resolve contract addresses from DEX registry
        if _HAS_REGISTRY:
            pm = get_position_manager_address(dex_slug, network)
            factory = get_factory_address(dex_slug, network)
            self.position_manager = pm or _FALLBACK_POSITION_MANAGER
            self.factory = factory or _FALLBACK_FACTORY
            self.dex_name = get_dex_display_name(dex_slug)
            self.dex_icon = get_dex_icon(dex_slug)
        else:
            self.position_manager = _FALLBACK_POSITION_MANAGER
            self.factory = _FALLBACK_FACTORY
            self.dex_name = "Uniswap V3"
            self.dex_icon = "🦄"

    async def _get_block_number(self) -> int:
        """Fetch current block number for audit trail reproducibility."""
        try:
            return await _eth_block_number(self.rpc_url)
        except Exception:  # noqa: BLE001
            return 0

    async def read_position(self, position_id: int, pool_address: str = None) -> Dict[str, Any]:
        """
        Read complete position data from the blockchain.

        Args:
            position_id: NFT token ID (integer)
            pool_address: Pool contract address (0x...). If None, auto-resolved
                          from on-chain data via Factory.getPool().

        Returns:
            Dict with position data, pool state, token amounts, fees,
            and audit trail (block number, raw calldata, RPC endpoint).
        """
        # ── Step 0: Validate inputs ────────────────────────────────
        if position_id < 0:
            raise ValueError(f"position_id must be non-negative, got {position_id}")
        if pool_address and (not pool_address.startswith("0x") or len(pool_address) != 42):
            raise ValueError(f"Invalid pool address: {pool_address}")

        # ── Step 0b: Capture block number for audit ──────────────────────
        block_number = await self._get_block_number()

        # ── Step 1: Read position NFT ────────────────────────────────────
        print(f"  📖 Reading position #{position_id} from {self.network}...")
        pos = await self._read_position_nft(position_id)

        # ── Step 1b: Auto-resolve pool address if not provided ───────
        if not pool_address:
            pool_address = await self._resolve_pool_address(
                pos["token0"], pos["token1"], pos["fee"]
            )
            print(f"  🎯 Auto-detected pool: {pool_address[:16]}...")

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
        except Exception:  # noqa: BLE001
            # Fallback to sequential calls if batch not supported
            batch_results = []
            for to, data in batch_calls:
                try:
                    r = await _eth_call(self.rpc_url, to, data)
                    batch_results.append(r)
                except Exception:  # noqa: BLE001
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
        except Exception:  # noqa: BLE001
            tick_batch = ["", ""]
            try:
                tick_batch[0] = await _eth_call(self.rpc_url, pool_address, tick_lower_call)
            except Exception:  # noqa: BLE001
                pass
            try:
                tick_batch[1] = await _eth_call(self.rpc_url, pool_address, tick_upper_call)
            except Exception:  # noqa: BLE001
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
        # Smart stablecoin detection (defi_cli.stablecoins) determines
        # which side is the quote asset (≈ $1). Falls back to token1
        # assumption for exotic pairs without an external price oracle.
        stable_idx = stablecoin_side(symbol0, symbol1)
        if stable_idx == 1:
            # token1 is stablecoin — token0 is priced in token1
            token0_value_usd = amounts["amount0"] * current_price
            token1_value_usd = amounts["amount1"]
            fee0_value_usd = fees["fees0"] * current_price
            fee1_value_usd = fees["fees1"]
        elif stable_idx == 0:
            # token0 is stablecoin — token1 is priced as 1/price
            token0_value_usd = amounts["amount0"]
            token1_value_usd = amounts["amount1"] / current_price if current_price > 0 else 0
            fee0_value_usd = fees["fees0"]
            fee1_value_usd = fees["fees1"] / current_price if current_price > 0 else 0
        else:
            # Neither is stablecoin — best effort using token1 as quote
            token0_value_usd = amounts["amount0"] * current_price
            token1_value_usd = amounts["amount1"]
            fee0_value_usd = fees["fees0"] * current_price
            fee1_value_usd = fees["fees1"]
        total_value_usd = token0_value_usd + token1_value_usd
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
            # DEX identification
            "dex_slug": self.dex_slug,
            "dex_name": self.dex_name,

            "audit_trail": {
                "block_number": block_number,
                "rpc_endpoint": self.rpc_url,
                "dex": self.dex_name,
                "contracts": {
                    "position_manager": self.position_manager,
                    "pool": pool_address,
                    "token0": pos["token0"],
                    "token1": pos["token1"],
                },
                "raw_calls": [
                    {
                        "label": "positions(uint256)",
                        "to": self.position_manager,
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
        result = await _eth_call(self.rpc_url, self.position_manager, calldata)

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

    # ── Internal: Resolve pool address from Factory ──────────────────

    async def _resolve_pool_address(self, token0: str, token1: str, fee: int) -> str:
        """
        Resolve pool address from UniswapV3Factory.getPool(token0, token1, fee).

        This enables auto-detection: given a position NFT, we can discover
        the pool address without the user providing it manually.

        Ref: https://github.com/Uniswap/v3-core/blob/main/contracts/UniswapV3Factory.sol
        """
        calldata = (
            SELECTORS["getPool"]
            + _encode_address(token0)
            + _encode_address(token1)
            + _encode_uint24(fee)
        )
        result = await _eth_call(self.rpc_url, self.factory, calldata)
        pool = _decode_address(result, 0)
        if pool == "0x" + "0" * 40:
            raise RuntimeError(
                f"Pool not found for {token0[:10]}.../{token1[:10]}... fee={fee}. "
                f"The position may be on a different network."
            )
        return pool

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
    pool_address: str | None = None,
    network: str = "arbitrum",
    dex_slug: str = "uniswap_v3",
) -> Dict:
    """Quick test: read a real position from chain.

    Usage:
        python position_reader.py <position_id> [pool_address] [network] [dex_slug]
    """
    reader = PositionReader(network, dex_slug=dex_slug)
    data = await reader.read_position(position_id, pool_address)

    print("\n" + "=" * 60)
    print(f"  Position #{data['position_id']} — {data['token0_symbol']}/{data['token1_symbol']}")
    print(f"  DEX: {data.get('dex_name', 'Uniswap V3')}")
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
    if len(sys.argv) < 2:
        print("Usage: python position_reader.py <position_id> [pool_address] [network] [dex_slug]")
        print("  position_id  : V3 NFT token ID (integer)")
        print("  pool_address : Pool contract address (0x...) — auto-detected if omitted")
        print("  network      : arbitrum | ethereum | polygon | base | optimism | bsc")
        print("  dex_slug     : uniswap_v3 | pancakeswap_v3 | sushiswap_v3")
        sys.exit(1)
    pos_id = int(sys.argv[1])
    pool = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2].startswith("0x") else None
    net = sys.argv[-1] if len(sys.argv) > 2 and not sys.argv[-1].startswith("0x") else "arbitrum"
    if len(sys.argv) > 3:
        net = sys.argv[3]
    dex = "uniswap_v3"
    for arg in sys.argv[2:]:
        if arg in ("uniswap_v3", "pancakeswap_v3", "sushiswap_v3"):
            dex = arg
            break
    asyncio.run(_test_position(pos_id, pool, net, dex))
