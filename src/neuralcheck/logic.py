import pdb
import numpy as np
import bitboardops as bb
import yaml
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from neuralcheck.bitboard import ChessBitboard
from typing import Tuple, List, Dict

class ChessBoard:
    def __init__(self):
        #NOTE This is high level representation of the board. 
        #It uses a 8x8 numpy matrix (check put method to see piece representation).
        #This class has direct communication with the UI to handle it.
        #This representation is not optimal for search or machine learning. 
        #There is a lower level for this using bitboard representations.
        #That level is syncronized with this for tracking pourpuses.
        
        self._initialize_resources()
        self.history = []
        self.last_turn = ''
        self.load_position('config/initial_position.yaml') 
        self.possible_moves = self.calculate_possible_moves()
        self.bitboard = ChessBitboard(self.board)

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

    def assess_king_status(self) -> Tuple[int, Dict[str, List[str]], Dict[str, List[str]]]:
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
        player_turn     = -1 if self.white_turn else 1 #Check for reverse code
        x, y            = np.where(self.board == 6 * player_turn)
        x, y            = x.item(), y.item()
        kings_position  = self.array2logic(x,y)
        enemy_movements = {}
        friendly_help   = {}
        for piece_code in range(1,6):
            all_alike   = np.where(self.board == piece_code * player_turn)
            all_alike   = np.array(all_alike).reshape(-1,2)
            piece       = 'black ' if self.white_turn else 'white '
            piece       += self.num2name[piece_code]
            for x, y in all_alike:
                position = self.array2logic(x,y)
                movements = self.allowed_movements(piece, position)
                if kings_position in movements:
                    enemy_movements[position] = movements
        
        danger = player_turn if len(enemy_movements) > 0 else 0 #Its a check if there is someone that can reach the king in the current turn
        king = 'white ' if self.white_turn else 'black '
        king += 'king'
        if danger > 0:
            kings_movements = self.allowed_movements(king, kings_position, in_check=True)
            danger *= 2 if len(kings_movements) + len(friendly_help) == 0 else 1 #It is a Mate if the king has no scape neither can a friendly piece bloc the mate
            #FIXME the king can be helped with a friendly piece which is not yet calculated

        return 0, enemy_movements

    def allowed_movements(self, piece:str, position:str, in_check:bool=False) -> List[str]:
        """
        Calculates all legal movements of the piece.

        Parameters:
            piece: a string indicating color and piece, e.g., 'white king'
            position: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'
            in_check: there is a check to the king

        Returns:
            List[str]: a list with all legal movements of the piece in chess-like format
        """
        def raycast(x:int, y:int, vectors:np.array) -> np.array:
            """
            Calculate a raycast of the piece from direction vectors stoping when an obstacule is founded

            Parameters:
                x: x position in the board of the piece
                y: y position in the board of the piece
                vectors: an array with all plausible directions for the piece to go

            Returns
                np.array: an array with all posible directions to travel acording to rules
            """
            moves = np.empty((0, 2), dtype=np.int64)
            player_turn = 1 if self.white_turn else -1
            for dx, dy in vectors: #All vectors should be unit vectors in the desired directions.
                for i in range(1, 8): #We advance i units in the desired direction and check for obstacles at each step.
                    if 0 < x + i*dx and x + i*dx < 8 and 0 < y + i*dy and y + i*dy < 8: #Ensure movement stays within the board
                        if player_turn * self.board[x + i*dx, y + i*dy] <= 0: #Check for enemy pieces (or empty squares); multiplying by player_turn adjusts the inequality.
                            moves = np.concatenate((moves, np.array([[i*dx, i*dy]])))
                            if player_turn * self.board[x + i*dx, y + i*dy] < 0: #Stops, but allows capturing.
                                break
                        else: #Encounter a piece of the same color; stops immediately.
                            break
            return moves
        
        def remove_illegal(x:int, y:int, vectors:np.array, is_king:bool=False) -> np.array:
            #NOTE el rey no se puede mover donde otras piezas lo estén atacando
            #TODO chequear que la pieza no esté pinneada al rey
            player_turn = 1 if self.white_turn else -1
            i = 0
            while i < len(vectors):
                dx, dy = vectors[i]            
                if player_turn * self.board[x + i*dx, y + i*dy] > 0: #There is a piece of its own
                    vectors = np.delete(vectors, i, axis=0)
                else:
                    i += 1
            return vectors

        #NOTE si el rey está en jaque las únicas piezas que se pueden mover son el mismo, y aquellas que lo protejen
        if 'black' in piece and self.white_turn:
            return []
        if 'white' in piece and not self.white_turn:
            return []
        
        line_vectors        = np.array([[1, 0], [-1, 0], [0, 1], [0, -1]])
        diagonal_vectors    = np.array([[1, 1], [-1, 1], [-1, -1], [1, -1]])
        
        x, y            = self.logic2array(position) #Be careful with notation when converting to NumPy arrays
        position        = np.array([x, y])
        
        if 'king' in piece:
            piece_moves = np.array([[1,0], [1,1], [0,1], [-1,1], [-1,0], [-1,-1], [0,-1], [1,-1]])
            piece_moves = remove_illegal(x, y, piece_moves, is_king=True)
            # TODO agregar enroque
            # El rey se ha movido antes: buscar en el historial
            # La torre se ha movido antes: buscar en el historial
            # Los espacios están libres: self.what_in == Empty
            # El rey no está en Jaque -> self.assess_king_status = 0, _, _
            # La torre no está siendo atacada

        elif 'queen' in piece:
            all_vectors = np.concatenate((line_vectors, diagonal_vectors))
            piece_moves = raycast(x, y, all_vectors)
        elif 'bishop' in piece:
            piece_moves = raycast(x, y, diagonal_vectors)
        elif 'knight' in piece:
            piece_moves = np.array([[2,1], [1,2], [-1,2], [-2,1], [-2,-1], [-1,-2], [1,-2], [2,-1]]) 
            piece_moves = remove_illegal(x, y, piece_moves)
        elif 'rook' in piece:
            piece_moves = raycast(x, y, diagonal_vectors)
        elif 'pawn' in piece:             
            if self.white_turn: 
                piece_moves = np.array([[-1, 0]])
                if x == 6: #Special movement for pawns in their starting rank
                    piece_moves = np.concatenate((piece_moves, np.array([[-2, 0]])))
                if y + 1 < 8 and x - 1 > 0:
                    if self.board[x - 1, y + 1] < 0: #There is an enemy piece
                        piece_moves = np.concatenate((piece_moves, np.array([[-1, 1]])))
                if y - 1 > 0 and x - 1 > 0:
                    if self.board[x - 1, y - 1] < 0: #Idem
                        piece_moves = np.concatenate((piece_moves, np.array([[-1, -1]])))
                if x == 1: #En passant TODO
                    #self.last_turn chequear si la pieza hizo un movimiento amplio en el turno anterior
                    pass

            else: 
                piece_moves = np.array([[1, 0]])
                if x == 1: #Special movement for pawns in their starting rank
                    piece_moves = np.concatenate((piece_moves, np.array([[2, 0]])))
                if y + 1 < 8 and x + 1 < 8:
                    if self.board[x + 1, y + 1] > 0: #There is an enemy piece
                        piece_moves = np.concatenate((piece_moves, np.array([[1, 1]])))
                if y - 1 > 0 and x + 1 < 8:
                    if self.board[x + 1, y - 1] > 0: #Idem
                        piece_moves = np.concatenate((piece_moves, np.array([[1, -1]])))
                if x == 6: #En passant TODO
                    pass
        else:
            piece_moves = np.array([[0,0]])

        destinations    = position + piece_moves
        mask            = np.all((destinations >= 0) & (destinations <= 7), axis=1) #Remove moves that go off the board
        destinations    = destinations[mask]
        legal_moves = [''] * len(destinations)
        for i, (x, y) in enumerate(destinations):
            legal_moves [i] = self.array2logic(x, y)

        return legal_moves 

    def calculate_possible_moves(self) -> Dict[str, str]:
        """
        Calculates and updates all movements that each piece can perform
        """
        #current_turn = self.w
        possible_moves = {}
        for x in range(8):
            for y in range(8):
                if self.board[x, y] != 0:
                    piece = 'white ' if self.board[x, y] > 0 else 'black '
                    piece += self.num2name[np.abs(self.board[x, y]).item()]
                    position = self.array2logic(x,y)
                    movements = self.allowed_movements(piece, position)
                    if len(movements) > 0:
                        possible_moves[position] = movements

        return possible_moves

    def make_move(self, piece:str, initial_position:str, end_position:str) -> Tuple[bool, str]:
        """
        Executes a move if it is legal.

        Parameters:
            piece: A string indicating the color and type of piece, e.g., 'white king'.
            initial_position: A two-character string representing the starting position, e.g., 'e2'.
            end_position: A two-character string representing the destination position, e.g., 'e4'.

        Returns:
            True if the move is legal and successfully executed, False otherwise.
        """        
        legal_movements = self.allowed_movements(piece, initial_position) #TODO reduce legal movements for check and pinned pieces
        
        xi, yi = self.logic2array(initial_position)
        xe, ye = self.logic2array(end_position)
        
        if end_position in legal_movements:
            movement = self.notation_from_move(piece, initial_position, end_position)
            if 'x' in movement: #TODO add to captured pieces whatever in end_position
                pass
            self.last_turn = [piece, movement] #Enables en passant
            self.set_piece('Empty square', initial_position)
            self.set_piece(piece, end_position)
            #TODO Agregar promoción de peones
            if self.white_turn:
                self.history.append([movement])
            else:
                self.history[-1].append(movement)
            self.white_turn = not self.white_turn
            self.possible_moves = self.calculate_possible_moves()
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
        #TODO enroque corto
        #TODO enroque largo
        #TODO jaque, y ojo, jaque a la descubierta
        #TODO mate
        #TODO promoción
        
        movement = ''
        if 'king' in piece:
            movement += 'K'
        elif 'queen' in piece:
            movement += 'Q'
        elif 'bishop' in piece:
            movement += 'B'
        elif 'knight' in piece:
            movement += 'N'
        elif 'rook' in piece:
            movement += 'R'

        same_piece = self.search_for(piece) #Check all pieces of the same type to the current piece
        if len(same_piece) > 1: #If there are other pieces            
            candidates = []
            for position in same_piece:
                if end_position in self.allowed_movements(piece, position): #FIXME En el caso de los peones hay que ver si ellos se pueden mover solo capturando.  hay que arreglar este método, probablemente haya que agregar la posición final para que pueda chequear si el peon puede llegar capturando
                    candidates.append(position)
            if len(candidates) > 1: #We need desammutation
                if len(set(pos[0] for pos in candidates)) == 1: #Check if the pieces are in the same column
                    movement += initial_position[1] #Disambiguate by row
                else: 
                    movement += initial_position[0] #Disambiguate by column

        if 'Empty' not in self.what_in(end_position):
            movement += 'x'

        return movement + end_position.lower()
        
    def read_move(self, play: str, white_player:bool) -> Tuple[str, str, str]:
        """
        Transcribes a move from a chess like play to a triplet for the move method to execute

        Parameters:
            play: A chess like play, e.g., 'Nf3'
            white_player: True if it is the white's player turn
        
        Returns:
            piece: A string representing the type of piece, e.g., 'knight', 'queen'.
            initial_position: A two-character string representing the starting position, e.g., 'g1'.
            end_position: A two-character string representing the destination position, e.g., 'f3'.

        """
        #TODO finish

        piece = 'white ' if white_player else 'black '

        if 'K' in play:
            piece += 'king'
        elif 'Q' in play:
            piece += 'queen'
        elif 'B' in play:
            piece += 'bishop'
        elif 'B' in play:
            piece += 'knight'
        elif 'R' in play:
            piece += 'rook'
        elif play == 'O-O':
            piece += 'king'
        elif play == 'O-O-O':
            piece += 'king'
        else:
            piece += 'pawn'

        piece = ''
        initial_position = ''
        end_position = play[-2:] #Solo si no es enroque, revisar
        return piece, initial_position, end_position

    def save_position(self, filename:str) -> None:
        """
        Saves a position to a YAML file. It doesn't saves the plays.
        """
        board = {}
        for x in range(8):
            for y in range(8):
                position    = self.array2logic(x,y)
                piece       = self.what_in(position)
                if 'Empty' not in piece:
                    board[position] = piece
        board["Playe's Turn"] = 'white' if self.white_turn else 'black'
        with open(filename, "w", encoding="utf-8") as file:
            yaml.dump(board, file, allow_unicode=True, default_flow_style=False)
    
    def load_position(self, filename) -> None:
        """
        Loads a position from a YAML file. It has no knoledge of the plays.
        """
        with open(filename, "r", encoding="utf-8") as file:
            board = yaml.safe_load(file)

        self.board = np.zeros((8,8), dtype=np.int64)
        for position, piece in board.items():
            if position == "Playe's Turn":
                continue
            self.put(piece, position)

        self.white_turn = board["Playe's Turn"] == 'white'
        self.bitboard = ChessBitboard(self.board)

    def save_game(self, filename:str) -> None:
        """
        Saves a game to a YAML file. It doesn't saves the position.
        """
        with open(filename, "w", encoding="utf-8") as file:
            yaml.dump(self.history, file, allow_unicode=True, default_flow_style=False)

    def load_game(self, filename:str) -> None:
        """
        Loads a game from a YAML file. It infers the position.
        """
        with open(filename, "r", encoding="utf-8") as file:
            history = yaml.safe_load(file)

        self.history = history
        self.load_position('config/initial_position.yaml')

        for white_turn, black_turn in self.history: 
            piece, initial_position, end_position = self.read_move(white_turn)
            self.make_move(piece, initial_position, end_position)
            self.white_turn = False
            if black_turn is None:
                break
            piece, initial_position, end_position = self.read_move(black_turn)
            self.make_move(piece, initial_position, end_position)
            self.white_turn = True

if __name__ == '__main__':
    board = ChessBoard()

