import tkinter as tk
import yaml
from PIL import Image, ImageTk
from logic import ChessBoard
import pdb

class ChessUI:
    def __init__(self, master, rotation):
        with open('config/board.yaml', 'r') as file: 
            self.config = yaml.safe_load(file)
        self.cell_size  = self.config['Size']

        self.master     = master
        self.rotation   = rotation #False if White's view, True for Black's view
        self.board      = ChessBoard()
        self.canvas     = tk.Canvas(master, 
                                    width=self.cell_size * 8, 
                                    height=self.cell_size * 8)
        self.canvas.pack()
        self.pieces     = self._load_pieces()
        self.cols_str = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'] 
        if self.rotation: 
            self.cols_str = self.cols_str[::-1]        
        self.draw_board()
        self.canvas.bind("<Button-1>", self.on_click)
        self.selected   = None #To store selected box

    def draw_board(self):
        """
        Draw a 8x8 board with alternating colors
        """
        colors = ["white", "gray"]
        for row in range(8):
            for col in range(8):
                color   = colors[(row + col) % 2]
                x1      = col * self.cell_size
                y1      = row * self.cell_size
                x2      = x1 + self.cell_size
                y2      = y1 + self.cell_size
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color)

        #Dibujar las piezas
        for piece_name in self.board.pieces.keys():
            piece       = self.board.pieces[piece_name]
            col, row    = self._translate_position_logic2px(piece.col, piece.row)
            color       = 'white' if 'white' in piece_name else 'black'
            key         = f'{color} {piece.type}'
            self.canvas.create_image(col, row, image=self.pieces[key], anchor='nw')

    def _translate_position_logic2px(self, logic_col, logic_row):
        cols_int = {col:num for num, col in enumerate(self.cols_str)}
        
        col = cols_int[logic_col] * self.cell_size

        if self.rotation:
            row = (logic_row - 1) * self.cell_size
        else:
            row = (8 - logic_row) * self.cell_size
        
        return col, row
    
    def _translate_position_px2logic(self, col, row):
        cols_str = {num:col for num, col in enumerate(self.cols_str)}
        
        col = col // self.cell_size
        row = row // self.cell_size
        
        logic_col = cols_str[col]
        if self.rotation:
            logic_row = row + 1
        else:
            logic_row = 8 - row

        return logic_col, logic_row

    def _load_pieces(self):
        def load_and_format(path):
            image = Image.open(path).convert("RGBA")
            image = image.resize((self.cell_size, self.cell_size), Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(image)
        
        images = {}
        for side in self.config['Pieces paths'].keys():
            for piece in self.config['Pieces paths'][side].keys():
                key = f'{side} {piece}'
                images[key] = load_and_format(self.config['Pieces paths'][side][piece])

        return images

    def on_click(self, event):
        # Determina la casilla clickeada y maneja la selección/movimiento
        col = event.x // self.cell_size
        row = event.y // self.cell_size
        pos = (row, col)
        logic_col, logic_row = self._translate_position_px2logic(event.x, event.y)
        if self.selected is None:
            # Selecciona la pieza a mover
            self.selected = pos
            print(logic_col, logic_row)
        else:
            # Intenta mover la pieza desde self.selected hasta pos
            #moved = self.chess_board.move_piece(self.selected, pos)
            #if moved:
            #    print("Movimiento realizado de", self.selected, "a", pos)
                # Redibuja el tablero para reflejar el nuevo estado
            #    self.canvas.delete("all")
            #    self.draw_board()
            #else:
            #    print("Movimiento inválido")
            self.selected = None

if __name__ == "__main__":
    root = tk.Tk()
    app = ChessUI(root, True)
    root.mainloop()            