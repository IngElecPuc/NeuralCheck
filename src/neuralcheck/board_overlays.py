"""Board overlay primitives used by the desktop UI.

The helpers in this module are deliberately independent from Tkinter so the
geometry used by arrows can be tested without creating a window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FILES = "abcdefgh"
ArrowStyle = Literal["straight", "knight_l"]


@dataclass(frozen=True)
class BoardArrow:
    """A transient or theory-driven arrow drawn on the board."""

    from_square: str
    to_square: str
    color: str = "#e0a800"
    halo_color: str = "#f6d065"
    source: str = "manual"

    @property
    def style(self) -> ArrowStyle:
        return arrow_style_for_squares(self.from_square, self.to_square)


def square_delta(from_square: str, to_square: str) -> tuple[int, int]:
    """Return file/rank delta from origin to target in chess coordinates."""
    _validate_square(from_square)
    _validate_square(to_square)
    file_delta = FILES.index(to_square[0]) - FILES.index(from_square[0])
    rank_delta = int(to_square[1]) - int(from_square[1])
    return file_delta, rank_delta


def is_knight_jump(from_square: str, to_square: str) -> bool:
    """Return true when two squares form a knight move geometry."""
    file_delta, rank_delta = square_delta(from_square, to_square)
    return (abs(file_delta), abs(rank_delta)) in {(1, 2), (2, 1)}


def arrow_style_for_squares(from_square: str, to_square: str) -> ArrowStyle:
    """Select the visual arrow style for a square pair."""
    return "knight_l" if is_knight_jump(from_square, to_square) else "straight"


def _validate_square(square: str) -> None:
    if len(square) != 2 or square[0] not in FILES or square[1] not in "12345678":
        raise ValueError(f"Invalid chess square: {square!r}")
