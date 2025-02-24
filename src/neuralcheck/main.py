import tkinter as tk
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../")))
from neuralcheck.ui import ChessUI

# TODO: Implementar la función de validación
# FIXME: Corregir el error de índice en la línea 20
# BUG: La variable no está inicializada correctamente
# HACK: Solución temporal, mejorar en la próxima versión
# NOTE: Esta función es utilizada en varios módulos
# OPTIMIZE → Indica partes del código que podrían mejorarse en rendimiento.
# REVIEW → Para marcar código que necesita revisión antes de ser fusionado.
# QUESTION → Señala dudas o preguntas sobre el código.
# IDEA → Resalta sugerencias o posibles mejoras.
# DEPRECATED → Indica código que ya no debería usarse

if __name__ == "__main__":
    root = tk.Tk()
    app = ChessUI(root, False)
    root.mainloop()
