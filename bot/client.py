"""
client.py — Low-level Binance Futures Testnet REST client.

Responsibilities:
  - HMAC-SHA256 request signing
  - HTTP request dispatch with retry logic
  - Raw JSON response parsing
  - Translating HTTP / API errors into typed exceptions

No business logic lives here.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from bot.config import (
    BINANCE_API_KEY,
    BINANCE_SECRET_KEY,
    MAX_RETRIES,
    REQUEST_TIMEOUT,
    RETRY_DELAY,
    TESTNET_BASE_URL,
)
from bot.exceptions import AuthenticationError, BinanceClientError, ConfigurationError, NetworkError
from bot.logging_config import logger


class BinanceFuturesClient:
    """Signed REST client for Binance USDT-M Futures Testnet."""

    # Endpoints
    _PING = "/fapi/v1/ping"
    _SERVER_TIME = "/fapi/v1/time"
    _EXCHANGE_INFO = "/fapi/v1/exchangeInfo"
    _NEW_ORDER = "/fapi/v1/order"

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or BINANCE_API_KEY
        self._secret_key = secret_key or BINANCE_SECRET_KEY
        self._base_url = (base_url or TESTNET_BASE_URL).rstrip("/")

        if not self._api_key or not self._secret_key:
            raise ConfigurationError(
                "BINANCE_API_KEY and BINANCE_SECRET_KEY must be set in .env "
                "or passed explicitly."
            )

        self._session = self._build_session()
        logger.info("BinanceFuturesClient initialised. Base URL: %s", self._base_url)

    # ── Session / retry setup ─────────────────────────────────────────────────

    def _build_session(self) -> requests.Session:
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=RETRY_DELAY,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.headers.update(
            {
                "X-MBX-APIKEY": self._api_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )
        return session

    # ── Signing helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _timestamp() -> int:
        return int(time.time() * 1000)

    def _sign(self, params: dict) -> str:
        query = urlencode(params)
        return hmac.new(
            self._secret_key.encode("utf-8"),
            query.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _signed_params(self, params: dict) -> dict:
        params["timestamp"] = self._timestamp()
        params["signature"] = self._sign(params)
        return params

    # ── HTTP dispatch ─────────────────────────────────────────────────────────

    def _request(self, method: str, endpoint: str, params: dict | None = None, signed: bool = False) -> Any:
        url = f"{self._base_url}{endpoint}"
        params = dict(params or {})

        if signed:
            params = self._signed_params(params)

        logger.debug("→ %s %s  params=%s", method.upper(), endpoint, {k: v for k, v in params.items() if k != "signature"})

        try:
            if method.upper() == "GET":
                response = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            elif method.upper() == "POST":
                response = self._session.post(url, data=params, timeout=REQUEST_TIMEOUT)
            elif method.upper() == "DELETE":
                response = self._session.delete(url, params=params, timeout=REQUEST_TIMEOUT)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
        except requests.exceptions.Timeout:
            logger.error("Request timed out: %s %s", method, endpoint)
            raise NetworkError(f"Request timed out after {REQUEST_TIMEOUT}s: {method} {endpoint}")
        except requests.exceptions.ConnectionError as exc:
            logger.error("Connection error: %s", exc)
            raise NetworkError(f"Connection failed: {exc}")
        except requests.exceptions.RequestException as exc:
            logger.error("Unexpected requests error: %s", exc)
            raise NetworkError(f"Network error: {exc}")

        logger.debug("← HTTP %s  body=%s", response.status_code, response.text[:500])

        return self._parse_response(response)

    def _parse_response(self, response: requests.Response) -> Any:
        try:
            data = response.json()
        except ValueError:
            raise BinanceClientError(
                f"Non-JSON response (HTTP {response.status_code}): {response.text[:200]}",
                status_code=response.status_code,
            )

        # Binance error: {"code": -XXXX, "msg": "..."}
        if isinstance(data, dict) and "code" in data and data["code"] != 200:
            error_code = data["code"]
            msg = data.get("msg", "Unknown Binance error")
            logger.error("Binance API error %s: %s", error_code, msg)

            if error_code in (-2014, -2015, -1102):
                raise AuthenticationError(f"Authentication failed ({error_code}): {msg}")

            raise BinanceClientError(
                msg, status_code=response.status_code, error_code=error_code
            )

        if not response.ok:
            raise BinanceClientError(
                f"HTTP {response.status_code}: {response.text[:200]}",
                status_code=response.status_code,
            )

        return data

    # ── Public API ────────────────────────────────────────────────────────────

    def ping(self) -> bool:
        """Returns True if testnet is reachable."""
        self._request("GET", self._PING)
        logger.info("Ping successful.")
        return True

    def get_server_time(self) -> int:
        """Returns Binance server time in milliseconds."""
        data = self._request("GET", self._SERVER_TIME)
        return data["serverTime"]

    def get_exchange_info(self) -> dict:
        """Returns exchange metadata (symbols, filters, etc.)."""
        return self._request("GET", self._EXCHANGE_INFO)

    def place_market_order(self, symbol: str, side: str, quantity: float) -> dict:
        """
        Submit a MARKET order.

        Returns the raw Binance response dict.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }
        logger.info(
            "Placing MARKET order: symbol=%s side=%s qty=%s",
            symbol, side, quantity,
        )
        return self._request("POST", self._NEW_ORDER, params=params, signed=True)

    def place_limit_order(
        self, symbol: str, side: str, quantity: float, price: float, time_in_force: str = "GTC"
    ) -> dict:
        """
        Submit a LIMIT order.

        Returns the raw Binance response dict.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "LIMIT",
            "quantity": quantity,
            "price": price,
            "timeInForce": time_in_force,
        }
        logger.info(
            "Placing LIMIT order: symbol=%s side=%s qty=%s price=%s tif=%s",
            symbol, side, quantity, price, time_in_force,
        )
        return self._request("POST", self._NEW_ORDER, params=params, signed=True)

    def place_stop_market_order(
        self, symbol: str, side: str, quantity: float, stop_price: float
    ) -> dict:
        """
        Submit a STOP_MARKET order (bonus order type).

        Returns the raw Binance response dict.
        """
        params = {
            "symbol": symbol,
            "side": side,
            "type": "STOP_MARKET",
            "quantity": quantity,
            "stopPrice": stop_price,
        }
        logger.info(
            "Placing STOP_MARKET order: symbol=%s side=%s qty=%s stop=%s",
            symbol, side, quantity, stop_price,
        )
        return self._request("POST", self._NEW_ORDER, params=params, signed=True)
