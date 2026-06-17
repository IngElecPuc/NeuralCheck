"""Application-level chess clock state.

The UI renders this object, but clock policy is kept outside Tkinter so it can
later be reused by a backend or by other frontends.
"""

from __future__ import annotations

from dataclasses import dataclass


RAPID_3_0 = "rapid_3_0"
CORRESPONDENCE = "correspondence"


@dataclass(frozen=True)
class ClockSnapshot:
    """Current clock view for rendering."""

    mode: str
    visible: bool
    running: bool
    white_seconds: int
    black_seconds: int

    def label_for_white(self) -> str:
        return f"White: {self._format_seconds(self.white_seconds)}"

    def label_for_black(self) -> str:
        return f"Black: {self._format_seconds(self.black_seconds)}"

    @staticmethod
    def _format_seconds(seconds: int) -> str:
        safe_seconds = max(0, int(seconds))
        minutes, remainder = divmod(safe_seconds, 60)
        return f"{minutes:02d}:{remainder:02d}"


class ChessClock:
    """Small clock model with explicit game/theory modes."""

    def __init__(self, mode: str = RAPID_3_0, initial_seconds: int = 180, increment_seconds: int = 0):
        self.mode = mode
        self.initial_seconds = int(initial_seconds)
        self.increment_seconds = int(increment_seconds)
        self.white_seconds = int(initial_seconds)
        self.black_seconds = int(initial_seconds)

    @classmethod
    def rapid_3_0(cls) -> "ChessClock":
        return cls(mode=RAPID_3_0, initial_seconds=180, increment_seconds=0)

    @classmethod
    def correspondence(cls) -> "ChessClock":
        return cls(mode=CORRESPONDENCE, initial_seconds=0, increment_seconds=0)

    def set_rapid_3_0(self) -> None:
        self.mode = RAPID_3_0
        self.initial_seconds = 180
        self.increment_seconds = 0
        self.white_seconds = 180
        self.black_seconds = 180

    def set_correspondence(self) -> None:
        self.mode = CORRESPONDENCE
        self.initial_seconds = 0
        self.increment_seconds = 0
        self.white_seconds = 0
        self.black_seconds = 0

    @property
    def visible(self) -> bool:
        return self.mode != CORRESPONDENCE

    @property
    def running(self) -> bool:
        return self.visible and self.white_seconds > 0 and self.black_seconds > 0

    def tick(self, white_turn: bool) -> ClockSnapshot:
        """Advance the clock by one second for the player to move."""
        if not self.running:
            return self.snapshot()

        if white_turn:
            self.white_seconds = max(0, self.white_seconds - 1)
        else:
            self.black_seconds = max(0, self.black_seconds - 1)
        return self.snapshot()

    def snapshot(self) -> ClockSnapshot:
        return ClockSnapshot(
            mode=self.mode,
            visible=self.visible,
            running=self.running,
            white_seconds=self.white_seconds,
            black_seconds=self.black_seconds,
        )
