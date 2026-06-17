"""Application-level chess clock state.

The UI renders this object, but clock policy is kept outside Tkinter so it can
later be reused by a backend or by other frontends.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


BULLET = "bullet"
BLITZ = "blitz"
RAPID = "rapid"
CORRESPONDENCE_CATEGORY = "correspondence"
TOURNAMENT = "tournament"

CORRESPONDENCE = "correspondence"
RAPID_3_0 = "rapid_3_0"

AUTO_START = "auto_start"
BLACK_SIGNAL_START = "black_signal_start"
START_POLICIES = (AUTO_START, BLACK_SIGNAL_START)


@dataclass(frozen=True)
class TimeControl:
    """Named time-control preset."""

    key: str
    label: str
    category: str
    base_seconds: int
    increment_seconds: int = 0
    visible: bool = True
    bonus_after_move: int | None = None
    bonus_seconds: int = 0
    description: str = ""


TIME_CONTROLS: Tuple[TimeControl, ...] = (
    TimeControl("bullet_1_0", "Bala 1+0", BULLET, 60, 0),
    TimeControl("bullet_1_1", "Bala 1+1", BULLET, 60, 1),
    TimeControl("bullet_2_1", "Bala 2+1", BULLET, 120, 1),
    TimeControl("bullet_30s_0", "Bala 30s+0", BULLET, 30, 0),
    TimeControl("bullet_20s_1", "Bala 20s+1", BULLET, 20, 1),
    TimeControl("blitz_3_0", "Blitz 3+0", BLITZ, 180, 0),
    TimeControl("blitz_3_2", "Blitz 3+2", BLITZ, 180, 2),
    TimeControl("blitz_5_0", "Blitz 5+0", BLITZ, 300, 0),
    TimeControl("blitz_5_3", "Blitz 5+3", BLITZ, 300, 3),
    TimeControl("rapid_10_0", "Rápida 10+0", RAPID, 600, 0),
    TimeControl("rapid_10_5", "Rápida 10+5", RAPID, 600, 5),
    TimeControl("rapid_15_10", "Rápida 15+10", RAPID, 900, 10),
    TimeControl("rapid_30_0", "Rápida 30+0", RAPID, 1800, 0),
    TimeControl("rapid_20_0", "Rápida 20+0", RAPID, 1200, 0),
    TimeControl("rapid_60_0", "Rápida 60+0", RAPID, 3600, 0),
    TimeControl(
        "fide_90_40_30_30",
        "FIDE 90/40 + 30 + 30s",
        TOURNAMENT,
        5400,
        30,
        bonus_after_move=40,
        bonus_seconds=1800,
        description="90 minutos para 40 jugadas, luego 30 minutos para el resto, con 30s por jugada desde la jugada 1.",
    ),
    TimeControl(
        CORRESPONDENCE,
        "Correspondencia",
        CORRESPONDENCE_CATEGORY,
        0,
        0,
        visible=False,
        description="Sin reloj visible.",
    ),
)
TIME_CONTROLS_BY_KEY: Dict[str, TimeControl] = {control.key: control for control in TIME_CONTROLS}
TIME_CONTROLS_BY_CATEGORY: Dict[str, Tuple[TimeControl, ...]] = {
    category: tuple(control for control in TIME_CONTROLS if control.category == category)
    for category in (BULLET, BLITZ, RAPID, TOURNAMENT, CORRESPONDENCE_CATEGORY)
}


@dataclass(frozen=True)
class ClockSnapshot:
    """Current clock view for rendering."""

    mode: str
    label: str
    visible: bool
    running: bool
    paused: bool
    waiting_for_start: bool
    start_policy: str
    white_seconds: int
    black_seconds: int

    def label_for_white(self) -> str:
        return f"Blancas: {self._format_seconds(self.white_seconds)}"

    def label_for_black(self) -> str:
        return f"Negras: {self._format_seconds(self.black_seconds)}"

    def status_label(self) -> str:
        if not self.visible:
            return "Correspondencia"
        if self.waiting_for_start:
            return f"{self.label} · esperando señal de negras"
        if self.paused:
            return f"{self.label} · pausado"
        if self.running:
            return self.label
        return f"{self.label} · detenido"

    @staticmethod
    def _format_seconds(seconds: int) -> str:
        safe_seconds = max(0, int(seconds))
        hours, remainder = divmod(safe_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"


class ChessClock:
    """Clock model with presets, increments, staged bonuses and pause policy."""

    def __init__(
        self,
        mode: str = RAPID_3_0,
        initial_seconds: int | None = None,
        increment_seconds: int | None = None,
        start_policy: str = AUTO_START,
    ):
        if mode == RAPID_3_0:
            mode = "blitz_3_0"
        self.start_policy = self._require_start_policy(start_policy)
        self.control = self._control_from_legacy_args(mode, initial_seconds, increment_seconds)
        self.white_seconds = int(self.control.base_seconds)
        self.black_seconds = int(self.control.base_seconds)
        self.white_move_count = 0
        self.black_move_count = 0
        self._white_bonus_applied = False
        self._black_bonus_applied = False
        self.paused = False
        self.waiting_for_start = False
        self._running = False
        self.start_new_game()

    @classmethod
    def rapid_3_0(cls) -> "ChessClock":
        return cls(mode="blitz_3_0")

    @classmethod
    def correspondence(cls) -> "ChessClock":
        return cls(mode=CORRESPONDENCE)

    @property
    def mode(self) -> str:
        return self.control.key

    @property
    def initial_seconds(self) -> int:
        return self.control.base_seconds

    @property
    def increment_seconds(self) -> int:
        return self.control.increment_seconds

    @property
    def visible(self) -> bool:
        return self.control.visible

    @property
    def running(self) -> bool:
        return (
            self.visible
            and self._running
            and not self.paused
            and not self.waiting_for_start
            and self.white_seconds > 0
            and self.black_seconds > 0
        )

    def set_rapid_3_0(self) -> None:
        self.set_time_control("blitz_3_0")

    def set_correspondence(self) -> None:
        self.set_time_control(CORRESPONDENCE)

    def set_time_control(self, key: str) -> None:
        self.control = self._require_time_control(key)
        self.start_new_game()

    def set_start_policy(self, start_policy: str) -> None:
        self.start_policy = self._require_start_policy(start_policy)
        self.start_new_game()

    def start_new_game(self) -> None:
        self.white_seconds = int(self.control.base_seconds)
        self.black_seconds = int(self.control.base_seconds)
        self.white_move_count = 0
        self.black_move_count = 0
        self._white_bonus_applied = False
        self._black_bonus_applied = False
        self.paused = False
        if not self.visible:
            self.waiting_for_start = False
            self._running = False
        elif self.start_policy == BLACK_SIGNAL_START:
            self.waiting_for_start = True
            self._running = False
        else:
            self.waiting_for_start = False
            self._running = True

    def signal_start(self) -> None:
        if not self.visible:
            return
        self.waiting_for_start = False
        self.paused = False
        self._running = True

    def pause(self) -> None:
        if self.visible and self._running:
            self.paused = True

    def resume(self) -> None:
        if self.visible and self._running:
            self.paused = False

    def toggle_pause(self) -> None:
        if self.paused:
            self.resume()
        else:
            self.pause()

    def tick(self, white_turn: bool) -> ClockSnapshot:
        """Advance the clock by one second for the player to move."""
        if not self.running:
            return self.snapshot()

        if white_turn:
            self.white_seconds = max(0, self.white_seconds - 1)
        else:
            self.black_seconds = max(0, self.black_seconds - 1)
        return self.snapshot()

    def on_move_completed(self, white_player: bool) -> ClockSnapshot:
        """Apply increment and staged bonus for the player who just moved."""
        if not self.visible:
            return self.snapshot()

        if white_player:
            self.white_move_count += 1
            self.white_seconds += self.increment_seconds
            if self._should_apply_bonus(self.white_move_count, self._white_bonus_applied):
                self.white_seconds += self.control.bonus_seconds
                self._white_bonus_applied = True
        else:
            self.black_move_count += 1
            self.black_seconds += self.increment_seconds
            if self._should_apply_bonus(self.black_move_count, self._black_bonus_applied):
                self.black_seconds += self.control.bonus_seconds
                self._black_bonus_applied = True
        return self.snapshot()

    def snapshot(self) -> ClockSnapshot:
        return ClockSnapshot(
            mode=self.mode,
            label=self.control.label,
            visible=self.visible,
            running=self.running,
            paused=self.paused,
            waiting_for_start=self.waiting_for_start,
            start_policy=self.start_policy,
            white_seconds=self.white_seconds,
            black_seconds=self.black_seconds,
        )

    def _should_apply_bonus(self, move_count: int, already_applied: bool) -> bool:
        return (
            not already_applied
            and self.control.bonus_after_move is not None
            and move_count >= self.control.bonus_after_move
            and self.control.bonus_seconds > 0
        )

    def _control_from_legacy_args(
        self,
        mode: str,
        initial_seconds: int | None,
        increment_seconds: int | None,
    ) -> TimeControl:
        if initial_seconds is None and increment_seconds is None:
            return self._require_time_control(mode)
        base = 180 if initial_seconds is None else int(initial_seconds)
        increment = 0 if increment_seconds is None else int(increment_seconds)
        return TimeControl(
            key=mode,
            label=f"Personalizado {base // 60}+{increment}",
            category="custom",
            base_seconds=base,
            increment_seconds=increment,
            visible=mode != CORRESPONDENCE,
        )

    @staticmethod
    def _require_time_control(key: str) -> TimeControl:
        if key not in TIME_CONTROLS_BY_KEY:
            raise ValueError(f"Control de tiempo desconocido: {key}")
        return TIME_CONTROLS_BY_KEY[key]

    @staticmethod
    def _require_start_policy(start_policy: str) -> str:
        if start_policy not in START_POLICIES:
            raise ValueError(f"Política de inicio desconocida: {start_policy}")
        return start_policy
