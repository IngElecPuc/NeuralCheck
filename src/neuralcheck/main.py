import tkinter as tk
from neuralcheck.ui import ChessUI
"""
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
"""
if __name__ == "__main__":
    root = tk.Tk()
    app = ChessUI(root, False)
    root.mainloop()
