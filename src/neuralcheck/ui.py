from pathlib import Path
from typing import Dict, Optional, Tuple
import tkinter as tk
from tkinter import filedialog

import yaml
from PIL import Image, ImageOps, ImageTk

from neuralcheck.application.game_controller import GameController, MoveAttempt


PROJECT_ROOT = Path(__file__).resolve().parents[2]


# TODO: Agregar información sobre a qué jugador corresponde el turno.
# TODO: Agregar reloj configurable.
# TODO: Agregar piezas capturadas.
# TODO: Agregar opción de girar el tablero desde la UI.


class ChessUI:
    """Tkinter interface for Neuralcheck.

    This class owns widgets and drawing only. Game state, selection, history
    navigation and legal move lookup are delegated to ``GameController``.
    """

    def __init__(self, master, rotation: bool, controller: Optional[GameController] = None):
        self.config = self._load_config()
        self.cell_size = self.config["Size"]["square"]

        self.master = master
        self.rotation = rotation  # False for White's view, True for Black's view.
        self.controller = controller if controller is not None else GameController()
        self.white_time = 180
        self.black_time = 180
        self.increments = 0
        self.coordinates = True

        master.geometry(f"{self.config['Size']['width']}x{self.config['Size']['height']}")
        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)

        self._build_menu(master)
        self._build_layout(master)

        self.pieces = self._load_pieces()
        self.cols_str = ["a", "b", "c", "d", "e", "f", "g", "h"]
        if self.rotation:
            self.cols_str = self.cols_str[::-1]

        self.draw_board()
        self.draw_moves(see_end=False)
        self.board.bind("<Button-1>", self.on_click)
        self.update_clock()

    def _load_config(self) -> dict:
        config_path = PROJECT_ROOT / "config" / "board.yaml"
        with config_path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file)

    def _resolve_asset_path(self, path: str) -> Path:
        asset_path = Path(path)
        if asset_path.is_absolute():
            return asset_path
        return PROJECT_ROOT / asset_path

    def _build_menu(self, master) -> None:
        self.menubar = tk.Menu(master)
        master.config(menu=self.menubar)

        archivo_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Archivo", menu=archivo_menu)
        archivo_menu.add_command(label="Nueva partida", command=self.new_game)
        archivo_menu.add_command(label="Cargar partida", command=self.load_game)
        archivo_menu.add_command(label="Guardar partida", command=self.save_game)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="Salir", command=master.quit)

    def _build_layout(self, master) -> None:
        self.main_frame = tk.Frame(master)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=1)

        self._build_board_panel()
        self._build_history_panel()
        self._build_control_panel()

    def _build_board_panel(self) -> None:
        self.panel_canvas = tk.Frame(self.main_frame)
        self.panel_canvas.grid(row=0, column=0, sticky="nsew")
        self.panel_canvas.columnconfigure(0, weight=0)
        self.panel_canvas.columnconfigure(1, weight=1)

        self.offboard = tk.Canvas(
            self.panel_canvas,
            width=self.cell_size * 3,
            height=self.cell_size * 8,
        )
        self.offboard.grid(row=0, column=0)
        self.clock_white_id = self.offboard.create_text(
            self.cell_size * 1.5,
            self.cell_size,
            text="White: 03:00",
            font=("Arial", 12, "bold"),
        )
        self.clock_black_id = self.offboard.create_text(
            self.cell_size * 1.5,
            self.cell_size * 7,
            text="Black: 03:00",
            font=("Arial", 12, "bold"),
        )

        self.board = tk.Canvas(
            self.panel_canvas,
            width=self.cell_size * 8,
            height=self.cell_size * 8,
        )
        self.board.grid(row=0, column=1)

    def _build_history_panel(self) -> None:
        self.panel_history = tk.Frame(self.main_frame)
        self.panel_history.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.panel_history.columnconfigure(0, weight=1)

        self.history_text = tk.Text(self.panel_history, width=25, height=20, wrap=tk.WORD)
        self.history_text.grid(row=0, column=1, sticky="ns", padx=10)
        self.history_scrollbar = tk.Scrollbar(self.panel_history, command=self.history_text.yview)
        self.history_scrollbar.grid(row=0, column=2, sticky="ns")
        self.history_text.config(yscrollcommand=self.history_scrollbar.set)

        self.nav_frame = tk.Frame(self.panel_history)
        self.nav_frame.grid(row=1, column=0, columnspan=2, pady=10)

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

    def _build_control_panel(self) -> None:
        self.panel_controls = tk.Frame(self.main_frame)
        self.panel_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        self.panel_controls.columnconfigure(0, weight=1)
        self.panel_controls.columnconfigure(1, weight=1)

        self.new_button = tk.Button(self.panel_controls, text="New Game", command=self.new_game)
        self.new_button.grid(row=0, column=0, padx=20, pady=5)
        self.load_button = tk.Button(self.panel_controls, text="Load Game", command=self.load_game)
        self.load_button.grid(row=1, column=0, padx=20, pady=5)
        self.save_button = tk.Button(self.panel_controls, text="Save Game", command=self.save_game)
        self.save_button.grid(row=2, column=0, padx=20, pady=5)

        # HACK: Debug bridge kept from the original UI. It no longer reaches the
        # ChessBoard directly; the controller owns that temporary boundary.
        self.entry = tk.Entry(self.panel_controls, width=40)
        self.entry.grid(row=0, column=1, columnspan=2, pady=5)
        self.label = tk.Label(self.panel_controls, text="Texto enviado: ", font=("Arial", 12))
        self.label.grid(row=1, column=1, columnspan=2, pady=5)
        self.entry.bind("<Return>", self.send_text)
        self.breakpoint_button = tk.Button(self.panel_controls, text="Breakpoint", command=self.self_breakpoint)
        self.breakpoint_button.grid(row=2, column=1, pady=5)

    def send_text(self, event) -> None:  # HACK: borrar en el futuro.
        text = self.entry.get().strip()
        if not text:
            return

        self.controller.make_debug_bitboard_move(text)
        self.label.config(text=f"Texto enviado: {text}")
        self.entry.delete(0, tk.END)

    def self_breakpoint(self) -> None:  # HACK: borrar en el futuro.
        breakpoint()

    def draw_moves(self, see_beginning: bool = False, see_end: bool = True) -> None:
        current_view = self.history_text.yview()[0]
        self.history_text.delete("1.0", tk.END)

        for row in self.controller.history_rows():
            white_pointer = "➡" if row.white_pointer else ""
            black_pointer = "➡" if row.black_pointer else ""
            self.history_text.insert(
                tk.END,
                f"{row.turn_number}\t{white_pointer + row.white_move}\t{black_pointer + row.black_move}\n",
            )

        if see_beginning:
            self.history_text.see("1.0")
        elif see_end:
            self.history_text.see(tk.END)
        else:
            self.history_text.yview_moveto(current_view)

    def draw_board(self) -> None:
        colors = ["white", "gray"]
        for row in range(8):
            for col in range(8):
                color = colors[(row + col) % 2]
                x1 = col * self.cell_size
                y1 = row * self.cell_size
                x2 = x1 + self.cell_size
                y2 = y1 + self.cell_size
                self.board.create_rectangle(x1, y1, x2, y2, fill=color)

        self._draw_pieces()
        self._draw_selection()
        self._draw_coordinates()

    def _draw_pieces(self) -> None:
        for col in self.cols_str:
            for row in range(1, 9):
                position = f"{col}{row}"
                piece = self.controller.piece_at(position)
                if "Empty" in piece:
                    continue

                x, y = self._translate_position_logic2px(position)
                self.board.create_image(x, y, image=self.pieces[piece], anchor="nw")

    def _draw_selection(self) -> None:
        selected = self.controller.selected
        if selected is None:
            return

        piece_colors = ["black", "gray10"]
        position, piece = selected
        x1, y1 = self._translate_position_logic2px(position)
        x2 = x1 + self.cell_size
        y2 = y1 + self.cell_size
        row, col = self._logic_position_to_board_indexes(position)
        color = piece_colors[(row + col) % 2]
        self.board.create_rectangle(x1, y1, x2, y2, fill=color)
        self.board.create_image(x1, y1, image=self.pieces[piece + " inverted"], anchor="nw")

        for target in self.controller.selected_legal_targets():
            self._draw_target_marker(target)

    def _draw_target_marker(self, target: str) -> None:
        x, y = self._translate_position_logic2px(target)
        margin = self.cell_size * 0.1
        if self.controller.is_empty(target):
            self.board.create_oval(
                x + margin,
                y + margin,
                x + self.cell_size - margin,
                y + self.cell_size - margin,
                outline="#5A5A5A",
                width=3,
            )
            return

        self.board.create_rectangle(
            x + margin,
            y + margin,
            x + self.cell_size - margin,
            y + self.cell_size - margin,
            outline="black",
            width=3,
        )
        self.board.create_line(
            x + margin,
            y + margin,
            x + self.cell_size - margin,
            y + self.cell_size - margin,
            fill="black",
            width=3,
        )
        self.board.create_line(
            x + self.cell_size - margin,
            y + margin,
            x + margin,
            y + self.cell_size - margin,
            fill="black",
            width=3,
        )

    def _draw_coordinates(self) -> None:
        if not self.coordinates:
            return

        margin = 2
        for col in range(8):
            x1 = col * self.cell_size
            y1 = 7 * self.cell_size
            x2 = x1 + self.cell_size
            y2 = y1 + self.cell_size
            letter = self.cols_str[col]
            self.board.create_text(
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
            self.board.create_text(
                x2 - margin,
                y2 - margin + offset,
                text=str(logic_row),
                anchor="se",
                font=("Arial", 10, "bold"),
                fill="black",
            )

    def _translate_position_logic2px(self, position: str) -> Tuple[int, int]:
        logic_col, logic_row = position[0], int(position[1])
        cols_int = {col: num for num, col in enumerate(self.cols_str)}
        col = cols_int[logic_col] * self.cell_size

        if self.rotation:
            row = (logic_row - 1) * self.cell_size
        else:
            row = (8 - logic_row) * self.cell_size

        return col, row

    def _translate_position_px2logic(self, col: int, row: int) -> Optional[str]:
        board_col = col // self.cell_size
        board_row = row // self.cell_size
        if not (0 <= board_col < 8 and 0 <= board_row < 8):
            return None

        logic_col = self.cols_str[board_col]
        if self.rotation:
            logic_row = board_row + 1
        else:
            logic_row = 8 - board_row

        return f"{logic_col}{logic_row}"

    def _logic_position_to_board_indexes(self, position: str) -> Tuple[int, int]:
        col_letter, row_number = position[0], int(position[1])
        col = ["a", "b", "c", "d", "e", "f", "g", "h"].index(col_letter)
        row = 8 - row_number
        return row, col

    def _invert_image(self, image: Image.Image) -> Image.Image:
        if image.mode == "RGBA":
            r, g, b, a = image.split()
            rgb_image = Image.merge("RGB", (r, g, b))
            inverted_rgb = ImageOps.invert(rgb_image)
            r2, g2, b2 = inverted_rgb.split()
            return Image.merge("RGBA", (r2, g2, b2, a))
        return ImageOps.invert(image)

    def _load_pieces(self) -> Dict[str, ImageTk.PhotoImage]:
        def load_and_format(path: str) -> Image.Image:
            image = Image.open(self._resolve_asset_path(path)).convert("RGBA")
            image = image.resize((self.cell_size, self.cell_size), Image.Resampling.LANCZOS)
            return image

        images: Dict[str, ImageTk.PhotoImage] = {}
        for side in self.config["Pieces paths"].keys():
            for piece in self.config["Pieces paths"][side].keys():
                key = f"{side} {piece}"
                image = load_and_format(self.config["Pieces paths"][side][piece])
                images[key] = ImageTk.PhotoImage(image)
                images[f"{key} inverted"] = ImageTk.PhotoImage(self._invert_image(image))

        return images

    def pawn_promotion(self) -> Optional[str]:
        selected_piece = None

        def on_piece_click(event, piece_key: str) -> None:
            nonlocal selected_piece
            selected_piece = piece_key
            popup.destroy()

        popup = tk.Toplevel(self.master)
        popup.title("Select a piece for promotion")
        popup.geometry(f"{self.cell_size * 4}x{self.cell_size}")
        canvas = tk.Canvas(popup, width=self.cell_size * 4, height=self.cell_size)
        canvas.pack(fill="both", expand=True)

        pieces_to_show = ["queen", "rook", "knight", "bishop"]
        prefix = "white " if self.controller.white_turn else "black "
        pieces_to_show = [prefix + piece for piece in pieces_to_show]

        for index, piece in enumerate(pieces_to_show):
            image_id = canvas.create_image(index * self.cell_size, 0, image=self.pieces[piece], anchor="nw")
            canvas.tag_bind(
                image_id,
                "<Button-1>",
                lambda event, piece_key=piece: on_piece_click(event, piece_key),
            )

        popup.grab_set()
        self.master.wait_window(popup)
        return selected_piece

    def on_click(self, event: tk.Event) -> None:
        target_position = self._translate_position_px2logic(event.x, event.y)
        if target_position is None:
            return

        result = self.controller.click_square(target_position, promotion_provider=self.pawn_promotion)
        if result.moved:
            self.draw_moves()
        elif result.invalid_reason in {"illegal_move", "illegal_replay_move"}:
            self._print_invalid_move(result)

        self.refresh_board()

    def _print_invalid_move(self, result: MoveAttempt) -> None:
        print("Movimiento inválido")
        if result.piece and result.origin:
            print(f"Los movimientos válidos para la pieza {result.piece} en {result.origin} son:")
        else:
            print("Los movimientos válidos para esa pieza son:")
        print(list(result.legal_targets) if result.legal_targets else "Ninguno")

    def update_clock(self) -> None:
        if self.controller.white_turn:
            if self.white_time > 0:
                self.white_time += self.increments
                self.white_time -= 1
        else:
            if self.black_time > 0:
                self.black_time += self.increments
                self.black_time -= 1

        white_minutes, white_seconds = divmod(self.white_time, 60)
        black_minutes, black_seconds = divmod(self.black_time, 60)
        self.offboard.itemconfig(self.clock_white_id, text=f"White: {white_minutes:02d}:{white_seconds:02d}")
        self.offboard.itemconfig(self.clock_black_id, text=f"Black: {black_minutes:02d}:{black_seconds:02d}")

        if self.white_time > 0 and self.black_time > 0:
            self.master.after(1000, self.update_clock)

    def refresh_board(self) -> None:
        self.board.delete("all")
        self.draw_board()

    def new_game(self) -> None:
        self.controller.new_game()
        self.white_time = 180
        self.black_time = 180
        self.increments = 0
        self.refresh_board()
        self.draw_moves(see_end=False)
        self.update_clock()

    def load_game(self) -> None:
        filename = filedialog.askopenfilename(
            initialdir="test/test_games",
            title="Select YAML file",
            filetypes=(("YAML files", "*.yaml"), ("PGN files", "*.pgn"), ("All files", "*.*")),
        )
        if not filename:
            return

        self.controller.load_game(filename)
        self.refresh_board()
        self.draw_moves(see_beginning=True, see_end=False)

    def save_game(self) -> None:
        filename = filedialog.asksaveasfilename(
            initialdir="test/test_games",
            title="Save YAML file",
            defaultextension=".yaml",
            filetypes=(("YAML files", "*.yaml"), ("PGN files", "*.pgn"), ("All files", "*.*")),
        )
        if filename:
            self.controller.save_game(filename)

    def go_to_first(self) -> None:
        self.controller.go_to_first()
        self.refresh_board()
        self.draw_moves(see_beginning=True, see_end=False)

    def previous_step(self) -> None:
        if self.controller.previous_step():
            self.refresh_board()
            self.draw_moves(see_end=False)

    def execute_move(self) -> None:
        result = self.controller.execute_current_replay_move()
        if not result.moved and result.invalid_reason not in {"no_replay_move"}:
            self._print_invalid_move(result)

        self.refresh_board()
        self.draw_moves(see_end=False)

    def next_step(self) -> None:
        if self.controller.next_step():
            self.refresh_board()
            self.draw_moves(see_end=False)

    def go_to_last(self) -> None:
        if self.controller.go_to_last():
            self.refresh_board()
            self.draw_moves(see_end=True)
