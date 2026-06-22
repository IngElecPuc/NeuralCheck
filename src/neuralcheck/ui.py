from pathlib import Path
from typing import Dict, Optional, Tuple
import tkinter as tk
from tkinter import filedialog

import yaml
from PIL import Image, ImageOps, ImageTk

from neuralcheck.application.clock import (
    AUTO_START,
    BLACK_SIGNAL_START,
    BLITZ,
    BULLET,
    CORRESPONDENCE,
    CORRESPONDENCE_CATEGORY,
    RAPID,
    TOURNAMENT,
    ChessClock,
    TIME_CONTROLS_BY_CATEGORY,
)
from neuralcheck.application.game_controller import GameController, MoveAttempt
from neuralcheck.application.theory_controller import TheoryController
from neuralcheck.board_overlays import BoardArrow, is_knight_jump
from neuralcheck.ui_position_editor import PositionEditorWindow
from neuralcheck.ui_theory import TheoryWindow


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
        self.master.title("NeuralCheck")
        self.rotation = rotation  # False for White's view, True for Black's view.
        self.controller = controller if controller is not None else GameController()
        self.theory_controller = TheoryController.with_sqlite(game_controller=self.controller)
        self.theory_window: Optional[TheoryWindow] = None
        self.clock = ChessClock.rapid_3_0()
        self.clock_after_id: Optional[str] = None
        self.clock_control_var = tk.StringVar(master, value=self.clock.mode)
        self.clock_start_policy_var = tk.StringVar(master, value=self.clock.start_policy)
        self.coordinates = True
        self.coordinates_var = tk.BooleanVar(master, value=True)
        self.board_view_var = tk.StringVar(master, value="black" if self.rotation else "white")
        self.history_visible_var = tk.BooleanVar(master, value=True)
        self.theory_continuation_arrows_var = tk.BooleanVar(master, value=True)
        self.theory_auto_save_var = tk.BooleanVar(master, value=False)
        self._theory_mode_active = False
        self._clock_panel_visible: Optional[bool] = None
        self._base_window_width = 0
        self._base_window_height = 0
        self.manual_board_arrows: list[BoardArrow] = []
        self._board_arrow_drag_origin: Optional[str] = None
        self._board_arrow_drag_target: Optional[str] = None

        master.rowconfigure(0, weight=1)
        master.columnconfigure(0, weight=1)

        self._build_menu(master)
        self._build_layout(master)
        self._configure_window_size(master)
        master.protocol("WM_DELETE_WINDOW", self.close)

        self.pieces = self._load_pieces()
        self.preview_pieces = self._load_pieces(size=20)
        self.cols_str = ["a", "b", "c", "d", "e", "f", "g", "h"]
        if self.rotation:
            self.cols_str = self.cols_str[::-1]

        self.draw_board()
        self.draw_moves(see_end=False)
        self.board.bind("<Button-1>", self.on_click)
        self.board.bind("<ButtonPress-3>", self.on_board_arrow_start)
        self.board.bind("<B3-Motion>", self.on_board_arrow_motion)
        self.board.bind("<ButtonRelease-3>", self.on_board_arrow_release)
        self.start_clock()

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
        archivo_menu.add_command(label="Configurar posición", command=self.open_position_editor)
        archivo_menu.add_separator()
        archivo_menu.add_command(label="Salir", command=master.quit)

        settings_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Configuración", menu=settings_menu)
        clock_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="Reloj", menu=clock_menu)
        self._build_clock_menu(clock_menu)

        board_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="Tablero", menu=board_menu)
        self._build_board_menu(board_menu)

        view_menu = tk.Menu(settings_menu, tearoff=0)
        settings_menu.add_cascade(label="Vista", menu=view_menu)
        self._build_view_menu(view_menu)

        theory_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Teoría", menu=theory_menu)
        theory_menu.add_command(label="Abrir panel de teoría", command=self.open_theory_panel)
        theory_menu.add_checkbutton(
            label="Mostrar flechas de continuación",
            variable=self.theory_continuation_arrows_var,
            command=self.refresh_board,
        )

    def _build_clock_menu(self, clock_menu: tk.Menu) -> None:
        grouped_controls = (
            ("Bala", BULLET),
            ("Blitz", BLITZ),
            ("Rápida", RAPID),
            ("FIDE", TOURNAMENT),
            ("Correspondencia", CORRESPONDENCE_CATEGORY),
        )
        for label, category in grouped_controls:
            submenu = tk.Menu(clock_menu, tearoff=0)
            clock_menu.add_cascade(label=label, menu=submenu)
            for control in TIME_CONTROLS_BY_CATEGORY[category]:
                submenu.add_radiobutton(
                    label=control.label,
                    variable=self.clock_control_var,
                    value=control.key,
                    command=lambda key=control.key: self.set_clock_control(key),
                )

        clock_menu.add_separator()
        start_menu = tk.Menu(clock_menu, tearoff=0)
        clock_menu.add_cascade(label="Inicio", menu=start_menu)
        start_menu.add_radiobutton(
            label="Nueva partida inicia el reloj",
            variable=self.clock_start_policy_var,
            value=AUTO_START,
            command=lambda: self.set_clock_start_policy(AUTO_START),
        )
        start_menu.add_radiobutton(
            label="Esperar señal de negras",
            variable=self.clock_start_policy_var,
            value=BLACK_SIGNAL_START,
            command=lambda: self.set_clock_start_policy(BLACK_SIGNAL_START),
        )
        start_menu.add_command(label="Dar señal para iniciar blancas", command=self.signal_clock_start)

        clock_menu.add_separator()
        clock_menu.add_command(label="Pausar reloj", command=self.pause_clock)
        clock_menu.add_command(label="Reanudar reloj", command=self.resume_clock)

    def _build_board_menu(self, board_menu: tk.Menu) -> None:
        board_menu.add_checkbutton(
            label="Mostrar coordenadas",
            variable=self.coordinates_var,
            command=self.toggle_coordinates,
        )

    def _build_view_menu(self, view_menu: tk.Menu) -> None:
        view_menu.add_radiobutton(
            label="Vista blancas",
            variable=self.board_view_var,
            value="white",
            command=lambda: self.set_board_view("white"),
        )
        view_menu.add_radiobutton(
            label="Vista negras",
            variable=self.board_view_var,
            value="black",
            command=lambda: self.set_board_view("black"),
        )
        view_menu.add_separator()
        view_menu.add_checkbutton(
            label="Mostrar historial",
            variable=self.history_visible_var,
            command=self.toggle_history_panel,
        )

    def _build_layout(self, master) -> None:
        self.main_frame = tk.Frame(master)
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.rowconfigure(0, weight=1)
        self.main_frame.rowconfigure(1, weight=0)
        self.main_frame.columnconfigure(0, weight=1)
        self.main_frame.columnconfigure(1, weight=0)

        self._build_board_panel()
        self._build_history_panel()
        self._build_control_panel()

    def _configure_window_size(self, master) -> None:
        """Keep the board from being clipped by fixed config dimensions."""
        master.update_idletasks()
        configured_width = int(self.config["Size"].get("width", 0))
        configured_height = int(self.config["Size"].get("height", 0))
        required_width = max(configured_width, master.winfo_reqwidth())
        required_height = max(configured_height, master.winfo_reqheight())
        self._base_window_width = required_width
        self._base_window_height = required_height
        master.minsize(required_width, required_height)
        master.geometry(f"{required_width}x{required_height}")

    def _build_board_panel(self) -> None:
        self.panel_canvas = tk.Frame(self.main_frame)
        self.panel_canvas.grid(row=0, column=0, sticky="nw")
        self.panel_canvas.columnconfigure(0, weight=0)
        self.panel_canvas.columnconfigure(1, weight=0)

        self.offboard = tk.Canvas(
            self.panel_canvas,
            width=self.cell_size * 3,
            height=self.cell_size * 8,
        )
        self.offboard.grid(row=0, column=0)
        self.clock_white_id = self.offboard.create_text(
            self.cell_size * 1.5,
            self.cell_size,
            text="Blancas: 03:00",
            font=("Arial", 12, "bold"),
        )
        self.clock_black_id = self.offboard.create_text(
            self.cell_size * 1.5,
            self.cell_size * 7,
            text="Negras: 03:00",
            font=("Arial", 12, "bold"),
        )
        self.clock_status_id = self.offboard.create_text(
            self.cell_size * 1.5,
            self.cell_size * 4,
            text="Blitz 3+0",
            font=("Arial", 9),
            width=self.cell_size * 2.8,
            justify="center",
        )

        self.board = tk.Canvas(
            self.panel_canvas,
            width=self.cell_size * 8,
            height=self.cell_size * 8,
        )
        self.board.grid(row=0, column=1)

    def _build_history_panel(self) -> None:
        self.panel_history = tk.Frame(self.main_frame)
        self.panel_history.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=10, pady=10)
        self.panel_history.rowconfigure(0, weight=1)
        self.panel_history.columnconfigure(0, weight=1)

        self.history_text = tk.Text(self.panel_history, width=25, height=24, wrap=tk.WORD)
        self.history_text.grid(row=0, column=0, sticky="nsew")
        self.history_scrollbar = tk.Scrollbar(self.panel_history, command=self.history_text.yview)
        self.history_scrollbar.grid(row=0, column=1, sticky="ns")
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

        self.history_hint = tk.Label(
            self.panel_history,
            text="Click en una jugada para saltar a esa posición",
            font=("Arial", 9),
        )
        self.history_hint.grid(row=2, column=0, columnspan=2, sticky="w")

    def _build_control_panel(self) -> None:
        self.panel_controls = tk.Frame(self.main_frame)
        self.panel_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=6)
        self.panel_controls.columnconfigure(0, weight=0)
        self.panel_controls.columnconfigure(1, weight=0)

        self.controls_spacer = tk.Frame(self.panel_controls, width=self.cell_size * 3, height=1)
        self.controls_spacer.grid(row=0, column=0, sticky="w")
        self.controls_spacer.grid_propagate(False)

        self.board_controls = tk.Frame(self.panel_controls)
        self.board_controls.grid(row=0, column=1, sticky="w")

        self.basic_controls = tk.Frame(self.board_controls)
        self.basic_controls.grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.board_view_toggle_button = tk.Button(
            self.basic_controls,
            width=4,
            font=("Arial", 14, "bold"),
            command=self.toggle_board_view,
        )
        self.board_view_toggle_button.grid(row=0, column=1, padx=2, pady=(0, 2))
        self.new_button = tk.Button(self.basic_controls, text="New Game", command=self.new_game)
        self.new_button.grid(row=1, column=0, padx=2, pady=2)
        self.load_button = tk.Button(self.basic_controls, text="Load Game", command=self.load_game)
        self.load_button.grid(row=1, column=1, padx=2, pady=2)
        self.save_button = tk.Button(self.basic_controls, text="Save Game", command=self.save_game)
        self.save_button.grid(row=1, column=2, padx=2, pady=2)
        self._sync_board_view_toggle_button()

        self.theory_board_controls = tk.LabelFrame(self.board_controls, text="Teoría desde tablero")
        self.theory_board_controls.grid(row=0, column=1, sticky="w", padx=(6, 0), pady=0)
        self.theory_status_var = tk.StringVar(value="Mueve una pieza desde el nodo seleccionado para preparar una rama.")
        self.add_theory_node_button = tk.Button(
            self.theory_board_controls,
            text="Agregar",
            command=self.add_theory_node_from_board,
            state="disabled",
            width=10,
        )
        self.add_theory_node_button.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        self.prepare_theory_move_button = tk.Button(
            self.theory_board_controls,
            text="Nueva",
            command=self.prepare_theory_move_from_board,
            state="disabled",
            width=10,
        )
        self.prepare_theory_move_button.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        self.auto_theory_save_button = tk.Button(
            self.theory_board_controls,
            text="Auto OFF",
            command=self.toggle_theory_auto_save,
            width=10,
        )
        self._auto_theory_save_default_style = {
            "bg": self.auto_theory_save_button.cget("background"),
            "fg": self.auto_theory_save_button.cget("foreground"),
            "activebackground": self.auto_theory_save_button.cget("activebackground"),
            "activeforeground": self.auto_theory_save_button.cget("activeforeground"),
        }
        self.auto_theory_save_button.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        self.cancel_theory_move_button = tk.Button(
            self.theory_board_controls,
            text="Cancelar",
            command=self.cancel_theory_board_move,
            state="disabled",
            width=10,
        )
        self.cancel_theory_move_button.grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        self.theory_board_controls.columnconfigure(0, weight=1)
        self.theory_board_controls.columnconfigure(1, weight=1)
        self._sync_theory_auto_save_button()
        self.theory_board_controls.grid_remove()

    def draw_moves(self, see_beginning: bool = False, see_end: bool = True) -> None:
        current_view = self.history_text.yview()[0]
        self.history_text.config(state="normal")
        self.history_text.delete("1.0", tk.END)

        for row in self.controller.history_rows():
            self.history_text.insert(tk.END, f"{row.turn_number}\t")

            white_pointer = "➡" if row.white_pointer else ""
            white_tag = f"move_{row.turn_index}_white"
            self.history_text.insert(tk.END, white_pointer + row.white_move, (white_tag,))
            self.history_text.tag_bind(
                white_tag,
                "<Button-1>",
                lambda event, turn=row.turn_index: self.jump_to_move(turn, True),
            )
            self.history_text.tag_config(white_tag, foreground="black", underline=False)

            self.history_text.insert(tk.END, "\t")
            if row.black_move:
                black_pointer = "➡" if row.black_pointer else ""
                black_tag = f"move_{row.turn_index}_black"
                self.history_text.insert(tk.END, black_pointer + row.black_move, (black_tag,))
                self.history_text.tag_bind(
                    black_tag,
                    "<Button-1>",
                    lambda event, turn=row.turn_index: self.jump_to_move(turn, False),
                )
                self.history_text.tag_config(black_tag, foreground="black", underline=False)
            self.history_text.insert(tk.END, "\n")

        self.history_text.config(state="disabled")

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
        self._draw_board_overlays()
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

    def _draw_board_overlays(self) -> None:
        self._draw_theory_continuation_arrows()
        self._draw_manual_board_arrows()
        self._draw_board_arrow_preview()

    def _draw_theory_continuation_arrows(self) -> None:
        if not self.theory_continuation_arrows_var.get():
            return
        if self.theory_window is None or not self.theory_window.exists():
            return
        if self.theory_controller.selected_node_id is None:
            return
        try:
            hints = self.theory_controller.continuation_move_hints()
        except Exception:
            return
        for _child_id, _move_san, hint in hints:
            if not hint.complete:
                continue
            self._draw_board_arrow(hint.from_square, hint.to_square)

    def _draw_manual_board_arrows(self) -> None:
        for arrow in self.manual_board_arrows:
            self._draw_board_arrow(
                arrow.from_square,
                arrow.to_square,
                color=arrow.color,
                halo_color=arrow.halo_color,
            )

    def _draw_board_arrow_preview(self) -> None:
        if self._board_arrow_drag_origin is None or self._board_arrow_drag_target is None:
            return
        if self._board_arrow_drag_origin == self._board_arrow_drag_target:
            return
        self._draw_board_arrow(
            self._board_arrow_drag_origin,
            self._board_arrow_drag_target,
            color="#d97706",
            halo_color="#fde68a",
        )

    def _draw_board_arrow(
        self,
        from_square: str,
        to_square: str,
        *,
        color: str = "#e0a800",
        halo_color: str = "#f6d065",
    ) -> None:
        if is_knight_jump(from_square, to_square):
            self._draw_knight_board_arrow(from_square, to_square, color=color, halo_color=halo_color)
            return
        x1, y1 = self._square_center(from_square)
        x2, y2 = self._square_center(to_square)
        dx = x2 - x1
        dy = y2 - y1
        distance = max((dx * dx + dy * dy) ** 0.5, 1.0)
        ux = dx / distance
        uy = dy / distance
        margin = self.cell_size * 0.22
        start_x = x1 + ux * margin
        start_y = y1 + uy * margin
        end_x = x2 - ux * margin
        end_y = y2 - uy * margin
        width = max(5, int(self.cell_size * 0.13))
        self._draw_arrow_line(
            ((start_x, start_y), (end_x, end_y)),
            color=color,
            halo_color=halo_color,
            width=width,
        )

    def _draw_knight_board_arrow(
        self,
        from_square: str,
        to_square: str,
        *,
        color: str = "#e0a800",
        halo_color: str = "#f6d065",
    ) -> None:
        x1, y1 = self._square_center(from_square)
        x2, y2 = self._square_center(to_square)
        dx = x2 - x1
        dy = y2 - y1
        if abs(dx) >= abs(dy):
            elbow = (x2, y1)
        else:
            elbow = (x1, y2)

        margin = self.cell_size * 0.22
        first_start = self._point_toward((x1, y1), elbow, margin)
        final_end = self._point_toward((x2, y2), elbow, margin)
        width = max(5, int(self.cell_size * 0.13))
        self._draw_arrow_line(
            (first_start, elbow, final_end),
            color=color,
            halo_color=halo_color,
            width=width,
        )

    def _draw_arrow_line(
        self,
        points: Tuple[Tuple[float, float], ...],
        *,
        color: str,
        halo_color: str,
        width: int,
    ) -> None:
        if len(points) < 2:
            return
        for index, (start, end) in enumerate(zip(points, points[1:])):
            arrow = tk.LAST if index == len(points) - 2 else tk.NONE
            self.board.create_line(
                start[0],
                start[1],
                end[0],
                end[1],
                fill=halo_color,
                width=width + 4,
                arrow=arrow,
                arrowshape=(20, 24, 8),
            )
        for index, (start, end) in enumerate(zip(points, points[1:])):
            arrow = tk.LAST if index == len(points) - 2 else tk.NONE
            self.board.create_line(
                start[0],
                start[1],
                end[0],
                end[1],
                fill=color,
                width=width,
                arrow=arrow,
                arrowshape=(18, 22, 7),
            )

    def _point_toward(
        self,
        point: Tuple[float, float],
        target: Tuple[float, float],
        distance: float,
    ) -> Tuple[float, float]:
        dx = target[0] - point[0]
        dy = target[1] - point[1]
        norm = max((dx * dx + dy * dy) ** 0.5, 1.0)
        return point[0] + dx / norm * distance, point[1] + dy / norm * distance

    def _square_center(self, position: str) -> Tuple[float, float]:
        x, y = self._translate_position_logic2px(position)
        return x + self.cell_size / 2, y + self.cell_size / 2

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

    def _load_pieces(self, size: Optional[int] = None) -> Dict[str, ImageTk.PhotoImage]:
        target_size = size or self.cell_size

        def load_and_format(path: str) -> Image.Image:
            image = Image.open(self._resolve_asset_path(path)).convert("RGBA")
            image = image.resize((target_size, target_size), Image.Resampling.LANCZOS)
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

    def on_board_arrow_start(self, event: tk.Event) -> None:
        origin = self._translate_position_px2logic(event.x, event.y)
        self._board_arrow_drag_origin = origin
        self._board_arrow_drag_target = origin
        if origin is not None:
            self.board.focus_set()

    def on_board_arrow_motion(self, event: tk.Event) -> None:
        if self._board_arrow_drag_origin is None:
            return
        target = self._translate_position_px2logic(event.x, event.y)
        if target == self._board_arrow_drag_target:
            return
        self._board_arrow_drag_target = target
        self.refresh_board()

    def on_board_arrow_release(self, event: tk.Event) -> None:
        origin = self._board_arrow_drag_origin
        target = self._translate_position_px2logic(event.x, event.y)
        self._board_arrow_drag_origin = None
        self._board_arrow_drag_target = None
        if origin is None or target is None:
            self.refresh_board()
            return
        if origin == target:
            self._clear_manual_board_arrows()
            self.refresh_board()
            return

        arrow = BoardArrow(origin, target)
        if arrow in self.manual_board_arrows:
            self.manual_board_arrows = [existing for existing in self.manual_board_arrows if existing != arrow]
        else:
            self.manual_board_arrows.append(arrow)
        self.refresh_board()

    def _clear_manual_board_arrows(self) -> None:
        self.manual_board_arrows.clear()
        self._board_arrow_drag_origin = None
        self._board_arrow_drag_target = None

    def on_click(self, event: tk.Event) -> None:
        target_position = self._translate_position_px2logic(event.x, event.y)
        if target_position is None:
            return

        if self._theory_has_active_move_draft():
            self.theory_status_var.set("Guarda o cancela la jugada preparada antes de mover otra pieza.")
            return

        result = self.controller.click_square(target_position, promotion_provider=self.pawn_promotion)
        if result.moved:
            self._clear_manual_board_arrows()
            self._on_live_move_completed(result)
            self._register_theory_board_move(result)
            self.draw_moves()
        elif result.invalid_reason in {"illegal_move", "illegal_replay_move"}:
            self._print_invalid_move(result)

        self.refresh_board()

    def _on_live_move_completed(self, result: MoveAttempt) -> None:
        if result.piece is None:
            return
        self.clock.on_move_completed(white_player=result.piece.startswith("white "))
        self._render_clock()

    def _print_invalid_move(self, result: MoveAttempt) -> None:
        print("Movimiento inválido")
        if result.piece and result.origin:
            print(f"Los movimientos válidos para la pieza {result.piece} en {result.origin} son:")
        else:
            print("Los movimientos válidos para esa pieza son:")
        print(list(result.legal_targets) if result.legal_targets else "Ninguno")

    def open_position_editor(self) -> None:
        PositionEditorWindow(
            master=self.master,
            controller=self.controller,
            pieces_images=self.pieces,
            cell_size=self.cell_size,
            rotation=self.rotation,
            on_apply=self._on_position_editor_apply,
        )

    def _on_position_editor_apply(self) -> None:
        self._clear_manual_board_arrows()
        self.refresh_board()
        self.draw_moves(see_beginning=True, see_end=False)

    def jump_to_move(self, turn_index: int, white_player: bool) -> None:
        if self.controller.jump_to_move(turn_index, white_player):
            self._clear_manual_board_arrows()
            self.refresh_board()
            self.draw_moves(see_end=False)


    def open_theory_panel(self) -> None:
        self._enter_theory_mode()
        if self.theory_window is not None and self.theory_window.exists():
            self.theory_window.set_board_rotation(self.rotation)
            self.theory_window.set_auto_save_from_board(self.theory_auto_save_var.get())
            self.theory_window.focus()
            self.show_theory_board_controls()
            return

        self.theory_window = TheoryWindow(
            master=self.master,
            controller=self.theory_controller,
            on_board_changed=self._on_theory_board_changed,
            on_close=self._on_theory_window_close,
            on_move_draft_changed=self.refresh_theory_board_controls,
            preview_piece_images=self.preview_pieces,
            board_rotation=self.rotation,
        )
        self.theory_window.set_auto_save_from_board(self.theory_auto_save_var.get())
        self.show_theory_board_controls()

    def _on_theory_board_changed(self) -> None:
        self._clear_manual_board_arrows()
        self.refresh_board()
        self.draw_moves(see_beginning=True, see_end=False)

    def _on_theory_window_close(self) -> None:
        self.theory_window = None
        self.hide_theory_board_controls()
        self._exit_theory_mode()

    def _enter_theory_mode(self) -> None:
        self._theory_mode_active = True
        self.set_correspondence_clock()
        self._apply_main_layout_mode()

    def _exit_theory_mode(self) -> None:
        self._theory_mode_active = False
        self.reset_selected_clock_for_game()
        self._apply_main_layout_mode()

    def _apply_main_layout_mode(self) -> None:
        if not hasattr(self, "main_frame"):
            return
        self._set_history_panel_visible(self.history_visible_var.get(), schedule_fit=False)
        if self._theory_mode_active or not self.history_visible_var.get():
            self.main_frame.columnconfigure(0, weight=0)
        else:
            self.main_frame.columnconfigure(0, weight=1)
        self.master.after_idle(self._fit_main_window_to_mode)

    def _fit_main_window_to_mode(self) -> None:
        if not self.master.winfo_exists():
            return
        self.master.update_idletasks()
        compact_width = self._theory_mode_active or not self.history_visible_var.get()
        if compact_width:
            required_width = max(self.main_frame.winfo_reqwidth(), 1)
            required_height = max(self.main_frame.winfo_reqheight(), 1)
            self.master.minsize(required_width, required_height)
            self.master.geometry(f"{required_width}x{required_height}")
            return
        required_width = max(self._base_window_width, self.master.winfo_reqwidth())
        required_height = max(self._base_window_height, self.master.winfo_reqheight())
        self.master.minsize(required_width, required_height)
        self.master.geometry(f"{required_width}x{required_height}")

    def show_theory_board_controls(self) -> None:
        self.theory_board_controls.grid()
        self.refresh_theory_board_controls()

    def hide_theory_board_controls(self) -> None:
        self.theory_board_controls.grid_remove()

    def toggle_theory_auto_save(self) -> None:
        self.theory_auto_save_var.set(not self.theory_auto_save_var.get())
        self._sync_theory_auto_save_button()
        if self.theory_window is not None and self.theory_window.exists():
            self.theory_window.set_auto_save_from_board(self.theory_auto_save_var.get())
        self.refresh_theory_board_controls()

    def _sync_theory_auto_save_button(self) -> None:
        if not hasattr(self, "auto_theory_save_button"):
            return
        if self.theory_auto_save_var.get():
            self.auto_theory_save_button.config(
                text="Auto ON",
                bg="#dcfce7",
                fg="#14532d",
                activebackground="#bbf7d0",
                activeforeground="#14532d",
            )
        else:
            default_style = getattr(self, "_auto_theory_save_default_style", {})
            self.auto_theory_save_button.config(
                text="Auto OFF",
                bg=default_style.get("bg", self.auto_theory_save_button.cget("background")),
                fg=default_style.get("fg", self.auto_theory_save_button.cget("foreground")),
                activebackground=default_style.get("activebackground", self.auto_theory_save_button.cget("activebackground")),
                activeforeground=default_style.get("activeforeground", self.auto_theory_save_button.cget("activeforeground")),
            )

    def toggle_history_panel(self) -> None:
        self._set_history_panel_visible(self.history_visible_var.get(), schedule_fit=True)

    def _set_history_panel_visible(self, visible: bool, *, schedule_fit: bool = True) -> None:
        if not hasattr(self, "panel_history"):
            return
        if visible:
            self.panel_history.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=10, pady=10)
        else:
            self.panel_history.grid_remove()
        if schedule_fit:
            self._apply_main_layout_mode()

    def refresh_theory_board_controls(self) -> None:
        self._sync_theory_auto_save_button()
        active = self._theory_has_active_move_draft()
        state = "normal" if active else "disabled"
        self.add_theory_node_button.config(state=state)
        self.prepare_theory_move_button.config(state=state)
        self.cancel_theory_move_button.config(state=state)
        if active and self.theory_window is not None:
            draft = self.theory_controller.get_move_draft()
            if draft is not None:
                self.theory_status_var.set(f"Jugada preparada: {draft.move_san}")
        elif self.theory_window is not None:
            self.theory_status_var.set("Mueve una pieza desde el nodo seleccionado para preparar una rama.")

    def add_theory_node_from_board(self) -> None:
        if self.theory_window is None:
            return
        self.theory_window.commit_board_move_as_node()
        self.refresh_theory_board_controls()

    def prepare_theory_move_from_board(self) -> None:
        if self.theory_window is None:
            return
        self.theory_window.prepare_board_move_as_form()
        self.refresh_theory_board_controls()

    def cancel_theory_board_move(self) -> None:
        if self.theory_window is None:
            return
        self.theory_window.cancel_board_move_draft()
        self.refresh_theory_board_controls()

    def _register_theory_board_move(self, result: MoveAttempt) -> None:
        if self.theory_window is None or not self.theory_window.exists():
            return
        if self.theory_controller.selected_node_id is None:
            self.theory_status_var.set("Selecciona un nodo de teoría para preparar ramas desde el tablero.")
            return
        self.theory_window.set_auto_save_from_board(self.theory_auto_save_var.get())
        self.theory_window.register_board_move(result.movement)
        self.refresh_theory_board_controls()

    def _theory_has_active_move_draft(self) -> bool:
        return self.theory_window is not None and self.theory_window.exists() and self.theory_window.has_active_move_draft()

    def toggle_board_view(self) -> None:
        self.set_board_view("white" if self.rotation else "black")

    def _sync_board_view_toggle_button(self) -> None:
        if not hasattr(self, "board_view_toggle_button"):
            return
        if self.rotation:
            self.board_view_toggle_button.config(
                text="♟",
                bg="#111111",
                fg="#ffffff",
                activebackground="#333333",
                activeforeground="#ffffff",
                relief="raised",
            )
        else:
            self.board_view_toggle_button.config(
                text="♙",
                bg="#ffffff",
                fg="#111111",
                activebackground="#eeeeee",
                activeforeground="#111111",
                relief="raised",
            )

    def set_board_view(self, view: str) -> None:
        self.rotation = view == "black"
        self.board_view_var.set("black" if self.rotation else "white")
        self._sync_board_view_toggle_button()
        self.cols_str = ["a", "b", "c", "d", "e", "f", "g", "h"]
        if self.rotation:
            self.cols_str = self.cols_str[::-1]
        if self.theory_window is not None and self.theory_window.exists():
            self.theory_window.set_board_rotation(self.rotation)
        self.refresh_board()

    def toggle_coordinates(self) -> None:
        self.coordinates = bool(self.coordinates_var.get())
        self.refresh_board()

    def close(self) -> None:
        self._cancel_clock_callback()
        if self.theory_window is not None and self.theory_window.exists():
            self.theory_window.close()
        self.theory_controller.close()
        self.master.destroy()

    def set_clock_control(self, control_key: str) -> None:
        self.clock.set_time_control(control_key)
        self.clock_control_var.set(control_key)
        self.clock_start_policy_var.set(self.clock.start_policy)
        self.start_clock()

    def set_clock_start_policy(self, start_policy: str) -> None:
        self.clock.set_start_policy(start_policy)
        self.clock_start_policy_var.set(start_policy)
        self.start_clock()

    def signal_clock_start(self) -> None:
        self.clock.signal_start()
        self.start_clock()

    def pause_clock(self) -> None:
        self.clock.pause()
        self.start_clock()

    def resume_clock(self) -> None:
        self.clock.resume()
        self.start_clock()

    def reset_selected_clock_for_game(self) -> None:
        if self.clock_control_var.get() == CORRESPONDENCE:
            self.clock_control_var.set("blitz_3_0")
        self.clock.set_time_control(self.clock_control_var.get())
        self.clock.set_start_policy(self.clock_start_policy_var.get())
        self.start_clock()

    def set_correspondence_clock(self) -> None:
        self.clock.set_time_control(CORRESPONDENCE)
        self.start_clock()

    def start_clock(self) -> None:
        self._cancel_clock_callback()
        self._render_clock()
        if self.clock.snapshot().running:
            self.clock_after_id = self.master.after(1000, self.update_clock)

    def update_clock(self) -> None:
        self.clock.tick(self.controller.white_turn)
        self._render_clock()
        if self.clock.snapshot().running:
            self.clock_after_id = self.master.after(1000, self.update_clock)
        else:
            self.clock_after_id = None

    def _cancel_clock_callback(self) -> None:
        if self.clock_after_id is None:
            return
        try:
            self.master.after_cancel(self.clock_after_id)
        except tk.TclError:
            pass
        self.clock_after_id = None

    def _render_clock(self) -> None:
        snapshot = self.clock.snapshot()
        visible = bool(snapshot.visible and not self._theory_mode_active)
        self._set_clock_panel_visible(visible)
        if not visible:
            self.offboard.itemconfig(self.clock_white_id, text="", state="hidden")
            self.offboard.itemconfig(self.clock_black_id, text="", state="hidden")
            self.offboard.itemconfig(self.clock_status_id, text="", state="hidden")
            return

        self.offboard.itemconfig(
            self.clock_white_id,
            text=snapshot.label_for_white(),
            state="normal",
        )
        self.offboard.itemconfig(
            self.clock_black_id,
            text=snapshot.label_for_black(),
            state="normal",
        )
        self.offboard.itemconfig(
            self.clock_status_id,
            text=snapshot.status_label(),
            state="normal",
        )

    def _set_clock_panel_visible(self, visible: bool) -> None:
        if self._clock_panel_visible == visible:
            return
        self._clock_panel_visible = visible
        if visible:
            self.offboard.grid(row=0, column=0)
            if hasattr(self, "controls_spacer"):
                self.controls_spacer.config(width=self.cell_size * 3)
        else:
            self.offboard.grid_remove()
            if hasattr(self, "controls_spacer"):
                self.controls_spacer.config(width=0)
        self._apply_main_layout_mode()

    def refresh_board(self) -> None:
        self.board.delete("all")
        self.draw_board()

    def new_game(self) -> None:
        self._clear_manual_board_arrows()
        self.controller.new_game()
        self.reset_selected_clock_for_game()
        self.refresh_board()
        self.draw_moves(see_end=False)

    def load_game(self) -> None:
        filename = filedialog.askopenfilename(
            initialdir="test/test_games",
            title="Select YAML file",
            filetypes=(("YAML files", "*.yaml"), ("PGN files", "*.pgn"), ("All files", "*.*")),
        )
        if not filename:
            return

        self._clear_manual_board_arrows()
        self.controller.load_game(filename)
        self.reset_selected_clock_for_game()
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
        self._clear_manual_board_arrows()
        self.controller.go_to_first()
        self.refresh_board()
        self.draw_moves(see_beginning=True, see_end=False)

    def previous_step(self) -> None:
        if self.controller.previous_step():
            self._clear_manual_board_arrows()
            self.refresh_board()
            self.draw_moves(see_end=False)

    def execute_move(self) -> None:
        result = self.controller.execute_current_replay_move()
        if not result.moved and result.invalid_reason not in {"no_replay_move"}:
            self._print_invalid_move(result)

        self._clear_manual_board_arrows()
        self.refresh_board()
        self.draw_moves(see_end=False)

    def next_step(self) -> None:
        if self.controller.next_step():
            self._clear_manual_board_arrows()
            self.refresh_board()
            self.draw_moves(see_end=False)

    def go_to_last(self) -> None:
        if self.controller.go_to_last():
            self._clear_manual_board_arrows()
            self.refresh_board()
            self.draw_moves(see_end=True)
