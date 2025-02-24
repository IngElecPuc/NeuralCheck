import numpy as np
import bitboardops as bb
import re
import pdb

class ChessPiece: #FIXME esta clase no aporta mucho, borrar
    def __init__(self, ptype: str, position: str, white_player_turn: bool):
        self.ptype = ptype
        self.position = position
        self.white_player_turn = white_player_turn

    def value(self):
        values = {
            'king': 100,
            'queen': 9,
            'rook': 5,
            'bishop': 3,
            'knight': 3,
            'pawn': 1
        }
        return values[self.type]

"""
bitboard_blancas = 0b0000000000000000000000000000000000000000000000001111111100000000
print(f"{bitboard_blancas:064b}")
Tablero
a8 b8 c8 d8 e8 f8 g8 h8
a7 b7 c7 d7 e7 f7 g7 h7
a6 b6 c6 d6 e6 f6 g6 h6
a5 b5 c5 d5 e5 f5 g5 h5
a4 b4 c4 d4 e4 f4 g4 h4
a3 b3 c3 d3 e3 f3 g3 h3
a2 b2 c2 d2 e2 f2 g2 h2
a1 b1 c1 d1 e1 f1 g1 h1
Entero (Posición del bit)
63 62 61 60 59 58 57 56
55 54 53 52 51 50 49 48
47 46 45 44 43 42 41 40
39 38 37 36 35 34 33 32
31 30 29 28 27 26 25 24
23 22 21 20 19 18 17 16
15 14 13 12 11 10 09 08
07 06 05 04 03 02 01 00
"""


"""
Por el momento la lógica de bits se prueba en Python, pero más tarde se debe enviar a C para optimización de velocidad. 
Python puede trabajar con expresiones regulares para procesar las órdenes de movimiento por mientras que crece la aplicación.
TODO
Más adelante habrá que regular bien el flujo de procesamiento según el nivel de abstracción pues está comenzando a crecer desordenado esto.

"""

class ChessBitboard:
    def __init__(self, board=None):
        self.board = board
        self._initialize_pieces(board)        
        self._cols_str  = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        self._cols2int  = {col:num for num, col in enumerate(self._cols_str[::-1])}
        self._int2cols  = {num:col for num, col in enumerate(self._cols_str[::-1])}
        
        """
        init_positions  = [['king', ['e1', 'e8']], 
                          ['queen', ['d1', 'd8']], 
                          ['bishop', ['c1', 'c8']], 
                          ['bishop', ['f1', 'f8']],
                          ['knight', ['b1', 'b8']], 
                          ['knight', ['g1', 'g8']],
                          ['rook', ['a1', 'a8']], 
                          ['rook', ['h1', 'h8']]]
        self.pieces     = [] #Representación para ML y para seguir track de las piezas

        for (ptype, (p1, p2)) in init_positions:
            self.pieces.append(ChessPiece(ptype, p1, True))
            self.pieces.append(ChessPiece(ptype, p2, False))

        for col in self._cols_str:
            self.pieces.append(ChessPiece('pawn', f'{col}2', True))
            self.pieces.append(ChessPiece('pawn', f'{col}1', False))
        """

        self.positional_masks = {}
        for col in self._cols_str:
            for row in range(1,8):
                position = f'{col}{row}'
                self.positional_masks[position] = self.get_bitboard_position(position) #Se utilizan tanto que mejor traducirlas directo a diccionario

    def _initialize_pieces(self, board:np.array) -> None:
        """
        Infer the bitboard masks of the pieces based on the board matrix.

        Parameters:
            board: a 8x8 int numpy array with maping as ChessBoard class
        """        
        kings   = 0
        queens  = 0
        bishops = 0
        knights = 0
        rooks   = 0
        pawns   = 0
        white   = 0
        black   = 0

        if board is None:
            kings   = 0x0800000000000008
            queens  = 0x1000000000000010
            bishops = 0x2400000000000024
            knights = 0x4200000000000042
            rooks   = 0x8100000000000081
            pawns   = 0x00FF00000000FF00
            white   = 0x000000000000FFFF
            black   = 0xFFFF000000000000
        else:
            flatboard = board.reshape(-1)[::-1] #Flatten and reverse to iterate from the least significant bit to the most
            for piece in range(-6, 7): #Numerical representation of ChessBoard pieces
                if piece == 0: #Zero represents an empty space
                    continue
                detected = (flatboard == piece).astype(int)
                bitboard = 0
                for i, bit in enumerate(detected):
                    bitboard += 2**i if bit == 1 else 0

                if abs(piece) == 6:
                    kings += bitboard
                elif abs(piece) == 5:
                    queens += bitboard
                elif abs(piece) == 4:
                    rooks += bitboard 
                elif abs(piece) == 3:
                    bishops += bitboard                    
                elif abs(piece) == 2:
                    knights += bitboard 
                elif abs(piece) == 1:
                    pawns += bitboard 

                if piece > 0:
                    white += bitboard 
                elif piece < 0:
                    black += bitboard 
                
        self.masks = {
            'K' : kings,
            'Q' : queens,
            'B' : bishops,
            'N' : knights,
            'R' : rooks,
            'P' : pawns,
            'white': white,
            'black': black
        }
    
    def visualize(self, num:int, coords:bool=False) -> None:
        """
        Displays an 8x8 ordered bit-like matrix that represents a 64-bit integer in binary.
        The representation goes from left to right and top to bottom, following the most 
        significant bit to the least.

        Parameters:
            num: A 64-bit integer representing a map or mask of the board
            coords: an optional parameter that allows to print the coordinates
        """
        all_cols = ''
        bitnum = f'{num:064b}'
        for i in range(8):
            print(f"{bitnum[8*i:8*(i+1)]}{8-i if coords else ''}")
            all_cols += self._cols_str[i]
        if coords:
            print(all_cols)

    def get_bitboard_position(self, position:str) -> int:
        """
        Transforms a single chess-like position declaration to a 64-bit integer such as
        that only one bit has a high value and maps exactly to the position desired

        Parameters:
            position: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'

        Returns:
            int: a bitboard number with the position encoded as one bit active
        """
        col, row = position[0], position[1]
        col = self._cols2int[col]
        row = int(row) - 1
        return 1 << col + row * 8

    def flip_horizontal(self, bitboard: int) -> int: 
        """
        Flips the bitboard horizontally, as it was a mirror.

        This operation mirrors the board along the vertical axis, swapping ranks 
        (e.g., the first rank becomes the eighth, the second becomes the seventh, etc.).
        
        Parameters:
            bitboard: A 64-bit integer representing the board's bitboard.

        Returns:
            int: A 64-bit integer representing the horizontally flipped bitboard.
        """
        #This is a Hanoi tower like algorithm where we want to swap rows to achieve vertical flip.
        #We work each column as a byte group
        k1 = 0x5555555555555555 #k1 mask: selects every other byte to prepare for swapping adjacent bytes. A single row looks like 01010101
        k2 = 0x3333333333333333 #k2 mask: selects every other 16-bit word to prepare for swapping 16-bit groups. A single row looks like 00110011
        k3 = 0X0F0F0F0F0F0F0F0F #k3 mask: selects every other 32-bit word to prepare for swapping 32-bit groups. A single row looks like 00001111
        
        #Step 1: Swap adjacent bits.
        #- (bitboard >> 1) shifts the board right by one bit; "& k1" selects bytes originally in odd positions.
        #- (bitboard & k1) selects bytes originally in even positions; "<< 1" shifts them left by one bit.
        #The OR operation combines these two parts, effectively swapping each pair of adjacent bytes
        bitboard = (bitboard >> 1) & k1 | (bitboard & k1) << 1
        #Step 2: Swap adjacent 16-bit words.
        bitboard = (bitboard >> 2) & k2 | (bitboard & k2) << 2
        #Step 3: Swap the 32-bit halves.
        bitboard = (bitboard >> 4) & k3 | (bitboard & k3) << 4
        
        return bitboard & 0xFFFFFFFFFFFFFFFF #Return the final 64-bit result, ensuring no overflow beyond 64 bits.

    def flip_vertical(self, bitboard: int) -> int:
        """
        Flips the bitboard vertically, transforming the board as if viewed from Black's 
        perspective when combining with flip_horizontal.

        This operation mirrors the board along the horizontal axis, swapping ranks 
        (e.g., the first rank becomes the eighth, the second becomes the seventh, etc.).
        
        Parameters:
            bitboard: A 64-bit integer representing the board's bitboard.

        Returns:
            int: A 64-bit integer representing the vertically flipped bitboard.
        """
        k1 = 0x00FF00FF00FF00FF #k1 mask: selects every other byte (0x00FF00FF00FF00FF) to prepare for swapping adjacent bytes.
        k2 = 0x0000FFFF0000FFFF #k2 mask: selects every other 16-bit word (0x0000FFFF0000FFFF) to prepare for swapping 16-bit groups.
        k3 = 0x00000000FFFFFFFF #k3 mask: selects every other 32-bit word (0x00000000FFFFFFFF) to prepare for swapping 32-bit groups.

        bitboard = ((bitboard >> 8) & k1) | ((bitboard & k1) << 8)
        bitboard = ((bitboard >> 16) & k2) | ((bitboard & k2) << 16)
        bitboard = (bitboard >> 32) & k3 | (bitboard & k3) << 32

        return bitboard & 0xFFFFFFFFFFFFFFFF

    def active_positions(self, bitmap): #Chequear un método más rápido que retorne algo parecido
        candidates = []
        for col in self._cols_str:
            for row in range(1,8):
                mask = self.get_bitboard_position(f'{col}{row}')
                if mask & bitmap > 0:
                    candidates.append(f'{col}{row}')

        return candidates

    def print_hex(self, num:int) -> None:
        """
        Prints the number in hexadecimal format

        Parameters:
            num: an 64-bit integer
        """
        print(f"{num:#018x}".upper())

    def move(self, order: str, white_player_turn: bool) -> None:
        """
        Processes a move order in algebraic notation (e.g., "Nf6") and updates the board bitboards accordingly.

        The function:
        - Extracts the target square from the order.
        - Determines the piece type (defaulting to Pawn if no letter is present).
        - Finds candidate source squares for the piece that can reach the target square.
        - (Later) updates internal bitboards to remove the piece from its source and place it at the target.

        Note:
        - Board flipping is used for Black's turn so that move generation can be implemented from a "white perspective".
        - Debug code and candidate evaluation for move disambiguation are present and will be removed or refactored later.
        
        Parameters:
        order (str): The move in algebraic notation.
        white_player_turn (bool): True if it's White's turn; False otherwise.
        """

        
        target_pattern = r"[a-h][1-8]" #Pattern to extract the target square (e.g., "f6").
        piece_pattern = r"[KQBNRO]" #Pattern to extract the piece type letter. (Note: 'O' indicates castling.)
        whole_board = self.masks['white'] | self.masks['black'] # Bitboard for all pieces on the board.
        
        target_matches = re.findall(target_pattern, order) #Extract the target square from the order.
        assert len(target_matches ) >= 1, "Notation error: target square not found."
        if len(target_matches) == 0: #If no target square is found, it might be a castling move (not handled yet).
            pass
        target_square  = target_matches[0]

        piece_matches = re.findall(piece_pattern, order) # Extract the piece type from the order.
        if not piece_matches:
            pieces_key = 'P' #No piece letter found, so assume the move is by a pawn.
            #For pawn moves, define the starting rank mask.
            #For white, pawns start on rank 2. For Black, the board will be flipped later.
            first_row = 0x000000000000FF00  
        else:
            pieces_key = piece_matches[0] #For non-pawn moves, first_row is not used.

        player_key = 'white' if white_player_turn else 'black'
        
        pieces_value = self.masks[pieces_key] #Retrieve the bitboard for pieces of this type.
        player_value = self.masks[player_key] #Retrieve the bitboard for the current player's pieces.

        capture = 'x' in order #Determine if the move is a capture.

        target_bitmap = self.get_bitboard_position(target_square) #Get the bitboard corresponding to the target square.
        #FIXME A esta altura debe esar bien el filtrado de la orden, pero hay que revisar por los casos raros de desamgibüación
        
        if not white_player_turn: #Flip the board for Black's turn so that move logic can be written from a white perspective.
            pieces_value    = self.flip_vertical(pieces_value)
            player_value    = self.flip_vertical(player_value)
            target_bitmap   = self.flip_vertical(target_bitmap)
            #pieces_value    = self.flip_horizontal(pieces_value) TODO
            #player_value    = self.flip_horizontal(player_value)
            #target_bitmap   = self.flip_horizontal(target_bitmap)


        #TODO Más tarde implementar lógica de movimiento en funciones para cada pieza o esto va a crecer descontroladamente
        pieces = pieces_value & player_value #Limit the candidate pieces to those belonging to the current player.
        source_bitmap = 0 #This variable will hold the bitmask of the source square of the moving piece.

        #La lógica aplica llevando las piezas a la posición objetivo. Si hay calce, la pieza se selecciona haciendo el movimiento inverso desde la posición objetivo
        if pieces_key == 'K': #King move logic. Evaluate all king moves (one square in any direction).
            #TODO agregar enroque corto
            #TODO agregar enroque largo
            #TODO chequar que no esté el otro rey en el espacio a llegar o se tratará de un movimiento ilegal
            #BUG King teleport
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue # Skip no movement.
                    shift = dx + 8 * dy                
                    if shift > 0: #Handle positive and negative shifts separately.
                        if (pieces << shift) & target_bitmap: # Shift the candidate pieces to see if one can reach the target.
                            source_bitmap = target_bitmap >> shift
                    elif shift < 0:
                        if (pieces >> (-shift)) & target_bitmap:
                            source_bitmap = target_bitmap << (-shift)
        elif pieces_key == 'Q': #Queen move logic
            pass
        elif pieces_key == 'B': #Bishop move logic
            pass
        elif pieces_key == 'N': # Knight move logic
            #TODO Chequear desambigüación            
            #TODO iterar acá, e ir agregando los resultados a una lista, luego evaluar si hay más de una que sea no nula para desambigüar
            #BUG Not erasing original black knight
            #BUG Chequear Ng3, Nd4, Ng5 -> Se crean piezas que no existen
            knight_offsets = [17, 15, 10, 6, -17, -15, -10, -6]
            candidates = []
            for offset in knight_offsets:
                if offset > 0:
                    if (pieces << offset) & target_bitmap:
                        source_bitmap = target_bitmap >> offset
                        candidates.append(source_bitmap)
                elif offset < 0:
                    if (pieces >> (-offset)) & target_bitmap:
                        source_bitmap = target_bitmap << (-offset)
                        candidates.append(source_bitmap)

            if len(candidates) == 1:
                source_bitmap = candidates[0]
            elif len(candidates) >= 1: #TODO Desamgibüar Si hay más de un caballo que puede llegar a la casilla objetivo
                pass
            
        elif pieces_key == 'R': # Rook move logic
            pass
        else: #Lógica de movimiento para los peones. TODO #Chequear desambigüación. Además, evaluar si quitar el else pues si no obliga a mover peones incluso si la orden está mal dada
            #TODO agregar captura al paso
            #TODO agregar coronación
            #BUG Self capture e4, d3, d3 (captura desde c2 a e3)           
            #NOTE: For pawn moves, shifting left simulates moving forward (after board flip for Black).
            #Pawn advance and capture moves.
            #Note: For pawn moves, shifting left simulates moving forward (after board flip for Black).
            if ((pieces & first_row) << 16) & target_bitmap and not (whole_board & target_bitmap): #Double advance move (from starting rank) if target square is empty.
                source_bitmap = target_bitmap >> 16
            elif ((pieces & first_row) << 8) & target_bitmap and not (whole_board & target_bitmap): #Single advance move.
                source_bitmap = target_bitmap >> 8
            elif ((pieces & first_row) << 9) & target_bitmap and (whole_board & target_bitmap): #Capture move to the left.
                source_bitmap = target_bitmap >> 9
            elif ((pieces & first_row) << 7) & target_bitmap and (whole_board & target_bitmap): # Capture move to the right.
                source_bitmap = target_bitmap >> 7
            else:
                source_bitmap = 0  # No matching pawn move found.

        #BUG carga un source_bitmap incluso para posiciones inválidas por lo que si llego y aplico esto se cambia el tablero. Con posiciones inválidas source_bitmap debe ser cero     
        self.masks[pieces_key] = self.masks[pieces_key] ^ source_bitmap #Eliminate piece from initial position
        self.masks[player_key] = self.masks[player_key] ^ source_bitmap #Eliminate piece from initial position
        self.masks[pieces_key] = self.masks[pieces_key] ^ target_bitmap #Add piece to objective position
        self.masks[player_key] = self.masks[player_key] ^ target_bitmap #Add piece to objective position

    """
            #pdb.set_trace()
            print(self.visualize(pieces))
            print(self.visualize(player))
            print(self.visualize(first_row))
            print(self.visualize(target_bitmap))
            pass        
                
        
        #Falta responder la pregunta, ¿cuál es la pieza que puede llegar a target_bitmap?
        candidates = self.active_positions(target_bitmap)
        real_options = []
        for candidate in candidates:
            
            source_bitmap = self.get_bitboard_position('e2')
    """
    

"""
Sugerencias
Suggestions & Observations
Assertion Bug:
The second assertion uses assert len(target) >= 1 when checking for a piece. It should be removed or adjusted since if no piece letter is found, you default to a Pawn.

Negative Shifts:
Shifting by a negative number isn’t allowed. In your King (and Knight) move logic, you now separate the cases for positive and negative shifts. Consider abstracting this pattern into a helper function.

Knight Move Logic:
Instead of writing eight similar if statements, define a list of knight offsets (as shown) and loop through them. This not only reduces code repetition but also makes it easier to maintain.

Pawn Movement Conditions:
For pawn captures, note that testing whole_board & target_bitmap == 1 is not reliable since target_bitmap is a bit mask (not necessarily equal to 1). I changed these conditions to simply check if the target is occupied (non-zero).

Board Flipping and Pawn Start Row:
When flipping the board for Black’s turn, update the pawn starting mask (first_row) so that your move generation logic works uniformly for both sides.

Disambiguation and Candidate Moves:
The current logic for candidate evaluation (i.e. self.active_positions(target_bitmap) and the loop afterward) is a placeholder. In the future, consider collecting all candidate source squares and then applying disambiguation logic if more than one candidate is found.

Modularization:
As noted in the comments, you might want to refactor the move generation for each piece into its own function. This will help keep the move function manageable.

Operator Precedence:
Be mindful of operator precedence when using shifts with arithmetic (e.g., pieces << (i + 8*j)). Using explicit parentheses (as done above) helps avoid ambiguity.

"""



"""
from neuralcheck.logic import *
from neuralcheck.utils.class_explorer import Explorer
explorer = Explorer()
board = ChessBoard()
import yaml
with open('test/games.yaml') as file:
 games = yaml.safe_load(file)

board.bitboard.move(games['game1'][0][0], True)

"""