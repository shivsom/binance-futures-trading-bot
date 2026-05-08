"""
validators.py — Input validation for order parameters.

All functions raise ValidationError on failure so callers never need to
handle raw assertion errors or ad-hoc value checks.
"""

from __future__ import annotations

from bot.config import VALID_SIDES, VALID_ORDER_TYPES
from bot.exceptions import ValidationError
from bot.logging_config import logger


def validate_symbol(symbol: str) -> str:
    """Symbol must be a non-empty alphanumeric string."""
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValidationError("Symbol cannot be empty.")
    if not symbol.isalnum():
        raise ValidationError(f"Symbol '{symbol}' contains invalid characters. Example: BTCUSDT")
    return symbol


def validate_side(side: str) -> str:
    """Side must be BUY or SELL (case-insensitive)."""
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValidationError(f"Side must be one of {VALID_SIDES}. Got: '{side}'")
    return side


def validate_order_type(order_type: str) -> str:
    """Order type must be MARKET, LIMIT, or STOP_MARKET (case-insensitive)."""
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Order type must be one of {VALID_ORDER_TYPES}. Got: '{order_type}'"
        )
    return order_type


def validate_quantity(quantity: float | str) -> float:
    """Quantity must be a positive number."""
    try:
        qty = float(quantity)
    except (ValueError, TypeError):
        raise ValidationError(f"Quantity must be a number. Got: '{quantity}'")
    if qty <= 0:
        raise ValidationError(f"Quantity must be greater than 0. Got: {qty}")
    return qty





def validate_price(price: float | str | None, order_type: str) -> float | None:
    """
    For LIMIT and STOP_MARKET orders a positive price is required.
    For MARKET orders price must be None / not provided.
    Price is required only for LIMIT orders.
    """
    # STOP_MARKET triggers a MARKET order when stopPrice is reached.
    # MARKET and STOP_MARKET do not need price
    if order_type in ("MARKET", "STOP_MARKET"):
        return None

    # LIMIT requires price
    if price is None:
        raise ValidationError(f"Price is required for {order_type} orders.")

    try:
        p = float(price)
    except (ValueError, TypeError):
        raise ValidationError(f"Price must be a number. Got: '{price}'")

    if p <= 0:
        raise ValidationError(f"Price must be greater than 0. Got: {p}")

    return p

def validate_stop_price(stop_price: float | str | None, order_type: str) -> float | None:
    """Stop price is required only for STOP_MARKET orders."""
    if order_type != "STOP_MARKET":
        return None
    if stop_price is None:
        raise ValidationError("Stop price (--stop-price) is required for STOP_MARKET orders.")
    try:
        sp = float(stop_price)
    except (ValueError, TypeError):
        raise ValidationError(f"Stop price must be a number. Got: '{stop_price}'")
    if sp <= 0:
        raise ValidationError(f"Stop price must be greater than 0. Got: {sp}")
    return sp


def validate_order_params(
    *,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float | str,
    price: float | str | None = None,
    stop_price: float | str | None = None,
) -> dict:
    """
    Validate all order parameters at once.

    Returns a cleaned dict ready to be passed to OrderService.
    Raises ValidationError if any field is invalid.
    """
    logger.debug("Validating order parameters: %s", locals())

    cleaned = {
        "symbol": validate_symbol(symbol),
        "side": validate_side(side),
        "order_type": validate_order_type(order_type),
        "quantity": validate_quantity(quantity),
    }

    cleaned["price"] = validate_price(price, cleaned["order_type"])
    cleaned["stop_price"] = validate_stop_price(stop_price, cleaned["order_type"])

    logger.debug("Validation passed: %s", cleaned)
    return cleaned
