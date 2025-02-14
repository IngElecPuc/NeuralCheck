import tkinter as tk
import yaml

class ChessUI:
    def __init__(self, master, rotation):
        with open('config/board.yaml', 'r') as file: 
            self.config = yaml.safe_load(file)

        self.master = master
        self.canvas = tk.Canvas(master, 
                                width=self.config['Size']['width'], 
                                height=self.config['Size']['height'])
        self.cell_size = self.config['Size']['cell_size']
        self.rotation = rotation #False if White's view, True for Black's view
        self.canvas.pack()
        self.draw_board(self.player)
        self.canvas.bind("<Button-1>", self.on_click)
        self.selected = None #To store selected box

    def draw_board(self, rotation):
        """
        Draw a 8x8 board with alternating colors
        """
        colors = ["white", "gray"]
        for row in range(8):
            for col in range(8):
                color = colors[(row + col) % 2]
                x1 = col * self.cell_size
                y1 = row * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color)

        #Dibujar las piezas

    def on_click(self, event):
        # Determina la casilla clickeada y maneja la selección/movimiento
        col = event.x // self.cell_size
        row = event.y // self.cell_size
        pos = (row, col)
        if self.selected is None:
            # Selecciona la pieza a mover
            self.selected = pos
        else:
            # Intenta mover la pieza desde self.selected hasta pos
            moved = self.chess_board.move_piece(self.selected, pos)
            if moved:
                print("Movimiento realizado de", self.selected, "a", pos)
                # Redibuja el tablero para reflejar el nuevo estado
                self.canvas.delete("all")
                self.draw_board()
            else:
                print("Movimiento inválido")
            self.selected = None

if __name__ == "__main__":
    root = tk.Tk()
    app = ChessUI(root)
    root.mainloop()            