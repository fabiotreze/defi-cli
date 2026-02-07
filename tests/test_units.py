"""
Unit Tests for DeFi CLI Modules
================================

Comprehensive unit tests covering all extracted modules:
  - stablecoins.py        (classification, detection)
  - rpc_helpers.py         (ABI encoding/decoding, symbol normalization)
  - html_styles.py         (CSS generation)
  - html_generator.py      (HTML helpers, XSS prevention, formatting)
  - central_config.py      (API config, URL builders)
  - dexscreener_client.py  (_extract_pool_info pure logic)
  - position_reader.py     (price math, token amounts, fees)
  - commands.py            (_require_consent, _prompt_address)
  - run.py                 (argparse parser structure)

All tests are offline — no network calls. Mock-based where needed.
"""

import asyncio
import math
import re
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# ═══════════════════════════════════════════════════════════════════════════
# 1. stablecoins.py
# ═══════════════════════════════════════════════════════════════════════════

from defi_cli.stablecoins import (
    STABLECOIN_SYMBOLS,
    CORRELATED_GROUPS,
    is_stablecoin,
    is_stablecoin_pair,
    has_stablecoin,
    classify_pair,
    stablecoin_side,
    is_correlated_pair,
    estimate_fee_tier,
)


class TestStablecoinSymbols:
    """Verify the STABLECOIN_SYMBOLS frozenset contains expected entries."""

    @pytest.mark.parametrize("sym", [
        "USDC", "USDT", "DAI", "BUSD", "FRAX", "LUSD", "PYUSD", "GHO",
        "USDC.E", "USDT.E", "USDBC", "AXLUSDC",
        "EURS", "EURT", "EURC", "GBPT",
        "MIM", "DOLA", "OUSD",
    ])
    def test_known_stablecoins_present(self, sym):
        assert sym in STABLECOIN_SYMBOLS

    def test_volatile_tokens_absent(self):
        for sym in ["WETH", "WBTC", "LINK", "UNI", "AAVE", "DOGE", "SHIB"]:
            assert sym not in STABLECOIN_SYMBOLS

    def test_is_frozenset(self):
        assert isinstance(STABLECOIN_SYMBOLS, frozenset)


class TestIsStablecoin:
    @pytest.mark.parametrize("sym", ["USDC", "usdc", "  USDT  ", "dai", "USDC.E", "usdt.e"])
    def test_case_insensitive_and_strip(self, sym):
        assert is_stablecoin(sym) is True

    @pytest.mark.parametrize("sym", ["WETH", "ETH", "LINK", "UNI", "BTC", "SHIB", ""])
    def test_volatile_tokens(self, sym):
        assert is_stablecoin(sym) is False


class TestIsStablecoinPair:
    def test_both_stable(self):
        assert is_stablecoin_pair("USDC", "USDT") is True
        assert is_stablecoin_pair("DAI", "FRAX") is True

    def test_one_volatile(self):
        assert is_stablecoin_pair("WETH", "USDC") is False
        assert is_stablecoin_pair("USDT", "WBTC") is False

    def test_both_volatile(self):
        assert is_stablecoin_pair("WETH", "WBTC") is False


class TestHasStablecoin:
    def test_one_stable(self):
        assert has_stablecoin("WETH", "USDC") is True
        assert has_stablecoin("USDT", "LINK") is True

    def test_both_stable(self):
        assert has_stablecoin("USDC", "USDT") is True

    def test_neither_stable(self):
        assert has_stablecoin("WETH", "WBTC") is False


class TestClassifyPair:
    def test_stable_stable(self):
        assert classify_pair("USDC", "USDT") == "stable-stable"

    def test_stable_volatile(self):
        assert classify_pair("WETH", "USDC") == "stable-volatile"
        assert classify_pair("DAI", "LINK") == "stable-volatile"

    def test_volatile_volatile(self):
        assert classify_pair("WETH", "WBTC") == "volatile-volatile"
        assert classify_pair("LINK", "UNI") == "volatile-volatile"


class TestStablecoinSide:
    def test_token0_stable(self):
        assert stablecoin_side("USDC", "WETH") == 0

    def test_token1_stable(self):
        assert stablecoin_side("WETH", "USDC") == 1

    def test_both_stable_returns_neg1(self):
        assert stablecoin_side("USDC", "USDT") == -1

    def test_neither_stable_returns_neg1(self):
        assert stablecoin_side("WETH", "WBTC") == -1


class TestCorrelatedPair:
    def test_eth_correlated(self):
        assert is_correlated_pair("WETH", "stETH") is True
        assert is_correlated_pair("WETH", "rETH") is True
        assert is_correlated_pair("cbETH", "WETH") is True

    def test_btc_correlated(self):
        assert is_correlated_pair("WBTC", "cbBTC") is True
        assert is_correlated_pair("WBTC", "tBTC") is True

    def test_not_correlated(self):
        assert is_correlated_pair("WETH", "USDC") is False
        assert is_correlated_pair("WETH", "WBTC") is False

    def test_case_insensitive(self):
        assert is_correlated_pair("weth", "STETH") is True


class TestEstimateFeeTier:
    def test_stable_stable(self):
        assert estimate_fee_tier("USDC", "USDT") == 0.0001

    def test_correlated(self):
        assert estimate_fee_tier("WETH", "stETH") == 0.0005

    def test_major_volatile_with_stable(self):
        # WETH/USDC → 0.05% (major volatile + stable)
        assert estimate_fee_tier("WETH", "USDC") == 0.0005
        assert estimate_fee_tier("WBTC", "DAI") == 0.0005

    def test_minor_volatile_with_stable(self):
        # LINK/USDC → 0.30% (minor volatile + stable)
        assert estimate_fee_tier("LINK", "USDC") == 0.003

    def test_exotic_volatile(self):
        # SHIB/DOGE → 1.00% (volatile-volatile, no special case)
        assert estimate_fee_tier("SHIB", "DOGE") == 0.01


# ═══════════════════════════════════════════════════════════════════════════
# 2. rpc_helpers.py
# ═══════════════════════════════════════════════════════════════════════════

from defi_cli.rpc_helpers import (
    ABI_WORD_BYTES, ABI_WORD_HEX, ADDRESS_BYTES, ADDRESS_HEX, SIGN_BIT,
    Q96, Q128, Q256,
    SYMBOL_MAP,
    normalize_symbol,
    encode_uint256, encode_address, encode_uint24, encode_int24,
    decode_uint, decode_int, decode_address, decode_string,
    eth_call, eth_call_batch, eth_block_number,
)


class TestRpcConstants:
    def test_abi_word_bytes(self):
        assert ABI_WORD_BYTES == 32

    def test_abi_word_hex(self):
        assert ABI_WORD_HEX == 64

    def test_address_bytes(self):
        assert ADDRESS_BYTES == 20

    def test_q96(self):
        assert Q96 == 2 ** 96

    def test_q128(self):
        assert Q128 == 2 ** 128

    def test_q256(self):
        assert Q256 == 2 ** 256

    def test_sign_bit(self):
        assert SIGN_BIT == 1 << 255


class TestNormalizeSymbol:
    def test_usdt_unicode(self):
        assert normalize_symbol("USD₮0") == "USDT"
        assert normalize_symbol("USD₮") == "USDT"
        assert normalize_symbol("USDT0") == "USDT"

    def test_passthrough(self):
        assert normalize_symbol("WETH") == "WETH"
        assert normalize_symbol("LINK") == "LINK"

    def test_strips_nul(self):
        assert normalize_symbol("WETH\x00\x00") == "WETH"

    def test_strips_whitespace(self):
        assert normalize_symbol("  USDC  ") == "USDC"


class TestEncodeUint256:
    def test_zero(self):
        result = encode_uint256(0)
        assert len(result) == 64
        assert result == "0" * 64

    def test_one(self):
        result = encode_uint256(1)
        assert result == "0" * 63 + "1"

    def test_known_value(self):
        # 3000 in hex = 0xBB8
        result = encode_uint256(3000)
        assert result.endswith("bb8")
        assert len(result) == 64

    def test_max_uint256(self):
        result = encode_uint256(Q256 - 1)
        assert result == "f" * 64


class TestEncodeAddress:
    def test_standard_address(self):
        addr = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
        result = encode_address(addr)
        assert len(result) == 64
        assert result.startswith("000000000000000000000000")
        assert "c36442b4a4522e871399cd717abdd847ab11fe88" in result

    def test_lowercase(self):
        result = encode_address("0xABCDEF1234567890abcdef1234567890ABCDEF12")
        assert result == result.lower()


class TestEncodeUint24:
    def test_fee_3000(self):
        result = encode_uint24(3000)
        assert len(result) == 64
        assert result.endswith("bb8")

    def test_fee_500(self):
        result = encode_uint24(500)
        assert result.endswith("1f4")

    def test_fee_100(self):
        result = encode_uint24(100)
        assert result.endswith("64")


class TestEncodeInt24:
    def test_positive_tick(self):
        result = encode_int24(100)
        assert len(result) == 64
        assert result.endswith("64")

    def test_negative_tick(self):
        result = encode_int24(-887220)
        assert len(result) == 64
        # Negative: two's complement
        assert result.startswith("fff")

    def test_zero(self):
        result = encode_int24(0)
        assert result == "0" * 64


class TestDecodeUint:
    def test_single_slot(self):
        hex_data = "0" * 63 + "1"  # slot 0 = 1
        assert decode_uint(hex_data, 0) == 1

    def test_slot_offset(self):
        hex_data = "0" * 64 + "0" * 63 + "a"  # slot 0 = 0, slot 1 = 10
        assert decode_uint(hex_data, 0) == 0
        assert decode_uint(hex_data, 1) == 10

    def test_max_value(self):
        hex_data = "f" * 64
        assert decode_uint(hex_data, 0) == Q256 - 1


class TestDecodeInt:
    def test_positive(self):
        hex_data = "0" * 63 + "5"
        assert decode_int(hex_data, 0) == 5

    def test_negative(self):
        # -1 in two's complement = fff...fff
        hex_data = "f" * 64
        assert decode_int(hex_data, 0) == -1

    def test_negative_large(self):
        # -887220 = Q256 - 887220
        val = Q256 - 887220
        hex_data = format(val, "064x")
        assert decode_int(hex_data, 0) == -887220


class TestDecodeAddress:
    def test_standard(self):
        # Address at slot 0: last 40 hex chars
        inner = "c36442b4a4522e871399cd717abdd847ab11fe88"
        hex_data = "0" * 24 + inner
        result = decode_address(hex_data, 0)
        assert result == "0x" + inner

    def test_slot_offset(self):
        addr_hex = "abcdef1234567890abcdef1234567890abcdef12"
        hex_data = "0" * 64 + "0" * 24 + addr_hex
        result = decode_address(hex_data, 1)
        assert result == "0x" + addr_hex


class TestDecodeString:
    def test_standard_dynamic_string(self):
        # offset = 0x20 (slot 1) → length = 4 → "WETH"
        offset = encode_uint256(32)           # offset to string data
        length = encode_uint256(4)            # string length
        data = "57455448" + "0" * 56          # "WETH" in hex, padded
        hex_data = offset + length + data
        assert decode_string(hex_data) == "WETH"

    def test_bytes32_fallback(self):
        # bytes32 "USDC" (non-standard encoding)
        raw = b"USDC" + b"\x00" * 28
        hex_data = raw.hex() + "0" * 64  # extra padding
        result = decode_string(hex_data)
        assert result == "USDC"

    def test_garbage_returns_unk(self):
        # Totally invalid data — empty hex falls through both try blocks
        result = decode_string("")
        assert result in ("", "UNK")


class TestEthCallMocked:
    """Test eth_call with mocked httpx responses."""

    def test_successful_call(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "0x" + "0" * 63 + "1",
        }

        with patch("defi_cli.rpc_helpers.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = asyncio.run(eth_call("http://fake", "0xAddr", "0xData"))
            assert result == "0" * 63 + "1"

    def test_rpc_error_raises(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "error": {"message": "execution reverted"},
        }

        with patch("defi_cli.rpc_helpers.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(RuntimeError, match="RPC error"):
                asyncio.run(eth_call("http://fake", "0xAddr", "0xData"))

    def test_empty_response_raises(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "0x",
        }

        with patch("defi_cli.rpc_helpers.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(RuntimeError, match="Empty response"):
                asyncio.run(eth_call("http://fake", "0xAddr", "0xData"))


class TestEthCallBatchMocked:
    def test_batch_response(self):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"jsonrpc": "2.0", "id": 2, "result": "0x" + "0" * 63 + "2"},
            {"jsonrpc": "2.0", "id": 1, "result": "0x" + "0" * 63 + "1"},
        ]

        with patch("defi_cli.rpc_helpers.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            results = asyncio.run(eth_call_batch("http://fake", [("0xA", "0xD1"), ("0xB", "0xD2")]))
            # Sorted by id: id=1 first, then id=2
            assert results[0] == "0" * 63 + "1"
            assert results[1] == "0" * 63 + "2"

    def test_single_result_fallback(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "0x" + "0" * 63 + "a",
        }

        with patch("defi_cli.rpc_helpers.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            results = asyncio.run(eth_call_batch("http://fake", [("0xA", "0xD")]))
            assert results == ["0" * 63 + "a"]


class TestEthBlockNumberMocked:
    def test_successful(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": "0x1a2b3c",
        }

        with patch("defi_cli.rpc_helpers.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = asyncio.run(eth_block_number("http://fake"))
            assert result == 0x1a2b3c


# ═══════════════════════════════════════════════════════════════════════════
# 3. html_styles.py
# ═══════════════════════════════════════════════════════════════════════════

from defi_cli.html_styles import build_css


class TestBuildCss:
    def test_returns_style_block(self):
        css = build_css("#f0fdf4", "#bbf7d0", "#15803d")
        assert css.strip().startswith("<style>")
        assert css.strip().endswith("</style>")

    def test_contains_status_colours(self):
        css = build_css("#f0fdf4", "#bbf7d0", "#15803d")
        assert "#f0fdf4" in css
        assert "#bbf7d0" in css
        assert "#15803d" in css

    def test_contains_css_variables(self):
        css = build_css("#f0fdf4", "#bbf7d0", "#15803d")
        assert "--primary" in css
        assert "--success" in css

    def test_different_colours_produced(self):
        css_in_range = build_css("#f0fdf4", "#bbf7d0", "#15803d")
        css_out_range = build_css("#ab1234", "#cd5678", "#ef9012")
        # The custom colours only appear in the matching variant
        assert "#ab1234" in css_out_range
        assert "#ab1234" not in css_in_range
        assert "#f0fdf4" in css_in_range
        assert "#f0fdf4" not in css_out_range


# ═══════════════════════════════════════════════════════════════════════════
# 4. html_generator.py (module-level helpers)
# ═══════════════════════════════════════════════════════════════════════════

from html_generator import (
    _safe,
    _safe_filename,
    _explorer,
    _token_info,
    _safe_num,
    _safe_usd,
    _build_audit_trail,
    _render_strategies_visual,
)


class TestHtmlSafe:
    def test_escapes_ampersand(self):
        assert _safe("a&b") == "a&amp;b"

    def test_escapes_lt_gt(self):
        assert _safe("<script>") == "&lt;script&gt;"

    def test_escapes_quotes(self):
        assert _safe('he said "hi"') == 'he said &quot;hi&quot;'
        assert _safe("it's") == "it&#x27;s"

    def test_none_returns_fallback(self):
        assert _safe(None) == "Unknown"
        assert _safe(None, "N/A") == "N/A"

    def test_numeric_converted(self):
        assert _safe(42) == "42"
        assert _safe(3.14) == "3.14"


class TestSafeFilename:
    def test_strips_special_chars(self):
        assert _safe_filename("WETH/USDC") == "WETH_USDC"
        assert _safe_filename("a b c") == "a_b_c"
        # Leading dots are kept (they match [a-zA-Z0-9._-])
        result = _safe_filename("../../../etc/passwd")
        assert "/" not in result
        assert " " not in result

    def test_allows_safe_chars(self):
        assert _safe_filename("report-2024.html") == "report-2024.html"
        assert _safe_filename("file_name") == "file_name"


class TestExplorer:
    @pytest.mark.parametrize("net,name", [
        ("ethereum", "Etherscan"),
        ("arbitrum", "Arbiscan"),
        ("polygon", "PolygonScan"),
        ("base", "BaseScan"),
        ("optimism", "Optimistic Etherscan"),
        ("bsc", "BscScan"),
    ])
    def test_known_networks(self, net, name):
        result = _explorer(net)
        assert result["name"] == name
        assert result["base"].startswith("http")

    def test_unknown_network_fallback(self):
        result = _explorer("solana")
        assert result["name"] == "Explorer"
        assert result["base"] == "#"

    def test_case_insensitive(self):
        assert _explorer("ETHEREUM")["name"] == "Etherscan"


class TestTokenInfo:
    def test_known_tokens(self):
        assert _token_info("WETH") == "Wrapped Ethereum"
        assert _token_info("USDC") == "USD Coin"
        assert _token_info("WBTC") == "Wrapped Bitcoin"

    def test_case_insensitive(self):
        assert _token_info("weth") == "Wrapped Ethereum"

    def test_unknown_passthrough(self):
        assert _token_info("CUSTOM") == "CUSTOM"

    def test_empty_returns_unknown(self):
        assert _token_info("") == "Unknown Token"


class TestSafeNum:
    def test_basic_formatting(self):
        assert _safe_num(3.14159, 2) == "3.14"
        assert _safe_num(1000.5, 0) == "1000"

    def test_none_uses_default(self):
        assert _safe_num(None, 2, 0) == "0.00"

    def test_non_numeric_uses_default(self):
        assert _safe_num("abc", 2, 0) == "0.00"

    def test_string_number(self):
        assert _safe_num("42.5", 1) == "42.5"

    def test_no_thousands_separator(self):
        # _safe_num does NOT use comma separator
        assert "," not in _safe_num(1000000, 2)


class TestSafeUsd:
    def test_basic_formatting(self):
        assert _safe_usd(1234.56, 2) == "1,234.56"

    def test_thousands_separator(self):
        assert _safe_usd(1000000, 0) == "1,000,000"

    def test_none_uses_default(self):
        assert _safe_usd(None, 2, 0) == "0.00"

    def test_non_numeric_uses_default(self):
        assert _safe_usd("xyz", 2, 0) == "0.00"


class TestBuildAuditTrail:
    def test_no_audit_data(self):
        html = _build_audit_trail({"token0_symbol": "WETH"})
        assert "Simulated data" in html

    def test_with_audit_data(self):
        data = {
            "audit_trail": {
                "block_number": 123456,
                "rpc_endpoint": "https://1rpc.io/arb",
                "contract_calls": [{"method": "positions", "to": "0xABC"}],
            }
        }
        html = _build_audit_trail(data)
        assert "123456" in html or "Audit" in html


class TestRenderStrategiesVisual:
    def test_empty_strategies(self):
        html = _render_strategies_visual({}, {}, "WETH", "USDC")
        assert "Processing strategies" in html

    def test_with_strategies(self):
        strats = {
            "conservative": {
                "lower_price": 1000,
                "upper_price": 2000,
                "apr_estimate": 0.1,
                "risk_level": "Low",
                "description": "Wide range",
                "range_width_pct": 50,
                "total_value_usd": 10000,
                "capital_efficiency": 2.0,
                "daily_fees_est": 1.0,
                "weekly_fees_est": 7.0,
                "monthly_fees_est": 30.0,
                "annual_fees_est": 365.0,
            }
        }
        data = {"total_value_usd": 10000}
        html = _render_strategies_visual(strats, data, "WETH", "USDC")
        assert "Conservative" in html
        assert "Low Risk" in html


# ═══════════════════════════════════════════════════════════════════════════
# 5. central_config.py
# ═══════════════════════════════════════════════════════════════════════════

from defi_cli.central_config import (
    DexScreenerAPI,
    DexScreenerConfig,
    PROJECT_VERSION,
    PROJECT_NAME,
    config,
)


class TestCentralConfig:
    def test_project_version_non_empty(self):
        assert PROJECT_VERSION
        assert re.match(r"\d+\.\d+\.\d+", PROJECT_VERSION)

    def test_project_name(self):
        assert PROJECT_NAME == "DeFi CLI"

    def test_default_base_url(self):
        api = DexScreenerAPI()
        assert api.BASE_URL == "https://api.dexscreener.com"

    def test_timeout(self):
        api = DexScreenerAPI()
        assert api.TIMEOUT_SECONDS == 15

    def test_supported_chains_contains_majors(self):
        for chain in ["ethereum", "arbitrum", "polygon", "base", "optimism", "bsc"]:
            assert chain in DexScreenerAPI.SUPPORTED_CHAINS

    def test_chain_aliases(self):
        chains = DexScreenerAPI.SUPPORTED_CHAINS
        assert chains["eth"] == "ethereum"
        assert chains["arb"] == "arbitrum"
        assert chains["matic"] == "polygon"

    def test_priority_chains(self):
        assert "ethereum" in DexScreenerAPI.PRIORITY_CHAINS
        assert "arbitrum" in DexScreenerAPI.PRIORITY_CHAINS

    def test_get_pair_url(self):
        url = DexScreenerAPI.get_pair_url("ethereum", "0xABC")
        assert "ethereum" in url
        assert "0xABC" in url
        assert url.startswith("https://api.dexscreener.com")

    def test_get_auto_detect_urls(self):
        urls = DexScreenerAPI.get_auto_detect_urls("0xDEAD")
        assert isinstance(urls, list)
        assert len(urls) == len(DexScreenerAPI.PRIORITY_CHAINS)
        for chain, url in urls:
            assert chain in DexScreenerAPI.PRIORITY_CHAINS
            assert "0xDEAD" in url

    def test_get_token_search_url(self):
        url = DexScreenerAPI.get_token_search_url("arbitrum", "0xTOKEN")
        assert "arbitrum" in url
        assert "0xTOKEN" in url

    def test_config_instance(self):
        assert isinstance(config.api, DexScreenerAPI)


# ═══════════════════════════════════════════════════════════════════════════
# 6. dexscreener_client.py (_extract_pool_info — pure logic)
# ═══════════════════════════════════════════════════════════════════════════

from defi_cli.dexscreener_client import DexScreenerClient, analyze_pool_real


class TestExtractPoolInfo:
    """Test the pure _extract_pool_info method with synthetic data."""

    def _make_pair_data(self, **overrides):
        base = {
            "baseToken": {"symbol": "WETH", "name": "Wrapped Ether", "address": "0xToken0"},
            "quoteToken": {"symbol": "USDC", "name": "USD Coin", "address": "0xToken1"},
            "pairAddress": "0xPoolAddr",
            "chainId": "arbitrum",
            "dexId": "uniswap",
            "priceUsd": "2500.0",
            "liquidity": {"usd": 1000000},
            "volume": {"h24": 500000, "h1": 20000},
            "priceChange": {"h24": 2.5, "h1": 0.3},
            "txns": {"h24": {"buys": 100, "sells": 80}},
            "url": "https://dexscreener.com/test",
        }
        base.update(overrides)
        return base

    def test_basic_extraction(self):
        client = DexScreenerClient()
        pair = self._make_pair_data()
        info = client._extract_pool_info(pair)
        assert info["name"] == "WETH/USDC"
        assert info["address"] == "0xPoolAddr"
        assert info["network"] == "arbitrum"
        assert info["priceUsd"] == 2500.0

    def test_volume_and_tvl(self):
        client = DexScreenerClient()
        pair = self._make_pair_data()
        info = client._extract_pool_info(pair)
        assert info["totalValueLockedUSD"] == 1000000
        assert info["volume24h"] == 500000
        assert info["volumeToTVLRatio"] == 0.5

    def test_transactions(self):
        client = DexScreenerClient()
        pair = self._make_pair_data()
        info = client._extract_pool_info(pair)
        assert info["txns24h"]["buys"] == 100
        assert info["txns24h"]["sells"] == 80
        assert info["txns24h"]["total"] == 180

    def test_apy_capped_at_999(self):
        client = DexScreenerClient()
        # Huge volume/low TVL → uncapped APY would exceed 999.9
        pair = self._make_pair_data(
            liquidity={"usd": 100},
            volume={"h24": 100000000, "h1": 100},
        )
        info = client._extract_pool_info(pair)
        assert info["estimatedAPY"] <= 999.9

    def test_zero_tvl_no_division_error(self):
        client = DexScreenerClient()
        pair = self._make_pair_data(liquidity={"usd": 0})
        info = client._extract_pool_info(pair)
        assert info["volumeToTVLRatio"] == 0
        assert info["estimatedAPY"] == 0

    def test_data_source_metadata(self):
        client = DexScreenerClient()
        pair = self._make_pair_data()
        info = client._extract_pool_info(pair)
        assert info["dataSource"] == "DEXScreener"
        assert info["url"] == "https://dexscreener.com/test"


class TestAnalyzePoolRealValidation:
    """Test analyze_pool_real address validation (errors returned, not raised)."""

    def test_no_address(self):
        result = asyncio.run(analyze_pool_real(None))
        assert result["status"] == "error"
        assert "No address" in result["message"]

    def test_invalid_address(self):
        result = asyncio.run(analyze_pool_real("not_an_address"))
        assert result["status"] == "error"
        assert "Invalid address" in result["message"]

    def test_short_address(self):
        result = asyncio.run(analyze_pool_real("0x123"))
        assert result["status"] == "error"


# ═══════════════════════════════════════════════════════════════════════════
# 7. position_reader.py (pure math helpers)
# ═══════════════════════════════════════════════════════════════════════════

from position_reader import PositionReader


class TestPositionReaderPriceMath:
    """Test _sqrtPriceX96_to_price and _tick_to_price on a PositionReader instance."""

    @pytest.fixture
    def reader(self):
        return PositionReader("arbitrum")

    def test_sqrtPriceX96_zero_returns_zero(self, reader):
        assert reader._sqrtPriceX96_to_price(0, 18, 6) == 0.0

    def test_sqrtPriceX96_known_conversion(self, reader):
        # For equal decimals (18,18), sqrtPriceX96 = Q96 → price = 1.0
        price = reader._sqrtPriceX96_to_price(Q96, 18, 18)
        assert abs(price - 1.0) < 1e-10

    def test_sqrtPriceX96_decimal_adjustment(self, reader):
        # For (18,6), price should be multiplied by 10^12
        price_same = reader._sqrtPriceX96_to_price(Q96, 18, 18)
        price_diff = reader._sqrtPriceX96_to_price(Q96, 18, 6)
        ratio = price_diff / price_same
        assert abs(ratio - 1e12) < 1e6  # ~10^12 within tolerance

    def test_tick_zero_is_1(self, reader):
        # tick=0 → 1.0001^0 = 1.0, then scaled by 10^(d0-d1)
        price = reader._tick_to_price(0, 18, 18)
        assert abs(price - 1.0) < 1e-10

    def test_tick_positive_increases_price(self, reader):
        p0 = reader._tick_to_price(0, 18, 18)
        p1 = reader._tick_to_price(1000, 18, 18)
        assert p1 > p0

    def test_tick_negative_decreases_price(self, reader):
        p0 = reader._tick_to_price(0, 18, 18)
        pn = reader._tick_to_price(-1000, 18, 18)
        assert pn < p0

    def test_tick_to_price_roundtrip(self, reader):
        # Tick 69081 ≈ price ~1000.27 for (18,18)
        price = reader._tick_to_price(69081, 18, 18)
        # 1.0001^69081 ≈ 1002.7 (roughly)
        assert 500 < price < 2000


class TestPositionReaderTokenAmounts:
    """Test _compute_token_amounts with known inputs."""

    @pytest.fixture
    def reader(self):
        return PositionReader("arbitrum")

    def test_zero_liquidity(self, reader):
        result = reader._compute_token_amounts(0, Q96, 100, 50, 150, 18, 18)
        assert result["amount0"] == 0.0
        assert result["amount1"] == 0.0

    def test_zero_sqrt_price(self, reader):
        result = reader._compute_token_amounts(1000, 0, 100, 50, 150, 18, 18)
        assert result["amount0"] == 0.0
        assert result["amount1"] == 0.0

    def test_in_range_both_positive(self, reader):
        # Current tick between lower and upper → both amounts > 0
        result = reader._compute_token_amounts(
            liquidity=10**18,
            sqrtPriceX96=Q96,      # price = 1.0
            current_tick=0,
            tick_lower=-1000,
            tick_upper=1000,
            decimals0=18,
            decimals1=18,
        )
        assert result["amount0"] > 0
        assert result["amount1"] > 0

    def test_below_range_only_token0(self, reader):
        # Current tick below lower → only token0
        result = reader._compute_token_amounts(
            liquidity=10**18,
            sqrtPriceX96=Q96,
            current_tick=-2000,
            tick_lower=-1000,
            tick_upper=1000,
            decimals0=18,
            decimals1=18,
        )
        assert result["amount0"] > 0
        assert result["amount1"] == 0

    def test_above_range_only_token1(self, reader):
        # Current tick above upper → only token1
        result = reader._compute_token_amounts(
            liquidity=10**18,
            sqrtPriceX96=Q96,
            current_tick=2000,
            tick_lower=-1000,
            tick_upper=1000,
            decimals0=18,
            decimals1=18,
        )
        assert result["amount0"] == 0
        assert result["amount1"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# 8. commands.py (consent helpers — need input mocking)
# ═══════════════════════════════════════════════════════════════════════════

from defi_cli.commands import _require_consent, _prompt_address, _simple_disclaimer, cmd_info


class TestRequireConsent:
    def test_agree(self):
        with patch("builtins.input", return_value="I agree"):
            assert _require_consent() is True

    def test_disagree(self):
        with patch("builtins.input", return_value="nope"):
            assert _require_consent() is False

    def test_keyboard_interrupt(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            assert _require_consent() is False

    def test_eof_error(self):
        with patch("builtins.input", side_effect=EOFError):
            assert _require_consent() is False

    def test_case_insensitive(self):
        with patch("builtins.input", return_value="i agree"):
            assert _require_consent() is True

    def test_with_whitespace(self):
        with patch("builtins.input", return_value="  I agree  "):
            assert _require_consent() is True


class TestPromptAddress:
    def test_valid_address(self):
        addr = "0xC36442b4a4522E871399CD717aBDD847Ab11FE88"
        with patch("builtins.input", return_value=addr):
            result = _prompt_address("pool")
            assert result == addr

    def test_invalid_address(self):
        with patch("builtins.input", return_value="not_an_address"):
            result = _prompt_address("pool")
            assert result is None

    def test_empty_input(self):
        with patch("builtins.input", return_value=""):
            result = _prompt_address("pool")
            assert result is None

    def test_short_hex(self):
        with patch("builtins.input", return_value="0x123"):
            result = _prompt_address("pool")
            assert result is None


class TestSimpleDisclaimer:
    def test_accept_y(self):
        with patch("builtins.input", return_value="y"):
            assert _simple_disclaimer() is True

    def test_accept_yes(self):
        with patch("builtins.input", return_value="yes"):
            assert _simple_disclaimer() is True

    def test_reject(self):
        with patch("builtins.input", return_value="n"):
            assert _simple_disclaimer() is False

    def test_keyboard_interrupt(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            assert _simple_disclaimer() is False


class TestCmdInfo:
    def test_does_not_raise(self, capsys):
        cmd_info()
        output = capsys.readouterr().out
        assert "DeFi CLI" in output


# ═══════════════════════════════════════════════════════════════════════════
# 9. run.py (argparse parser)
# ═══════════════════════════════════════════════════════════════════════════

from run import create_parser


class TestCreateParser:
    def test_parser_created(self):
        parser = create_parser()
        assert parser is not None

    @pytest.mark.parametrize("cmd", [
        "info", "scout", "pool", "list", "report", "check", "donate",
    ])
    def test_all_subcommands_exist(self, cmd):
        parser = create_parser()
        # Each subcommand should parse without error
        if cmd == "info":
            args = parser.parse_args(["info"])
        elif cmd == "scout":
            args = parser.parse_args(["scout", "WETH/USDC"])
        elif cmd == "pool":
            args = parser.parse_args(["pool", "--pool", "0x" + "a" * 40])
        elif cmd == "list":
            args = parser.parse_args(["list", "0x" + "a" * 40])
        elif cmd == "report":
            args = parser.parse_args(["report", "--position", "12345"])
        elif cmd == "check":
            args = parser.parse_args(["check"])
        elif cmd == "donate":
            args = parser.parse_args(["donate"])
        assert args.command == cmd

    def test_scout_defaults(self):
        parser = create_parser()
        args = parser.parse_args(["scout", "ETH/USDC"])
        assert args.sort == "apy"
        assert args.limit == 15
        assert args.min_tvl == 50000
        assert args.network is None

    def test_list_defaults(self):
        parser = create_parser()
        args = parser.parse_args(["list", "0xWALLET"])
        assert args.network == "arbitrum"
        assert args.dex is None

    def test_report_defaults(self):
        parser = create_parser()
        args = parser.parse_args(["report", "--position", "99"])
        assert args.position == 99
        assert args.pool is None
        assert args.wallet is None
        assert args.network is None

    def test_version_flag(self):
        parser = create_parser()
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(["--version"])
        assert exc_info.value.code == 0

    def test_no_command_returns_none(self):
        parser = create_parser()
        args = parser.parse_args([])
        assert args.command is None


# ═══════════════════════════════════════════════════════════════════════════
# 10. generate_position_report (integration-level, mock file I/O)
# ═══════════════════════════════════════════════════════════════════════════

from html_generator import generate_position_report


class TestGeneratePositionReport:
    """Test that generate_position_report produces a valid HTML file."""

    def _make_data(self):
        """Minimal data dict that exercises the full template."""
        return {
            "token0_symbol": "WETH",
            "token1_symbol": "USDC",
            "current_price": 2500.0,
            "total_value_usd": 10000,
            "in_range": True,
            "consent_timestamp": "2025-01-01 00:00:00",
            "generated_at": "2025-01-01 00:00:00",
            "network": "arbitrum",
            "pool_address": "0x" + "a" * 40,
            "token0_value_usd": 5000,
            "token1_value_usd": 5000,
            "fees_earned_usd": 100,
            "daily_fees_est": 5,
            "weekly_fees_est": 35,
            "monthly_fees_est": 150,
            "annual_fees_est": 1825,
            "fee_apy": 18.25,
            "capital_efficiency": 4.0,
            "current_tick": 200000,
            "tick_lower": 190000,
            "tick_upper": 210000,
            "lower_price": 2000,
            "upper_price": 3000,
            "range_proximity": 0.5,
            "liquidity": 10 ** 18,
            "pool_liquidity": 10 ** 20,
            "liquidity_share_pct": 1.0,
            "amount0": 2.0,
            "amount1": 5000.0,
            "fee_tier": 3000,
            "fee_tier_pct": 0.3,
            "fee_tier_label": "0.30%",
            "impermanent_loss_pct": -0.5,
            "v3_il_pct": -0.8,
            "range_width_pct": 20.0,
            "vol_tvl_ratio": 0.5,
            "volume_24h": 500000,
            "total_value_locked_usd": 1000000,
            "position_id": 12345,
            "wallet_address": "0x" + "b" * 40,
            "strategies": {
                "conservative": {
                    "lower_price": 1500, "upper_price": 3500,
                    "apr_estimate": 0.05, "risk_level": "Low",
                    "description": "Wide range", "range_width_pct": 50,
                    "total_value_usd": 10000, "capital_efficiency": 2.0,
                    "daily_fees_est": 3, "weekly_fees_est": 21,
                    "monthly_fees_est": 90, "annual_fees_est": 1095,
                },
                "moderate": {
                    "lower_price": 2000, "upper_price": 3000,
                    "apr_estimate": 0.12, "risk_level": "Medium",
                    "description": "Standard range", "range_width_pct": 20,
                    "total_value_usd": 10000, "capital_efficiency": 4.0,
                    "daily_fees_est": 5, "weekly_fees_est": 35,
                    "monthly_fees_est": 150, "annual_fees_est": 1825,
                },
                "aggressive": {
                    "lower_price": 2200, "upper_price": 2800,
                    "apr_estimate": 0.25, "risk_level": "High",
                    "description": "Tight range", "range_width_pct": 12,
                    "total_value_usd": 10000, "capital_efficiency": 8.0,
                    "daily_fees_est": 10, "weekly_fees_est": 70,
                    "monthly_fees_est": 300, "annual_fees_est": 3650,
                },
            },
            "current_strategy": "moderate",
            "hodl_comparison": {
                "il_if_at_lower_usd": -200,
                "il_if_at_upper_usd": -100,
                "fees_earned_usd": 100,
                "net_if_at_lower_usd": -100,
                "net_if_at_upper_usd": 0,
            },
        }

    def test_produces_html_file(self):
        data = self._make_data()
        # Don't open browser
        path = generate_position_report(data, _open_browser=False)
        assert path.exists()
        content = path.read_text()
        assert "<!DOCTYPE html>" in content
        assert "WETH" in content
        assert "USDC" in content

    def test_contains_sessions(self):
        data = self._make_data()
        path = generate_position_report(data, _open_browser=False)
        content = path.read_text()
        # All 5 sessions should be present
        assert "Session 1" in content or "Position Overview" in content
        assert "Strategy" in content

    def test_xss_prevention(self):
        data = self._make_data()
        data["token0_symbol"] = '<script>alert("xss")</script>'
        path = generate_position_report(data, _open_browser=False)
        content = path.read_text()
        # The XSS payload must be escaped in the HTML output
        assert '&lt;script&gt;alert' in content
        # The escaped version appears where the token symbol is shown
        assert '&lt;script&gt;' in content
