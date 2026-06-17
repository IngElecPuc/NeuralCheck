"""Tkinter canvas renderer for theory trees.

This view is intentionally storage-agnostic: it receives a depth-limited
``TheoryMapView`` from the application controller and renders it as a graph.
The layout is still lightweight, but it keeps nodes separated, supports zoom and
scrolling, and provides board previews on hover.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import Callable, Dict, Optional, Tuple

from neuralcheck.application.theory_controller import TheoryController
from neuralcheck.theory.models import TheoryMapNode, TheoryMapView


PIECE_SYMBOLS = {
    "P": "♙",
    "N": "♘",
    "B": "♗",
    "R": "♖",
    "Q": "♕",
    "K": "♔",
    "p": "♟",
    "n": "♞",
    "b": "♝",
    "r": "♜",
    "q": "♛",
    "k": "♚",
}


class TheoryMapCanvas(tk.Frame):
    """Depth-limited visual map for a selected theory node."""

    def __init__(
        self,
        master: tk.Misc,
        controller: TheoryController,
        on_node_selected: Callable[[str], None],
        width: int = 760,
        height: int = 430,
    ):
        super().__init__(master)
        self.controller = controller
        self.on_node_selected = on_node_selected
        self.depth = 4
        self.zoom = 1.0
        self.node_positions: Dict[str, Tuple[float, float]] = {}
        self.tooltip: Optional[tk.Toplevel] = None

        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)

        controls = tk.Frame(self)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=2, pady=2)

        tk.Label(controls, text="Profundidad:").grid(row=0, column=0, sticky="w", padx=2)
        self.depth_var = tk.IntVar(value=self.depth)
        self.depth_spinbox = tk.Spinbox(
            controls,
            from_=1,
            to=8,
            width=3,
            textvariable=self.depth_var,
            command=self._on_depth_change,
        )
        self.depth_spinbox.grid(row=0, column=1, sticky="w", padx=2)
        tk.Button(controls, text="Aplicar", command=self._on_depth_change).grid(row=0, column=2, padx=2)
        tk.Button(controls, text="Zoom +", command=self.zoom_in).grid(row=0, column=3, padx=2)
        tk.Button(controls, text="Zoom -", command=self.zoom_out).grid(row=0, column=4, padx=2)
        tk.Button(controls, text="Restablecer", command=self.reset_zoom).grid(row=0, column=5, padx=2)

        self.canvas = tk.Canvas(
            self,
            width=width,
            height=height,
            background="#f8f8f8",
            highlightthickness=1,
            highlightbackground="#b0b0b0",
            xscrollincrement=20,
            yscrollincrement=20,
        )
        self.canvas.grid(row=1, column=0, sticky="nsew", padx=(2, 0), pady=(2, 0))

        self.vertical_scroll = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.vertical_scroll.grid(row=1, column=1, sticky="ns", pady=(2, 0))
        self.horizontal_scroll = tk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.horizontal_scroll.grid(row=2, column=0, sticky="ew", padx=(2, 0), pady=(0, 2))
        self.canvas.configure(
            xscrollcommand=self.horizontal_scroll.set,
            yscrollcommand=self.vertical_scroll.set,
        )
        self.canvas.bind("<Configure>", lambda event: self.refresh())

    def refresh(self) -> None:
        try:
            self.depth = max(1, int(self.depth_var.get()))
        except (tk.TclError, ValueError):
            self.depth = 4
        view = self.controller.get_map_view(depth=self.depth)
        self._render(view)

    def zoom_in(self) -> None:
        self.zoom = min(3.0, self.zoom + 0.15)
        self.refresh()

    def zoom_out(self) -> None:
        self.zoom = max(0.25, self.zoom - 0.15)
        self.refresh()

    def reset_zoom(self) -> None:
        self.zoom = 1.0
        self.refresh()

    def _on_depth_change(self) -> None:
        self.refresh()

    def _render(self, view: TheoryMapView) -> None:
        self._hide_tooltip()
        self.canvas.delete("all")
        self.node_positions.clear()

        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        if not view.nodes:
            self.canvas.create_text(
                width / 2,
                height / 2,
                text="Selecciona una entrada con nodo raíz para ver el mapa.",
                fill="#555555",
            )
            self.canvas.configure(scrollregion=(0, 0, width, height))
            return

        nodes_by_id = {node.id: node for node in view.nodes}
        children_by_parent: Dict[str, list[str]] = {node.id: [] for node in view.nodes}
        for edge in view.edges:
            if edge.parent_node_id in children_by_parent and edge.child_node_id in nodes_by_id:
                children_by_parent[edge.parent_node_id].append(edge.child_node_id)

        root_id = view.root_node_id or view.nodes[0].id
        center = (width / 2, height / 2)
        node_radius = self._node_radius()
        radius_step = max(node_radius * 2.9, 120.0 * self.zoom)

        weights = self._descendant_weights(root_id, children_by_parent)
        self._layout_radial(
            node_id=root_id,
            children_by_parent=children_by_parent,
            weights=weights,
            center=center,
            radius_step=radius_step,
            depth=0,
            angle_start=-math.pi,
            angle_end=math.pi,
        )
        self._separate_overlapping_nodes(root_id=root_id, center=center, node_radius=node_radius)

        edge_labels = {(edge.parent_node_id, edge.child_node_id): edge.move_san for edge in view.edges}
        for edge in view.edges:
            if edge.parent_node_id not in self.node_positions or edge.child_node_id not in self.node_positions:
                continue
            self._draw_edge(
                self.node_positions[edge.parent_node_id],
                self.node_positions[edge.child_node_id],
                edge_labels[(edge.parent_node_id, edge.child_node_id)],
                node_radius,
            )

        for node in view.nodes:
            position = self.node_positions.get(node.id)
            if position is None:
                continue
            self._draw_node(node, *position)

        bbox = self.canvas.bbox("all")
        if bbox is None:
            self.canvas.configure(scrollregion=(0, 0, width, height))
            return
        margin = int(node_radius + 40)
        x1, y1, x2, y2 = bbox
        self.canvas.configure(
            scrollregion=(
                min(0, x1 - margin),
                min(0, y1 - margin),
                max(width, x2 + margin),
                max(height, y2 + margin),
            )
        )

    def _node_radius(self) -> float:
        return max(26.0, 42.0 * self.zoom)

    def _descendant_weights(self, root_id: str, children_by_parent: Dict[str, list[str]]) -> Dict[str, int]:
        weights: Dict[str, int] = {}

        def count(node_id: str) -> int:
            children = children_by_parent.get(node_id, [])
            if not children:
                weights[node_id] = 1
                return 1
            total = sum(count(child_id) for child_id in children)
            weights[node_id] = max(1, total)
            return weights[node_id]

        count(root_id)
        return weights

    def _layout_radial(
        self,
        node_id: str,
        children_by_parent: Dict[str, list[str]],
        weights: Dict[str, int],
        center: Tuple[float, float],
        radius_step: float,
        depth: int,
        angle_start: float,
        angle_end: float,
    ) -> None:
        center_x, center_y = center
        if depth == 0:
            self.node_positions[node_id] = center
        else:
            angle = (angle_start + angle_end) / 2
            radius = radius_step * depth
            self.node_positions[node_id] = (
                center_x + math.cos(angle) * radius,
                center_y + math.sin(angle) * radius,
            )

        children = children_by_parent.get(node_id, [])
        if not children:
            return

        total_weight = max(1, sum(weights.get(child_id, 1) for child_id in children))
        min_child_span = math.radians(16)
        available_span = angle_end - angle_start
        cursor = angle_start
        for child_id in children:
            child_weight = weights.get(child_id, 1)
            child_span = max(min_child_span, available_span * child_weight / total_weight)
            child_end = min(angle_end, cursor + child_span)
            self._layout_radial(
                node_id=child_id,
                children_by_parent=children_by_parent,
                weights=weights,
                center=center,
                radius_step=radius_step,
                depth=depth + 1,
                angle_start=cursor,
                angle_end=child_end,
            )
            cursor = child_end

    def _separate_overlapping_nodes(
        self,
        root_id: str,
        center: Tuple[float, float],
        node_radius: float,
    ) -> None:
        min_distance = node_radius * 2.0 + max(18.0, 22.0 * self.zoom)
        ids = list(self.node_positions.keys())
        if len(ids) < 2:
            return

        for iteration in range(36):
            moved = False
            for left_index, left_id in enumerate(ids):
                for right_id in ids[left_index + 1 :]:
                    x1, y1 = self.node_positions[left_id]
                    x2, y2 = self.node_positions[right_id]
                    dx = x2 - x1
                    dy = y2 - y1
                    distance = math.hypot(dx, dy)
                    if distance >= min_distance:
                        continue
                    if distance < 0.001:
                        angle = (iteration + left_index + 1) * 0.73
                        dx = math.cos(angle)
                        dy = math.sin(angle)
                        distance = 1.0
                    overlap = (min_distance - distance) / 2.0
                    push_x = dx / distance * overlap
                    push_y = dy / distance * overlap
                    if left_id != root_id:
                        self.node_positions[left_id] = (x1 - push_x, y1 - push_y)
                    if right_id != root_id:
                        self.node_positions[right_id] = (x2 + push_x, y2 + push_y)
                    moved = True
            if not moved:
                break

        root_position = self.node_positions.get(root_id)
        if root_position is None:
            return
        shift_x = center[0] - root_position[0]
        shift_y = center[1] - root_position[1]
        if abs(shift_x) < 0.001 and abs(shift_y) < 0.001:
            return
        for node_id, (x, y) in list(self.node_positions.items()):
            self.node_positions[node_id] = (x + shift_x, y + shift_y)

    def _draw_edge(
        self,
        source: Tuple[float, float],
        target: Tuple[float, float],
        move_san: str,
        node_radius: float,
    ) -> None:
        x1, y1 = source
        x2, y2 = target
        dx = x2 - x1
        dy = y2 - y1
        length = max(math.hypot(dx, dy), 1.0)
        ux = dx / length
        uy = dy / length
        start_x = x1 + ux * (node_radius + 2)
        start_y = y1 + uy * (node_radius + 2)
        end_x = x2 - ux * (node_radius + 4)
        end_y = y2 - uy * (node_radius + 4)
        self.canvas.create_line(start_x, start_y, end_x, end_y, arrow=tk.LAST, fill="#606060", width=1.5)

        label_x = (start_x + end_x) / 2
        label_y = (start_y + end_y) / 2
        self.canvas.create_text(
            label_x,
            label_y,
            text=move_san,
            font=("Arial", max(8, int(9 * self.zoom)), "bold"),
            fill="#303030",
        )

    def _draw_node(self, node: TheoryMapNode, x: float, y: float) -> None:
        radius = self._node_radius()
        fill = "#fff5cc" if node.is_selected else "#ffffff"
        outline = "#cc7a00" if node.is_selected else "#303030"
        border_width = 3 if node.is_selected else 1
        tag = f"node:{node.id}"
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline=outline,
            width=border_width,
            tags=(tag,),
        )
        label = self._shorten(node.label, 12)
        evaluation = node.evaluation or "—"
        side = "B" if node.side_to_move == "white" else "N"
        self.canvas.create_text(
            x,
            y - 14 * self.zoom,
            text=label,
            font=("Arial", max(8, int(9 * self.zoom)), "bold"),
            tags=(tag,),
        )
        self.canvas.create_text(
            x,
            y + 2 * self.zoom,
            text=f"Turno: {side}",
            font=("Arial", max(7, int(8 * self.zoom))),
            tags=(tag,),
        )
        self.canvas.create_text(
            x,
            y + 17 * self.zoom,
            text=f"Eval: {evaluation}",
            font=("Arial", max(7, int(8 * self.zoom))),
            tags=(tag,),
        )
        self.canvas.tag_bind(tag, "<Button-1>", lambda event, node_id=node.id: self.on_node_selected(node_id))
        self.canvas.tag_bind(tag, "<Enter>", lambda event, node=node: self._show_tooltip(event, node))
        self.canvas.tag_bind(tag, "<Leave>", lambda event: self._hide_tooltip())

    def _show_tooltip(self, event: tk.Event, node: TheoryMapNode) -> None:
        self._hide_tooltip()
        self.tooltip = tk.Toplevel(self)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 14}")
        board = tk.Canvas(self.tooltip, width=144, height=144, background="white", highlightthickness=1)
        board.pack()
        self._draw_fen_preview(board, node.fen, 18)

    def _hide_tooltip(self) -> None:
        if self.tooltip is not None and self.tooltip.winfo_exists():
            self.tooltip.destroy()
        self.tooltip = None

    @staticmethod
    def _draw_fen_preview(canvas: tk.Canvas, fen: str, cell_size: int) -> None:
        placement = fen.split()[0]
        rows = placement.split("/")
        colors = ("#eeeeee", "#999999")
        if len(rows) != 8:
            return
        for row_index in range(8):
            col_index = 0
            for token in rows[row_index]:
                if token.isdigit():
                    for _ in range(int(token)):
                        TheoryMapCanvas._draw_preview_square(canvas, row_index, col_index, cell_size, colors)
                        col_index += 1
                    continue
                TheoryMapCanvas._draw_preview_square(canvas, row_index, col_index, cell_size, colors)
                canvas.create_text(
                    col_index * cell_size + cell_size / 2,
                    row_index * cell_size + cell_size / 2,
                    text=PIECE_SYMBOLS.get(token, token),
                    font=("Arial", 10),
                )
                col_index += 1

    @staticmethod
    def _draw_preview_square(canvas: tk.Canvas, row: int, col: int, cell_size: int, colors: Tuple[str, str]) -> None:
        x1 = col * cell_size
        y1 = row * cell_size
        x2 = x1 + cell_size
        y2 = y1 + cell_size
        canvas.create_rectangle(x1, y1, x2, y2, fill=colors[(row + col) % 2], outline="")

    @staticmethod
    def _shorten(value: str, max_len: int) -> str:
        return value if len(value) <= max_len else value[: max_len - 1] + "…"
