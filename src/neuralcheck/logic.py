import numpy as np
import bitboardops as bb
import yaml
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from neuralcheck.bitboard import ChessBitboard
from typing import Tuple, List, Dict
BOARD_SIZE = 8

class ChessBoard:
    def __init__(self):
        #NOTE This is a high level representation of the board. 
        #It uses a 8x8 numpy matrix (check put method to see piece representation).
        #This class has direct communication with the UI to handle it.
        #This representation is not optimal for search or machine learning. 
        #There is a lower level for this using bitboard representations.
        #That level is syncronized with this for tracking pourpuses.
        
        self.initializing       = True
        self._initialize_resources()
        self.clear_board()
        self.load_position('config/initial_position.yaml') 
        self.line_vectors       = np.array([[1, 0], [-1, 0], [0, 1], [0, -1]])
        self.diagonal_vectors   = np.array([[1, 1], [-1, 1], [-1, -1], [1, -1]])
        self.pinned_pieces      = []
        self.possible_moves     = self.calculate_possible_moves()
        self.bitboard           = ChessBitboard(self.board)
        self.pointer            = (0, True)
        self.last_turn          = (None, None, None)
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
    
    def clear_board(self) -> None:
        """
        Clears all history and pieces from the board
        """
        self.board = np.zeros((BOARD_SIZE,BOARD_SIZE), dtype=np.int64)
        self.history = []
        self.last_turn = (None, None, None)
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

    def allowed_movements(self, 
                          piece:str, 
                          position:str, 
                          in_check:bool=False, 
                          restrict_turn:bool=True,
                          remove_own:bool=True
                          ) -> List[str]:
        """
        Calculates all legal movements of the piece.

        Parameters:
            piece: a string indicating color and piece, e.g., 'white king'
            position: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'
            in_check: there is a check to the king
            restrict_turn: a boolean that signas to only calculate movements for pieces of the current player
            remove_own: a boolean that signals that the square should be eliminated 
            if there is a friendly piece -> should be True except when calculating
            for attaqued squares

        Returns:
            List[str]: a list with all legal movements of the piece in chess-like format
        """

        #NOTE si el rey está en jaque las únicas piezas que se pueden mover son el mismo, y aquellas que lo protejen
        
        x, y                = self.logic2array(position) #Be careful with notation when converting to NumPy arrays
        white_turn          = 'white' in piece
        if restrict_turn and (white_turn != self.white_turn):
            return []

        if 'king' in piece:
            piece_moves = np.array([[1,0], [1,1], [0,1], [-1,1], [-1,0], [-1,-1], [0,-1], [1,-1], [0,2], [0,-2]])
            piece_moves = self.remove_illegal(x, y, piece_moves, in_check, white_turn, is_king=True, remove_own=remove_own)
        elif 'queen' in piece:
            all_vectors = np.concatenate((self.line_vectors, self.diagonal_vectors))
            piece_moves = self.raycast(x, y, all_vectors, white_turn, remove_own=remove_own)
        elif 'bishop' in piece:
            piece_moves = self.raycast(x, y, self.diagonal_vectors, white_turn, remove_own=remove_own)
        elif 'knight' in piece:
            piece_moves = np.array([[2,1], [1,2], [-1,2], [-2,1], [-2,-1], [-1,-2], [1,-2], [2,-1]]) 
            piece_moves = self.remove_illegal(x, y, piece_moves, in_check, white_turn, remove_own=remove_own)
        elif 'rook' in piece:
            piece_moves = self.raycast(x, y, self.line_vectors, white_turn, remove_own=remove_own)
        elif 'pawn' in piece:             
            if white_turn: 
                if self.board[x - 1, y] == 0: #There is no piece in foward movement
                    piece_moves = np.array([[-1, 0]])
                else:
                    piece_moves = np.array([[0, 0]])
                if x == 6 and self.board[4, y] == 0: #Special movement for pawns in their starting rank
                    piece_moves = np.concatenate((piece_moves, np.array([[-2, 0]])))
                if y + 1 < BOARD_SIZE and x - 1 >= 0:
                    if self.board[x - 1, y + 1] < 0: #There is an enemy piece
                        piece_moves = np.concatenate((piece_moves, np.array([[-1, 1]])))
                if y - 1 >= 0 and x - 1 >= 0:
                    if self.board[x - 1, y - 1] < 0: #Idem
                        piece_moves = np.concatenate((piece_moves, np.array([[-1, -1]])))
                if x == 3: #En passant 
                    last_piece, last_init, last_end = self.last_turn
                    xp, yp = self.logic2array(last_end)
                    if 'pawn' in last_piece and xp == 3 and np.abs(y - yp) == 1: #Piece goes from starting does a 2 square movement and lands besides current piece
                        piece_moves = np.concatenate((piece_moves, np.array([[-1, yp - y]])))

            else: 
                if self.board[x + 1, y] == 0: #There is no piece in foward movement
                    piece_moves = np.array([[1, 0]])
                else:
                    piece_moves = np.array([[0, 0]])
                if x == 1 and self.board[3, y] == 0: #Special movement for pawns in their starting rank
                    piece_moves = np.concatenate((piece_moves, np.array([[2, 0]])))
                if y + 1 < BOARD_SIZE and x + 1 < BOARD_SIZE:
                    if self.board[x + 1, y + 1] > 0: #There is an enemy piece
                        piece_moves = np.concatenate((piece_moves, np.array([[1, 1]])))
                if y - 1 >= 0 and x + 1 < BOARD_SIZE:
                    if self.board[x + 1, y - 1] > 0: #Idem
                        piece_moves = np.concatenate((piece_moves, np.array([[1, -1]])))
                if x == 4: #En passant
                    last_piece, last_init, last_end = self.last_turn
                    xp, yp = self.logic2array(last_end)
                    if 'pawn' in last_piece and xp == 4 and np.abs(y - yp) == 1: #Piece goes from starting does a 2 square movement and lands besides current piece
                        piece_moves = np.concatenate((piece_moves, np.array([[1, yp - y]])))
            
        else:
            piece_moves = np.array([[0, 0]])

        if in_check and 'king' not in piece: #If there is a check the piece can't move unless it can help the king
            piece_moves = self.remove_illegal(x, y, piece_moves, in_check, white_turn, remove_own=remove_own)
        
        if type(piece_moves) == List: #FIXME sometimes piece_moves = [] when there are not movements other times piece_moves = np.array([[0, 0]])
            piece_moves = piece_moves if piece_moves else np.array([[0, 0]])

        destinations = np.array([x, y]) + piece_moves
        legal_moves = [''] * len(destinations)
        for i, (dest_x, dest_y) in enumerate(destinations):
            move_vector = piece_moves[i]
            if 'king' in piece and move_vector[0] == 0 and abs(move_vector[1]) == 2:
                legal_moves[i] = self.array2logic(dest_x, dest_y)
            else:
                legal_moves[i] = self.array2logic(dest_x, dest_y)

        if position in legal_moves: #Means that it didn't encounter new positions so we clean the answer
            return []

        return legal_moves
    
    def raycast(self, x:int, y:int, vectors:np.array, white_turn:bool, remove_own:bool=True) -> np.array:
        """
        Calculate a raycast of the piece from direction vectors stoping when an obstacule is founded

        Parameters:
            x: x position in the board of the piece
            y: y position in the board of the piece
            vectors: an array with all plausible directions for the piece to go
            white_turn: True is the calculations are done for white's player turn
            remove_own: a boolean that signals that the square should be eliminated 
            if there is a friendly piece -> should be True except when calculating
            for attaqued squares

        Returns
            np.array: an array with all posible directions to travel acording to rules
        """
        moves = np.empty((0, 2), dtype=np.int64)
        player_turn = 1 if white_turn else -1
        for dx, dy in vectors: #All vectors should be unit vectors in the desired directions.
            for i in range(1, BOARD_SIZE): #We advance i units in the desired direction and check for obstacles at each step.
                xp, yp = x + i*dx, y + i*dy
                if 0 <= xp < BOARD_SIZE and 0 <= yp < BOARD_SIZE: #Ensure movement stays within the board
                    if player_turn * self.board[xp, yp] <= 0: #Check for enemy pieces (or empty squares); multiplying by player_turn adjusts the inequality.
                        moves = np.concatenate((moves, np.array([[i*dx, i*dy]])))
                        if player_turn * self.board[xp, yp] < 0: #Stops, but allows capturing; but first check for pinned pieces.
                            for j in range(i + 1, BOARD_SIZE):
                                x_check, y_check = x + j*dx, y + j*dy
                                if 0 <= x_check < BOARD_SIZE and 0 <= y_check < BOARD_SIZE:
                                    if player_turn * self.board[x_check, y_check] < 0 and np.abs(self.board[x_check, y_check]) != 6: #There is another enemy piece which is not a king -> nothing hapens
                                        break
                                    if player_turn * self.board[x_check, y_check] == -6 and self.array2logic(xp, yp) not in self.pinned_pieces: #There is an enemy king behind the lines so this piece must be pinned
                                        self.pinned_pieces.append(self.array2logic(xp, yp))
                                        break
                            break
                    else: 
                        if remove_own: #Encounter a piece of the same color; stops immediately.
                            break
                        else: #If used for attaques squares agregate that only quare and then stop
                            moves = np.concatenate((moves, np.array([[i * dx, i * dy]])))
                            break
                else: #Stops searching off the board
                    break
        return moves      
          
    def remove_illegal(self, 
                       x:int, 
                       y:int, 
                       vectors:np.array, 
                       in_check:bool, 
                       white_turn:bool, 
                       is_king:bool=False,
                       remove_own:bool=True,
                       ) -> np.array:
        """
        Attempts to remove ilegal moves that could be in from raw initial movements

        Parameters:
            x: x position in the board of the piece
            y: y position in the board of the piece
            vectors: an array with all plausible directions for the piece to go
            in_check: there is a check to the king
            white_turn: True is the calculations are done for white's player turn
            is_king: a boolean that signals that the king is being evaluated here
            remove_own: a boolean that signals that the square should be eliminated 
            if there is a friendly piece -> should be True except when calculating
            for attaqued squares

        Returns
            np.array: an array with all posible directions to travel acording to rules
        """
        def filter_out_of_bounds_and_friendly(vectors: np.array) -> np.array:
            """
            Filter movements that goes out of the board or that fall in own pieces
            """
            player_turn = 1 if white_turn else -1
            valid_vectors = []
            for vec in vectors:
                dx, dy = vec
                new_x, new_y = x + dx, y + dy
                if not (0 <= new_x < BOARD_SIZE and 0 <= new_y < BOARD_SIZE):
                    continue
                if remove_own and player_turn * self.board[new_x, new_y] > 0:
                    continue
                valid_vectors.append(vec)
            return np.array(valid_vectors)

        def filter_castling_moves(vectors: np.array) -> np.array:
            """
            Apply castling restrictions for the king.
            Remove castling moves when conditions that prevent it are met,
            such as non-empty squares, check along the path, or if the piece (king or rook) has already moved.
            """
            elements_to_remove = []
            king_moved = self.castle_flags['white king moved'] if white_turn else self.castle_flags['black king moved']
            if in_check or king_moved:
                elements_to_remove.extend([[0, 2], [0, -2]]) 
            #Rook restrictions
            if (white_turn and self.castle_flags['a1 rook moved']) or (not white_turn and self.castle_flags['a8 rook moved']):
                if [0, -2] not in elements_to_remove:
                    elements_to_remove.append([0, -2])
            if (white_turn and self.castle_flags['h1 rook moved']) or (not white_turn and self.castle_flags['h8 rook moved']):
                if [0, 2] not in elements_to_remove:
                    elements_to_remove.append([0, 2])
            #Empty squares restrictions
            if white_turn:
                if self.assess_empty_squares(['b1', 'c1', 'd1']).astype(int).sum() < 3 and [0, -2] not in elements_to_remove:
                    elements_to_remove.append([0, -2])
                if self.assess_empty_squares(['f1', 'g1']).astype(int).sum() < 2 and [0, 2] not in elements_to_remove:
                    elements_to_remove.append([0, 2])
            else:
                if self.assess_empty_squares(['b8', 'c8', 'd8']).astype(int).sum() < 3 and [0, -2] not in elements_to_remove:
                    elements_to_remove.append([0, -2])
                if self.assess_empty_squares(['f8', 'g8']).astype(int).sum() < 2 and [0, 2] not in elements_to_remove:
                    elements_to_remove.append([0, 2])
            #Attacked squares restrictions
            def squares_in(subset: List[str], target_set: List[str]) -> bool:
                return all(elem in target_set for elem in subset)

            enemy_moves = [] if self.initializing else self.assess_ataqued_squares(not white_turn)
            if white_turn:
                if squares_in(['a1', 'b1', 'c1', 'd1'], enemy_moves) and [0, -2] not in elements_to_remove:
                    elements_to_remove.append([0, -2])
                if squares_in(['f1', 'g1', 'h1'], enemy_moves) and [0, 2] not in elements_to_remove:
                    elements_to_remove.append([0, 2])
            else:
                if squares_in(['a8', 'b8', 'c8', 'd8'], enemy_moves) and [0, -2] not in elements_to_remove:
                    elements_to_remove.append([0, -2])
                if squares_in(['f8', 'g8', 'h8'], enemy_moves) and [0, 2] not in elements_to_remove:
                    elements_to_remove.append([0, 2])
            
            filtered = [vec for vec in vectors if list(vec) not in elements_to_remove]
            return np.array(filtered)

        def filter_moves_in_check(vectors: np.array) -> np.array:
            """
            If the piece is not the king and is in check, only moves that capture 
            the attacker or block the threat are allowed.
            """
            player_turn = 1 if white_turn else -1
            enemy_color = 'black' if white_turn else 'white'
            
            # Locate the enemy king
            king_indices = np.where(self.board == 6 * player_turn)
            if king_indices[0].size == 0:
                return vectors
            xk, yk = king_indices[0].item(), king_indices[1].item()
            kings_position = self.array2logic(xk, yk)
            
            enemy_possible_moves = self.calculate_possible_moves(in_check=False, remove_own=False)[enemy_color]
            attackers = [pos for pos, moves in enemy_possible_moves.items() if kings_position in moves]
            
            if len(attackers) > 1:
                return np.array([])  # If there is more than one attacker, the only option is to move the king.
            
            attacker_position = attackers[0]
            
            # If the attacking piece is a sliding piece, blocking its trajectory is allowed.
            piece_rays = ['queen', 'bishop', 'rook']
            attacker_type = self.what_in(attacker_position).split(' ')[1]
            onray = np.empty((0, 2), dtype=np.int64)
            
            if attacker_type in piece_rays:
                xa, ya = self.logic2array(attacker_position)
                dir_vector = np.sign(np.array([xk - xa, yk - ya]))
                ray = self.raycast(xa, ya, dir_vector, white_turn, remove_own=True)
                path = {tuple((vec + np.array([xa, ya])).tolist()) for vec in ray}
                my_moves = {tuple((np.array([x, y]) + vec).tolist()) for vec in vectors}
                intersection = np.array([np.array(m) for m in my_moves.intersection(path)])
                if intersection.size > 0:
                    onray = intersection - np.array([x, y])
            
            # Only moves that capture the attacker are allowed.
            filtered = []
            for vec in vectors:
                pos = self.array2logic(x + vec[0], y + vec[1])
                if pos == attacker_position:
                    filtered.append(vec)
            
            filtered = np.array(filtered)
            if filtered.size and onray.size:
                return np.concatenate((filtered, onray))
            return filtered

        vectors = filter_out_of_bounds_and_friendly(vectors) #Step 1: Filter out moves that are out of bounds or contain friendly pieces.
        if not remove_own:
            return vectors
        
        if is_king: #Step 2: Additional filtering depending on whether the piece is the king or if it is in check.
            vectors = filter_castling_moves(vectors)
            enemy_moves = [] if self.initializing else self.assess_ataqued_squares(not white_turn)
            valid = [vec for vec in vectors if self.array2logic(x + vec[0], y + vec[1]) not in enemy_moves]
            vectors = np.array(valid)
        elif in_check:
            vectors = filter_moves_in_check(vectors)

        return vectors

    def assess_king_status(self, white_player:bool, restrict_turn:bool=True) -> int:
        """
        Search the position to check if the king is in checks or mated

        Returns:
            int:    -2 if it is a black's mate 
                    -1 if it is a black's check
                    0 if nothing
                    1 if it is a white's check
                    2 if it is a white's mate
            enemy_movements: a dictionary with all posible movements and positions 
            of enemy pieces that checks or mates the king
            friendly_help: a dictionary with all posible movements and positions
            of frendly pieces that can bloc the check or the mate
        """
        enemy_color     = 'black' if white_player else 'white'
        player_turn     = 1 if white_player else -1 #Check for reverse code
        x, y            = np.where(self.board == 6 * player_turn)
        x, y            = x.item(), y.item()
        kings_position  = self.array2logic(x,y)
        enemy_movements = {}
        friendly_help   = {} #TODO Pin pieces
        danger          = 0
        for pos, moves in self.possible_moves[enemy_color].items():
            if kings_position in moves:
                danger += 1
                enemy_movements[pos] = moves

        danger = 1 if danger > 0 else 0
        king = 'white ' if white_player else 'black '
        king += 'king'
        
        if danger > 0:
            kings_movements = self.allowed_movements(king, kings_position, in_check=True, restrict_turn=restrict_turn)
            danger *= 2 if len(kings_movements) + len(friendly_help) == 0 else 1 #It is a Mate if the king has no scape neither can a friendly piece bloc the mate
            #FIXME the king can be helped with a friendly piece which is not yet calculated
        
        return danger
    
    def assess_ataqued_squares(self, white_player:bool) -> List[str]:
        """
        Calculates and updates all movements that each piece can attack
        """
        possible_moves = self.calculate_possible_moves(remove_own=False)
        color = 'white' if white_player else 'black'
        ataqued_squares = []
        for position, moves in possible_moves[color].items():
            if color in self.what_in(position):
                ataqued_squares += moves

        unique_ataqued_squares = []
        for square in ataqued_squares:
            if square not in unique_ataqued_squares:
                unique_ataqued_squares.append(square)
        return unique_ataqued_squares

    def assess_empty_squares(self, targets:List[str]) -> np.array:
        """
        Assess if targets squares are empty

        Parameters:
            targets: a list of positions to assess

        Returns:
            np.array: an array of boolean items checking for each square if it is attacked
        """

        squares_status = []
        for square in targets:
            squares_status.append('Empty' in self.what_in(square))

        return np.array(squares_status)

    def calculate_possible_moves(self, in_check:bool=False, remove_own:bool=True) -> Dict[str, List[str]]:
        """
        Calculates and updates all movements that each piece can perform
        
        Parameters:
            in_check: there is a check to the king
            remove_own: a boolean that signals that the square should be eliminated 
            if there is a friendly piece -> should be True except when calculating
            for attaqued squares

        Returns:
            Dict: a diccionary with position entry, and a list of positions for values indicating
            where is legal that the piece in the key can move
        """        
        possible_moves = {'white': {}, 'black':{}}
        for x in range(BOARD_SIZE):
            for y in range(BOARD_SIZE):
                if self.board[x, y] != 0:
                    color = 'white' if self.board[x, y] > 0 else 'black'
                    piece = color + ' '
                    piece += self.num2name[np.abs(self.board[x, y]).item()]
                    position = self.array2logic(x,y)
                    movements = self.allowed_movements(piece, position, restrict_turn=False, in_check=in_check, remove_own=remove_own)
                    if len(movements) > 0:
                        possible_moves[color][position] = movements
        
        for key in list(possible_moves[color].keys()): #Filtering pinned pieces
            if key in self.pinned_pieces:
                del possible_moves[color][key]

        return possible_moves

    def make_move(self, 
                  piece:str, 
                  initial_position:str, 
                  end_position:str, 
                  promote2:str=None, 
                  add2history:bool=True
                  ) -> Tuple[bool, str]:
        """
        Executes a move if it is legal.

        Parameters:
            piece: A string indicating the color and type of piece, e.g., 'white king'.
            initial_position: A two-character string representing the starting position, e.g., 'e2'.
            end_position: A two-character string representing the destination position, e.g., 'e4'.
            promote: A string indicating the color and type of piece for pawn promotion, e.g., 'white queen'.
            add2history: A boolean that allows this move to be recorded

        Returns:
            True if the move is legal and successfully executed, False otherwise.
        """        
        def en_passant_conditions(piece:str, initial_position:str, end_position:str, last_piece:str, last_end:str) -> bool:
            """
            Set of conditions for en passant

            Parameters
                piece: A string indicating the color and type of piece, e.g., 'white king'.
                initial_position: A two-character string representing the starting position, e.g., 'e2'.
                end_position: A two-character string representing the destination position, e.g., 'e4'.
                last_piece: A string indicating the color and type of piece last piece moved, e.g., 'white king'.
                last_end: A two-character string representing the last destination position, e.g., 'e4'.

            Returns
                bool: True if en passant can be played in current conditions
            """
            if last_piece is None:
                return False
            allows = True
            allows = allows and 'pawn' in piece
            allows = allows and 'pawn' in last_piece
            allows = allows and 'Empty' in self.what_in(end_position)
            x, y    = self.logic2array(initial_position)
            xp, yp  = self.logic2array(last_end)
            specifics = ((self.white_turn, x, xp) == (True, 3, 3)) or ((self.white_turn, x, xp) == (False, 4, 4)) 
            allows = allows and specifics
            allows = allows and np.abs(y-yp) == 1
            return allows

        king_status = self.assess_king_status(self.white_turn)
        if np.abs(king_status) == 2:
            return False, ''

        moving_color = 'white' if 'white' in piece else 'black'
        if initial_position in self.possible_moves[moving_color]:
            if end_position in self.possible_moves[moving_color][initial_position]:
                movement = self.notation_from_move(piece, initial_position, end_position)
                last_piece, last_init, last_end = self.last_turn
                self.last_turn = (piece, initial_position, end_position) #Enables en passant

                if en_passant_conditions(piece, initial_position, end_position, last_piece, last_end): 
                    self.set_piece('Empty square', last_end)
                    movement = initial_position[0] + 'x' + movement
                
                self.set_piece('Empty square', initial_position)
                self.set_piece(piece, end_position)
                
                if movement == 'O-O': #King movement is already done, we need to move the rook
                    if self.white_turn:
                        self.set_piece('Empty square', 'h1')
                        self.set_piece('white rook', 'f1')
                    else:
                        self.set_piece('Empty square', 'h8')
                        self.set_piece('black rook', 'f8')
                if movement == 'O-O-O': #Same
                    if self.white_turn:
                        self.set_piece('Empty square', 'a1')
                        self.set_piece('white rook', 'd1')
                    else:
                        self.set_piece('Empty square', 'a8')
                        self.set_piece('black rook', 'd8')
                
                if promote2 is not None and 'pawn' in piece:
                    if (self.white_turn and '8' in end_position) or (not self.white_turn and '1' in end_position):
                        self.set_piece(promote2, end_position)
                        promotions = {'queen' : 'Q', 'rook' : 'R', 'knight' : 'N', 'bishop' : 'B'}
                        movement += '=' + promotions[promote2.split(' ')[1]]

                if 'x' in movement: #TODO add to captured pieces whatever in end_position
                    pass

                if 'K' in movement:
                    if self.white_turn:
                        self.castle_flags['white king moved'] = True
                    else:
                        self.castle_flags['black king moved'] = True
                elif 'R' in movement:
                    if initial_position == 'a1':
                        self.castle_flags['a1 rook moved'] = True
                    elif initial_position == 'h1':
                        self.castle_flags['h1 rook moved'] = True
                    elif initial_position == 'a8':
                        self.castle_flags['a8 rook moved'] = True
                    elif initial_position == 'h8':
                        self.castle_flags['h8 rook moved'] = True
                
                self.pinned_pieces = []
                self.possible_moves = self.calculate_possible_moves() #Recalculate legal moves just after modifying the board to check the impact
                king_status = self.assess_king_status(not self.white_turn, restrict_turn=False)
                if np.abs(king_status) == 1:
                    self.possible_moves = self.calculate_possible_moves(in_check=True)
                    movement += '+'
                elif np.abs(king_status) == 2:                
                    movement += '#'

                if add2history:
                    fen = self.numpy2fen(self.board)
                    if self.white_turn:
                        self.history.append([[movement], [fen]])
                    else:
                        self.history[-1][0].append(movement)
                        self.history[-1][1].append(fen)

                turn, _ = self.pointer
                if not self.white_turn:
                    turn += 1
                self.white_turn = not self.white_turn
                self.pointer = (turn, self.white_turn)
                return True, movement
        else:
            return False, ''
        
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
        """
        In case there is more than one candidate for the starting position, 
        a disambiguation logic is applied: for pawns, the origin column is used, 
        and for other pieces, the piece information (e.g., its notation) is used.

        Parameters:
            piece: A string representing the type of piece, e.g., 'knight', 'queen'
            play_stripped: A chess like play, e.g., 'Nf3' but withouth '+' or '#'
            candidates: a list of candidate pieces

        Returns:
            str: piece name 
        """
        if len(candidates) == 1:
            return candidates[0]
        else:
            if 'pawn' in piece: #Find the candidate that matches the column indicated in the notation
                for candidate in candidates:
                    if candidate[0] == play_stripped[0]:
                        return candidate
            else: #Attempt to disambiguate using the full description of the piece
                candidates_dict = {self.what_in(position): position for position in candidates}
                return candidates_dict.get(piece, candidates[0])

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
        with open(filename, "w", encoding="utf-8") as file:
            yaml.dump(board, file, allow_unicode=True, default_flow_style=False)
    
    def load_position(self, filename:str) -> None:
        """
        Loads a position from a YAML file. It has no knoledge of the plays.

        Parameters:
            filename: A string with the name and route to the target file
        """
        with open(filename, "r", encoding="utf-8") as file:
            board = yaml.safe_load(file)

        self.clear_board()
        for position, piece in board.items():
            if position == "Playe's Turn":
                continue
            self.set_piece(piece, position)

        self.white_turn = board["Playe's Turn"] == 'white'
        self.bitboard = ChessBitboard(self.board)

    def save_game(self, filename:str) -> None:
        """
        Saves a game to a YAML file. It doesn't saves the position.

        Parameters:
            filename: A string with the name and route to the target file
        """
        with open(filename, "w", encoding="utf-8") as file:
            yaml.dump(self.history, file, allow_unicode=True, default_flow_style=False)

    def load_game(self, filename:str, go2last:bool=False) -> None:
        """
        Loads a game from a YAML file. It infers the position.

        Parameters:
            filename: A string with the name and route to the target file
        """
        with open(filename, "r", encoding="utf-8") as file:
            history = yaml.safe_load(file)

        self.clear_board()
        self.load_position('config/initial_position.yaml')
        self.history = history
        self.pointer = (0, True)
        
        if go2last:
            if len(history[-1][0]) == 1:
                history[-1][0].append('quit')
            for i, ((white_move, black_move), (white_fen, black_fen)) in enumerate(self.history):
                piece, initial_position, end_position = self.read_move(white_move)
                self.make_move(piece, initial_position, end_position)
                self.white_turn = False
                if black_move == 'quit':
                    break
                piece, initial_position, end_position = self.read_move(black_move)
                self.make_move(piece, initial_position, end_position)
                self.white_turn = True
        self.bitboard = ChessBitboard(self.board)

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
        
        position = fen.split(' ')[0] #The first field is the position itself
        
        board = []
        for row in position.split('/'): #Rows are separated by /
            current_row = []
            for char in row:
                if char.isdigit():
                    current_row.extend([0] * int(char)) #Digits are for empty squares
                else:
                    current_row.append(mapping[char])
            board.append(current_row)
        
        return np.array(board)
    
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
    
    def go2(self, turn:int, white_player:bool) -> None:
        """
        Actualizes the position and pointer to fit the given number

        Parameters:
            turn: the position in the sequence of the target turn
            white_player: True is the calculations are done for white's player turn
        """
        entry = self.history[turn]
        moves, fens = entry
        white_fen = fens[0]
        black_fen = fens[1] if len(fens) > 1 else None
        self.board = self.fen2numpy(white_fen) if white_player else self.fen2numpy(black_fen)
        self.white_turn = white_player
        self.possible_moves = self.calculate_possible_moves()
        self.pointer = (turn, white_player)

if __name__ == '__main__':
    board = ChessBoard()

