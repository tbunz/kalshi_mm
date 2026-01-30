"""Main Textual application for Kalshi Market Maker"""
import asyncio
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import Static
from textual.binding import Binding

from .panels import (
    AccountPanel,
    PositionPanel,
    MarketPanel,
    OrderbookPanel,
    FillsPanel,
    StatusBar,
    LiveClock,
)
from ..market_maker import MarketMakerBot
from .. import config


class MarketMakerApp(App):
    """Terminal UI for Kalshi Market Maker"""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1;
        grid-rows: 3 8 1fr 1;
    }

    #header-row {
        height: 3;
        background: $surface;
        border-bottom: solid $primary;
        layout: horizontal;
        align: center middle;
    }

    #header-title {
        text-align: center;
        text-style: bold;
        color: $text;
        width: 1fr;
    }

    #live-clock {
        width: auto;
        padding: 0 2;
    }

    #top-panels {
        height: 8;
        layout: horizontal;
    }

    #bottom-panels {
        height: 100%;
        layout: horizontal;
    }

    #status-row {
        height: 1;
        background: $surface;
        border-top: solid $primary;
    }

    .top-panel {
        width: 1fr;
        height: 100%;
    }

    .bottom-panel {
        width: 1fr;
        height: 100%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("r", "refresh", "Refresh", show=True),
    ]

    def __init__(self):
        super().__init__()
        self.bot = None
        self._trading_task = None
        self._update_queue = asyncio.Queue()

    def compose(self) -> ComposeResult:
        yield Container(
            Static(f"KALSHI MM - {config.MARKET_TICKER}", id="header-title"),
            LiveClock(id="live-clock"),
            id="header-row",
        )

        yield Horizontal(
            AccountPanel(id="account-panel", classes="top-panel"),
            PositionPanel(id="position-panel", classes="top-panel"),
            MarketPanel(id="market-panel", classes="top-panel"),
            id="top-panels",
        )

        yield Horizontal(
            OrderbookPanel(id="orderbook-panel", classes="bottom-panel"),
            FillsPanel(id="fills-panel", classes="bottom-panel"),
            id="bottom-panels",
        )

        yield Container(
            StatusBar(id="status-bar"),
            id="status-row",
        )

    async def on_mount(self) -> None:
        """Called when app is mounted - start trading loop"""
        self._trading_task = asyncio.create_task(self._run_trading_loop())
        asyncio.create_task(self._monitor_updates())

    async def _run_trading_loop(self) -> None:
        """Run the market maker bot"""
        try:
            async with MarketMakerBot() as bot:
                self.bot = bot
                await bot.run(update_callback=self._update_queue.put)
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")
            await asyncio.sleep(3)
            self.exit()

    async def _monitor_updates(self) -> None:
        """Monitor update queue and refresh UI"""
        while True:
            try:
                update = await asyncio.wait_for(
                    self._update_queue.get(),
                    timeout=1.0
                )
                self._apply_update(update)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.notify(f"UI update error: {e}", severity="warning")

    def _apply_update(self, update: dict) -> None:
        """Apply update data to UI panels"""
        try:
            # Update account panel
            if "balance" in update:
                exposure = update.get("exposure", 0.0)
                self.query_one("#account-panel", AccountPanel).update_data(
                    balance=update["balance"],
                    exposure=exposure,
                )

            # Update position panel
            if "position" in update:
                pos = update["position"]
                self.query_one("#position-panel", PositionPanel).update_data(
                    position=pos.position,
                    side=pos.side.value if pos.side else "flat",
                    avg_price=pos.avg_entry_price,
                    pnl=0.0,
                )

            # Update market panel
            if "market" in update:
                market = update["market"]
                self.query_one("#market-panel", MarketPanel).update_data(
                    bid=market.get("yes_bid", 0),
                    ask=market.get("yes_ask", 0),
                    volume=market.get("volume", 0),
                    status=market.get("status", "unknown"),
                )

            # Update orderbook panel
            if "orderbook" in update:
                ob = update["orderbook"]
                self.query_one("#orderbook-panel", OrderbookPanel).update_data(
                    yes_levels=ob.get("yes", []),
                    no_levels=ob.get("no", []),
                )

            # Update status bar
            if "iteration" in update:
                self.query_one("#status-bar", StatusBar).update_data(
                    iteration=update["iteration"],
                    max_iterations=config.MAX_RUNTIME,
                    elapsed=update.get("elapsed", 0),
                )

        except Exception as e:
            self.log.error(f"Error applying update: {e}")

    def action_refresh(self) -> None:
        """Manual refresh action"""
        self.notify("Refreshing...")

    async def action_quit(self) -> None:
        """Quit the application"""
        if self._trading_task:
            self._trading_task.cancel()
            try:
                await self._trading_task
            except asyncio.CancelledError:
                pass
        self.exit()
