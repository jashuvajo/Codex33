from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrailingState:
    entry: float
    stop: float
    target: float
    breakeven_moved: bool = False


class TrailingEngine:
    """
    Aggressive trailing for 5-point scalp objective.
    """

    def __init__(self) -> None:
        self._positions: dict[str, TrailingState] = {}

    def on_entry(self, symbol: str, entry_price: float) -> None:
        self._positions[symbol] = TrailingState(
            entry=entry_price,
            stop=entry_price - 2.0,
            target=entry_price + 5.0,
        )

    def evaluate(self, symbol: str, ltp: float, momentum_velocity: float) -> str | None:
        state = self._positions.get(symbol)
        if not state:
            return None

        # Breakeven shift once move reaches +2 points.
        if not state.breakeven_moved and ltp >= state.entry + 2.0:
            state.stop = state.entry
            state.breakeven_moved = True

        # Extend target during strong momentum.
        if momentum_velocity > 0.2 and ltp >= state.target:
            state.target += 2.0
            state.stop = max(state.stop, ltp - 1.5)

        if ltp <= state.stop:
            self._positions.pop(symbol, None)
            return "EXIT_STOP"

        if ltp >= state.target and momentum_velocity <= 0.05:
            self._positions.pop(symbol, None)
            return "EXIT_TARGET"

        return None
