import pdb
import numpy as np

class ChessBoard:
    def __init__(self):
        #Inicialmente el tablero tiene una representación en matriz de 8x8
        #Esta representación no es óptima para la búsqueda con la lógica -> más adelante se utilizará BitMap
        #Por ahora esta representación servirá a la UI para dibujar el tablero
        
        self._initialize_resources()
        self._initialize_pieces()
        self.board_colors = np.zeros((8,8), dtype=np.int64)
        for row in range(8):
            for col in range(8):
                self.board_colors[row, col] = (col + row) % 2

    def _initialize_resources(self):
        self._cols_str = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        self._cols2int = {col:num for num, col in enumerate(self._cols_str)}
        self._int2cols = {num:col for num, col in enumerate(self._cols_str)}
        self._pieces = ['pawn', 'knight', 'bishop', 'rook', 'queen', 'king']
        self.name2num = {name:(num+1) for num, name in enumerate(self._pieces)}
        self.num2name = {(num+1):name for num, name in enumerate(self._pieces)}
        self.name2num['Empty square'] = 0
        self.num2name[0] = 'Empty square'

    def _initialize_pieces(self):
        """

        """
        row = [0]*8
        board = [row]*8
        self.board = np.array(board, dtype=np.int64)

        self.put('white', 'king', 'E', 1)
        self.put('white', 'queen', 'D', 1)
        self.put('white', 'bishop', 'F', 1)
        self.put('white', 'bishop', 'C', 1)
        self.put('white', 'knight', 'G', 1)
        self.put('white', 'knight', 'B', 1)
        self.put('white', 'rook', 'H', 1)
        self.put('white', 'rook', 'A', 1)
        self.put('black', 'king', 'E', 8)
        self.put('black', 'queen', 'D', 8)
        self.put('black', 'bishop', 'F', 8)
        self.put('black', 'bishop', 'C', 8)
        self.put('black', 'knight', 'G', 8)
        self.put('black', 'knight', 'B', 8)
        self.put('black', 'rook', 'H', 8)
        self.put('black', 'rook', 'A', 8)
        
        for i, col in enumerate(self._cols_str):
            self.put('white', 'pawn', col, 2)
            self.put('black', 'pawn', col, 7)
    
    def logic2array(self, col, row):
        x = 8 - row
        y = self._cols2int[col]
        return x, y
    
    def array2logic(self, x, y):
        col = self._int2cols[y]
        row = x - 8        
        return col, row

    def put(self, color, piece, col, row):
        """
        Pone piezas en el tablero utilizando coordenadas del juego
            Piece map:
            white -> positive
            black -> negative
            pawn -> 1
            knight -> 2
            bishop -> 3
            rook -> 4
            queen -> 5
            king -> 6
        """
        x, y = self.logic2array(col, row)
        self.board[x, y] = self.name2num[piece] * (1 if color == 'white' else -1)

    def what_in(self, col, row):
        x, y = self.logic2array(col, row)
        piece = self.board[x, y]
        color = 'white' if piece > 0 else 'black'
        name = self.num2name[np.abs(piece)]
        if name == 'Empty square': 
            color = 'white' if (x + y) % 2 == 0 else 'black'
            return f'Empty {color} square'
        else:
            return f'{color} {name}'

    def is_white_square(self, col, row):
        cols_str = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        cols_int = {col:num for num, col in enumerate(cols_str)}

        pass

    def print(self):
        print(np.array(board))

    def allowed_movements(self, piece, col, row):
        """
        Retorna una lista con los movimientos legales que tiene la pieza. 
        """

        if piece == 'king':
            pass
        if piece == 'queen':
            pass
        if piece == 'bishop':
            pass
        if piece == 'knight':
            pass
        if piece == 'rook':
            pass
        if piece == 'pawn':
            pass

if __name__ == '__main__':
    board = ChessBoard()