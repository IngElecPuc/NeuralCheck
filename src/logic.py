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
        """
        Inicializa una serie de listas, arrays y diccionarios para no calcularlos después
        """
        self._cols_str = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        self._cols2int = {col:num for num, col in enumerate(self._cols_str)}
        self._int2cols = {num:col for num, col in enumerate(self._cols_str)}
        self._pieces = ['pawn', 'knight', 'bishop', 'rook', 'queen', 'king']
        self.name2num = {name:(num+1) for num, name in enumerate(self._pieces)}
        self.num2name = {(num+1):name for num, name in enumerate(self._pieces)}
        self.name2num['Empty square'] = 0
        self.num2name[0] = 'Empty square'

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
        queen_movement_matrix   = np.concatenate((rook_movement_matrix, rook_movement_matrix))
        knight_movement_matrix  = np.array([[2,1], [1,2], [-1,2], [-2,1], [-2,-1], [-1,-2], [1,-2], [2,-1]])
        king_movement_matrix   = np.column_stack((-king_movement_matrix[:, 1], king_movement_matrix[:, 0])) #Convirtiendo de lógica cartesiana a notación numpy: fila = (n - 1) - y; columna = x
        queen_movement_matrix  = np.column_stack((-queen_movement_matrix[:, 1], queen_movement_matrix[:, 0]))
        bishop_movement_matrix = np.column_stack((-bishop_movement_matrix[:, 1], bishop_movement_matrix[:, 0]))
        knight_movement_matrix = np.column_stack((-knight_movement_matrix[:, 1], knight_movement_matrix[:, 0]))
        rook_movement_matrix   = np.column_stack((-rook_movement_matrix[:, 1], rook_movement_matrix[:, 0]))
        wpawn_movement_matrix  = np.column_stack((-wpawn_movement_matrix[:, 1], wpawn_movement_matrix[:, 0]))
        bpawn_movement_matrix  = np.column_stack((-bpawn_movement_matrix[:, 1], bpawn_movement_matrix[:, 0]))
        self.movemnts_matrices = {
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

    def _initialize_pieces(self):
        """

        """
        row = [0]*8
        board = [row]*8
        self.board = np.array(board, dtype=np.int64)

        self.put('white', 'king', 'E1')
        self.put('white', 'queen', 'D1')
        self.put('white', 'bishop', 'F1')
        self.put('white', 'bishop', 'C1')
        self.put('white', 'knight', 'G1')
        self.put('white', 'knight', 'B1')
        self.put('white', 'rook', 'H1')
        self.put('white', 'rook', 'A1')
        self.put('black', 'king', 'E8')
        self.put('black', 'queen', 'D8')
        self.put('black', 'bishop', 'F8')
        self.put('black', 'bishop', 'C8')
        self.put('black', 'knight', 'G8')
        self.put('black', 'knight', 'B8')
        self.put('black', 'rook', 'H8')
        self.put('black', 'rook', 'A8')
        
        for i, col in enumerate(self._cols_str):
            self.put('white', 'pawn', f'{col}2')
            self.put('black', 'pawn', f'{col}7')
    
    def logic2array(self, position): #Convertir esto después a Numpy arrays
        col, row = position[0], int(position[1])
        x = 8 - row
        y = self._cols2int[col]
        return x, y
    
    def array2logic(self, x, y): #Convertir esto después a Numpy arrays
        col = self._int2cols[y]
        row = x - 8        
        return f'{col}{row}'

    def put(self, color, piece, position):
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
        x, y = self.logic2array(position) #Ojo con la notación cuando esto se convierta a numpy arrays
        self.board[x, y] = self.name2num[piece] * (1 if color == 'white' else -1)

    def what_in(self, position):
        x, y = self.logic2array(position) #Ojo con la notación cuando esto se convierta a numpy arrays
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

    def allowed_movements(self, piece, position):
        """
        Retorna una lista con los movimientos legales que tiene la pieza. 
        """
        
        x, y    = self.logic2array(position) #Ojo con la notación cuando esto se convierta a numpy arrays
        pos     = np.array([x, y])
        movs    = pos + self.movemnts_matrices[piece]
        mask    = np.all((movs >= 0) & (movs <= 7), axis=1) #Se eliminan movimientos que acaben fuera del tablero
        #Falta chequear si los movimientos terminan sobre una pieza y qué tipo de pieza es
        #Falta chequear los movimientos de proyección en línea: reina, alfil, torre

        return movs[mask]

if __name__ == '__main__':
    board = ChessBoard()

    """
    Versiones futuras de los métodos de conversión de coordenadas con soporte para múltiples instancias

    def logic2array(self, *args): 
        
        Este método puede funcionar de dos formas:
        1. Recibiendo dos argumentos (col, row) en notación ajedrecística.
        2. Recibiendo un único argumento que sea un np.array de forma (n, 2)
           o, en el caso de un único vector (2,) se interpretará como una coordenada.
        
        if len(args) == 1 and isinstance(args[0], np.ndarray):
            arr = args[0]
            if arr.ndim == 2:
                assert arr.shape[1] == 2, "El array debe tener dimensión (n,2)"
                out = [[]]*arr.shape[0]
                for i, (col, row) in enumerate(arr):
                    col = str(col)
                    try:
                        row = int(row)
                    except Exception as e:
                        raise ValueError(f"El valor de row '{row}' no se puede convertir a entero.") from e
                    out[i] = [8 - row, self._cols2int[col]]
                return np.array(out)
            elif arr.ndim == 1:
                assert arr.shape[0] == 2, "El array debe tener dos elementos (col, row)"
                col, row = arr
                return 8 - row, self._cols2int[col]
            else:
                raise ValueError("Dimensión del array no soportada.")
        
        elif len(args) == 2:
            col, row = args
            return 8 - row, self._cols2int[col]
        
        else:
            raise ValueError("Número incorrecto de argumentos. Utilice (col, row) o un array de dimensión (n,2).")    
        
    def array2logic(self, *args):
        
        Este método permite dos formas de uso:
        1. Recibiendo dos argumentos (x, y) que representan la posición en un array.
        2. Recibiendo un único argumento que sea un np.array de forma (n,2) o (2,)
           y convirtiéndolo a notación lógica de ajedrez.
        
        La conversión se realiza de la siguiente manera:
          - col: se obtiene a partir de self._int2cols usando el valor y.
          - row: se calcula como x - 8.
        
        if len(args) == 1 and isinstance(args[0], np.ndarray):
            arr = args[0]
            if arr.ndim == 2:
                assert arr.shape[1] == 2, "El array debe tener forma (n,2)"
                out = [[]]*arr.shape[0]
                for i, (x, y) in enumerate(arr):
                    out[i] = [self._int2cols[y], x - 8]
                return np.array(out)
            elif arr.ndim == 1:
                assert arr.shape[0] == 2, "El array debe tener dos elementos (x, y)"
                x, y = arr
                col = self._int2cols[y]
                row = x - 8
                return col, row
            else:
                raise ValueError("Dimensión del array no soportada.")
        
        elif len(args) == 2:
            x, y = args
            col = self._int2cols[y]
            row = x - 8
            return col, row
        
        else:
            raise ValueError("Número incorrecto de argumentos. Use (x, y) o un array de dimensión (n,2).")
    """    