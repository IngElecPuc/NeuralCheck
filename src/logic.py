import pdb

class ChessPiece:
    def __init__(self, ptype: str, col: str, row: int, white_player: bool):
        self.type = ptype
        self.col = col
        self.row = row
        self.white_player = white_player
        self.on_board = True #Capturada o en el tablero
    
    def allowed_movements(self):
        pass

class ChessBoard:
    def __init__(self):
        #Inicialmente el tablero tiene una representación en matriz de 8x8
        #Esta representación no es óptima para la búsqueda con la lógica -> más adelante se utilizará BitMap
        #Por ahora esta representación servirá a la UI para dibujar el tablero
        self.pieces = self._initialize_pieces()


    def _initialize_pieces(self):
        cols = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
        pieces = {}
        pieces['white king']    = ChessPiece('king', 'E', 1, True)
        pieces['white queen']   = ChessPiece('queen', 'D', 1, True)
        pieces['white bishop1'] = ChessPiece('bishop', 'F', 1, True)
        pieces['white bishop2'] = ChessPiece('bishop', 'C', 1, True)
        pieces['white knight1'] = ChessPiece('knight', 'G', 1, True)
        pieces['white knight2'] = ChessPiece('knight', 'B', 1, True)
        pieces['white rook1']   = ChessPiece('rook', 'H', 1, True)
        pieces['white rook2']   = ChessPiece('rook', 'A', 1, True)
        pieces['black king']    = ChessPiece('king', 'E', 8, False)
        pieces['black queen']   = ChessPiece('queen', 'D', 8, False)
        pieces['black bishop1'] = ChessPiece('bishop', 'F', 8, False)
        pieces['black bishop2'] = ChessPiece('bishop', 'C', 8, False)
        pieces['black knight1'] = ChessPiece('knight', 'G', 8, False)
        pieces['black knight2'] = ChessPiece('knight', 'B', 8, False)
        pieces['black rook1']   = ChessPiece('rook', 'H', 8, False)
        pieces['black rook2']   = ChessPiece('rook', 'A', 8, False)
        
        for i, col in enumerate(cols):
            pieces[f'white pawn{i+1}'] = ChessPiece('pawn', col, 2, True)
            pieces[f'black pawn{i+1}'] = ChessPiece('pawn', col, 7, False)

        return pieces