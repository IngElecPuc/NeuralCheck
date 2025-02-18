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
    
    def visualize(self, num:int) -> None:
        """
        Displays an 8x8 ordered bit-like matrix that represents a 64-bit integer in binary.
        The representation goes from left to right and top to bottom, following the most 
        significant bit to the least.

        Parameters:
            num: A 64-bit integer representing a map or mask of the board.
        """
        bitnum = f'{num:064b}'
        for i in range(8):
            print(bitnum[8*i:8*(i+1)])

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

    def flip_vertical(self, bitboard: int) -> int:
        """
        Flips the bitboard vertically, transforming the board as if viewed from Black's perspective.

        This operation mirrors the board along the horizontal axis, swapping ranks 
        (e.g., the first rank becomes the eighth, the second becomes the seventh, etc.).
        
        Parameters:
            bitboard: A 64-bit integer representing the board's bitboard.

        Returns:
            A 64-bit integer representing the vertically flipped bitboard.
        """
        
        k1 = 0x00FF00FF00FF00FF #k1 mask: selects every other byte (0x00FF00FF00FF00FF) to prepare for swapping adjacent bytes.
        k2 = 0x0000FFFF0000FFFF #k2 mask: selects every other 16-bit word (0x0000FFFF0000FFFF) to prepare for swapping 16-bit groups.

        # Step 1: Swap adjacent bytes.
        # - (bitboard >> 8) shifts the board right by one byte; "& k1" selects bytes originally in odd positions.
        # - (bitboard & k1) selects bytes originally in even positions; "<< 8" shifts them left by one byte.
        # The OR operation combines these two parts, effectively swapping each pair of adjacent bytes.
        bitboard = ((bitboard >> 8) & k1) | ((bitboard & k1) << 8)

        # Step 2: Swap adjacent 16-bit words.
        # - (bitboard >> 16) shifts the board right by 16 bits; "& k2" selects the lower 16 bits of each 32-bit block.
        # - (bitboard & k2) selects the lower 16 bits of each 32-bit block; "<< 16" shifts them left by 16 bits.
        # This swaps the two-byte groups within each 32-bit half of the board.
        bitboard = ((bitboard >> 16) & k2) | ((bitboard & k2) << 16)

        # Step 3: Swap the 32-bit halves.
        # - (bitboard >> 32) moves the upper 32 bits to the lower 32-bit half.
        # - (bitboard << 32) moves the lower 32 bits to the upper 32-bit half.
        # The OR operation completes the reversal of all 8 bytes.
        bitboard = (bitboard >> 32) | (bitboard << 32)

        # Return the final 64-bit result, ensuring no overflow beyond 64 bits.
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
        whole_board = self.white | self.black # Bitboard for all pieces on the board.
        
        target_matches = re.findall(target_pattern, order) #Extract the target square from the order.
        assert len(target_matches ) >= 1, "Notation error: target square not found."
        if len(target_matches) == 0: #If no target square is found, it might be a castling move (not handled yet).
            pass
        target_square  = target_matches[0]

        piece_matches = re.findall(piece_pattern, order) # Extract the piece type from the order.
        if not piece_matches:
            ptype = 'P' #No piece letter found, so assume the move is by a pawn.
            #For pawn moves, define the starting rank mask.
            #For white, pawns start on rank 2. For Black, the board will be flipped later.
            first_row = 0x000000000000FF00  
        else:
            ptype = piece_matches[0] #For non-pawn moves, first_row is not used.
            
            
        pieces = self.masks[ptype] #Retrieve the bitboard for pieces of this type.
        player = self.masks['white'] if white_player_turn else self.masks['black'] #Retrieve the bitboard for the current player's pieces.

        capture = 'x' in order #Determine if the move is a capture.

        target_bitmap = self.get_bitboard_position(target_square) #Get the bitboard corresponding to the target square.
        #FIXME A esta altura debe esar bien el filtrado de la orden, pero hay que revisar por los casos raros de desamgibüación
        
        if not white_player_turn: #Flip the board for Black's turn so that move logic can be written from a white perspective.
            pieces          = self.flip_vertical(pieces)
            player          = self.flip_vertical(player)
            target_bitmap   = self.flip_vertical(target_bitmap)

        #TODO Más tarde implementar lógica de movimiento en funciones para cada pieza o esto va a crecer descontroladamente
        pieces = pieces & player #Limit the candidate pieces to those belonging to the current player.
        source_bitmap = 0 #This variable will hold the bitmask of the source square of the moving piece.

        #La lógica aplica llevando las piezas a la posición objetivo. Si hay calce, la pieza se selecciona haciendo el movimiento inverso desde la posición objetivo
        if ptype == 'K': #Lógica de movimiento para el rey
            #TODO agregar enroque corto
            #TODO agregar enroque largo
            #TODO chequar que no esté el otro rey en el espacio a llegar o se tratará de un movimiento ilegal
            for i in range(-1,2):
                for j in range(-1,2):
                    if i == 0 and j == 0:
                        continue
                    if (pieces << i + 8*j) & target_bitmap > 0: 
                        source_bitmap = target_bitmap >> i + 8*j
            pass
        elif ptype == 'Q': #Lógica de movimiento para la reina
            pass
        elif ptype == 'B': #Lógica de movimiento para los alfiles
            pass
        elif ptype == 'N': #Lógica de movimiento para los caballos. TODO #Chequear desambigüación            
            #TODO iterar acá, e ir agregando los resultados a una lista, luego evaluar si hay más de una que sea no nula para desambigüar
            if (pieces << 8 - 2) & target_bitmap > 0: 
                source_bitmap = target_bitmap >> 8 - 2
            if (pieces << 16 - 1) & target_bitmap > 0: 
                source_bitmap = target_bitmap >> 16 - 1
            if (pieces << 16 + 1) & target_bitmap > 0: 
                source_bitmap = target_bitmap >> 16 + 1
            if (pieces << 8 - 2) & target_bitmap > 0: 
                source_bitmap = target_bitmap >> 8 + 2
            if (pieces >> 8 - 2) & target_bitmap > 0: 
                source_bitmap = target_bitmap << 8 - 2
            if (pieces >> 16 - 1) & target_bitmap > 0: 
                source_bitmap = target_bitmap << 16 - 1
            if (pieces >> 16 + 1) & target_bitmap > 0: 
                source_bitmap = target_bitmap << 16 + 1
            if (pieces >> 8 - 2) & target_bitmap > 0: 
                source_bitmap = target_bitmap << 8 + 2
        elif ptype == 'R': #Lógica de movimiento para las torres
            pass
        else: #Lógica de movimiento para los peones. TODO #Chequear desambigüación
            #TODO agregar captura al paso
            #TODO agregar coronación
            if ((pieces & firstrow) << 16) & target_bitmap > 0 and whole_board & target_bitmap == 0: #Si hay peones en la primera fila que alcanzan la posición con un avance doble (y no hay piezas en la posición objetivo)
                source_bitmap = target_bitmap >> 16 #Me devuelvo y encuentro el peón que generó el avance
            elif ((pieces & firstrow) << 8) & target_bitmap > 0 and whole_board & target_bitmap == 0: #Si hay peones alcanzan la posición con un avance normal (y no hay piezas en la posición objetivo)
                source_bitmap = target_bitmap >> 8
            elif ((pieces & firstrow) << 9) & target_bitmap > 0 and whole_board & target_bitmap == 1: #Si hay peones alcanzan la posición comiendo a la izquierda (y hay piezas en la posición objetivo -> posible captura)
                source_bitmap = target_bitmap >> 9
            elif ((pieces & firstrow) << 7) & target_bitmap > 0 and whole_board & target_bitmap == 1: #Si hay peones alcanzan la posición comiendo a la derecha (y hay piezas en la posición objetivo -> posible captura)
                source_bitmap = target_bitmap >> 7 
            else:
                source_bitmap = 0 #No se encontró ningún peón que cumpla
            #    if 
            
            #pdb.set_trace()
            print(self.visualize(pieces))
            print(self.visualize(player))
            print(self.visualize(firstrow))
            print(self.visualize(target_bitmap))
            pass        
                
        
        #Falta responder la pregunta, ¿cuál es la pieza que puede llegar a target_bitmap?
        candidates = self.active_positions(target_bitmap)
        real_options = []
        for candidate in candidates:
            
            source_bitmap = self.get_bitboard_position('e2')



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