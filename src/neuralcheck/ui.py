import tkinter as tk
import yaml
from PIL import Image, ImageTk, ImageOps
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
        self.cols_str   = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H'] 
        if self.rotation: 
            self.cols_str = self.cols_str[::-1]        
        self.selected   = None #To store selected box
        self.draw_board()
        self.canvas.bind("<Button-1>", self.on_click)

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
        for col in self.cols_str:
            for row in range(1, 9):
                position = f'{col}{row}'
                response = self.board.what_in(position)
                if 'Empty' in response:
                    continue                
                x, y = self._translate_position_logic2px(position)
                self.canvas.create_image(x, y, image=self.pieces[response], anchor='nw')

        if self.selected is not None:
            colors = ["black", "gray10"]
            position, piece = self.selected
            x1, y1          = self._translate_position_logic2px(position)
            x2              = x1 + self.cell_size
            y2              = y1 + self.cell_size
            col, row        = self.board.logic2array(position)
            color           = colors[(row + col) % 2]
            self.canvas.create_rectangle(x1, y1, x2, y2, fill=color)
            self.canvas.create_image(x1, y1, image=self.pieces[piece+' inverted'], anchor='nw')

    def _translate_position_logic2px(self, position):
        logic_col, logic_row = position[0], int(position[1])
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

        return f'{logic_col}{logic_row}'

    def _invert_image(self, image):
        if image.mode == "RGBA":
            r, g, b, a = image.split()
            rgb_image = Image.merge("RGB", (r, g, b))
            inverted_rgb = ImageOps.invert(rgb_image)
            r2, g2, b2 = inverted_rgb.split()
            return Image.merge("RGBA", (r2, g2, b2, a))
        else:
            return ImageOps.invert(image)

    def _load_pieces(self):
        def load_and_format(path):
            image = Image.open(path).convert("RGBA")
            image = image.resize((self.cell_size, self.cell_size), Image.Resampling.LANCZOS)
            return image
        
        images = {}
        for side in self.config['Pieces paths'].keys():
            for piece in self.config['Pieces paths'][side].keys():
                key = f'{side} {piece}'
                image = load_and_format(self.config['Pieces paths'][side][piece])
                images[key] = ImageTk.PhotoImage(image)
                key = f'{side} {piece} inverted'
                image = self._invert_image(image)
                images[key] = ImageTk.PhotoImage(image)

        return images

    def on_click(self, event):
        # Determina la casilla clickeada y maneja la selección/movimiento
        target_position = self._translate_position_px2logic(event.x, event.y)
        
        if self.selected is None:
            # Selecciona la pieza a mover
            piece = self.board.what_in(target_position)
            if not 'Empty' in piece:
                self.selected = (target_position, piece)
                self.canvas.delete("all")
                self.draw_board()
        else:
            piece_position, piece = self.selected
            self.selected = None
            if piece_position != target_position:
                moved = self.board.move(piece, piece_position, target_position)
                if moved:
                    self.canvas.delete("all")
                    self.draw_board() #Agregar nueva posición
                else:
                    print("Movimiento inválido")
            else: #Deseleccion
                self.canvas.delete("all")
                self.draw_board()                