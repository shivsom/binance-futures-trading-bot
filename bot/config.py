"""
config.py — Central configuration: loads env vars, sets constants.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Binance Futures Testnet ───────────────────────────────────────────────────
BINANCE_API_KEY: str = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY: str = os.getenv("BINANCE_SECRET_KEY", "")
TESTNET_BASE_URL: str = "https://testnet.binancefuture.com"

# ── Order constants ───────────────────────────────────────────────────────────
VALID_SIDES: tuple[str, ...] = ("BUY", "SELL")
VALID_ORDER_TYPES: tuple[str, ...] = ("MARKET", "LIMIT", "STOP_MARKET")
TIME_IN_FORCE: str = "GTC"         # Good-Till-Cancelled (required for LIMIT)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE: str = "logs/trading.log"
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ── Network ───────────────────────────────────────────────────────────────────
REQUEST_TIMEOUT: int = 10          # seconds
MAX_RETRIES: int = 3
RETRY_DELAY: float = 1.0           # seconds between retries
