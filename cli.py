#!/usr/bin/env python3
"""
cli.py — CLI entry point for the Binance Futures Testnet trading bot.

Usage examples:
  python cli.py place --symbol BTCUSDT --side BUY --type MARKET --quantity 0.001
  python cli.py place --symbol BTCUSDT --side SELL --type LIMIT --quantity 0.001 --price 65000
  python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET --quantity 0.001 --stop-price 60000
  python cli.py ping
  python cli.py info --symbol BTCUSDT
"""

from __future__ import annotations

from typing import Optional

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from bot.exceptions import ConfigurationError, NetworkError
from bot.logging_config import logger
from bot.orders import OrderResult, OrderService

app = typer.Typer(
    name="trading-bot",
    help="[bold cyan]Binance Futures Testnet[/] Trading Bot",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _print_request_summary(
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float],
    stop_price: Optional[float],
) -> None:
    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    table.add_column("Field", style="bold cyan", min_width=12)
    table.add_column("Value", style="white")

    table.add_row("Symbol", symbol.upper())
    table.add_row("Side", f"[green]{side.upper()}[/]" if side.upper() == "BUY" else f"[red]{side.upper()}[/]")
    table.add_row("Type", order_type.upper())
    table.add_row("Quantity", str(quantity))

    if price is not None:
        table.add_row("Price", str(price))
    if stop_price is not None:
        table.add_row("Stop Price", str(stop_price))

    console.print(Panel(table, title="[bold]ORDER REQUEST SUMMARY[/]", border_style="cyan"))


def _print_success(result: OrderResult) -> None:
    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    table.add_column("Field", style="bold cyan", min_width=16)
    table.add_column("Value", style="white")

    table.add_row("Order ID", str(result.order_id))
    table.add_row("Client Order ID", result.client_order_id or "—")
    table.add_row("Symbol", result.symbol)
    table.add_row("Side", f"[green]{result.side}[/]" if result.side == "BUY" else f"[red]{result.side}[/]")
    table.add_row("Type", result.order_type)
    table.add_row("Status", f"[yellow]{result.status}[/]")
    table.add_row("Original Qty", result.orig_qty)
    table.add_row("Executed Qty", result.executed_qty)
    table.add_row("Avg Price", result.avg_price)

    console.print(Panel(table, title="[bold]ORDER RESPONSE[/]", border_style="green"))
    console.print(Text("✅  Order placed successfully!", style="bold green"))


def _print_failure(message: str) -> None:
    console.print(
        Panel(
            Text(message, style="bold red"),
            title="[bold red]ORDER FAILED[/]",
            border_style="red",
        )
    )


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command(name="place", help="Place a new futures order on the testnet.")
def place_order(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Trading pair, e.g. BTCUSDT"),
    side: str = typer.Option(..., "--side", help="BUY or SELL"),
    order_type: str = typer.Option(..., "--type", "-t", help="MARKET | LIMIT | STOP_MARKET"),
    quantity: float = typer.Option(..., "--quantity", "-q", help="Order quantity"),
    price: Optional[float] = typer.Option(None, "--price", "-p", help="Limit price (required for LIMIT)"),
    stop_price: Optional[float] = typer.Option(None, "--stop-price", help="Stop price (required for STOP_MARKET)"),
) -> None:
    logger.info(
        "CLI 'place' invoked: symbol=%s side=%s type=%s qty=%s price=%s stop=%s",
        symbol, side, order_type, quantity, price, stop_price,
    )

    _print_request_summary(symbol, side, order_type, quantity, price, stop_price)

    try:
        service = OrderService()
    except ConfigurationError as exc:
        _print_failure(str(exc))
        raise typer.Exit(1)

    result: OrderResult = service.create_order(
        symbol=symbol,
        side=side,
        order_type=order_type,
        quantity=quantity,
        price=price,
        stop_price=stop_price,
    )

    if result.success:
        _print_success(result)
    else:
        _print_failure(result.error_message)
        raise typer.Exit(1)


@app.command(name="ping", help="Check connectivity to Binance Futures Testnet.")
def ping() -> None:
    from bot.client import BinanceFuturesClient

    try:
        client = BinanceFuturesClient()
        client.ping()
        server_time = client.get_server_time()
        console.print(f"[bold green]✅  Testnet is reachable.[/]  Server time: [cyan]{server_time}[/]")
    except (ConfigurationError, NetworkError) as exc:
        console.print(f"[bold red]❌  {exc}[/]")
        raise typer.Exit(1)


@app.command(name="info", help="Show exchange info for a symbol.")
def symbol_info(
    symbol: str = typer.Option(..., "--symbol", "-s", help="Trading pair, e.g. BTCUSDT"),
) -> None:
    from bot.client import BinanceFuturesClient

    symbol = symbol.strip().upper()

    try:
        client = BinanceFuturesClient()
        data = client.get_exchange_info()
    except (ConfigurationError, NetworkError) as exc:
        console.print(f"[bold red]❌  {exc}[/]")
        raise typer.Exit(1)

    symbols = data.get("symbols", [])
    match = next((s for s in symbols if s["symbol"] == symbol), None)

    if not match:
        console.print(f"[bold red]Symbol '{symbol}' not found on testnet.[/]")
        raise typer.Exit(1)

    table = Table(box=box.ROUNDED, show_header=False, padding=(0, 1))
    table.add_column("Field", style="bold cyan", min_width=20)
    table.add_column("Value", style="white")

    table.add_row("Symbol", match["symbol"])
    table.add_row("Status", match.get("status", "—"))
    table.add_row("Base Asset", match.get("baseAsset", "—"))
    table.add_row("Quote Asset", match.get("quoteAsset", "—"))
    table.add_row("Contract Type", match.get("contractType", "—"))
    table.add_row("Margin Asset", match.get("marginAsset", "—"))

    filters = match.get("filters", [])
    for f in filters:
        ft = f.get("filterType", "")
        if ft == "LOT_SIZE":
            table.add_row("Min Qty", f.get("minQty", "—"))
            table.add_row("Max Qty", f.get("maxQty", "—"))
            table.add_row("Step Size", f.get("stepSize", "—"))
        elif ft == "PRICE_FILTER":
            table.add_row("Min Price", f.get("minPrice", "—"))
            table.add_row("Tick Size", f.get("tickSize", "—"))

    console.print(Panel(table, title=f"[bold]SYMBOL INFO: {symbol}[/]", border_style="cyan"))


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app()
