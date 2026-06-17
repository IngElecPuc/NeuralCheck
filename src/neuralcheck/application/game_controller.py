"""Application boundary between the Tkinter UI and the chess domain logic.

The controller intentionally keeps ``ChessBoard`` as the rule engine for now.
Its job is to expose a stable, UI-oriented contract so widgets do not depend on
internal attributes such as ``possible_moves``, ``pointer`` or ``history``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Protocol, Tuple

from neuralcheck.logic import ChessBoard

PromotionProvider = Callable[[], Optional[str]]


class ChessBoardLike(Protocol):
    """Subset of ChessBoard used by the controller.

    This protocol is deliberately small enough to test the controller without a
    Tkinter root and without coupling UI code to every method in ``ChessBoard``.
    """

    white_turn: bool
    history: list
    pointer: Tuple[int, bool]
    possible_moves: dict

    def what_in(self, position: str) -> str: ...

    def make_move(
        self,
        piece: str,
        initial_position: str,
        end_position: str,
        promote2: Optional[str] = None,
        add2history: bool = True,
    ) -> Tuple[bool, Optional[str]]: ...

    def allowed_movements(self, piece: str, position: str) -> List[str]: ...

    def read_move(self, play: str, white_player: bool) -> Tuple[str, str, str]: ...

    def go2(self, turn: int, white_player: bool) -> None: ...

    def load_game(self, filename: str, go2last: bool = False) -> None: ...

    def save_game(self, filename: str) -> None: ...


@dataclass(frozen=True)
class HistoryRow:
    """One row rendered by the move-history panel."""

    turn_number: int
    white_move: str
    black_move: str
    white_pointer: bool = False
    black_pointer: bool = False


@dataclass(frozen=True)
class MoveAttempt:
    """Result of a user click that can select, clear or move a piece."""

    moved: bool = False
    movement: Optional[str] = None
    selected: bool = False
    cleared_selection: bool = False
    invalid_reason: Optional[str] = None
    piece: Optional[str] = None
    origin: Optional[str] = None
    target: Optional[str] = None
    legal_targets: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ReplayMove:
    """Parsed move from game history for controlled replay."""

    move: str
    piece: str
    origin: str
    target: str
    promote_to: Optional[str]
    white_player: bool


class GameController:
    """Facade used by the desktop UI.

    The class follows a small Controller/Facade pattern: Tkinter translates user
    events to board coordinates, then this object owns selection, movement,
    history navigation and file persistence calls.
    """

    def __init__(self, board: Optional[ChessBoardLike] = None):
        self._board: ChessBoardLike = board if board is not None else ChessBoard()
        self._selected_square: Optional[str] = None
        self._selected_piece: Optional[str] = None

    @property
    def white_turn(self) -> bool:
        return self._board.white_turn

    @property
    def active_color(self) -> str:
        return "white" if self._board.white_turn else "black"

    @property
    def selected_square(self) -> Optional[str]:
        return self._selected_square

    @property
    def selected_piece(self) -> Optional[str]:
        return self._selected_piece

    @property
    def selected(self) -> Optional[Tuple[str, str]]:
        if self._selected_square is None or self._selected_piece is None:
            return None
        return self._selected_square, self._selected_piece

    def new_game(self) -> None:
        self._board = ChessBoard()
        self.clear_selection()

    def piece_at(self, position: str) -> str:
        return self._board.what_in(position)

    def is_empty(self, position: str) -> bool:
        return "Empty" in self.piece_at(position)

    def can_select(self, position: str) -> bool:
        piece = self.piece_at(position)
        return "Empty" not in piece and self._piece_belongs_to_active_player(piece)

    def select(self, position: str) -> MoveAttempt:
        piece = self.piece_at(position)
        if "Empty" in piece:
            self.clear_selection()
            return MoveAttempt(
                cleared_selection=True,
                invalid_reason="empty_square",
                target=position,
            )

        if not self._piece_belongs_to_active_player(piece):
            self.clear_selection()
            return MoveAttempt(
                cleared_selection=True,
                invalid_reason="wrong_turn",
                piece=piece,
                target=position,
            )

        self._selected_square = position
        self._selected_piece = piece
        return MoveAttempt(
            selected=True,
            piece=piece,
            origin=position,
            legal_targets=tuple(self.legal_targets(position)),
        )

    def clear_selection(self) -> None:
        self._selected_square = None
        self._selected_piece = None

    def legal_targets(self, position: str) -> List[str]:
        color_moves = self._board.possible_moves.get(self.active_color, {})
        return list(color_moves.get(position, []))

    def selected_legal_targets(self) -> List[str]:
        if self._selected_square is None:
            return []
        return self.legal_targets(self._selected_square)

    def click_square(self, position: str, promotion_provider: Optional[PromotionProvider] = None) -> MoveAttempt:
        """Handle the selection/move state machine for a board click."""
        if self._selected_square is None or self._selected_piece is None:
            return self.select(position)

        origin = self._selected_square
        piece = self._selected_piece

        if origin == position:
            self.clear_selection()
            return MoveAttempt(
                cleared_selection=True,
                piece=piece,
                origin=origin,
                target=position,
            )

        promote_to = None
        if self._requires_promotion(piece, position):
            if promotion_provider is None:
                return MoveAttempt(
                    invalid_reason="promotion_required",
                    piece=piece,
                    origin=origin,
                    target=position,
                    legal_targets=tuple(self.legal_targets(origin)),
                )
            promote_to = promotion_provider()
            if promote_to is None:
                self.clear_selection()
                return MoveAttempt(
                    cleared_selection=True,
                    invalid_reason="promotion_cancelled",
                    piece=piece,
                    origin=origin,
                    target=position,
                )

        moved, movement = self._board.make_move(piece, origin, position, promote2=promote_to)
        legal_targets = tuple(self.legal_targets(origin))
        self.clear_selection()

        if not moved:
            return MoveAttempt(
                moved=False,
                invalid_reason="illegal_move",
                piece=piece,
                origin=origin,
                target=position,
                legal_targets=legal_targets,
            )

        return MoveAttempt(
            moved=True,
            movement=movement,
            piece=piece,
            origin=origin,
            target=position,
        )

    def load_game(self, filename: str | Path) -> None:
        self._board.load_game(str(filename))
        self.go_to_first()
        self.clear_selection()

    def save_game(self, filename: str | Path) -> None:
        self._board.save_game(str(filename))

    def history_rows(self) -> List[HistoryRow]:
        rows: List[HistoryRow] = []
        pointer_turn, pointer_white = self._board.pointer

        for turn_index, entry in enumerate(self._board.history):
            moves = self._extract_moves(entry)
            white_move = moves[0] if len(moves) >= 1 else ""
            black_move = moves[1] if len(moves) >= 2 else ""
            rows.append(
                HistoryRow(
                    turn_number=turn_index + 1,
                    white_move=white_move,
                    black_move=black_move,
                    white_pointer=(pointer_turn == turn_index and pointer_white),
                    black_pointer=(pointer_turn == turn_index and not pointer_white),
                )
            )

        return rows

    def go_to_first(self) -> bool:
        if not self._board.history:
            self.clear_selection()
            return False

        self._board.pointer = (0, True)
        self._board.go2(0, True)
        self.clear_selection()
        return True

    def previous_step(self) -> bool:
        turn, white_turn = self._board.pointer
        if turn == 0 and white_turn:
            return False

        if white_turn:
            turn -= 1
        white_turn = not white_turn
        self._board.pointer = (turn, white_turn)
        self._board.go2(turn, white_turn)
        self.clear_selection()
        return True

    def next_step(self) -> bool:
        turn, white_turn = self._board.pointer
        if turn == len(self._board.history) and white_turn:
            return False

        if white_turn:
            if turn >= len(self._board.history):
                return False
            moves = self._extract_moves(self._board.history[turn])
            if len(moves) == 1:
                return False
            white_turn = False
        else:
            turn += 1
            white_turn = True

        self._board.pointer = (turn, white_turn)
        self._board.go2(turn, white_turn)
        self.clear_selection()
        return True

    def go_to_last(self) -> bool:
        total_turns = len(self._board.history)
        if total_turns == 0:
            return False

        last_turn_index = total_turns - 1
        moves = self._extract_moves(self._board.history[last_turn_index])
        white_pointer = len(moves) == 1
        self._board.pointer = (last_turn_index, white_pointer)
        self._board.go2(last_turn_index, white_pointer)
        self.clear_selection()
        return True

    def current_replay_move(self) -> Optional[ReplayMove]:
        if not self._board.history:
            return None

        turn, white_player = self._board.pointer
        if turn >= len(self._board.history):
            return None

        moves = self._extract_moves(self._board.history[turn])
        if white_player and len(moves) == 1:
            return None
        if not white_player and len(moves) < 2:
            return None

        move = moves[0] if white_player else moves[1]
        move_without_promotion, promote_to = self._extract_promotion(move, white_player)
        piece, origin, target = self._board.read_move(move_without_promotion, white_player)
        return ReplayMove(
            move=move,
            piece=piece,
            origin=origin,
            target=target,
            promote_to=promote_to,
            white_player=white_player,
        )

    def execute_current_replay_move(self) -> MoveAttempt:
        replay_move = self.current_replay_move()
        if replay_move is None:
            return MoveAttempt(invalid_reason="no_replay_move")

        moved, movement = self._board.make_move(
            replay_move.piece,
            replay_move.origin,
            replay_move.target,
            promote2=replay_move.promote_to,
            add2history=False,
        )

        if not moved:
            legal_targets = tuple(self._board.allowed_movements(replay_move.piece, replay_move.origin))
            return MoveAttempt(
                moved=False,
                invalid_reason="illegal_replay_move",
                piece=replay_move.piece,
                origin=replay_move.origin,
                target=replay_move.target,
                legal_targets=legal_targets,
            )

        return MoveAttempt(
            moved=True,
            movement=movement,
            piece=replay_move.piece,
            origin=replay_move.origin,
            target=replay_move.target,
        )

    def make_debug_bitboard_move(self, movement: str) -> None:
        """Temporary bridge for the existing debug input in the UI."""
        bitboard = getattr(self._board, "bitboard", None)
        if bitboard is None:
            raise RuntimeError("Current board does not expose a bitboard instance")
        bitboard.make_move(movement, self._board.white_turn)

    def _piece_belongs_to_active_player(self, piece: str) -> bool:
        return piece.startswith(self.active_color)

    def _requires_promotion(self, piece: str, target_position: str) -> bool:
        if "pawn" not in piece:
            return False
        if self._board.white_turn:
            return target_position.endswith("8")
        return target_position.endswith("1")

    @staticmethod
    def _extract_moves(entry) -> List[str]:
        if isinstance(entry, (list, tuple)):
            moves = entry[0]
        else:
            moves = entry

        if isinstance(moves, str):
            return [moves]
        if moves is None:
            return []
        return list(moves)

    @staticmethod
    def _extract_promotion(move: str, white_player: bool) -> Tuple[str, Optional[str]]:
        if "=" not in move:
            return move, None

        move_without_promotion, promotion_code = move.split("=", 1)
        promotion_map = {"Q": "queen", "R": "rook", "N": "knight", "B": "bishop"}
        promotion_piece = promotion_map.get(promotion_code)
        if promotion_piece is None:
            return move_without_promotion, None

        prefix = "white " if white_player else "black "
        return move_without_promotion, prefix + promotion_piece
