"""
exceptions.py — Custom exception hierarchy for the trading bot.
"""


class TradingBotError(Exception):
    """Base exception for all trading bot errors."""


class ValidationError(TradingBotError):
    """Raised when CLI input or order parameters fail validation."""


class BinanceClientError(TradingBotError):
    """Raised when the Binance API returns an error response."""

    def __init__(self, message: str, status_code: int | None = None, error_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.status_code:
            parts.append(f"HTTP {self.status_code}")
        if self.error_code:
            parts.append(f"Binance code {self.error_code}")
        return " | ".join(parts)


class NetworkError(TradingBotError):
    """Raised on connection timeouts or network-level failures."""


class AuthenticationError(TradingBotError):
    """Raised when API key / secret are missing or rejected."""


class ConfigurationError(TradingBotError):
    """Raised when required configuration is missing or invalid."""
