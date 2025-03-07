import tkinter as tk
from tkinter import filedialog
import yaml
from PIL import Image, ImageTk, ImageOps
from neuralcheck.logic import ChessBoard
from typing import Tuple, Dict
import pdb

#TODO : Agregar información sobre a qué jugador corresponde el turno
#TODO : Agregar reloj
#TODO : Agregar piezas capturadas
#TODO : Agregar opción de girar el tablero

class ChessUI:
    def __init__(self, master, rotation):
        with open('config/board.yaml', 'r') as file: 
            self.config = yaml.safe_load(file)
        self.cell_size  = self.config['Size']['square']

        self.master     = master
        self.rotation   = rotation #False if White's view, True for Black's view
        self.logic      = ChessBoard()

        master.geometry(f"{self.config['Size']['width']}x{self.config['Size']['height']}")
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)
        
        self.main_frame = tk.Frame(master) #Principal frame for the board
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)
        
        #Panel 1: Two canvases (captured pieces and main board)
        self.panel_canvas = tk.Frame(self.main_frame)
        self.panel_canvas.grid(row=0, column=0, sticky="nsew")
        self.panel_canvas.columnconfigure(0, weight=0)
        self.panel_canvas.columnconfigure(1, weight=1)
        #Off board for drawing captured pieces and clock
        self.offboard   = tk.Canvas(self.panel_canvas, 
                                    width=self.cell_size * 3,
                                    height=self.cell_size * 8)
        self.offboard.grid(row=0, column=0)
        #Chess grafic board
        self.board      = tk.Canvas(self.panel_canvas, 
                                    width=self.cell_size * 8, 
                                    height=self.cell_size * 8)
        self.board.grid(row=0, column=1) 
        
        #Panel 2: History plays with scrooll bars and navigation buttons
        self.panel_history = tk.Frame(self.main_frame)
        self.panel_history.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.panel_history.columnconfigure(0, weight=1)
        #Text Widget for history plays
        self.history_text = tk.Text(self.panel_history, width=25, height=20, wrap=tk.WORD)
        self.history_text.grid(row=0, column=1, sticky="ns", padx=10)
        self.history_scrollbar = tk.Scrollbar(self.panel_history, command=self.history_text.yview)
        self.history_scrollbar.grid(row=0, column=2, sticky="ns")
        self.history_text.config(yscrollcommand=self.history_scrollbar.set)
        #Frame for navigation buttons
        self.nav_frame = tk.Frame(self.panel_history)
        self.nav_frame.grid(row=1, column=0, columnspan=2, pady=10)
        #Navigation buttons
        font = ("Arial", 12)
        self.first_button = tk.Button(self.nav_frame, text="⏮", command=self.go_to_first, font=font)
        self.first_button.grid(row=0, column=0, padx=2, pady=2)
        self.previous_button = tk.Button(self.nav_frame, text="⬅", command=self.previous_step, font=font)
        self.previous_button.grid(row=0, column=1, padx=2, pady=2)
        self.play_button = tk.Button(self.nav_frame, text="▶", command=self.execute_move, font=font)
        self.play_button.grid(row=0, column=2, padx=2, pady=2)
        self.next_button = tk.Button(self.nav_frame, text="➡", command=self.next_step, font=font)
        self.next_button.grid(row=0, column=3, padx=2, pady=2)
        self.last_button = tk.Button(self.nav_frame, text="⏭", command=self.go_to_last, font=font)
        self.last_button.grid(row=0, column=4, padx=2, pady=2)

        #Panel 3: Load and save buttons, rest of temporary controls
        self.panel_controls = tk.Frame(self.main_frame)
        self.panel_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        self.panel_controls.columnconfigure(0, weight=1)
        self.panel_controls.columnconfigure(1, weight=1)
        #Load and save buttons
        self.new_button = tk.Button(self.panel_controls, text="New Game", command=self.new_game)
        self.new_button.grid(row=0, column=0, padx=20, pady=5)
        self.load_button = tk.Button(self.panel_controls, text="Load Game", command=self.load_game)
        self.load_button.grid(row=1, column=0, padx=20, pady=5)
        self.save_button = tk.Button(self.panel_controls, text="Save Game", command=self.save_game)
        self.save_button.grid(row=2, column=0, padx=20, pady=5)

        #HACK Esta es una característica que me ayudará a debuguear las órdenes de movimiento, después borrar
        self.entry = tk.Entry(self.panel_controls, width=40)
        self.entry.grid(row=0, column=1, columnspan=2, pady=5)
        self.label = tk.Label(self.panel_controls, text="Texto enviado: ", font=("Arial", 12))
        self.label.grid(row=1, column=1, columnspan=2, pady=5)
        self.entry.bind("<Return>", self.send_text)
        self.breakpoint_button = tk.Button(self.panel_controls, text="Breakpoint", command=self.self_breakpoint)
        self.breakpoint_button.grid(row=2, column=1, pady=5)

        self.pieces     = self._load_pieces()
        self.cols_str   = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
        if self.rotation: 
            self.cols_str = self.cols_str[::-1]        
        self.selected   = None #To store selected box
        self.coordinates = True
        self.draw_board()
        self.board.bind("<Button-1>", self.on_click)

    def send_text(self, event): #HACK Borrar en el futuro
            texto = self.entry.get().strip()  # Evitar entradas vacías
            if texto:
                self.logic.bitboard.make_move(texto, self.logic.white_turn)
                self.label.config(text=f"Texto enviado: {texto}")
                self.entry.delete(0, tk.END)  # Limpiar la barra de entrada

    def self_breakpoint(self): #HACK Borrar en el futuro
        breakpoint()

    def draw_moves(self, see_beginning:bool=False, see_end:bool=True) -> None:
        """
        Adds a move to the history displayed in the text widget.

        Parameters: 
            move: the move text to add
        """
        
        current_view = self.history_text.yview()[0]
        self.history_text.delete("1.0", tk.END) #Delete and redraw all
        for turn, entry  in enumerate(self.logic.history):
            if isinstance(entry, (list, tuple)):
                moves = entry[0]
            else:
                moves = entry

            if isinstance(moves, str):
                moves = [moves]
            
            if len(moves) == 0:
                white_move, black_move = '', ''
            elif len(moves) == 1:
                white_move, black_move = moves[0], ''
            else:
                white_move, black_move = moves[0], moves[1]

            wpointer = '➡' if self.logic.pointer[0] == turn and self.logic.pointer[1] else ''
            bpointer = '➡' if self.logic.pointer[0] == turn and not self.logic.pointer[1] else ''
            self.history_text.insert(tk.END, f"{turn+1}\t{wpointer+white_move}\t{bpointer+black_move}\n")
        
        if see_beginning:
            self.history_text.see("1.0")
        elif see_end:
            self.history_text.see(tk.END)
        else:
            self.history_text.yview_moveto(current_view)

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
                response = self.logic.what_in(position)
                if 'Empty' in response:
                    continue                
                x, y = self._translate_position_logic2px(position)
                self.board.create_image(x, y, image=self.pieces[response], anchor='nw')

        #If a piece is selected draw it with inverted colors
        if self.selected is not None:
            piece_colors = ["black", "gray10"]
            position, piece = self.selected
            x1, y1          = self._translate_position_logic2px(position)
            x2              = x1 + self.cell_size
            y2              = y1 + self.cell_size
            col, row        = self.logic.logic2array(position)
            color           = piece_colors[(row + col) % 2]
            self.board.create_rectangle(x1, y1, x2, y2, fill=color)
            self.board.create_image(x1, y1, image=self.pieces[piece+' inverted'], anchor='nw')
            if position in self.logic.possible_moves.keys():
                for target in self.logic.possible_moves[position]: #Draw circles to indicate target squares that the piece can go to
                    x3, y3  = self._translate_position_logic2px(target)
                    margin = self.cell_size * 0.1  
                    if 'Empty' in self.logic.what_in(target):
                        self.board.create_oval(
                            x3 + margin, y3 + margin,
                            x3 + self.cell_size - margin, y3 + self.cell_size - margin,
                            outline="#5A5A5A",  
                            width=3)
                    else:
                        self.board.create_rectangle(
                            x3 + margin, y3 + margin,
                            x3 + self.cell_size - margin, y3 + self.cell_size - margin,
                            outline="black",  
                            width=3)
                        self.board.create_line(
                            x3 + margin, y3 + margin,
                            x3 + self.cell_size - margin, y3 + self.cell_size - margin,
                            fill="black", width=3)
                        self.board.create_line(
                            x3 + self.cell_size - margin, y3 + margin,
                            x3 + margin, y3 + self.cell_size - margin,
                            fill="black", width=3)                        

        if self.coordinates: #Draw coordinates to show in the board
            margin = 2  

            for col in range(8): #Col tags in last row 
                x1 = col * self.cell_size
                y1 = 7 * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                letter = self.cols_str[col] #Adjust to rotation
                self.board.create_text(
                    x2 - margin, y2 - margin,
                    text=letter,
                    anchor="se",
                    font=("Arial", 10, "bold"),
                    fill="black")

            for row in range(8): #Row tags in last col
                x1 = 7 * self.cell_size
                y1 = row * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                logic_row = (row + 1) if self.rotation else (8 - row)
                offset = -12 if row == 7 else 0
                self.board.create_text(
                    x2 - margin, y2 - margin + offset,
                    text=str(logic_row),
                    anchor="se",
                    font=("Arial", 10, "bold"),
                    fill="black"
                )

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

    def pawn_promotion(self) -> None:
        """
        Creates a popup that allows the user to select a piece for promotion
        """
        selected_piece = None
        def on_piece_click(event, piece_key):
            nonlocal selected_piece
            selected_piece = piece_key 
            popup.destroy()

        popup = tk.Toplevel(self.master)
        popup.title('Select a piece for promotion')
        popup.geometry(f'{self.cell_size*4}x{self.cell_size}')
        canvas = tk.Canvas(popup, width=self.cell_size*4, height=self.cell_size)
        canvas.pack(fill="both", expand=True)
        
        pieces_to_show = ['queen', 'rook', 'knight', 'bishop']
        prefix = 'white ' if self.logic.white_turn else 'black '
        pieces_to_show = [prefix + piece for piece in pieces_to_show]

        for i, piece in enumerate(pieces_to_show):
            img_id = canvas.create_image(i*self.cell_size, 0, image=self.pieces[piece], anchor="nw")
            canvas.tag_bind(img_id, "<Button-1>", lambda event, piece_key=piece: on_piece_click(event, piece_key)) #Asociates the click event with the selected piece before the destruccion of the popup

        popup.grab_set() #Makes the popup modal
        self.master.wait_window(popup) #Waits for the popup to be destroyed
        
        return selected_piece

    def on_click(self, event: tk.Event) -> None:
        """
        Determine the clicked square and handle selection/movement

        Parameters:
            event: a TKinter mouse click event
        """
        target_position = self._translate_position_px2logic(event.x, event.y)
        
        if self.selected is None: #Select the piece to move
            piece = self.logic.what_in(target_position)
            if not 'Empty' in piece:
                self.selected = (target_position, piece)
        else:
            piece_position, piece = self.selected
            self.selected = None
            if piece_position != target_position:
                promote2 = None
                if 'pawn' in piece and \
                    ((self.logic.white_turn and '8' in target_position) or \
                     (not self.logic.white_turn and '1' in target_position)):
                        promote2 = self.pawn_promotion()
                moved, movement = self.logic.make_move(piece, piece_position, target_position, promote2=promote2)
                if moved:
                    self.draw_moves() #Add move to history
                else:
                    print("Movimiento inválido")
                    print("Los movimientos válidos para esa pieza son:")
                    if piece_position in self.logic.possible_moves.keys():
                        print(self.logic.possible_moves[piece_position])
                    else:
                        print("Ninguno")

        self.board.delete("all")
        self.draw_board()              

    def new_game(self) -> None:
        """
        Clears the current board, and its logic
        """
        self.logic = ChessBoard()
        self.board.delete("all")
        self.draw_board()
        self.draw_moves(see_end=False)

    def load_game(self) -> None:
        """
        Asks user to loof for a file to load.
        """
        filename = filedialog.askopenfilename(
            initialdir="test/test_games",  
            title="Select YAML file",
            filetypes=(("YAML files", "*.yaml"), ("PGN files", "*.pgn"), ("All files", "*.*"))
        )
        self.logic.load_game(filename)
        self.go_to_first()

    def save_game(self) -> None:
        """
        Asks user to provide a name to save.
        """
        filename = filedialog.asksaveasfilename(
        initialdir="test/test_games",
        title="Save YAML file",
        defaultextension=".yaml",  
        filetypes=(("YAML files", "*.yaml"), ("PGN files", "*.pgn"), ("All files", "*.*"))
    )

        if filename:
            self.logic.save_game(filename)

    def go_to_first(self) -> None:
        """
        Set cursor to the first play of the game
        """
        self.logic.pointer = (0, True)
        self.logic.go2(0, True)
        self.board.delete("all")
        self.draw_board()
        self.draw_moves(see_beginning=True, see_end=False)

    def previous_step(self) -> None:
        """
        Set cursor to the previous play of the game
        """
        turn, white_turn = self.logic.pointer
        if turn == 0 and white_turn:
            return
        if white_turn:
            turn -= 1
        white_turn = not white_turn
        self.logic.pointer = (turn, white_turn)
        self.logic.go2(turn, white_turn)
        self.board.delete("all")
        self.draw_board()
        self.draw_moves(see_end=False)

    def execute_move(self) -> None:
        """
        Executes the move isntead of oly refresh the position.
        Validation of movements are taken into acount.
        """
        # TODO change this for an ongoing next_step call with a short period between calls
        promote2            = None
        turn, white_turn    = self.logic.pointer
        moves, _            = self.logic.history[turn]
        if white_turn and (turn == len(self.logic.history) or len(moves) == 1):
            return        
        move = moves[0] if white_turn else moves[1]
        if '=' in move:
            move        = move.split('=')
            prefix      = 'white ' if white_turn else 'black '
            promotions  = {'Q': 'queen', 'R' : 'rook', 'N' : 'knight', 'B' : 'bishop'}
            promote2    = prefix + promotions[move[1]]
            move        = move[0]

        piece, initial_position, end_position = self.logic.read_move(move, white_turn)
        moved, movement = self.logic.make_move(piece, 
                                                    initial_position, 
                                                    end_position, 
                                                    promote2=promote2, 
                                                    add2history=False)
        print(move, piece, initial_position, end_position, turn, white_turn)
        if not moved:
            print("Movimiento inválido")
            print(f"Los movimientos válidos para la pieza {piece} en {initial_position} son:")
            print(self.logic.allowed_movements(piece, initial_position))
        
        self.board.delete("all")
        self.draw_board()
        self.draw_moves(see_end=False)

    def next_step(self) -> None:
        """
        Set cursor to the next play of the game
        """
        turn, white_turn = self.logic.pointer
        if turn == len(self.logic.history) and white_turn:
            return
        if white_turn:
            moves, _ = self.logic.history[turn]
            if len(moves) == 1:
                return
            white_turn = not white_turn  
        else:
            turn += 1
            white_turn = not white_turn  
        self.logic.pointer = (turn, white_turn)
        self.logic.go2(turn, white_turn)
        self.board.delete("all")
        self.draw_board()
        self.draw_moves(see_end=False)

    def go_to_last(self) -> None:
        """
        Set cursor to the last play of the game
        """
        tot = len(self.logic.history)
        last_turn = self.logic.history[tot - 1]
        moves = last_turn[0]
        if len(moves) == 1:
            self.logic.pointer = (tot - 1, True)
            self.logic.go2(tot - 1, True)
        else:
            self.logic.pointer = (tot - 1, False)
            self.logic.go2(tot - 1, False)
        self.board.delete("all")
        self.draw_board()
        self.draw_moves(see_end=True)

    