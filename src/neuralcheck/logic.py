import pdb
import numpy as np
import bitboardops as bb
from neuralcheck.bitboard import ChessBitboard
from typing import Tuple, List

class ChessBoard:
    def __init__(self):
        #NOTE This is high level representation of the board. 
        #It uses a 8x8 numpy matrix (check put method to see piece representation).
        #This class has direct communication with the UI to handle it.
        #This representation is not optimal for search or machine learning. 
        #There is a lower level for this using bitboard representations.
        #That level is syncronized with this for tracking pourpuses.
        
        self._initialize_resources()
        self._initialize_pieces()
        self.white_turn = True
        self.history = []
        self.last_turn = ''
        self.bitboard = ChessBitboard()

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

        #FIXME for now movement is done with arrays
        king_movement_matrix    = np.array([[1,0], [1,1], [0,1], [-1,1], [-1,0], [-1,-1], [0,-1], [1,-1]])
        wpawn_movement_matrix   = np.array([[1,1], [0,1], [-1,1]])
        bpawn_movement_matrix   = np.array([[-1,-1], [0,-1], [1,-1]])
        bishop_movement_matrix  = np.array([[a,a] for a in np.arange(1,8)])
        bishop_movement_matrix  = np.concatenate((bishop_movement_matrix, np.array([[-a,-a] for a in np.arange(1,8)])))
        bishop_movement_matrix  = np.concatenate((bishop_movement_matrix, np.array([[a,-a] for a in np.arange(1,8)])))
        bishop_movement_matrix  = np.concatenate((bishop_movement_matrix, np.array([[-a,a] for a in np.arange(1,8)])))
        rook_movement_matrix    = np.array([[a,0] for a in np.arange(1,8)])
        rook_movement_matrix    = np.concatenate((rook_movement_matrix, np.array([[-a,0] for a in np.arange(1,8)])))
        rook_movement_matrix    = np.concatenate((rook_movement_matrix, np.array([[0,a] for a in np.arange(1,8)])))
        rook_movement_matrix    = np.concatenate((rook_movement_matrix, np.array([[0,-a] for a in np.arange(1,8)])))
        queen_movement_matrix   = np.concatenate((bishop_movement_matrix, rook_movement_matrix))
        knight_movement_matrix  = np.array([[2,1], [1,2], [-1,2], [-2,1], [-2,-1], [-1,-2], [1,-2], [2,-1]])
        king_movement_matrix    = np.column_stack((-king_movement_matrix[:, 1], king_movement_matrix[:, 0])) #Converting from cartesian logic to numpy notation: row = (n - 1) - y; column = x
        queen_movement_matrix   = np.column_stack((-queen_movement_matrix[:, 1], queen_movement_matrix[:, 0]))
        bishop_movement_matrix  = np.column_stack((-bishop_movement_matrix[:, 1], bishop_movement_matrix[:, 0]))
        knight_movement_matrix  = np.column_stack((-knight_movement_matrix[:, 1], knight_movement_matrix[:, 0]))
        rook_movement_matrix    = np.column_stack((-rook_movement_matrix[:, 1], rook_movement_matrix[:, 0]))
        wpawn_movement_matrix   = np.column_stack((-wpawn_movement_matrix[:, 1], wpawn_movement_matrix[:, 0]))
        bpawn_movement_matrix   = np.column_stack((-bpawn_movement_matrix[:, 1], bpawn_movement_matrix[:, 0]))
        self.movemnts_matrices  = {
            'white king': king_movement_matrix,
            'white queen': queen_movement_matrix,
            'white bishop': bishop_movement_matrix,
            'white knight': knight_movement_matrix,
            'white rook': rook_movement_matrix,
            'white pawn': wpawn_movement_matrix,
            'black king': king_movement_matrix,
            'black queen': queen_movement_matrix,
            'black bishop': bishop_movement_matrix,
            'black knight': knight_movement_matrix,
            'black rook': rook_movement_matrix,
            'black pawn': bpawn_movement_matrix
        }

    def _initialize_pieces(self) -> None:
        """
        Initializes numpy matrix with the corresponding piece code
        """
        row = [0]*8
        board = [row]*8
        self.board = np.array(board, dtype=np.int64)

        self.put('white king', 'e1')
        self.put('white queen', 'd1')
        self.put('white bishop', 'f1')
        self.put('white bishop', 'c1')
        self.put('white knight', 'g1')
        self.put('white knight', 'b1')
        self.put('white rook', 'h1')
        self.put('white rook', 'a1')
        self.put('black king', 'e8')
        self.put('black queen', 'd8')
        self.put('black bishop', 'f8')
        self.put('black bishop', 'c8')
        self.put('black knight', 'g8')
        self.put('black knight', 'b8')
        self.put('black rook', 'h8')
        self.put('black rook', 'a8')
        
        for i, col in enumerate(self._cols_str):
            self.put('white pawn', f'{col}2')
            self.put('black pawn', f'{col}7')
    
    def logic2array(self, position:str) -> Tuple[int, int]:
        """
        Transforms a chess position to an index position fro drawing

        Parameters:
            position: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'

        Returns:
            Tuple(int, int): two ints representing the position in numpy index coordinates
        """
        col, row = position[0], int(position[1])
        x = 8 - row
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
        row = 8 - x
        return f'{col}{row}'

    def put(self, piece:str, position:str) -> None:
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

    def allowed_movements(self, piece:str, position:str) -> List[str]:
        """
        Calculates all legal movements of the piece.

        Parameters:
            piece: a string indicating color and piece, e.g., 'white king'
            position: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'

        Returns:
            List[str]: a list with all legal movements of the piece in chess-like format
        """
        if 'black' in piece and self.white_turn:
            return []
        if 'white' in piece and not self.white_turn:
            return []
        
        x, y = self.logic2array(position) #Be careful with notation when converting to NumPy arrays
        pos = np.array([x, y])
        pmm = self.movemnts_matrices[piece]
        
        if 'pawn' in piece: #Special movement for pawns in their starting rank
            if self.white_turn and x == 6:
                pmm = np.concatenate((pmm, np.array([[-2, 0]])))
            if not self.white_turn and x == 1:
                pmm = np.concatenate((pmm, np.array([[2, 0]])))

        movs = pos + pmm
        mask = np.all((movs >= 0) & (movs <= 7), axis=1) #Remove moves that go off the board
        movs = movs[mask]
        #TODO Falta chequear si los movimientos terminan sobre una pieza y qué tipo de pieza es
        #TODO Falta chequear los movimientos de proyección en línea: reina, alfil, torre
        #TODO Faltan chequear movimientos especiales:
        #   -Captura al paso
        #   -Enroque

        npos = [''] * len(movs)
        for i, (x, y) in enumerate(movs):
            npos[i] = self.array2logic(x, y)

        return npos

    def move(self, piece:str, initial_position:str, end_position:str) -> bool:
        """
        Executes a move if it is legal.

        Parameters:
            piece: A string indicating the color and type of piece, e.g., 'white king'.
            initial_position: A two-character string representing the starting position, e.g., 'e2'.
            end_position: A two-character string representing the destination position, e.g., 'e4'.

        Returns:
            True if the move is legal and successfully executed, False otherwise.
        """        
        legal_movements = self.allowed_movements(piece, initial_position)
        
        xi, yi = self.logic2array(initial_position)
        xe, ye = self.logic2array(end_position)
        
        if end_position in legal_movements:
            self.put('Empty square', initial_position)
            self.put(piece, end_position)
            #TODO Agregar promoción de peones
            turn = self.transcribe(piece, initial_position, end_position)
            self.last_turn = turn
            if self.white_turn:
                self.history.append([turn])
            else:
                self.history[-1].append(turn)
            self.white_turn = not self.white_turn
            return True
        else:
            return False
            
    def transcribe(self, piece: str, initial_position: str, end_position: str) -> str:
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

        #TODO capura
        #TODO enroque corto
        #TODO enroque largo
        #TODO jate
        #TODO mate
        #TODO promoción
        #TODO desambigüación de dos piezas que pueden ir a una misma casilla
        movement = ''

        return movement + initial_position.lower()
        

if __name__ == '__main__':
    board = ChessBoard()

