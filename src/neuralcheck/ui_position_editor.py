from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple
import tkinter as tk
from tkinter import messagebox

from neuralcheck.application.game_controller import GameController


EMPTY_SQUARE = "Empty square"


def position_editor_palette_options() -> tuple[str, ...]:
    """Return the 4x4 visual palette used by the manual position editor."""
    return (
        "black king",
        "black queen",
        "black rook",
        "black bishop",
        "black knight",
        "black pawn",
        EMPTY_SQUARE,
        EMPTY_SQUARE,
        "white king",
        "white queen",
        "white rook",
        "white bishop",
        "white knight",
        "white pawn",
        EMPTY_SQUARE,
        EMPTY_SQUARE,
    )


class PositionEditorWindow:
    """Manual position editor for the desktop UI.

    The editor keeps a local draft until the user presses Apply. The controller
    remains the authority for validation and for committing the position.
    """

    def __init__(
        self,
        master: tk.Misc,
        controller: GameController,
        pieces_images: dict,
        cell_size: int,
        rotation: bool,
        on_apply: Callable[[], None],
    ):
        self.master = master
        self.controller = controller
        self.pieces_images = pieces_images
        self.cell_size = cell_size
        self.palette_cell_size = cell_size
        self.rotation = rotation
        self.on_apply = on_apply
        self.draft_pieces: Dict[str, str] = controller.board_pieces()
        self.palette_options = position_editor_palette_options()
        self.selected_palette_index = self.palette_options.index("white pawn")
        self.selected_piece = tk.StringVar(value="white pawn")
        self.white_turn = tk.BooleanVar(value=controller.white_turn)
        self.fen_value = tk.StringVar(value=controller.current_fen(include_state=True))
        self.status_value = tk.StringVar(value="Selecciona una pieza y haz click en el tablero.")
        self.cols_str = ["a", "b", "c", "d", "e", "f", "g", "h"]
        if rotation:
            self.cols_str = self.cols_str[::-1]

        self.window = tk.Toplevel(master)
        self.window.title("Configurar posición")
        self.window.transient(master)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.cancel)

        self._build_layout()
        self.draw_board()
        self.draw_piece_palette()

    def _build_layout(self) -> None:
        self.window.columnconfigure(0, weight=0)
        self.window.columnconfigure(1, weight=1)
        self.window.rowconfigure(0, weight=1)

        self.canvas = tk.Canvas(
            self.window,
            width=self.cell_size * 8,
            height=self.cell_size * 8,
        )
        self.canvas.grid(row=0, column=0, rowspan=4, padx=10, pady=10)
        self.canvas.bind("<Button-1>", self.on_board_click)

        controls = tk.Frame(self.window)
        controls.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        controls.columnconfigure(0, weight=1)

        palette_frame = tk.LabelFrame(controls, text="Pieza a colocar")
        palette_frame.grid(row=0, column=0, sticky="ew")
        palette_frame.columnconfigure(0, weight=1)
        self.palette_canvas = tk.Canvas(
            palette_frame,
            width=self.palette_cell_size * 4,
            height=self.palette_cell_size * 4,
            highlightthickness=1,
            highlightbackground="#b0b0b0",
        )
        self.palette_canvas.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        self.palette_canvas.bind("<Button-1>", self.on_palette_click)

        self.selected_piece_label = tk.StringVar(value=self._piece_label(self.selected_piece.get()))
        tk.Label(palette_frame, textvariable=self.selected_piece_label, anchor="w").grid(
            row=1,
            column=0,
            sticky="ew",
            padx=4,
            pady=(0, 4),
        )

        turn_frame = tk.LabelFrame(controls, text="Turno")
        turn_frame.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        tk.Radiobutton(turn_frame, text="Blancas", variable=self.white_turn, value=True).pack(anchor="w")
        tk.Radiobutton(turn_frame, text="Negras", variable=self.white_turn, value=False).pack(anchor="w")

        fen_frame = tk.LabelFrame(controls, text="FEN")
        fen_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        fen_frame.columnconfigure(0, weight=1)
        tk.Entry(fen_frame, textvariable=self.fen_value, width=52).grid(row=0, column=0, columnspan=3, sticky="ew")
        tk.Button(fen_frame, text="Cargar FEN", command=self.load_fen).grid(row=1, column=0, sticky="ew", pady=2)
        tk.Button(fen_frame, text="Actualizar FEN", command=self.update_fen).grid(row=1, column=1, sticky="ew", pady=2)
        tk.Button(fen_frame, text="Limpiar", command=self.clear_board).grid(row=1, column=2, sticky="ew", pady=2)

        button_frame = tk.Frame(controls)
        button_frame.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)
        tk.Button(button_frame, text="Aplicar", command=self.apply).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Button(button_frame, text="Cancelar", command=self.cancel).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        tk.Label(controls, textvariable=self.status_value, wraplength=360, justify="left").grid(
            row=4,
            column=0,
            sticky="ew",
            pady=(10, 0),
        )

    def on_palette_click(self, event) -> None:
        col = event.x // self.palette_cell_size
        row = event.y // self.palette_cell_size
        if not (0 <= col < 4 and 0 <= row < 4):
            return
        index = row * 4 + col
        if not (0 <= index < len(self.palette_options)):
            return
        self.selected_palette_index = index
        self.selected_piece.set(self.palette_options[index])
        self.selected_piece_label.set(self._piece_label(self.selected_piece.get()))
        self.status_value.set(f"Pieza seleccionada: {self.selected_piece_label.get()}.")
        self.draw_piece_palette()

    def draw_piece_palette(self) -> None:
        self.palette_canvas.delete("all")
        colors = ["white", "gray"]
        for index, piece in enumerate(self.palette_options):
            row = index // 4
            col = index % 4
            x1 = col * self.palette_cell_size
            y1 = row * self.palette_cell_size
            x2 = x1 + self.palette_cell_size
            y2 = y1 + self.palette_cell_size
            self.palette_canvas.create_rectangle(x1, y1, x2, y2, fill=colors[(row + col) % 2], outline="#909090")

            if piece == EMPTY_SQUARE:
                self.palette_canvas.create_text(
                    x1 + self.palette_cell_size / 2,
                    y1 + self.palette_cell_size / 2,
                    text="∅",
                    font=("Arial", max(14, int(self.palette_cell_size * 0.35)), "bold"),
                    fill="#555555",
                )
            else:
                self.palette_canvas.create_image(x1, y1, image=self.pieces_images[piece], anchor="nw")

            if index == self.selected_palette_index:
                inset = 3
                self.palette_canvas.create_rectangle(
                    x1 + inset,
                    y1 + inset,
                    x2 - inset,
                    y2 - inset,
                    outline="black",
                    width=4,
                )

    def on_board_click(self, event) -> None:
        position = self._translate_position_px2logic(event.x, event.y)
        if position is None:
            return

        piece = self.selected_piece.get()
        if piece == EMPTY_SQUARE:
            self.draft_pieces.pop(position, None)
        else:
            self.draft_pieces[position] = piece
        self.update_fen()
        self.draw_board()

    def draw_board(self) -> None:
        self.canvas.delete("all")
        colors = ["white", "gray"]
        for row in range(8):
            for col in range(8):
                color = colors[(row + col) % 2]
                x1 = col * self.cell_size
                y1 = row * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color)

        for position, piece in self.draft_pieces.items():
            x, y = self._translate_position_logic2px(position)
            self.canvas.create_image(x, y, image=self.pieces_images[piece], anchor="nw")

        self._draw_coordinates()

    def _draw_coordinates(self) -> None:
        margin = 2
        for col in range(8):
            x1 = col * self.cell_size
            y1 = 7 * self.cell_size
            x2 = x1 + self.cell_size
            y2 = y1 + self.cell_size
            letter = self.cols_str[col]
            self.canvas.create_text(
                x2 - margin,
                y2 - margin,
                text=letter,
                anchor="se",
                font=("Arial", 10, "bold"),
                fill="black",
            )

        for row in range(8):
            x1 = 7 * self.cell_size
            y1 = row * self.cell_size
            x2 = x1 + self.cell_size
            y2 = y1 + self.cell_size
            logic_row = (row + 1) if self.rotation else (8 - row)
            offset = -12 if row == 7 else 0
            self.canvas.create_text(
                x2 - margin,
                y2 - margin + offset,
                text=str(logic_row),
                anchor="se",
                font=("Arial", 10, "bold"),
                fill="black",
            )

    def update_fen(self) -> None:
        placement = self._pieces_to_placement_fen()
        active_color = "w" if self.white_turn.get() else "b"
        self.fen_value.set(f"{placement} {active_color} - - 0 1")
        self.status_value.set("FEN actualizado desde el tablero editable.")

    def load_fen(self) -> None:
        fen = self.fen_value.get().strip()
        result = self.controller.apply_fen_position(fen)
        if not result.valid:
            messagebox.showerror("Posición inválida", "\n".join(result.errors), parent=self.window)
            return

        self.draft_pieces = self.controller.board_pieces()
        self.white_turn.set(self.controller.white_turn)
        self.status_value.set("FEN cargado y aplicado.")
        self.on_apply()
        self.draw_board()

    def clear_board(self) -> None:
        self.draft_pieces = {}
        self.update_fen()
        self.draw_board()

    def apply(self) -> None:
        result = self.controller.apply_manual_position(self.draft_pieces, self.white_turn.get())
        if not result.valid:
            messagebox.showerror("Posición inválida", "\n".join(result.errors), parent=self.window)
            return

        if result.warnings:
            self.status_value.set("\n".join(result.warnings))
        self.on_apply()
        self.window.destroy()

    def cancel(self) -> None:
        self.window.destroy()

    def _pieces_to_placement_fen(self) -> str:
        piece_to_fen = {
            "white king": "K",
            "white queen": "Q",
            "white rook": "R",
            "white bishop": "B",
            "white knight": "N",
            "white pawn": "P",
            "black king": "k",
            "black queen": "q",
            "black rook": "r",
            "black bishop": "b",
            "black knight": "n",
            "black pawn": "p",
        }
        ranks = []
        for rank in range(8, 0, -1):
            empty_count = 0
            fen_rank = ""
            for file_name in "abcdefgh":
                piece = self.draft_pieces.get(f"{file_name}{rank}")
                if piece is None:
                    empty_count += 1
                    continue
                if empty_count:
                    fen_rank += str(empty_count)
                    empty_count = 0
                fen_rank += piece_to_fen[piece]
            if empty_count:
                fen_rank += str(empty_count)
            ranks.append(fen_rank)
        return "/".join(ranks)

    def _translate_position_logic2px(self, position: str) -> Tuple[int, int]:
        logic_col, logic_row = position[0], int(position[1])
        cols_int = {col: num for num, col in enumerate(self.cols_str)}
        col = cols_int[logic_col] * self.cell_size
        row = (logic_row - 1) * self.cell_size if self.rotation else (8 - logic_row) * self.cell_size
        return col, row

    def _translate_position_px2logic(self, col: int, row: int) -> Optional[str]:
        board_col = col // self.cell_size
        board_row = row // self.cell_size
        if not (0 <= board_col < 8 and 0 <= board_row < 8):
            return None

        logic_col = self.cols_str[board_col]
        logic_row = board_row + 1 if self.rotation else 8 - board_row
        return f"{logic_col}{logic_row}"

    @staticmethod
    def _piece_label(piece: str) -> str:
        labels = {
            EMPTY_SQUARE: "Espacio vacío",
            "white king": "Rey blanco",
            "white queen": "Dama blanca",
            "white rook": "Torre blanca",
            "white bishop": "Alfil blanco",
            "white knight": "Caballo blanco",
            "white pawn": "Peón blanco",
            "black king": "Rey negro",
            "black queen": "Dama negra",
            "black rook": "Torre negra",
            "black bishop": "Alfil negro",
            "black knight": "Caballo negro",
            "black pawn": "Peón negro",
        }
        return labels.get(piece, piece)
