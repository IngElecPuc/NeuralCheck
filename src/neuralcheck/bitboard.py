import numpy as np
import bitboardops as bb
import re
import pdb

class ChessPiece:
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

    def _initialize_pieces(self, board):
        """
        Infiere las máscaras bitboard de las piezas según la matriz de tablero board
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
            flatboard = board.reshape(-1)[::-1] #Se aplana y se invierte para iterar desde el bit menos significativo al más
            for piece in range(-6, 7): #Representación numérica de piezas de ChessBoard
                if piece == 0: #El cero es espacio vacío
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
    
    def visualize(self, num):
        bitnum = f'{num:064b}'
        for i in range(8):
            print(bitnum[8*i:8*(i+1)])

    def get_bitboard_position(self, position):
        col, row = position[0], position[1]
        col = self._cols2int[col]
        row = int(row) - 1
        return 1 << col + row * 8

    def flip_vertical(self, bitboard):
        """
        Gira el tablero para verlo como si fuera el turno de negro
        """
        k1 = 0x00FF00FF00FF00FF
        k2 = 0x0000FFFF0000FFFF
        bitboard = ((bitboard >> 8) & k1) | ((bitboard & k1) << 8)
        bitboard = ((bitboard >> 16) & k2) | ((bitboard & k2) << 16)
        bitboard = (bitboard >> 32) | (bitboard << 32)
        return bitboard & 0xFFFFFFFFFFFFFFFF

    def active_positions(self, bitmap): #Chequear un método más rápido que retorne algo parecido
        candidates = []
        for col in self._cols_str:
            for row in range(1,8):
                mask = self.get_bitboard_position(f'{col}{row}')
                if mask & bitmap > 0:
                    candidates.append(f'{col}{row}')

        return candidates

    def print_hex(self, num):
        print(f"{num:#018x}".upper())

    def reverse_move(self, ptype:str, source:str, target:str): 
        """
        Responde a la pregunta, qué pieza se pudo mover a target desde source, ptype indica el tipo de pieza y por lo tanto la forma de moverse
        """
        pass

    def move(self, order: str, white_player_turn:bool):
        
        target_pattern = r"[a-h][1-8]"
        piece_pattern = R"[KQBNRO]" #Con O encuentra un enroque
        whole_board = self.white | self.black
        
        target = re.findall(target_pattern, order)
        assert len(target) >= 1, "Error de notación, destino no encontrado"
        if len(target) == 0: #¿Enroque?
            pass
        target = target[0]

        ptype = re.findall(piece_pattern, order)
        assert len(target) >= 1, "Error de notación, pieza de inicio no encontrada"
        if len(ptype) == 0: #Se asume peones
            ptype = 'P'
            firstrow = 0X000000000000FF00 if white_player_turn else 0X00FF000000000000 #Máscara de los peones en primera fila
        else:
            ptype = ptype[0]
            
        pieces = self.masks[ptype]
        
        player = self.masks['white'] if white_player_turn else self.masks['black']

        capture = 'x' in order

        target_bitmap = self.get_bitboard_position(target) #A esta altura debe esar bien filtrado de la orden, pero hay que revisar por los casos raros de desamgibüación
        
        if not white_player_turn: #Se gira el tablero para evitar hacer dos sets de revisiones: uno por cada jugador
            pieces          = self.flip_vertical(pieces)
            player          = self.flip_vertical(player)
            target_bitmap   = self.flip_vertical(target_bitmap)
        
        """
        Más tarde implementar lógica de movimiento en funciones para cada pieza o esto va a crecer descontroladamente
        """
        pieces = pieces & player #Ojo con esto, revisar si está bien más adelante
        source_bitmap = 0

        #La lógica aplica llevando las piezas a la posición objetivo. Si hay calce, la pieza se selecciona haciendo el movimiento inverso desde la posición objetivo
        if ptype == 'K': #Lógica de movimiento para el rey
            #TODO agregar enroque corto
            #TODO agregar enroque largo
            #TODO chequar que no esté el otro rey en el espacio
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