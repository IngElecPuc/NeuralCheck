"""Application boundary between the Tkinter UI and the chess domain logic.

The controller intentionally keeps ``ChessBoard`` as the rule engine for now.
Its job is to expose a stable, UI-oriented contract so widgets do not depend on
internal attributes such as ``possible_moves``, ``pointer`` or ``history``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Protocol, Tuple

from neuralcheck.logic import ChessBoard, STARTING_FEN_PLACEMENT

PromotionProvider = Callable[[], Optional[str]]
MovePointer = Tuple[int, bool]
NO_MOVE_POINTER: MovePointer = (-1, True)


class ChessBoardLike(Protocol):
    """Subset of ChessBoard used by the controller."""

    white_turn: bool
    history: list
    pointer: MovePointer
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

    def set_position_from_pieces(
        self,
        pieces: Dict[str, str],
        white_turn: bool = True,
        clear_history: bool = True,
    ) -> None: ...

    def set_position_from_fen(self, fen: str, clear_history: bool = True) -> None: ...

    def export_fen(self, include_state: bool = True) -> str: ...

    def assess_ataqued_squares(self, white_player: bool) -> List[str]: ...

    def search_for(self, piece: str) -> List[str]: ...


@dataclass(frozen=True)
class HistoryRow:
    """One row rendered by the move-history panel."""

    turn_number: int
    white_move: str
    black_move: str
    turn_index: int
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
    pointer: MovePointer


@dataclass(frozen=True)
class PositionValidationResult:
    """Validation result for a manually configured chess position."""

    valid: bool
    errors: Tuple[str, ...] = ()
    warnings: Tuple[str, ...] = ()


@dataclass(frozen=True)
class PositionSourceContext:
    """How the current board position can be related to the initial game."""

    source_type: str
    initial_moves: Tuple[str, ...] = ()
    warning: Optional[str] = None

    @property
    def is_synchronized(self) -> bool:
        return self.source_type == "synchronized_line"


class GameController:
    """Facade used by the desktop UI."""

    BOARD_FILES = "abcdefgh"
    BOARD_RANKS = "12345678"
    PIECE_OPTIONS = (
        "Empty square",
        "white king",
        "white queen",
        "white rook",
        "white bishop",
        "white knight",
        "white pawn",
        "black king",
        "black queen",
        "black rook",
        "black bishop",
        "black knight",
        "black pawn",
    )

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

    @property
    def current_pointer(self) -> MovePointer:
        return self._board.pointer

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

    def piece_options(self) -> Tuple[str, ...]:
        return self.PIECE_OPTIONS

    def board_pieces(self) -> Dict[str, str]:
        pieces: Dict[str, str] = {}
        for file_name in self.BOARD_FILES:
            for rank in self.BOARD_RANKS:
                position = f"{file_name}{rank}"
                piece = self.piece_at(position)
                if "Empty" not in piece:
                    pieces[position] = piece
        return pieces

    def current_fen(self, include_state: bool = True) -> str:
        return self._board.export_fen(include_state=include_state)

    def current_position_source_context(self) -> PositionSourceContext:
        """Classify the current board as synchronized or independent.

        A synchronized line is reconstructible from the canonical initial
        position by replaying the visible move history up to the current
        pointer. A position created by the manual editor or by raw FEN loading is
        considered an independent position unless it is exactly the initial
        board.
        """
        initial_fen = f"{STARTING_FEN_PLACEMENT} w - - 0 1"
        current_fen = self.current_fen(include_state=True)
        if current_fen == initial_fen:
            return PositionSourceContext("synchronized_line", ())

        moves = self.current_line_moves()
        if moves is not None and self._line_replays_to_current_position(moves):
            return PositionSourceContext("synchronized_line", tuple(moves))

        return PositionSourceContext(
            "independent_position",
            (),
            "La posición actual no se puede reconstruir desde la partida inicial con el historial visible.",
        )

    def current_line_moves(self) -> Optional[List[str]]:
        """Return SAN-like moves from the beginning up to the shown pointer."""
        pointer_turn, pointer_white = self._board.pointer
        if pointer_turn < 0:
            return []
        if pointer_turn >= len(self._board.history):
            return None

        moves: List[str] = []
        for turn_index, entry in enumerate(self._board.history[: pointer_turn + 1]):
            row_moves = self._extract_moves(entry)
            if not row_moves:
                continue

            include_count = len(row_moves)
            if turn_index == pointer_turn:
                include_count = 1 if pointer_white else min(2, len(row_moves))

            for move in row_moves[:include_count]:
                if move and move != "...":
                    moves.append(move)
        return moves

    def load_line_from_initial(self, moves: List[str] | Tuple[str, ...]) -> PositionValidationResult:
        """Load a board by replaying a legal line from the initial position."""
        replay_board = ChessBoard()
        try:
            for ply_index, move in enumerate(moves):
                white_player = ply_index % 2 == 0
                replay_board.white_turn = white_player
                replay_board.possible_moves = replay_board.calculate_possible_moves()
                move_without_promotion, promote_to = self._extract_promotion(move, white_player)
                piece, origin, target = replay_board.read_move(move_without_promotion, white_player)
                moved, _ = replay_board.make_move(
                    piece,
                    origin,
                    target,
                    promote2=promote_to,
                    add2history=True,
                )
                if not moved:
                    return PositionValidationResult(False, (f"No se pudo reproducir la jugada: {move}",))
        except Exception as exc:
            return PositionValidationResult(False, (f"No se pudo reproducir la línea: {exc}",))

        self._board = replay_board
        self.clear_selection()
        return PositionValidationResult(True)

    def _line_replays_to_current_position(self, moves: List[str]) -> bool:
        validation = self._validate_line_against_fen(moves, self.current_fen(include_state=True))
        return validation.valid

    def _validate_line_against_fen(self, moves: List[str], expected_fen: str) -> PositionValidationResult:
        original_board = self._board
        original_selected_square = self._selected_square
        original_selected_piece = self._selected_piece
        try:
            validation = self.load_line_from_initial(moves)
            if not validation.valid:
                return validation
            actual_fen = self.current_fen(include_state=True)
            if actual_fen != expected_fen:
                return PositionValidationResult(
                    False,
                    (
                        "La línea visible no reconstruye la posición actual.",
                        f"Esperado: {expected_fen}",
                        f"Obtenido: {actual_fen}",
                    ),
                )
            return PositionValidationResult(True)
        finally:
            self._board = original_board
            self._selected_square = original_selected_square
            self._selected_piece = original_selected_piece

    def apply_manual_position(self, pieces: Dict[str, str], white_turn: bool) -> PositionValidationResult:
        validation = self.validate_manual_position(pieces, white_turn)
        if not validation.valid:
            return validation

        clean_pieces = {
            position: piece
            for position, piece in pieces.items()
            if piece != "Empty square"
        }
        self._board.set_position_from_pieces(clean_pieces, white_turn=white_turn, clear_history=True)
        self.clear_selection()
        return validation

    def apply_fen_position(self, fen: str) -> PositionValidationResult:
        try:
            candidate = ChessBoard()
            candidate.set_position_from_fen(fen, clear_history=True)
        except (KeyError, ValueError, IndexError) as exc:
            return PositionValidationResult(False, (f"FEN inválido: {exc}",))

        pieces: Dict[str, str] = {}
        for file_name in self.BOARD_FILES:
            for rank in self.BOARD_RANKS:
                position = f"{file_name}{rank}"
                piece = candidate.what_in(position)
                if "Empty" not in piece:
                    pieces[position] = piece

        validation = self.validate_manual_position(pieces, candidate.white_turn)
        if not validation.valid:
            return validation

        self._board.set_position_from_fen(fen, clear_history=True)
        self.clear_selection()
        return validation

    def validate_manual_position(self, pieces: Dict[str, str], white_turn: bool) -> PositionValidationResult:
        del white_turn  # Reserved for future checks that depend on side to move.
        errors: List[str] = []
        warnings: List[str] = []
        clean_pieces: Dict[str, str] = {}

        for position, piece in pieces.items():
            if piece == "Empty square":
                continue
            if not self._is_valid_square(position):
                errors.append(f"Casilla inválida: {position}")
                continue
            if piece not in self.PIECE_OPTIONS or piece == "Empty square":
                errors.append(f"Pieza inválida en {position}: {piece}")
                continue
            if "pawn" in piece and position[1] in {"1", "8"}:
                errors.append(f"Peón en fila de promoción sin promover: {position}")
            clean_pieces[position] = piece

        white_kings = [position for position, piece in clean_pieces.items() if piece == "white king"]
        black_kings = [position for position, piece in clean_pieces.items() if piece == "black king"]
        if len(white_kings) != 1:
            errors.append("Debe existir exactamente un rey blanco")
        if len(black_kings) != 1:
            errors.append("Debe existir exactamente un rey negro")

        if errors:
            return PositionValidationResult(False, tuple(errors), tuple(warnings))

        board = ChessBoard()
        board.set_position_from_pieces(clean_pieces, white_turn=True, clear_history=True)
        white_in_check = white_kings[0] in board.assess_ataqued_squares(False)
        black_in_check = black_kings[0] in board.assess_ataqued_squares(True)
        if white_in_check and black_in_check:
            errors.append("La posición deja ambos reyes en jaque")

        if not errors:
            warnings.append(
                "Los derechos de enroque y en passant aún no forman parte del contrato de posición manual"
            )

        return PositionValidationResult(not errors, tuple(errors), tuple(warnings))

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
                    turn_index=turn_index,
                    white_pointer=(pointer_turn == turn_index and pointer_white),
                    black_pointer=(pointer_turn == turn_index and not pointer_white),
                )
            )

        return rows

    def go_to_first(self) -> bool:
        if not self._board.history:
            self.clear_selection()
            return False

        self._board.go2(*NO_MOVE_POINTER)
        self.clear_selection()
        return True

    def previous_step(self) -> bool:
        previous_pointer = self._previous_pointer(self._board.pointer)
        if previous_pointer is None:
            return False

        self._board.go2(*previous_pointer)
        self.clear_selection()
        return True

    def next_step(self) -> bool:
        next_pointer = self._next_pointer(self._board.pointer)
        if next_pointer is None:
            return False

        self._board.go2(*next_pointer)
        self.clear_selection()
        return True

    def go_to_last(self) -> bool:
        last_pointer = self._last_pointer()
        if last_pointer is None:
            return False

        self._board.go2(*last_pointer)
        self.clear_selection()
        return True

    def jump_to_move(self, turn_index: int, white_player: bool) -> bool:
        if not self._pointer_exists((turn_index, white_player)):
            return False

        self._board.go2(turn_index, white_player)
        self.clear_selection()
        return True

    def current_replay_move(self) -> Optional[ReplayMove]:
        next_pointer = self._next_pointer(self._board.pointer)
        if next_pointer is None:
            return None

        turn, white_player = next_pointer
        moves = self._extract_moves(self._board.history[turn])
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
            pointer=next_pointer,
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

        self._board.pointer = replay_move.pointer
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

    def _pointer_exists(self, pointer: MovePointer) -> bool:
        turn, white_player = pointer
        if turn < 0:
            return True
        if turn >= len(self._board.history):
            return False
        moves = self._extract_moves(self._board.history[turn])
        return len(moves) >= (1 if white_player else 2)

    def _next_pointer(self, pointer: MovePointer) -> Optional[MovePointer]:
        if not self._board.history:
            return None

        turn, white_player = pointer
        if turn < 0:
            return (0, True) if self._pointer_exists((0, True)) else None

        if white_player:
            if self._pointer_exists((turn, False)):
                return (turn, False)
            next_turn = turn + 1
            return (next_turn, True) if self._pointer_exists((next_turn, True)) else None

        next_turn = turn + 1
        return (next_turn, True) if self._pointer_exists((next_turn, True)) else None

    def _previous_pointer(self, pointer: MovePointer) -> Optional[MovePointer]:
        turn, white_player = pointer
        if turn < 0:
            return None

        if not white_player:
            return (turn, True) if self._pointer_exists((turn, True)) else NO_MOVE_POINTER

        if turn == 0:
            return NO_MOVE_POINTER

        previous_turn = turn - 1
        if self._pointer_exists((previous_turn, False)):
            return (previous_turn, False)
        if self._pointer_exists((previous_turn, True)):
            return (previous_turn, True)
        return NO_MOVE_POINTER

    def _last_pointer(self) -> Optional[MovePointer]:
        if not self._board.history:
            return None

        last_turn_index = len(self._board.history) - 1
        moves = self._extract_moves(self._board.history[last_turn_index])
        if len(moves) >= 2:
            return last_turn_index, False
        if len(moves) == 1:
            return last_turn_index, True
        return None

    @classmethod
    def _is_valid_square(cls, position: str) -> bool:
        return (
            isinstance(position, str)
            and len(position) == 2
            and position[0] in cls.BOARD_FILES
            and position[1] in cls.BOARD_RANKS
        )

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
