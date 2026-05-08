"""
orders.py — Order service layer.

Sits between CLI and the raw Binance client.
Responsibilities:
  - Orchestrate validate → build payload → call client → process response
  - Return a normalised OrderResult dataclass (no raw dicts leak to CLI)
  - Log every meaningful step
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bot.client import BinanceFuturesClient
from bot.config import TIME_IN_FORCE
from bot.exceptions import BinanceClientError, NetworkError, ValidationError
from bot.logging_config import logger
from bot.validators import validate_order_params


@dataclass
class OrderResult:
    """Normalised representation of a Binance order response."""

    success: bool
    order_id: int | None = None
    client_order_id: str | None = None
    symbol: str = ""
    side: str = ""
    order_type: str = ""
    orig_qty: str = ""
    executed_qty: str = ""
    avg_price: str = ""
    status: str = ""
    error_message: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_response(cls, data: dict) -> "OrderResult":
        return cls(
            success=True,
            order_id=data.get("orderId"),
            client_order_id=data.get("clientOrderId"),
            symbol=data.get("symbol", ""),
            side=data.get("side", ""),
            order_type=data.get("type", ""),
            orig_qty=data.get("origQty", ""),
            executed_qty=data.get("executedQty", ""),
            avg_price=data.get("avgPrice", "0"),
            status=data.get("status", ""),
            raw=data,
        )

    @classmethod
    def from_error(cls, message: str) -> "OrderResult":
        return cls(success=False, error_message=message)


class OrderService:
    """
    High-level order service.

    Accepts raw (unvalidated) parameters, validates them, dispatches
    to the correct client method, and returns an OrderResult.
    """

    def __init__(self, client: BinanceFuturesClient | None = None) -> None:
        self._client = client or BinanceFuturesClient()

    def create_order(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float | str,
        price: float | str | None = None,
        stop_price: float | str | None = None,
    ) -> OrderResult:
        """
        Validate parameters and place the appropriate order.

        Returns an OrderResult (never raises — all exceptions are caught
        and surfaced via OrderResult.error_message + success=False).
        """
        logger.info(
            "create_order called: symbol=%s side=%s type=%s qty=%s price=%s stop=%s",
            symbol, side, order_type, quantity, price, stop_price,
        )

        # ── 1. Validate ───────────────────────────────────────────────────────
        try:
            params = validate_order_params(
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
            )
        except ValidationError as exc:
            logger.error("Validation failed: %s", exc)
            return OrderResult.from_error(f"Validation error: {exc}")

        # ── 2. Dispatch to correct order type ─────────────────────────────────
        try:
            raw = self._dispatch(params)
        except ValidationError as exc:
            logger.error("Order placement validation error: %s", exc)
            return OrderResult.from_error(str(exc))
        except BinanceClientError as exc:
            logger.error("Binance API error: %s", exc)
            return OrderResult.from_error(f"Binance API error: {exc}")
        except NetworkError as exc:
            logger.error("Network error: %s", exc)
            return OrderResult.from_error(f"Network error: {exc}")
        except Exception as exc:          # noqa: BLE001
            logger.exception("Unexpected error during order placement.")
            return OrderResult.from_error(f"Unexpected error: {exc}")

        # ── 3. Normalise and return ───────────────────────────────────────────
        result = OrderResult.from_response(raw)
        logger.info(
            "Order placed successfully: orderId=%s status=%s",
            result.order_id, result.status,
        )
        return result

    def _dispatch(self, params: dict) -> dict[str, Any]:
        ot = params["order_type"]
        sym = params["symbol"]
        side = params["side"]
        qty = params["quantity"]

        if ot == "MARKET":
            return self._client.place_market_order(sym, side, qty)

        elif ot == "LIMIT":
            return self._client.place_limit_order(
                sym, side, qty, params["price"], TIME_IN_FORCE
            )

        elif ot == "STOP_MARKET":
            return self._client.place_stop_market_order(
                sym, side, qty, params["stop_price"]
            )

        else:
            raise ValidationError(f"Unsupported order type in dispatcher: {ot}")
