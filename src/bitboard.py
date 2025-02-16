import numpy as np

class ChessPiece:
    def __init__(self, ptype: str, position: str, whiteplayer: bool):
        self.ptype = ptype
        self.position = position
        self.whiteplayer = whiteplayer

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


class ChessBitboard:
    def __init__(self, board):
        self.board = board
        self.kings = 576460752303423496
        self.queens = 1152921504606846992
        self.bishops = 2594073385365405732
        self.knights = 4755801206503243842
        self.rooks = 9295429630892703873
        self.pawns = 71776119061282560
        self.white = 65535
        self.black = 18446462598732840960
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

        self._cols_str  = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        self._cols2int  = {col:num for num, col in enumerate(self._cols_str[::-1])}
        self._int2cols  = {num:col for num, col in enumerate(self._cols_str[::-1])}
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

    def visualize(self, num):
        bitnum = f'{num:064b}'
        for i in range(8):
            print(bitnum[8*i:8*(i+1)])

    def get_bitboard_position(self, position):
        col, row = position[0], position[1]
        col = self._cols2int[col]
        row = int(row) - 1
        return 1 << col << row * 8

    #def check_piece_type(self, bitmap: int):
    #    if bitmap & self.kings > 0:

    def move(self, source: str, target: str):
        source_bitmap = self.get_bitboard_position(source)
        target_bitmap = self.get_bitboard_position(target)

        if source_bitmap & self.kings > 0:
            pass
        elif source_bitmap & self.queens > 0:
            pass
        elif source_bitmap & self.bishops > 0:
            pass
        elif source_bitmap & self.knights > 0:
            pass
        elif source_bitmap & self.rooks > 0:
            pass
        elif source_bitmap & self.pawns > 0:
            
            pass
        else:
            return None
