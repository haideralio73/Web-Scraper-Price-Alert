#!/usr/bin/env python3
"""
Price Tracker — Web Scraper + Email Alert System
──────────────────────────────────────────────────
Tracks product prices, stores them in SQLite, and sends
email alerts when prices drop below your target.

Usage:
    python main.py add <url> <target_price>    Add a product to track
    python main.py list                        Show all tracked products
    python main.py check                       Run one price-check cycle
    python main.py remove <id>                 Remove a product
    python main.py history <id>               Show price history
    python main.py serve                       Run scheduler (every N hours)
"""

import io
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import schedule
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from config import Settings

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
from database import (init_db, add_product, get_active_products,
                      get_all_products, update_price, remove_product,
                      deactivate_product, get_price_history, get_product_by_id)
from scraper import scrape_url
from email_alert import send_alert

console = Console(no_color=False, emoji=False, safe_box=True)


def cmd_add(url: str, target_price_str: str) -> None:
    target = _parse_price(target_price_str)
    if target is None:
        rprint("[red]Invalid target price.[/red]")
        return

    rprint(f"\n[bold yellow]Scraping[/bold yellow] {url} ...")
    result = scrape_url(url)

    if result is None:
        rprint("[red]Could not extract price from page. Adding anyway with no current price.[/red]")
        current = None
        name = "Unknown"
        currency = "$"
    else:
        current = result.price
        name = result.name[:200]
        currency = result.currency
        rprint(f"  [green]Found:[/green] {name}")
        rprint(f"  [green]Price:[/green] {currency}{current:.2f}")

    pid = add_product(url, name, target, current, currency)
    rprint(f"\n[bold green]Product added![/bold green] (ID: {pid})")


def cmd_list() -> None:
    products = get_all_products()
    if not products:
        rprint("[yellow]No products tracked yet.[/yellow]")
        return

    table = Table(title="Tracked Products", title_style="bold cyan")
    table.add_column("ID", justify="right", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Target", justify="right")
    table.add_column("Current", justify="right")
    table.add_column("Status", justify="center")
    table.add_column("Last Checked")

    for p in products:
        target = f"{p['currency']}{p['target_price']:.2f}"
        current = f"{p['currency']}{p['current_price']:.2f}" if p['current_price'] else "—"
        status = "Active" if p['is_active'] else "Inactive"
        last = p['last_checked'] or "never"
        table.add_row(str(p['id']), p['name'][:50], target, current, status, last)

    console.print(table)
    console.print(f"\nTotal: [bold]{len(products)}[/bold] product(s)")


def cmd_check() -> None:
    products = get_active_products()
    if not products:
        rprint("[yellow]No active products to check.[/yellow]")
        return

    rprint(f"\n[bold cyan]Checking {len(products)} product(s)...[/bold cyan]\n")

    alerts_sent = 0
    errors = 0

    for p in products:
        name_display = p['name'][:60]
        console.print(f"[bold]>[/bold] {name_display} ... ", end="")

        result = scrape_url(p['url'])
        if result is None:
            console.print("[red]FAILED[/red]")
            errors += 1
            continue

        update_price(p['id'], result.price)
        console.print(f"[green]{result.currency}{result.price:.2f}[/green]")

        if result.price <= p['target_price']:
            console.print(f"  [bold green]Target hit! Sending alert ...[/bold green]")
            ok = send_alert(
                product_name=p['name'],
                product_url=p['url'],
                current_price=result.price,
                target_price=p['target_price'],
                currency=result.currency,
            )
            if ok:
                alerts_sent += 1
                deactivate_product(p['id'])
                console.print("  [green]Alert sent[/green]")
            else:
                console.print("  [red]Alert failed[/red]")

    console.print(f"\n[bold]Summary:[/bold] {len(products)} checked, "
                  f"[green]{alerts_sent} alert(s) sent[/green], "
                  f"[red]{errors} error(s)[/red]")


def cmd_remove(product_id_str: str) -> None:
    pid = _parse_id(product_id_str)
    if pid is None:
        return
    p = get_product_by_id(pid)
    if not p:
        rprint(f"[red]Product ID {pid} not found.[/red]")
        return
    remove_product(pid)
    rprint(f"[green]Removed product #{pid} ({p['name']})[/green]")


def cmd_history(product_id_str: str) -> None:
    pid = _parse_id(product_id_str)
    if pid is None:
        return
    p = get_product_by_id(pid)
    if not p:
        rprint(f"[red]Product ID {pid} not found.[/red]")
        return

    rows = get_price_history(pid)
    if not rows:
        rprint(f"[yellow]No price history for #{pid} yet.[/yellow]")
        return

    table = Table(title=f"Price History — {p['name'][:50]}", title_style="bold cyan")
    table.add_column("Price", justify="right", style="green")
    table.add_column("Checked At", style="white")

    for row in rows:
        table.add_row(f"{p['currency']}{row['price']:.2f}", row['checked_at'])

    console.print(table)


def cmd_serve() -> None:
    errors = Settings.validate()
    if errors:
        for e in errors:
            rprint(f"[red]Config error: {e}[/red]")
        rprint("\n[yellow]Copy .env.example to .env and fill in your credentials.[/yellow]")
        sys.exit(1)

    rprint(Panel.fit(
        "[bold green]Price Tracker Scheduler[/bold green]\n"
        f"Checking every [cyan]{Settings.SCRAPE_INTERVAL_HOURS}[/cyan] hour(s)\n"
        f"Alerts to: [cyan]{Settings.ALERT_RECIPIENT}[/cyan]",
        title="Running",
    ))

    schedule.every(Settings.SCRAPE_INTERVAL_HOURS).hours.do(check_prices_job)
    schedule.every().day.at("00:00").do(lambda: rprint("[dim]── day rollover ──[/dim]"))

    check_prices_job()

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        rprint("\n[yellow]Shutting down.[/yellow]")


def check_prices_job() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    rprint(f"\n[bold cyan]Scheduled check — {now}[/bold cyan]")
    cmd_check()


def _parse_price(s: str) -> Optional[float]:
    try:
        return float(s.replace("$", "").replace("€", "").replace(",", ""))
    except ValueError:
        return None


def _parse_id(s: str) -> Optional[int]:
    try:
        return int(s)
    except ValueError:
        rprint(f"[red]Invalid ID: {s}[/red]")
        return None


def main() -> None:
    init_db()

    if len(sys.argv) < 2:
        rprint(Panel.fit(
            "[bold cyan]Price Tracker[/bold cyan]\n\n"
            "Commands:\n"
            "  [green]add <url> <price>[/green]     Add product to track\n"
            "  [green]list[/green]                   Show all products\n"
            "  [green]check[/green]                  Run one check cycle\n"
            "  [green]remove <id>[/green]           Remove a product\n"
            "  [green]history <id>[/green]          Show price history\n"
            "  [green]serve[/green]                  Start scheduled mode",
            title="Usage",
        ))
        return

    cmd = sys.argv[1]

    if cmd == "add" and len(sys.argv) == 4:
        cmd_add(sys.argv[2], sys.argv[3])
    elif cmd == "list":
        cmd_list()
    elif cmd == "check":
        cmd_check()
    elif cmd == "remove" and len(sys.argv) == 3:
        cmd_remove(sys.argv[2])
    elif cmd == "history" and len(sys.argv) == 3:
        cmd_history(sys.argv[2])
    elif cmd == "serve":
        cmd_serve()
    else:
        rprint(f"[red]Unknown command or wrong arguments: {cmd}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
