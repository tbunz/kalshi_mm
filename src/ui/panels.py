"""UI panel widgets for the market maker dashboard"""
from textual.widgets import Static
from rich.table import Table
from rich.text import Text
from rich.panel import Panel
from datetime import datetime


class LiveClock(Static):
    """A live clock that updates every second to show the app is responsive"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cycle = 0

    def on_mount(self):
        self.set_interval(1.0, self._tick)

    def _tick(self):
        self._cycle += 1
        self.refresh()

    def render(self) -> Text:
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")
        content = Text()
        content.append(time_str, style="bold cyan")
        content.append(f" [{self._cycle:>4}]", style="dim")
        return content


class AccountPanel(Static):
    """Displays account balance and exposure info"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._balance = 0.0
        self._exposure = 0.0

    def render(self) -> Panel:
        content = Text()
        content.append("Balance:  ", style="dim")
        content.append(f"${self._balance:.2f}\n", style="green bold")
        content.append("Exposure: ", style="dim")
        content.append(f"${self._exposure:.2f}\n", style="yellow")
        content.append("Available: ", style="dim")
        available = self._balance - self._exposure
        content.append(f"${available:.2f}", style="cyan")
        return Panel(content, title="Account", border_style="blue")

    def update_data(self, balance: float, exposure: float):
        self._balance = balance
        self._exposure = exposure
        self.refresh()


class PositionPanel(Static):
    """Displays current position info"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._position = 0
        self._side = "flat"
        self._avg_price = 0.0
        self._pnl = 0.0

    def render(self) -> Panel:
        content = Text()
        content.append("Net: ", style="dim")

        if self._position > 0:
            content.append(f"+{self._position} YES\n", style="green bold")
        elif self._position < 0:
            content.append(f"{self._position} NO\n", style="red bold")
        else:
            content.append("0 (flat)\n", style="dim")

        content.append("Avg Price: ", style="dim")
        content.append(f"{self._avg_price:.0f}c\n", style="white")
        content.append("P&L: ", style="dim")

        if self._pnl >= 0:
            content.append(f"+${self._pnl:.2f}", style="green")
        else:
            content.append(f"-${abs(self._pnl):.2f}", style="red")

        return Panel(content, title="Position", border_style="blue")

    def update_data(self, position: int, side: str, avg_price: float, pnl: float = 0.0):
        self._position = position
        self._side = side
        self._avg_price = avg_price
        self._pnl = pnl
        self.refresh()


class MarketPanel(Static):
    """Displays market bid/ask/spread info"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._bid = 0
        self._ask = 0
        self._volume = 0
        self._status = "unknown"

    def render(self) -> Panel:
        content = Text()
        spread = self._ask - self._bid if self._ask > self._bid else 0

        content.append("Bid: ", style="dim")
        content.append(f"{self._bid}c  ", style="green")
        content.append("Ask: ", style="dim")
        content.append(f"{self._ask}c\n", style="red")
        content.append("Spread: ", style="dim")
        content.append(f"{spread}c\n", style="yellow")
        content.append("Volume: ", style="dim")
        content.append(f"{self._volume:,}\n", style="white")
        content.append("Status: ", style="dim")

        status_style = "green" if self._status == "open" else "red"
        content.append(self._status.upper(), style=status_style)

        return Panel(content, title="Market", border_style="blue")

    def update_data(self, bid: int, ask: int, volume: int, status: str):
        self._bid = bid
        self._ask = ask
        self._volume = volume
        self._status = status
        self.refresh()


class OrderbookPanel(Static):
    """Displays orderbook depth"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._yes_levels = []
        self._no_levels = []

    def render(self) -> Panel:
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 1))
        table.add_column("YES", justify="right", style="green")
        table.add_column("Qty", justify="right")
        table.add_column("Qty", justify="right")
        table.add_column("NO", justify="left", style="red")

        max_levels = max(len(self._yes_levels), len(self._no_levels), 5)

        for i in range(min(max_levels, 5)):
            yes_price = f"{self._yes_levels[i][0]}c" if i < len(self._yes_levels) else ""
            yes_qty = str(self._yes_levels[i][1]) if i < len(self._yes_levels) else ""
            no_price = f"{self._no_levels[i][0]}c" if i < len(self._no_levels) else ""
            no_qty = str(self._no_levels[i][1]) if i < len(self._no_levels) else ""

            table.add_row(yes_price, yes_qty, no_qty, no_price)

        return Panel(table, title="Orderbook", border_style="blue")

    def update_data(self, yes_levels: list, no_levels: list):
        self._yes_levels = yes_levels or []
        self._no_levels = no_levels or []
        self.refresh()


class FillsPanel(Static):
    """Displays recent fills"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._fills = []

    def render(self) -> Panel:
        content = Text()

        if not self._fills:
            content.append("No fills yet", style="dim italic")
        else:
            for fill in self._fills[-5:]:  # Last 5 fills
                time_str = fill.get("time", "")
                action = fill.get("action", "")
                qty = fill.get("qty", 0)
                side = fill.get("side", "")
                price = fill.get("price", 0)

                content.append(f"{time_str} ", style="dim")

                action_style = "green" if action.upper() == "BUY" else "red"
                content.append(f"{action.upper()} ", style=action_style)
                content.append(f"{qty} {side.upper()} @ {price}c\n", style="white")

        return Panel(content, title="Recent Fills", border_style="blue")

    def update_data(self, fills: list):
        self._fills = fills
        self.refresh()

    def add_fill(self, fill: dict):
        self._fills.append(fill)
        if len(self._fills) > 20:
            self._fills = self._fills[-20:]
        self.refresh()


class StatusBar(Static):
    """Bottom status bar"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._iteration = 0
        self._max_iterations = 0
        self._elapsed = 0.0
        self._last_update = None

    def render(self) -> str:
        parts = []
        parts.append(f" Loop: {self._iteration}/{self._max_iterations}s")
        parts.append(f"| Elapsed: {self._elapsed:.0f}s")

        if self._last_update:
            ago = (datetime.now() - self._last_update).total_seconds()
            parts.append(f"| Updated: {ago:.1f}s ago")

        parts.append("| [Q]uit")

        return " ".join(parts)

    def update_data(self, iteration: int, max_iterations: int, elapsed: float):
        self._iteration = iteration
        self._max_iterations = max_iterations
        self._elapsed = elapsed
        self._last_update = datetime.now()
        self.refresh()
