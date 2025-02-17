import tkinter as tk
from neuralcheck.ui import ChessUI

if __name__ == "__main__":
    root = tk.Tk()
    app = ChessUI(root, False)
    root.mainloop()
