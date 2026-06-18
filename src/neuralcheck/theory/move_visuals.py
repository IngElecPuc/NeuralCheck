"""Visual helpers for theory moves.

These functions infer board highlights from two FEN positions. They are UI-agnostic
so the graph preview and main board overlays can share the same move detection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class MoveVisualHint:
    """Squares that communicate the move from one node to another."""

    from_square: Optional[str]
    to_square: Optional[str]

    @property
    def complete(self) -> bool:
        return self.from_square is not None and self.to_square is not None


FILES = "abcdefgh"
RANKS = "87654321"


def fen_piece_map(fen: str) -> Dict[str, str]:
    """Return a square -> FEN token mapping from a FEN string."""
    placement = fen.split()[0]
    rows = placement.split("/")
    if len(rows) != 8:
        return {}

    pieces: Dict[str, str] = {}
    for row_index, row_value in enumerate(rows):
        file_index = 0
        rank = RANKS[row_index]
        for token in row_value:
            if token.isdigit():
                file_index += int(token)
                continue
            if 0 <= file_index < 8:
                pieces[f"{FILES[file_index]}{rank}"] = token
            file_index += 1
    return pieces


def detect_move_visual_hint(parent_fen: Optional[str], child_fen: Optional[str]) -> MoveVisualHint:
    """Infer origin/destination squares from parent and child FEN positions.

    The result intentionally focuses on the piece move. For castling, the king
    move is reported. For en passant, the pawn origin and destination are
    reported and the captured pawn square is ignored for this visual purpose.
    """
    if not parent_fen or not child_fen:
        return MoveVisualHint(None, None)

    parent = fen_piece_map(parent_fen)
    child = fen_piece_map(child_fen)
    if not parent or not child:
        return MoveVisualHint(None, None)

    side_to_move = _side_to_move(parent_fen)
    is_moving_piece = str.isupper if side_to_move == "white" else str.islower

    changed_squares = {
        square for square in set(parent) | set(child) if parent.get(square) != child.get(square)
    }
    from_candidates = [
        square
        for square in changed_squares
        if square in parent and is_moving_piece(parent[square]) and child.get(square) != parent[square]
    ]
    to_candidates = [
        square
        for square in changed_squares
        if square in child and is_moving_piece(child[square]) and parent.get(square) != child[square]
    ]

    if not from_candidates or not to_candidates:
        return MoveVisualHint(None, None)

    castling_hint = _castling_hint(parent, child, from_candidates, to_candidates, side_to_move)
    if castling_hint.complete:
        return castling_hint

    best = _best_piece_match(parent, child, from_candidates, to_candidates)
    if best.complete:
        return best

    return MoveVisualHint(_sort_squares(from_candidates)[0], _sort_squares(to_candidates)[0])


def _side_to_move(fen: str) -> str:
    parts = fen.split()
    if len(parts) > 1 and parts[1] == "b":
        return "black"
    return "white"


def _castling_hint(
    parent: Dict[str, str],
    child: Dict[str, str],
    from_candidates: list[str],
    to_candidates: list[str],
    side_to_move: str,
) -> MoveVisualHint:
    king_token = "K" if side_to_move == "white" else "k"
    king_from = [square for square in from_candidates if parent.get(square) == king_token]
    king_to = [square for square in to_candidates if child.get(square) == king_token]
    if king_from and king_to:
        return MoveVisualHint(_sort_squares(king_from)[0], _sort_squares(king_to)[0])
    return MoveVisualHint(None, None)


def _best_piece_match(
    parent: Dict[str, str],
    child: Dict[str, str],
    from_candidates: list[str],
    to_candidates: list[str],
) -> MoveVisualHint:
    # Prefer same piece token, which covers normal moves and captures.
    for origin in _sort_squares(from_candidates):
        origin_piece = parent[origin]
        for target in _sort_squares(to_candidates):
            if child[target] == origin_piece:
                return MoveVisualHint(origin, target)

    # Promotion keeps color but changes piece type. Prefer pawn origins when no
    # same-token match exists.
    for origin in _sort_squares(from_candidates):
        if parent[origin].lower() != "p":
            continue
        for target in _sort_squares(to_candidates):
            if parent[origin].isupper() == child[target].isupper():
                return MoveVisualHint(origin, target)

    return MoveVisualHint(None, None)


def _sort_squares(squares: list[str]) -> list[str]:
    return sorted(squares, key=lambda square: (square[1], square[0]))
