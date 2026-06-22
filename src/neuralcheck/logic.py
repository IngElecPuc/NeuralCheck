import numpy as np
try:
    import bitboardops as bb
except ModuleNotFoundError:
    from neuralcheck import bitboardops_fallback as bb
import yaml
from pathlib import Path
from neuralcheck.bitboard import ChessBitboard
from typing import Tuple, List, Dict, Optional

BOARD_SIZE = 8
STARTING_FEN_PLACEMENT = 'rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR'
PROJECT_ROOT = Path(__file__).resolve().parents[2]

class ChessBoard:
    def __init__(self, board=None, white_turn: bool = True, position_file: str = None):
        #NOTE This is a high level representation of the board.
        #It uses a 8x8 numpy matrix (check put method to see piece representation).
        #This class has direct communication with the UI to handle it.
        #This representation is not optimal for search or machine learning.
        #There is a lower level for this using bitboard representations.
        #That level is synchronized with this for tracking purposes.

        self.initializing       = True
        self._initialize_resources()
        self.line_vectors       = np.array([[1, 0], [-1, 0], [0, 1], [0, -1]], dtype=np.int64)
        self.diagonal_vectors   = np.array([[1, 1], [-1, 1], [-1, -1], [1, -1]], dtype=np.int64)
        self.pinned_pieces      = []
        self.pointer            = (-1, True)

        self.clear_board()
        if board is None:
            self.load_position(position_file or 'config/initial_position.yaml')
        else:
            self.board = np.array(board, dtype=np.int64)
            if self.board.shape != (BOARD_SIZE, BOARD_SIZE):
                raise ValueError(f'board must have shape {(BOARD_SIZE, BOARD_SIZE)}')
            self.white_turn = bool(white_turn)
            self.bitboard = ChessBitboard(self.board)

        self.possible_moves     = self.calculate_possible_moves()
        self.bitboard           = ChessBitboard(self.board)
        self.initializing       = False

    def _initialize_resources(self) -> None:
        """
        Initialize a series of lists, arrays and dictionaries to not calculate them after
        """
        self._cols_str = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        self._cols2int = {col:num for num, col in enumerate(self._cols_str)}
        self._int2cols = {num:col for num, col in enumerate(self._cols_str)}
        self._pieces = ['pawn', 'knight', 'bishop', 'rook', 'queen', 'king']
        self.name2num = {name:(num+1) for num, name in enumerate(self._pieces)}
        self.num2name = {(num+1):name for num, name in enumerate(self._pieces)}
        self.name2num['Empty square'] = 0
        self.num2name[0] = 'Empty square'

    def _resolve_path(self, filename: str) -> Path:
        """Resolve project-relative files while still accepting absolute paths."""
        path = Path(filename)
        if path.is_absolute():
            return path

        cwd_path = Path.cwd() / path
        if cwd_path.exists():
            return cwd_path

        project_path = PROJECT_ROOT / path
        if project_path.exists():
            return project_path

        return project_path

    def _normalize_move_vectors(self, vectors) -> np.array:
        """Return movement vectors with a stable ``(n, 2)`` shape."""
        if vectors is None:
            return np.empty((0, 2), dtype=np.int64)

        array = np.asarray(vectors, dtype=np.int64)
        if array.size == 0:
            return np.empty((0, 2), dtype=np.int64)

        return array.reshape((-1, 2))
    
    def _position_in_bounds(self, position: str) -> bool:
        if not isinstance(position, str) or len(position) != 2:
            return False
        col, row = position[0], position[1]
        return col in self._cols2int and row in {str(i) for i in range(1, BOARD_SIZE + 1)}

    def _color_from_piece(self, piece: str) -> Optional[str]:
        if piece.startswith('white '):
            return 'white'
        if piece.startswith('black '):
            return 'black'
        return None

    def _color_from_value(self, value: int) -> Optional[str]:
        if value > 0:
            return 'white'
        if value < 0:
            return 'black'
        return None

    def _piece_from_value(self, value: int) -> str:
        color = self._color_from_value(value)
        if color is None:
            return 'Empty square'
        return f'{color} {self.num2name[abs(int(value))]}'

    def _piece_value(self, piece: str) -> int:
        if 'Empty' in piece:
            return 0
        color, name = piece.split(' ', 1)
        return self.name2num[name] * (1 if color == 'white' else -1)

    def _active_color(self) -> str:
        return 'white' if self.white_turn else 'black'

    def _opponent_color(self, color: str) -> str:
        return 'black' if color == 'white' else 'white'

    def _normalize_en_passant_target(self, target: Optional[str]) -> Optional[str]:
        if target is None or target == '-':
            return None
        if not self._position_in_bounds(target):
            raise ValueError(f"Invalid en-passant target square: {target}")
        if target[1] not in {'3', '6'}:
            raise ValueError(f"Invalid en-passant target rank: {target}")
        return target

    def _en_passant_target_from_last_turn(self, color: str) -> Optional[str]:
        """Return a legacy en-passant target inferred from ``last_turn``.

        Older code and tests represented the en-passant right only as the last
        double pawn move. The explicit FEN-backed state now lives in
        ``en_passant_target``, but this fallback keeps direct ``last_turn``
        callers compatible.
        """
        last_piece, last_initial, last_end = self.last_turn
        if last_piece is None or last_initial is None or last_end is None:
            return None
        if 'pawn' not in last_piece:
            return None
        if self._color_from_piece(last_piece) == color:
            return None

        last_initial_x, last_initial_y = self.logic2array(last_initial)
        last_end_x, last_end_y = self.logic2array(last_end)
        if last_initial_y != last_end_y or abs(last_initial_x - last_end_x) != 2:
            return None
        if int(self.board[last_end_x, last_end_y]) != self._piece_value(last_piece):
            return None

        return self.array2logic((last_initial_x + last_end_x) // 2, last_end_y)

    def _current_en_passant_target(self, color: str) -> Optional[str]:
        return self.en_passant_target or self._en_passant_target_from_last_turn(color)

    def _set_en_passant_after_move(self, piece: str, initial_position: str, end_position: str) -> None:
        self.en_passant_target = None
        if 'pawn' not in piece:
            return
        initial_x, initial_y = self.logic2array(initial_position)
        end_x, end_y = self.logic2array(end_position)
        if initial_y == end_y and abs(initial_x - end_x) == 2:
            self.en_passant_target = self.array2logic((initial_x + end_x) // 2, initial_y)

    def _is_en_passant_move_on_board(
        self,
        board: np.array,
        piece: str,
        initial_position: str,
        end_position: str,
    ) -> bool:
        color = self._color_from_piece(piece)
        if color is None or 'pawn' not in piece:
            return False
        initial_x, initial_y = self.logic2array(initial_position)
        end_x, end_y = self.logic2array(end_position)
        if initial_y == end_y or int(board[end_x, end_y]) != 0:
            return False

        target = self._current_en_passant_target(color)
        if end_position != target:
            return False

        captured_x = initial_x
        captured_y = end_y
        if not (0 <= captured_x < BOARD_SIZE and 0 <= captured_y < BOARD_SIZE):
            return False
        return int(board[captured_x, captured_y]) == -self._color_sign(color)

    def _color_sign(self, color: str) -> int:
        return 1 if color == 'white' else -1

    def _target_has_own_piece(self, board: np.array, x: int, y: int, color: str) -> bool:
        return self._color_sign(color) * int(board[x, y]) > 0

    def _target_has_enemy_piece(self, board: np.array, x: int, y: int, color: str) -> bool:
        return self._color_sign(color) * int(board[x, y]) < 0

    def _find_king_position(self, board: np.array, color: str) -> Optional[str]:
        king_value = 6 * self._color_sign(color)
        rows, cols = np.where(board == king_value)
        if rows.size != 1 or cols.size != 1:
            return None
        return self.array2logic(int(rows[0]), int(cols[0]))

    def _sync_bitboard(self) -> None:
        self.bitboard = ChessBitboard(self.board)

    def _refresh_possible_moves(self) -> None:
        self.pinned_pieces = []
        self.possible_moves = self.calculate_possible_moves()
        self._sync_bitboard()

    def refresh_state(self) -> None:
        """Recalculate legal moves and bitboards after direct board editing."""
        self._refresh_possible_moves()

    def _dedupe_preserve_order(self, moves: List[str]) -> List[str]:
        seen = set()
        unique_moves = []
        for move in moves:
            if move not in seen:
                seen.add(move)
                unique_moves.append(move)
        return unique_moves

    def _raycast_targets(
        self,
        board: np.array,
        x: int,
        y: int,
        vectors: np.array,
        color: str,
        for_attack: bool = False,
    ) -> List[str]:
        targets: List[str] = []
        for dx, dy in self._normalize_move_vectors(vectors):
            for distance in range(1, BOARD_SIZE):
                target_x, target_y = x + distance * dx, y + distance * dy
                if not (0 <= target_x < BOARD_SIZE and 0 <= target_y < BOARD_SIZE):
                    break

                value = int(board[target_x, target_y])
                if value == 0:
                    targets.append(self.array2logic(target_x, target_y))
                    continue

                if for_attack:
                    targets.append(self.array2logic(target_x, target_y))
                    break

                if self._target_has_enemy_piece(board, target_x, target_y, color):
                    targets.append(self.array2logic(target_x, target_y))
                break
        return targets

    def _pawn_targets(
        self,
        board: np.array,
        x: int,
        y: int,
        color: str,
        for_attack: bool = False,
    ) -> List[str]:
        direction = -1 if color == 'white' else 1
        start_rank_x = 6 if color == 'white' else 1
        en_passant_rank_x = 3 if color == 'white' else 4
        targets: List[str] = []

        for diagonal_y in (y - 1, y + 1):
            target_x = x + direction
            if 0 <= target_x < BOARD_SIZE and 0 <= diagonal_y < BOARD_SIZE:
                if for_attack:
                    targets.append(self.array2logic(target_x, diagonal_y))
                elif self._target_has_enemy_piece(board, target_x, diagonal_y, color):
                    targets.append(self.array2logic(target_x, diagonal_y))

        if for_attack:
            return targets

        one_step_x = x + direction
        if 0 <= one_step_x < BOARD_SIZE and board[one_step_x, y] == 0:
            targets.append(self.array2logic(one_step_x, y))
            two_step_x = x + 2 * direction
            if x == start_rank_x and 0 <= two_step_x < BOARD_SIZE and board[two_step_x, y] == 0:
                targets.append(self.array2logic(two_step_x, y))

        if x == en_passant_rank_x:
            targets.extend(self._en_passant_targets(board, x, y, color))

        return targets

    def _en_passant_targets(self, board: np.array, x: int, y: int, color: str) -> List[str]:
        target = self._current_en_passant_target(color)
        if target is None:
            return []

        target_x, target_y = self.logic2array(target)
        direction = -1 if color == 'white' else 1
        if target_x != x + direction or abs(target_y - y) != 1:
            return []
        if int(board[target_x, target_y]) != 0:
            return []

        captured_x = x
        captured_y = target_y
        if int(board[captured_x, captured_y]) != -self._color_sign(color):
            return []

        return [target]

    def _king_targets(
        self,
        board: np.array,
        x: int,
        y: int,
        color: str,
        for_attack: bool = False,
    ) -> List[str]:
        targets: List[str] = []
        for dx, dy in self._normalize_move_vectors(np.array([[1, 0], [1, 1], [0, 1], [-1, 1], [-1, 0], [-1, -1], [0, -1], [1, -1]])):
            target_x, target_y = x + dx, y + dy
            if not (0 <= target_x < BOARD_SIZE and 0 <= target_y < BOARD_SIZE):
                continue
            if for_attack or not self._target_has_own_piece(board, target_x, target_y, color):
                targets.append(self.array2logic(target_x, target_y))

        if not for_attack:
            targets.extend(self._castling_targets(board, color))

        return targets

    def _castling_targets(self, board: np.array, color: str) -> List[str]:
        targets: List[str] = []
        rank = '1' if color == 'white' else '8'
        king_start = f'e{rank}'
        king_x, king_y = self.logic2array(king_start)
        if self._piece_from_value(int(board[king_x, king_y])) != f'{color} king':
            return targets

        king_flag = f'{color} king moved'
        if self.castle_flags.get(king_flag, False):
            return targets
        if self._is_square_attacked_on_board(board, king_start, self._opponent_color(color)):
            return targets

        options = (
            {
                'rook_start': f'h{rank}',
                'rook_flag': f'h{rank} rook moved',
                'empty_squares': [f'f{rank}', f'g{rank}'],
                'safe_squares': [f'f{rank}', f'g{rank}'],
                'target': f'g{rank}',
            },
            {
                'rook_start': f'a{rank}',
                'rook_flag': f'a{rank} rook moved',
                'empty_squares': [f'b{rank}', f'c{rank}', f'd{rank}'],
                'safe_squares': [f'd{rank}', f'c{rank}'],
                'target': f'c{rank}',
            },
        )

        for option in options:
            rook_x, rook_y = self.logic2array(option['rook_start'])
            if self._piece_from_value(int(board[rook_x, rook_y])) != f'{color} rook':
                continue
            if self.castle_flags.get(option['rook_flag'], False):
                continue
            path_is_empty = True
            for square in option['empty_squares']:
                square_x, square_y = self.logic2array(square)
                if int(board[square_x, square_y]) != 0:
                    path_is_empty = False
                    break
            if not path_is_empty:
                continue
            if any(self._is_square_attacked_on_board(board, square, self._opponent_color(color)) for square in option['safe_squares']):
                continue
            targets.append(option['target'])

        return targets

    def _pseudo_targets_for_piece(
        self,
        board: np.array,
        piece: str,
        position: str,
        for_attack: bool = False,
    ) -> List[str]:
        if not self._position_in_bounds(position):
            return []

        color = self._color_from_piece(piece)
        if color is None:
            return []

        x, y = self.logic2array(position)
        if not (0 <= x < BOARD_SIZE and 0 <= y < BOARD_SIZE):
            return []

        if 'pawn' in piece:
            return self._dedupe_preserve_order(self._pawn_targets(board, x, y, color, for_attack=for_attack))
        if 'knight' in piece:
            vectors = np.array([[2, 1], [1, 2], [-1, 2], [-2, 1], [-2, -1], [-1, -2], [1, -2], [2, -1]])
            targets = []
            for dx, dy in self._normalize_move_vectors(vectors):
                target_x, target_y = x + dx, y + dy
                if not (0 <= target_x < BOARD_SIZE and 0 <= target_y < BOARD_SIZE):
                    continue
                if for_attack or not self._target_has_own_piece(board, target_x, target_y, color):
                    targets.append(self.array2logic(target_x, target_y))
            return self._dedupe_preserve_order(targets)
        if 'bishop' in piece:
            return self._dedupe_preserve_order(self._raycast_targets(board, x, y, self.diagonal_vectors, color, for_attack=for_attack))
        if 'rook' in piece:
            return self._dedupe_preserve_order(self._raycast_targets(board, x, y, self.line_vectors, color, for_attack=for_attack))
        if 'queen' in piece:
            all_vectors = np.concatenate((self.line_vectors, self.diagonal_vectors))
            return self._dedupe_preserve_order(self._raycast_targets(board, x, y, all_vectors, color, for_attack=for_attack))
        if 'king' in piece:
            return self._dedupe_preserve_order(self._king_targets(board, x, y, color, for_attack=for_attack))
        return []

    def _is_square_attacked_on_board(self, board: np.array, square: str, by_color: str) -> bool:
        for x in range(BOARD_SIZE):
            for y in range(BOARD_SIZE):
                value = int(board[x, y])
                if value == 0 or self._color_from_value(value) != by_color:
                    continue
                piece = self._piece_from_value(value)
                position = self.array2logic(x, y)
                if square in self._pseudo_targets_for_piece(board, piece, position, for_attack=True):
                    return True
        return False

    def _is_king_in_check_on_board(self, board: np.array, color: str) -> bool:
        king_position = self._find_king_position(board, color)
        if king_position is None:
            return False
        return self._is_square_attacked_on_board(board, king_position, self._opponent_color(color))

    def _board_after_move(self, piece: str, initial_position: str, end_position: str) -> np.array:
        board = self.board.copy()
        initial_x, initial_y = self.logic2array(initial_position)
        end_x, end_y = self.logic2array(end_position)
        color = self._color_from_piece(piece)

        if self._is_en_passant_move_on_board(board, piece, initial_position, end_position):
            # En passant removes the pawn behind the landing square.
            captured_x = initial_x
            captured_y = end_y
            board[captured_x, captured_y] = 0

        board[end_x, end_y] = board[initial_x, initial_y]
        board[initial_x, initial_y] = 0

        if 'king' in piece and abs(end_y - initial_y) == 2:
            if end_y > initial_y:
                rook_initial = f'h{initial_position[1]}'
                rook_end = f'f{initial_position[1]}'
            else:
                rook_initial = f'a{initial_position[1]}'
                rook_end = f'd{initial_position[1]}'
            rook_initial_x, rook_initial_y = self.logic2array(rook_initial)
            rook_end_x, rook_end_y = self.logic2array(rook_end)
            board[rook_end_x, rook_end_y] = board[rook_initial_x, rook_initial_y]
            board[rook_initial_x, rook_initial_y] = 0

        return board

    def _would_leave_king_in_check(self, piece: str, initial_position: str, end_position: str) -> bool:
        color = self._color_from_piece(piece)
        if color is None:
            return True
        board_after = self._board_after_move(piece, initial_position, end_position)
        return self._is_king_in_check_on_board(board_after, color)

    def _promotion_is_valid(self, piece: str, end_position: str, promote2: Optional[str]) -> bool:
        if 'pawn' not in piece:
            return promote2 is None
        reaches_last_rank = ('white' in piece and end_position.endswith('8')) or ('black' in piece and end_position.endswith('1'))
        if not reaches_last_rank:
            return promote2 is None
        if promote2 is None:
            return False
        if self._color_from_piece(promote2) != self._color_from_piece(piece):
            return False
        return any(name in promote2 for name in ('queen', 'rook', 'bishop', 'knight'))

    def _update_castle_flags_after_move(self, piece: str, initial_position: str, end_position: str, captured_piece: str) -> None:
        if 'king' in piece:
            if 'white' in piece:
                self.castle_flags['white king moved'] = True
            else:
                self.castle_flags['black king moved'] = True

        if 'rook' in piece:
            rook_flags = {
                'a1': 'a1 rook moved',
                'h1': 'h1 rook moved',
                'a8': 'a8 rook moved',
                'h8': 'h8 rook moved',
            }
            if initial_position in rook_flags:
                self.castle_flags[rook_flags[initial_position]] = True

        if 'rook' in captured_piece:
            captured_rook_flags = {
                'a1': 'a1 rook moved',
                'h1': 'h1 rook moved',
                'a8': 'a8 rook moved',
                'h8': 'h8 rook moved',
            }
            if end_position in captured_rook_flags:
                self.castle_flags[captured_rook_flags[end_position]] = True

    def clear_board(self) -> None:
        """
        Clears all history and pieces from the board
        """
        self.board = np.zeros((BOARD_SIZE,BOARD_SIZE), dtype=np.int64)
        self.history = []
        self.last_turn = (None, None, None)
        self.en_passant_target: Optional[str] = None
        self.castle_flags = {
            'white king moved': False,
            'black king moved': False,
            'a1 rook moved': False,
            'h1 rook moved': False,
            'a8 rook moved': False,
            'h8 rook moved': False
            }

    def logic2array(self, position:str) -> Tuple[int, int]:
        """
        Transforms a chess position to an index position fro drawing

        Parameters:
            position: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'

        Returns:
            Tuple(int, int): two ints representing the position in numpy index coordinates
        """
        col, row = position[0], int(position[1])
        x = BOARD_SIZE - row
        y = self._cols2int[col]
        return x, y
    
    def array2logic(self, x:int , y:int) -> str: 
        """
        Transforms a couple of numpy indexs to a chess position

        Parameters:
            x: the row index
            y: the col index

        Returns:
            str: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'
        """
        col = self._int2cols[y]
        row = BOARD_SIZE - x
        return f'{col}{row}'

    def set_piece(self, piece:str, position:str) -> None:
        """
        Puts pieces in the numpy board representation using index
            Piece map:
            white -> positive
            black -> negative
            pawn -> 1
            knight -> 2
            bishop -> 3
            rook -> 4
            queen -> 5
            king -> 6

        Parameters:
            piece: a string indicating color and piece, e.g., 'white king'
            position: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'
        """
        
        x, y = self.logic2array(position) 
        
        if 'Empty' not in piece:
            piece = piece.split(' ')
            color = piece[0]
            piece = piece[1]
            self.board[x, y] = self.name2num[piece] * (1 if color == 'white' else -1)
        else:
            self.board[x, y] = self.name2num[piece]

    def what_in(self, position:str) -> str:
        """
        Search position to display information of the piece in it or the color of the square if empty

        Parameters:
            position: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'        

        Returns:
            str: information founded in the position
        """
        x, y = self.logic2array(position) 
        piece = self.board[x, y]
        color = 'white' if piece > 0 else 'black'
        name = self.num2name[np.abs(piece)]
        if name == 'Empty square': 
            color = 'white' if (x + y) % 2 == 0 else 'black'
            return f'Empty {color} square'
        else:
            return f'{color} {name}'

    def search_for(self, piece:str) -> List:
        """
        Search for all positions of pieces of the same type

        Parameters:
            piece: a string indicating color and piece, e.g., 'white king'

        Returns:
            List: a list of all positions where is a piece of the same type
        """
        piece_code  = self.name2num[piece.split(' ')[1]]
        piece_code  = piece_code if 'white' in piece else -piece_code
        all_pieces  = np.where(self.board == piece_code)
        all_pieces  = np.array(all_pieces).T
        in_coords   = [0] * len(all_pieces)
        for i, (x, y) in enumerate(all_pieces):
            in_coords[i] = self.array2logic(x, y)
        return in_coords

    def allowed_movements(
        self,
        piece: str,
        position: str,
        in_check: bool = False,
        restrict_turn: bool = True,
        remove_own: bool = True,
    ) -> List[str]:
        """
        Return legal target squares for one piece.

        The pipeline is now explicit:
            1. Generate pseudo-legal targets for the piece.
            2. For attack maps, return pseudo-attacks without king-safety filtering.
            3. For legal moves, simulate each target and reject moves that leave
               the moving side's king in check.
        """
        del in_check  # Kept for backward compatibility with older call sites.

        if not self._position_in_bounds(position):
            return []

        color = self._color_from_piece(piece)
        if color is None:
            return []

        board_x, board_y = self.logic2array(position)
        board_piece = self._piece_from_value(int(self.board[board_x, board_y]))
        if board_piece != piece:
            return []

        if restrict_turn and color != self._active_color():
            return []

        if not remove_own:
            return self._pseudo_targets_for_piece(self.board, piece, position, for_attack=True)

        pseudo_targets = self._pseudo_targets_for_piece(self.board, piece, position, for_attack=False)
        legal_targets = [
            target
            for target in pseudo_targets
            if not self._would_leave_king_in_check(piece, position, target)
        ]
        return self._dedupe_preserve_order(legal_targets)

    def raycast(self, x: int, y: int, vectors: np.array, white_turn: bool, remove_own: bool = True) -> np.array:
        """
        Backward-compatible vector raycast wrapper.

        New rule code uses target-square helpers, but minimax/debug code may still
        call this method. It no longer mutates pinned-piece state as a side effect.
        """
        color = 'white' if white_turn else 'black'
        targets = self._raycast_targets(self.board, x, y, vectors, color, for_attack=not remove_own)
        origin = np.array([x, y], dtype=np.int64)
        vectors_out = []
        for target in targets:
            target_x, target_y = self.logic2array(target)
            vectors_out.append(np.array([target_x, target_y], dtype=np.int64) - origin)
        return self._normalize_move_vectors(vectors_out)

    def remove_illegal(
        self,
        x: int,
        y: int,
        vectors: np.array,
        in_check: bool,
        white_turn: bool,
        is_king: bool = False,
        remove_own: bool = True,
    ) -> np.array:
        """
        Backward-compatible vector filter.

        Public rule generation no longer depends on this method, but keeping it
        avoids breaking old experimental callers.
        """
        del in_check, is_king
        color = 'white' if white_turn else 'black'
        origin = self.array2logic(x, y)
        piece = self._piece_from_value(int(self.board[x, y]))
        valid_vectors = []

        for dx, dy in self._normalize_move_vectors(vectors):
            target_x, target_y = x + dx, y + dy
            if not (0 <= target_x < BOARD_SIZE and 0 <= target_y < BOARD_SIZE):
                continue
            if remove_own and self._target_has_own_piece(self.board, target_x, target_y, color):
                continue
            target = self.array2logic(target_x, target_y)
            if remove_own and piece != 'Empty square' and self._would_leave_king_in_check(piece, origin, target):
                continue
            valid_vectors.append([dx, dy])

        return self._normalize_move_vectors(valid_vectors)

    def assess_king_status(self, white_player: bool, restrict_turn: bool = True) -> int:
        """
        Return check/mate status for the requested side.

        Returns:
            0: no check
            1: white is in check
            2: white is checkmated
           -1: black is in check
           -2: black is checkmated
        """
        del restrict_turn  # Kept for compatibility with older call sites.
        color = 'white' if white_player else 'black'
        if not self._is_king_in_check_on_board(self.board, color):
            return 0

        legal_moves = self.calculate_possible_moves()
        has_escape = any(legal_moves[color].values())
        magnitude = 1 if has_escape else 2
        return magnitude if white_player else -magnitude

    def assess_ataqued_squares(self, white_player: bool) -> List[str]:
        """
        Return all squares attacked by the selected side.

        This intentionally uses pseudo-attacks rather than legal move generation:
        attack maps are needed to validate king movement and castling, and should
        not recurse through own-king safety filtering.
        """
        color = 'white' if white_player else 'black'
        attacked_squares: List[str] = []
        for x in range(BOARD_SIZE):
            for y in range(BOARD_SIZE):
                value = int(self.board[x, y])
                if value == 0 or self._color_from_value(value) != color:
                    continue
                piece = self._piece_from_value(value)
                position = self.array2logic(x, y)
                attacked_squares.extend(self._pseudo_targets_for_piece(self.board, piece, position, for_attack=True))
        return self._dedupe_preserve_order(attacked_squares)

    def assess_empty_squares(self, targets: List[str]) -> np.array:
        """
        Assess whether target squares are empty.
        """
        squares_status = []
        for square in targets:
            if not self._position_in_bounds(square):
                squares_status.append(False)
                continue
            x, y = self.logic2array(square)
            squares_status.append(int(self.board[x, y]) == 0)
        return np.array(squares_status)

    def calculate_possible_moves(self, in_check: bool = False, remove_own: bool = True) -> Dict[str, Dict[str, List[str]]]:
        """
        Calculate moves grouped by color and origin square.

        ``remove_own=True`` returns legal moves. ``remove_own=False`` returns
        attack maps for compatibility with older callers.
        """
        del in_check  # Legal filtering is now based on board simulation.
        possible_moves: Dict[str, Dict[str, List[str]]] = {'white': {}, 'black': {}}
        for x in range(BOARD_SIZE):
            for y in range(BOARD_SIZE):
                value = int(self.board[x, y])
                if value == 0:
                    continue
                color = self._color_from_value(value)
                if color is None:
                    continue
                piece = self._piece_from_value(value)
                position = self.array2logic(x, y)
                moves = self.allowed_movements(
                    piece,
                    position,
                    restrict_turn=False,
                    remove_own=remove_own,
                )
                if moves:
                    possible_moves[color][position] = moves
        return possible_moves

    def make_move(
        self,
        piece: str,
        initial_position: str,
        end_position: str,
        promote2: str = None,
        add2history: bool = True,
    ) -> Tuple[bool, str]:
        """
        Execute a move when it is legal and update board, turn, history and bitboard.
        """
        if not self._position_in_bounds(initial_position) or not self._position_in_bounds(end_position):
            return False, ''

        moving_color = self._color_from_piece(piece)
        if moving_color is None or moving_color != self._active_color():
            return False, ''

        initial_x, initial_y = self.logic2array(initial_position)
        end_x, end_y = self.logic2array(end_position)
        if self._piece_from_value(int(self.board[initial_x, initial_y])) != piece:
            return False, ''

        if not self._promotion_is_valid(piece, end_position, promote2):
            return False, ''

        legal_moves = self.possible_moves.get(moving_color, {})
        if end_position not in legal_moves.get(initial_position, []):
            return False, ''

        movement = self.notation_from_move(piece, initial_position, end_position)
        captured_piece = self.what_in(end_position)
        en_passant_capture_square = None

        if self._is_en_passant_move_on_board(self.board, piece, initial_position, end_position):
            en_passant_capture_square = self.array2logic(initial_x, end_y)
            captured_piece = self.what_in(en_passant_capture_square)
            movement = initial_position[0] + 'x' + end_position

        self.set_piece('Empty square', initial_position)
        if en_passant_capture_square is not None:
            self.set_piece('Empty square', en_passant_capture_square)
        self.set_piece(piece, end_position)

        if 'king' in piece and abs(end_y - initial_y) == 2:
            if end_y > initial_y:
                rook_initial = f'h{initial_position[1]}'
                rook_end = f'f{initial_position[1]}'
            else:
                rook_initial = f'a{initial_position[1]}'
                rook_end = f'd{initial_position[1]}'
            rook_piece = self.what_in(rook_initial)
            self.set_piece('Empty square', rook_initial)
            self.set_piece(rook_piece, rook_end)

        if promote2 is not None:
            self.set_piece(promote2, end_position)
            promotions = {'queen': 'Q', 'rook': 'R', 'knight': 'N', 'bishop': 'B'}
            movement += '=' + promotions[promote2.split(' ')[1]]

        self._update_castle_flags_after_move(piece, initial_position, end_position, captured_piece)
        self._set_en_passant_after_move(piece, initial_position, end_position)
        self.last_turn = (piece, initial_position, end_position)
        self.white_turn = not self.white_turn
        self._refresh_possible_moves()

        checked_color_is_white = self.white_turn
        king_status = self.assess_king_status(checked_color_is_white, restrict_turn=False)
        if np.abs(king_status) == 1:
            movement += '+'
        elif np.abs(king_status) == 2:
            movement += '#'

        if add2history:
            fen = self.export_fen(include_state=True)
            if moving_color == 'white':
                self.history.append([[movement], [fen]])
            elif self.history:
                self.history[-1][0].append(movement)
                self.history[-1][1].append(fen)
            else:
                self.history.append([['...', movement], ['', fen]])

        if add2history:
            self.pointer = (len(self.history) - 1, moving_color == 'white')
        return True, movement

    def notation_from_move(self, piece: str, initial_position: str, end_position: str) -> str:
        """
        Attempts to describe the move in chess notation. 
        For example, a knight moving to f6 -> "Nf6".
        
        Parameters:
            piece: A string representing the type of piece, e.g., 'knight', 'queen'.
            initial_position: A two-character string representing the starting position, e.g., 'g1'.
            end_position: A two-character string representing the destination position, e.g., 'f3'.
        
        Returns:
            A string in standard chess notation representing the move.
        """ 
        #TODO jaque, y ojo, jaque a la descubierta
        #TODO mate
        
        movement = ''
        if 'king' in piece:
            movement += 'K'
            if initial_position == 'e1' and end_position == 'g1':
                return 'O-O'
            elif initial_position == 'e1' and end_position == 'c1':
                return 'O-O-O'
            elif initial_position == 'e8' and end_position == 'g8':
                return 'O-O'
            elif initial_position == 'e8' and end_position == 'c8':
                return 'O-O-O'
        elif 'queen' in piece:
            movement += 'Q'
        elif 'bishop' in piece:
            movement += 'B'
        elif 'knight' in piece:
            movement += 'N'
        elif 'rook' in piece:
            movement += 'R'

        disambiguation = ''
        if 'pawn' not in piece:
            same_piece = self.search_for(piece) #Check all pieces of the same type to the current piece
            other_candidates = [pos for pos in same_piece if pos != initial_position and 
                                end_position in self.allowed_movements(piece, pos)]
        
            if other_candidates: #We need disambiguation
                if len(set(pos[0] for pos in other_candidates + [initial_position])) == 1: #Check if the pieces are in the same column
                    disambiguation = initial_position[1] #Disambiguate by row
                else:
                    disambiguation = initial_position[0] #Disambiguate by column
        
        if 'Empty' not in self.what_in(end_position): #Another piece in destiny -> capture
            if 'pawn' in piece:
                movement = initial_position[0] #For pawns, when capturing we must put the letter of the origin column
            movement += disambiguation + 'x'
        else:
            if 'pawn' not in piece: #For non pawns pieces we add the disambiguation if it exists
                movement += disambiguation

        return movement + end_position.lower()

    def read_move(self, play: str, white_player: bool) -> Tuple[str, str, str]:
        """
        Transcribes a move from a chess like play to a triplet for the move method to execute.
        This method does the convertion without cheking if it is legal (castle).

        Parameters:
            play: A chess like play, e.g., 'Nf3'
            white_player: True is the calculations are done for white's player turn
        
        Returns:
            piece: A string representing the type of piece, e.g., 'knight', 'queen'.
            initial_position: A two-character string representing the starting position, e.g., 'g1'.
            end_position: A two-character string representing the destination position, e.g., 'f3'.

        """
        play_stripped = play.replace('+', '').replace('#', '')

        if 'O-O' in play_stripped: #Castle moves
            return self._parse_castle_move(play_stripped, white_player)

        end_position = play_stripped[-2:] #For normal plays -> end_position is int las two characters
        piece = self._parse_piece_from_move(play_stripped, white_player)
        candidates = self._find_candidates(piece, end_position, white_player)
        initial_position = self._resolve_candidate_disambiguation(piece, play_stripped, candidates)

        return piece, initial_position, end_position

    def _parse_castle_move(self, play_stripped: str, white_player: bool) -> Tuple[str, str, str]:
        """
        Process castle moves

        Parameters:
            play_stripped: A chess like play, e.g., 'Nf3' but withouth '+' or '#'
            white_player: True is the calculations are done for white's player turn

        Returns:
            piece: A string representing the type of piece, e.g., 'knight', 'queen'.
            initial_position: A two-character string representing the starting position, e.g., 'g1'.
            end_position: A two-character string representing the destination position, e.g., 'f3'.
        """
        if 'O-O-O' in play_stripped:  #Long castle
            if white_player:
                return 'white king', 'e1', 'c1'
            else:
                return 'black king', 'e8', 'c8'
        else:  #Short castle
            if white_player:
                return 'white king', 'e1', 'g1'
            else:
                return 'black king', 'e8', 'g8'

    def _parse_piece_from_move(self, play_stripped: str, white_player: bool) -> str:
        """
        Determines piece type from notation
        If is not specified it is a pawn.

        Parameters:
            play_stripped: A chess like play, e.g., 'Nf3' but withouth '+' or '#'
            white_player: True is the calculations are done for white's player turn

        Returns:
            str: piece name
        """
        piece = 'white ' if white_player else 'black '
        if 'K' in play_stripped:
            piece += 'king'
        elif 'Q' in play_stripped:
            piece += 'queen'
        elif 'B' in play_stripped:
            piece += 'bishop'
        elif 'N' in play_stripped:
            piece += 'knight'
        elif 'R' in play_stripped:
            piece += 'rook'
        else:
            piece += 'pawn'
        return piece

    def _find_candidates(self, piece: str, end_position: str, white_player: bool) -> List[str]:
        """
        Search in self.possible_moves the positions from wich the right piece can move to target position 

        Parameters:
            piece: A string representing the type of piece, e.g., 'knight', 'queen'
            end_position: A two-character string representing the destination position, e.g., 'f3'.
            white_player: True is the calculations are done for white's player turn
        """
        color = 'white' if white_player else 'black'
        candidates = []
        for position, moves in self.possible_moves[color].items():
            if end_position in moves and self.what_in(position) == piece:
                candidates.append(position)

        if not candidates: #if there are not candidates we look for those that can move and thats it
            for position, moves in self.possible_moves[color].items():
                if end_position in moves:
                    candidates.append(position)
        return candidates

    def _resolve_candidate_disambiguation(self, piece: str, play_stripped: str, candidates: List[str]) -> str:
        """Resolve SAN disambiguation against legal candidate origins.

        SAN can identify the moving piece by file (``Ngf6``), rank
        (``N5f7``) or full square (``Nbd2`` / ``R1e1``). The previous
        implementation ignored that qualifier for non-pawns and could choose
        the wrong knight/rook when two identical pieces could reach the same
        square.
        """
        if not candidates:
            raise ValueError(f"No legal candidate found for move: {play_stripped}")

        qualifier = self._san_origin_qualifier(piece, play_stripped)
        if qualifier:
            filtered = [candidate for candidate in candidates if self._candidate_matches_qualifier(candidate, qualifier)]
            if len(filtered) == 1:
                return filtered[0]
            if filtered:
                candidates = filtered
            else:
                raise ValueError(
                    f"No legal candidate matches disambiguation {qualifier!r} for move: {play_stripped}"
                )

        if len(candidates) == 1:
            return candidates[0]

        raise ValueError(f"Ambiguous move without enough disambiguation: {play_stripped}")

    def _san_origin_qualifier(self, piece: str, play_stripped: str) -> str:
        """Return the SAN origin qualifier between piece/capture and target.

        Examples:
            ``Ngf6`` -> ``g``
            ``N5f7`` -> ``5``
            ``Nbd2`` -> ``b``
            ``exd5`` -> ``e``
            ``Nf3`` -> ````
        """
        core = play_stripped.replace("x", "")
        if len(core) < 2:
            return ""
        before_target = core[:-2]
        if "pawn" not in piece and before_target[:1] in {"K", "Q", "R", "B", "N"}:
            before_target = before_target[1:]
        return before_target

    @staticmethod
    def _candidate_matches_qualifier(candidate: str, qualifier: str) -> bool:
        if len(qualifier) == 2:
            return candidate == qualifier
        if len(qualifier) == 1:
            return candidate[0] == qualifier or candidate[1] == qualifier
        return False

    def set_position_from_pieces(
        self,
        pieces: Dict[str, str],
        white_turn: bool = True,
        clear_history: bool = True,
        en_passant_target: Optional[str] = None,
    ) -> None:
        """Replace the current board with an explicit piece map."""
        preserved_history = [] if clear_history else self.history
        preserved_pointer = (-1, True) if clear_history else self.pointer

        self.clear_board()
        for position, piece in pieces.items():
            self.set_piece(piece, position)

        self.white_turn = bool(white_turn)
        self.history = preserved_history
        self.pointer = preserved_pointer
        self.last_turn = (None, None, None)
        self.en_passant_target = self._normalize_en_passant_target(en_passant_target)
        self._refresh_possible_moves()

    def set_position_from_fen(
        self,
        fen: str,
        clear_history: bool = True,
    ) -> None:
        """Replace the current board from a FEN string.

        Piece placement, active color and en-passant target are preserved.
        Castling and move counters are still emitted with neutral placeholders.
        """
        fields = fen.strip().split()
        if not fields:
            raise ValueError('FEN is empty')

        board = self.fen2numpy(fen)
        white_turn = True
        if len(fields) >= 2:
            if fields[1] not in {'w', 'b'}:
                raise ValueError("FEN active color must be 'w' or 'b'")
            white_turn = fields[1] == 'w'
        en_passant_target = self._normalize_en_passant_target(fields[3] if len(fields) >= 4 else None)

        pieces: Dict[str, str] = {}
        for x in range(BOARD_SIZE):
            for y in range(BOARD_SIZE):
                value = int(board[x, y])
                if value == 0:
                    continue
                pieces[self.array2logic(x, y)] = self._piece_from_value(value)

        self.set_position_from_pieces(
            pieces,
            white_turn=white_turn,
            clear_history=clear_history,
            en_passant_target=en_passant_target,
        )

    def export_fen(self, include_state: bool = True) -> str:
        """Export the current board as FEN.

        The current engine tracks piece placement, active side and en-passant
        target. Castling rights and move counters are emitted with neutral
        placeholders until they are promoted to the position contract.
        """
        placement = self.numpy2fen(self.board)
        if not include_state:
            return placement
        active_color = 'w' if self.white_turn else 'b'
        en_passant = self.en_passant_target or '-'
        return f'{placement} {active_color} - {en_passant} 0 1'

    def reset_to_initial_position(self, preserve_history: bool = True) -> None:
        """Load the initial board and optionally keep the recorded move list."""
        preserved_history = self.history if preserve_history else []
        self.clear_board()
        self.load_position('config/initial_position.yaml')
        self.history = preserved_history
        self.pointer = (-1, True)
        self.last_turn = (None, None, None)
        self._refresh_possible_moves()

    def save_position(self, filename:str) -> None:
        """
        Saves a position to a YAML file. It doesn't saves the plays.

        Parameters:
            filename: A string with the name and route to the target file
        """
        board = {}
        for x in range(BOARD_SIZE):
            for y in range(BOARD_SIZE):
                position    = self.array2logic(x,y)
                piece       = self.what_in(position)
                if 'Empty' not in piece:
                    board[position] = piece
        board["Playe's Turn"] = 'white' if self.white_turn else 'black'
        path = self._resolve_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            yaml.dump(board, file, allow_unicode=True, default_flow_style=False)
    
    def load_position(self, filename:str) -> None:
        """
        Loads a position from a YAML file. It has no knoledge of the plays.

        Parameters:
            filename: A string with the name and route to the target file
        """
        path = self._resolve_path(filename)
        with open(path, "r", encoding="utf-8") as file:
            board = yaml.safe_load(file)

        if not isinstance(board, dict):
            raise ValueError(f'Invalid position file: {path}')

        self.clear_board()
        for position, piece in board.items():
            if position == "Playe's Turn":
                continue
            self.set_piece(piece, position)

        self.white_turn = board.get("Playe's Turn", 'white') == 'white'
        if hasattr(self, 'possible_moves'):
            self._refresh_possible_moves()
        else:
            self.bitboard = ChessBitboard(self.board)

    def save_game(self, filename:str) -> None:
        """
        Saves a game to a YAML file. It doesn't saves the position.

        Parameters:
            filename: A string with the name and route to the target file
        """
        path = self._resolve_path(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as file:
            yaml.dump(self.history, file, allow_unicode=True, default_flow_style=False)

    def load_game(self, filename:str, go2last:bool=False) -> None:
        """
        Loads a game from a YAML file. It infers the position.

        Parameters:
            filename: A string with the name and route to the target file
        """
        path = self._resolve_path(filename)
        with open(path, "r", encoding="utf-8") as file:
            history = yaml.safe_load(file)

        self.clear_board()
        self.load_position('config/initial_position.yaml')
        self.history = history if history is not None else []
        self.pointer = (-1, True)
        self.last_turn = (None, None, None)
        self._refresh_possible_moves()

        if go2last and self.history:
            last_turn_index = len(self.history) - 1
            moves = self.history[last_turn_index][0]
            white_player = len(moves) == 1
            self.go2(last_turn_index, white_player)

    def fen2numpy(self, fen:str) -> np.array:
        """
        Converts a fen position to a numpy array
        
        Parameters:
            fen: a string with a fen format

        Returns:
            np.array: an array with a ChessBoard-like format for the board
        """

        mapping = {
            'K': 6, 'Q': 5, 'R': 4, 'B': 3, 'N': 2, 'P': 1,
            'k': -6, 'q': -5, 'r': -4, 'b': -3, 'n': -2, 'p': -1
        }
        fields = fen.strip().split()
        if not fields:
            raise ValueError('FEN is empty')

        position = fields[0]
        rows = position.split('/')
        if len(rows) != BOARD_SIZE:
            raise ValueError('FEN must contain 8 ranks')

        board = []
        for row in rows:
            current_row = []
            for char in row:
                if char.isdigit():
                    current_row.extend([0] * int(char))
                elif char in mapping:
                    current_row.append(mapping[char])
                else:
                    raise ValueError(f'Invalid FEN character: {char}')
            if len(current_row) != BOARD_SIZE:
                raise ValueError('Each FEN rank must contain 8 files')
            board.append(current_row)
        
        return np.array(board, dtype=np.int64)
    
    def numpy2fen(self, board:np.array) -> str:
        """
        Converts a numpy array to a fen position
        
        Parameters:
            board: an array with a ChessBoard-like format for the board

        Returns:
            str: a string with a fen format
        """

        mapping = {
        6: 'K', 5: 'Q', 4: 'R', 3: 'B', 2: 'N', 1: 'P',
        -6: 'k', -5: 'q', -4: 'r', -3: 'b', -2: 'n', -1: 'p'
        }
        fen_rows = []
        
        for row in board:
            fen_row = ''
            empty_count = 0
            for square in row:
                if square == 0:
                    empty_count += 1
                else:
                    if empty_count:
                        fen_row += str(empty_count)
                        empty_count = 0
                    fen_row += mapping[square]
            if empty_count:
                fen_row += str(empty_count)
            fen_rows.append(fen_row)
        
        return '/'.join(fen_rows) #Joins rows with a /
    
    def _history_uses_pre_move_fens(self) -> bool:
        """Return True for legacy games whose FENs describe positions before moves.

        Early generated YAML games store, for each row, the position before White's
        move and the position before Black's move. New games created by
        ``make_move`` store the position after each half-move. Navigation must
        support both contracts without rewriting the loaded file.
        """
        if not self.history:
            return False

        moves, fens = self._split_history_entry(self.history[0])
        if not moves or not fens or not fens[0]:
            return False

        first_move = moves[0] if moves else ''
        first_placement = str(fens[0]).split()[0]
        return first_move != '...' and first_placement == STARTING_FEN_PLACEMENT

    @staticmethod
    def _split_history_entry(entry) -> Tuple[List[str], List[str]]:
        if isinstance(entry, (list, tuple)) and len(entry) >= 2:
            moves, fens = entry[0], entry[1]
        else:
            moves, fens = entry, []

        if moves is None:
            parsed_moves = []
        elif isinstance(moves, str):
            parsed_moves = [moves]
        else:
            parsed_moves = list(moves)

        if fens is None:
            parsed_fens = []
        elif isinstance(fens, str):
            parsed_fens = [fens]
        else:
            parsed_fens = list(fens)

        return parsed_moves, parsed_fens

    def _set_board_from_history_fen(self, fen: str, white_turn: bool) -> None:
        if not fen:
            raise ValueError('Requested move does not have an associated FEN')

        self.set_position_from_fen(fen, clear_history=False)
        self.white_turn = bool(white_turn)
        self._refresh_possible_moves()

    def _resolve_pre_move_history_target(self, turn: int, white_player: bool) -> Tuple[Optional[str], bool]:
        moves, fens = self._split_history_entry(self.history[turn])

        if white_player:
            if len(fens) >= 2 and fens[1]:
                return fens[1], False
            return None, False

        next_turn = turn + 1
        if next_turn < len(self.history):
            _, next_fens = self._split_history_entry(self.history[next_turn])
            if next_fens and next_fens[0]:
                return next_fens[0], True

        if len(fens) >= 2 and fens[1] and len(moves) >= 2:
            return None, True

        raise ValueError('Requested black move does not have enough history data')

    @staticmethod
    def _extract_promotion_from_history_move(move: str, white_player: bool) -> Tuple[str, Optional[str]]:
        if '=' not in move:
            return move, None

        move_without_promotion, promotion_suffix = move.split('=', 1)
        promotion_code = promotion_suffix.replace('+', '').replace('#', '')[:1]
        promotion_map = {'Q': 'queen', 'R': 'rook', 'N': 'knight', 'B': 'bishop'}
        promotion_piece = promotion_map.get(promotion_code)
        if promotion_piece is None:
            return move_without_promotion, None

        color = 'white' if white_player else 'black'
        return move_without_promotion, f'{color} {promotion_piece}'

    def _replay_pre_move_history_target(self, turn: int, white_player: bool) -> None:
        moves, fens = self._split_history_entry(self.history[turn])
        move_index = 0 if white_player else 1
        if len(moves) <= move_index:
            raise ValueError('Requested move is missing from history')
        if len(fens) <= move_index or not fens[move_index]:
            raise ValueError('Requested move does not have a prior FEN to replay from')

        move, promote2 = self._extract_promotion_from_history_move(moves[move_index], white_player)

        replay_board = ChessBoard()
        replay_board.set_position_from_fen(fens[move_index], clear_history=True)
        replay_board.white_turn = white_player
        replay_board.possible_moves = replay_board.calculate_possible_moves()

        piece, origin, target = replay_board.read_move(move, white_player)
        moved, _ = replay_board.make_move(piece, origin, target, promote2=promote2, add2history=False)
        if not moved:
            raise ValueError(f'Could not replay move from history: {moves[move_index]}')

        self.board = replay_board.board.copy()
        self.white_turn = replay_board.white_turn
        self.last_turn = replay_board.last_turn
        self.en_passant_target = replay_board.en_passant_target
        self.possible_moves = self.calculate_possible_moves()
        self._sync_bitboard()

    def go2(self, turn:int, white_player:bool) -> None:
        """
        Actualizes the position and pointer to fit the given number

        Parameters:
            turn: the position in the sequence of the target turn
            white_player: True if the target is White's move in the row,
                False if the target is Black's move in the row.
        """
        if turn < 0:
            self.reset_to_initial_position(preserve_history=True)
            return

        if turn >= len(self.history):
            raise IndexError('Requested turn is outside the loaded history')

        if self._history_uses_pre_move_fens():
            target_fen, target_white_turn = self._resolve_pre_move_history_target(turn, white_player)
            if target_fen is not None:
                self._set_board_from_history_fen(target_fen, target_white_turn)
            else:
                self._replay_pre_move_history_target(turn, white_player)
            self.pointer = (turn, white_player)
            return

        entry = self.history[turn]
        moves, fens = self._split_history_entry(entry)
        del moves
        white_fen = fens[0] if len(fens) >= 1 else None
        black_fen = fens[1] if len(fens) >= 2 else None
        target_fen = white_fen if white_player else black_fen
        if target_fen is None:
            raise ValueError('Requested move does not have an associated FEN')

        self._set_board_from_history_fen(target_fen, not white_player)
        self.pointer = (turn, white_player)


if __name__ == '__main__':
    board = ChessBoard()

