import tkinter as tk
import yaml
from PIL import Image, ImageTk, ImageOps
from neuralcheck.logic import ChessBoard
from typing import Tuple, Dict
import pdb

#TODO : Agregar información sobre a qué jugador corresponde el turno
#TODO : Agregar reloj
#TODO : Agregar piezas capturadas
#TODO : Agregar opción de girar el tablero
#TODO : Agregar historial de acciones jugadas, en qué turno y por cuál jugf

class ChessUI:
    def __init__(self, master, rotation):
        with open('config/board.yaml', 'r') as file: 
            self.config = yaml.safe_load(file)
        self.cell_size  = self.config['Size']['square']

        self.master     = master
        self.rotation   = rotation #False if White's view, True for Black's view
        self.logicboard = ChessBoard()

        master.geometry(f"{self.config['Size']['width']}x{self.config['Size']['height']}")
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)
        
        self.main_frame = tk.Frame(master) #Principal frame for the board
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        
        #Off board for drawing captured pieces and clock
        self.offboard   = tk.Canvas(self.main_frame, 
                                    width=self.cell_size * 3,
                                    height=self.cell_size * 8)
        self.offboard.grid(row=0, column=0)
        
        #Chess grafic board
        self.board      = tk.Canvas(self.main_frame, 
                                    width=self.cell_size * 8, 
                                    height=self.cell_size * 8)
        self.board.grid(row=0, column=1) 
        
        #Text Widget for history plays
        self.history_text = tk.Text(self.main_frame, width=20, height=20, wrap=tk.WORD)
        self.history_text.grid(row=0, column=2, sticky="ns", padx=10)
        self.history_scrollbar = tk.Scrollbar(self.main_frame, command=self.history_text.yview)
        self.history_scrollbar.grid(row=0, column=3, sticky="ns")
        self.history_text.config(yscrollcommand=self.history_scrollbar.set)
        
        self.pieces     = self._load_pieces()
        self.cols_str   = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        if self.rotation: 
            self.cols_str = self.cols_str[::-1]        
        self.selected   = None #To store selected box
        self.draw_board()
        self.board.bind("<Button-1>", self.on_click)

        #HACK Esta es una característica que me ayudará a debuguear las órdenes de movimiento, después borrar
        self.entry = tk.Entry(master, width=40)
        self.entry.grid(row=1, column=0, columnspan=2, pady=10)
        self.label = tk.Label(master, text="Texto enviado: ", font=("Arial", 12))
        self.label.grid(row=2, column=0, columnspan=2, pady=10)
        self.entry.bind("<Return>", self.send_text)

    def send_text(self, event): #HACK Borrar en el futuro
            texto = self.entry.get().strip()  # Evitar entradas vacías
            if texto:
                self.logicboard.bitboard.move(texto, self.logicboard.white_turn)
                self.label.config(text=f"Texto enviado: {texto}")
                self.entry.delete(0, tk.END)  # Limpiar la barra de entrada

    def add_move(self, move: str) -> None:
        """
        Adds a move to the history displayed in the text widget.

        Parameters: 
            move: the move text to add
        """
        
        self.history_text.delete("1.0", tk.END) #Delete and redraw all
        for turn, moves in enumerate(self.logicboard.history):
            if len(moves) == 1:
                white_move = moves[0]
                black_move = ""
            else:
                white_move, black_move = moves
            self.history_text.insert(tk.END, f"{turn+1}\t{white_move}\t{black_move}\n")
        self.history_text.see(tk.END)

    def draw_board(self) -> None:
        """
        Draw a 8x8 board with alternating colors
        """
        #Draw the board
        colors = ["white", "gray"]
        for row in range(8):
            for col in range(8):
                color   = colors[(row + col) % 2]
                x1      = col * self.cell_size
                y1      = row * self.cell_size
                x2      = x1 + self.cell_size
                y2      = y1 + self.cell_size
                self.board.create_rectangle(x1, y1, x2, y2, fill=color)

        #Draw the pieces
        for col in self.cols_str:
            for row in range(1, 9):
                position = f'{col}{row}'
                response = self.logicboard.what_in(position)
                if 'Empty' in response:
                    continue                
                x, y = self._translate_position_logic2px(position)
                self.board.create_image(x, y, image=self.pieces[response], anchor='nw')

        #If a piece is selected draw it with inverted colors
        if self.selected is not None:
            colors = ["black", "gray10"]
            position, piece = self.selected
            x1, y1          = self._translate_position_logic2px(position)
            x2              = x1 + self.cell_size
            y2              = y1 + self.cell_size
            col, row        = self.logicboard.logic2array(position)
            color           = colors[(row + col) % 2]
            self.board.create_rectangle(x1, y1, x2, y2, fill=color)
            self.board.create_image(x1, y1, image=self.pieces[piece+' inverted'], anchor='nw')

    def _translate_position_logic2px(self, position:str) -> Tuple[int, int]:
        """
        Transforms a chess position to a pixel position for drawing

        Parameters:
            position: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'

        Returns:
            Tuple(int, int): two ints representing the position in pixel coordinates
        """
        logic_col, logic_row = position[0], int(position[1])
        cols_int = {col:num for num, col in enumerate(self.cols_str)}
        
        col = cols_int[logic_col] * self.cell_size

        if self.rotation:
            row = (logic_row - 1) * self.cell_size
        else:
            row = (8 - logic_row) * self.cell_size
        
        return col, row
    
    def _translate_position_px2logic(self, col:int, row:int) -> str:
        """
        Transforms a couple of pixel coordinates to a chess position

        Parameters:
            col: the x coordinates
            row: the y coordinates

        Returns:
            str: a string of size 2 with a character from a to h and a number from 1 to 8, e.g., 'e4'
        """
        cols_str = {num:col for num, col in enumerate(self.cols_str)}
        
        col = col // self.cell_size
        row = row // self.cell_size
        
        logic_col = cols_str[col]

        if self.rotation:
            logic_row = row + 1
        else:
            logic_row = 8 - row

        return f'{logic_col}{logic_row}'

    def _invert_image(self, image: Image.Image) -> Image.Image:
        """
        Invert colors to augment contrast
        
        Parameters:
            image: a PIL image

        Returns:
            Image.Image: the inverted image
        """
        if image.mode == "RGBA": #This is important so check if the image is loaded with this mode previously
            r, g, b, a = image.split()
            rgb_image = Image.merge("RGB", (r, g, b))
            inverted_rgb = ImageOps.invert(rgb_image)
            r2, g2, b2 = inverted_rgb.split()
            return Image.merge("RGBA", (r2, g2, b2, a))
        else:
            return ImageOps.invert(image)

    def _load_pieces(self) -> Dict[str, ImageTk.PhotoImage]:
        """
        Loads all important piece images to memory

        Returns:
            Dict: a dictionary with both normal pieces images and the inverted RGB version
        """

        def load_and_format(path): #This inner function is here to reduce code length
            image = Image.open(path).convert("RGBA") #NOTE Important for later transformations
            image = image.resize((self.cell_size, self.cell_size), Image.Resampling.LANCZOS)
            return image
        
        images: Dict[str, ImageTk.PhotoImage] = {}
        for side in self.config['Pieces paths'].keys():
            for piece in self.config['Pieces paths'][side].keys():
                key = f'{side} {piece}'
                image = load_and_format(self.config['Pieces paths'][side][piece])
                images[key] = ImageTk.PhotoImage(image)
                key = f'{side} {piece} inverted'
                image = self._invert_image(image)
                images[key] = ImageTk.PhotoImage(image)

        return images

    def on_click(self, event: tk.Event) -> None:
        """
        Determine the clicked square and handle selection/movement

        Parameters:
            event: a TKinter mouse click event
        """
        target_position = self._translate_position_px2logic(event.x, event.y)
        
        if self.selected is None: #Select the piece to move
            piece = self.logicboard.what_in(target_position)
            if not 'Empty' in piece:
                self.selected = (target_position, piece)
#                self.board.delete("all")
#                self.draw_board()
        else:
            piece_position, piece = self.selected
            self.selected = None
            if piece_position != target_position:
                moved, movement = self.logicboard.move(piece, piece_position, target_position)
                if moved:
#                    self.board.delete("all")
#                    self.draw_board() #Draw new position
                    self.add_move(movement) #Add move to history
                else:
                    print("Movimiento inválido")
                    print("Los movimientos válidos son:")
                    print(self.logicboard.allowed_movements(piece, piece_position))

#            else: #Deselect
        self.board.delete("all")
        self.draw_board()              
