"""Advanced Tkinter canvas renderer for theory trees.

The map is storage-agnostic: it receives a bounded ``TheoryMapView`` from the
application controller, precomputes a radial layout, and then renders the graph.
Stage 6.5 keeps this as a tree-oriented layout. If theory later supports true
transpositions as a DAG, the renderer can get a second layout strategy without
changing the storage contract.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
import tkinter as tk
from typing import Callable, Dict, Iterable, Mapping, Optional, Tuple

from neuralcheck.application.theory_controller import TheoryController
from neuralcheck.theory.models import TheoryMapNode, TheoryMapView


NAVIGATION_FIXED = "fixed"
NAVIGATION_CONTEXTUAL = "contextual"


# The hover preview favors legibility over ornamental chess glyphs. Uppercase
# means white piece and lowercase means black piece, which remains readable even
# at very small sizes.
PREVIEW_PIECE_SYMBOLS = {
    "P": "P",
    "N": "N",
    "B": "B",
    "R": "R",
    "Q": "Q",
    "K": "K",
    "p": "p",
    "n": "n",
    "b": "b",
    "r": "r",
    "q": "q",
    "k": "k",
}


@dataclass(frozen=True)
class GraphLayoutNode:
    """Computed location for one visible theory node."""

    id: str
    x: float
    y: float
    depth: int


@dataclass(frozen=True)
class GraphLayout:
    """Precomputed map layout consumed by the Tkinter renderer."""

    nodes: Dict[str, GraphLayoutNode]
    center_node_id: Optional[str]


class TheoryMapLayoutEngine:
    """Radial tree layout with ancestor context and minimum-node spacing."""

    def __init__(
        self,
        *,
        node_radius: float,
        forward_step: float,
        backward_step: float,
        rotation_radians: float = 0.0,
        min_margin: float = 28.0,
    ):
        self.node_radius = node_radius
        self.forward_step = forward_step
        self.backward_step = backward_step
        self.rotation_radians = rotation_radians
        self.min_margin = min_margin

    def layout(
        self,
        view: TheoryMapView,
        *,
        selected_node_id: Optional[str],
        center: Tuple[float, float],
    ) -> GraphLayout:
        if not view.nodes:
            return GraphLayout(nodes={}, center_node_id=None)

        nodes_by_id = {node.id: node for node in view.nodes}
        selected_id = selected_node_id if selected_node_id in nodes_by_id else view.root_node_id
        if selected_id not in nodes_by_id:
            selected_id = view.nodes[0].id

        children_by_parent: Dict[str, list[str]] = {node.id: [] for node in view.nodes}
        parent_by_child: Dict[str, str] = {}
        for edge in view.edges:
            if edge.parent_node_id in children_by_parent and edge.child_node_id in nodes_by_id:
                children_by_parent[edge.parent_node_id].append(edge.child_node_id)
                parent_by_child[edge.child_node_id] = edge.parent_node_id

        positions: Dict[str, Tuple[float, float]] = {}
        for node in view.nodes:
            if node.layout_x is not None and node.layout_y is not None:
                positions[node.id] = (float(node.layout_x), float(node.layout_y))
        had_persisted_positions = bool(positions)
        positions.setdefault(selected_id, center)
        weights = self._descendant_weights(selected_id, children_by_parent)
        self._layout_forward_tree(
            node_id=selected_id,
            children_by_parent=children_by_parent,
            weights=weights,
            positions=positions,
            center=center,
            depth=0,
            angle_start=self.rotation_radians - math.radians(125),
            angle_end=self.rotation_radians + math.radians(125),
        )
        self._layout_ancestor_chain(
            selected_id=selected_id,
            parent_by_child=parent_by_child,
            positions=positions,
            center=center,
        )
        self._layout_lateral_context(
            children_by_parent=children_by_parent,
            weights=weights,
            positions=positions,
        )
        if not had_persisted_positions:
            self._separate_overlapping_nodes(positions, locked_node_id=selected_id, center=center)
            self._recenter(positions, selected_id, center)

        return GraphLayout(
            nodes={
                node_id: GraphLayoutNode(
                    id=node_id,
                    x=position[0],
                    y=position[1],
                    depth=nodes_by_id[node_id].depth,
                )
                for node_id, position in positions.items()
                if node_id in nodes_by_id
            },
            center_node_id=selected_id,
        )

    def _descendant_weights(self, root_id: str, children_by_parent: Dict[str, list[str]]) -> Dict[str, int]:
        del root_id  # Kept for backwards compatibility with older tests/callers.
        weights: Dict[str, int] = {}
        visiting: set[str] = set()

        def count(node_id: str) -> int:
            if node_id in weights:
                return weights[node_id]
            if node_id in visiting:
                weights[node_id] = 1
                return 1
            visiting.add(node_id)
            children = children_by_parent.get(node_id, [])
            if not children:
                total = 1
            else:
                total = max(1, sum(count(child_id) for child_id in children))
            visiting.discard(node_id)
            weights[node_id] = total
            return total

        for node_id in children_by_parent:
            count(node_id)
        return weights

    def _layout_forward_tree(
        self,
        *,
        node_id: str,
        children_by_parent: Dict[str, list[str]],
        weights: Dict[str, int],
        positions: Dict[str, Tuple[float, float]],
        center: Tuple[float, float],
        depth: int,
        angle_start: float,
        angle_end: float,
    ) -> None:
        children = children_by_parent.get(node_id, [])
        if not children:
            return

        total_weight = max(1, sum(weights.get(child_id, 1) for child_id in children))
        available_span = max(math.radians(8), angle_end - angle_start)
        min_child_span = math.radians(18)
        cursor = angle_start
        parent_position = positions[node_id]

        for index, child_id in enumerate(children):
            child_weight = weights.get(child_id, 1)
            if index == len(children) - 1:
                child_end = angle_end
            else:
                child_span = max(min_child_span, available_span * child_weight / total_weight)
                child_end = min(angle_end, cursor + child_span)

            angle = (cursor + child_end) / 2
            # Each generation gets a little more distance from its parent so
            # long opening lines do not become a compressed vertical chain.
            radius = self.forward_step * (1.0 + depth * 0.18)
            positions.setdefault(
                child_id,
                (
                    parent_position[0] + math.cos(angle) * radius,
                    parent_position[1] + math.sin(angle) * radius,
                ),
            )
            self._layout_forward_tree(
                node_id=child_id,
                children_by_parent=children_by_parent,
                weights=weights,
                positions=positions,
                center=center,
                depth=depth + 1,
                angle_start=cursor,
                angle_end=child_end,
            )
            cursor = child_end

    def _layout_ancestor_chain(
        self,
        *,
        selected_id: str,
        parent_by_child: Dict[str, str],
        positions: Dict[str, Tuple[float, float]],
        center: Tuple[float, float],
    ) -> None:
        current_id = selected_id
        distance = self.backward_step
        angle = self.rotation_radians + math.pi
        x, y = center
        while current_id in parent_by_child:
            parent_id = parent_by_child[current_id]
            x = x + math.cos(angle) * distance
            y = y + math.sin(angle) * distance
            positions.setdefault(parent_id, (x, y))
            current_id = parent_id
            distance *= 1.08

    def _layout_lateral_context(
        self,
        *,
        children_by_parent: Dict[str, list[str]],
        weights: Dict[str, int],
        positions: Dict[str, Tuple[float, float]],
    ) -> None:
        """Place visible siblings/context branches around already positioned parents.

        The selected line is laid out first. Ancestor context can include siblings
        reached by going back to a parent and then sideways. Those nodes are not
        descendants of the selected node, so they need a second pass to become
        visible and reachable with the keyboard arrows.
        """
        positioned_parent_ids = list(positions.keys())
        for parent_id in positioned_parent_ids:
            children = children_by_parent.get(parent_id, [])
            missing_children = [child_id for child_id in children if child_id not in positions]
            if not missing_children:
                continue

            px, py = positions[parent_id]
            positioned_children = [child_id for child_id in children if child_id in positions]
            if positioned_children:
                reference_child = positioned_children[0]
                cx, cy = positions[reference_child]
                base_angle = math.atan2(cy - py, cx - px)
            else:
                base_angle = self.rotation_radians

            offsets = self._balanced_angle_offsets(len(missing_children), math.radians(42))
            radius = self.forward_step * 1.05
            for child_id, offset in zip(missing_children, offsets):
                angle = base_angle + offset
                positions.setdefault(child_id, (px + math.cos(angle) * radius, py + math.sin(angle) * radius))
                self._layout_forward_tree(
                    node_id=child_id,
                    children_by_parent=children_by_parent,
                    weights=weights,
                    positions=positions,
                    center=positions[child_id],
                    depth=1,
                    angle_start=angle - math.radians(34),
                    angle_end=angle + math.radians(34),
                )

    @staticmethod
    def _balanced_angle_offsets(count: int, step: float) -> list[float]:
        if count <= 0:
            return []
        offsets: list[float] = []
        for index in range(count):
            magnitude = (index // 2 + 1) * step
            sign = 1 if index % 2 == 0 else -1
            offsets.append(sign * magnitude)
        return offsets

    def _separate_overlapping_nodes(
        self,
        positions: Dict[str, Tuple[float, float]],
        *,
        locked_node_id: str,
        center: Tuple[float, float],
    ) -> None:
        min_distance = self.node_radius * 2.0 + self.min_margin
        node_ids = list(positions.keys())
        if len(node_ids) < 2:
            return

        for iteration in range(72):
            moved = False
            for left_index, left_id in enumerate(node_ids):
                for right_id in node_ids[left_index + 1 :]:
                    x1, y1 = positions[left_id]
                    x2, y2 = positions[right_id]
                    dx = x2 - x1
                    dy = y2 - y1
                    distance = math.hypot(dx, dy)
                    if distance >= min_distance:
                        continue
                    if distance < 0.001:
                        angle = (iteration + left_index + 1) * 0.91
                        dx = math.cos(angle)
                        dy = math.sin(angle)
                        distance = 1.0
                    overlap = (min_distance - distance) / 2.0
                    push_x = dx / distance * overlap
                    push_y = dy / distance * overlap
                    if left_id != locked_node_id:
                        positions[left_id] = (x1 - push_x, y1 - push_y)
                    if right_id != locked_node_id:
                        positions[right_id] = (x2 + push_x, y2 + push_y)
                    moved = True
            if not moved:
                break

    @staticmethod
    def _recenter(positions: Dict[str, Tuple[float, float]], locked_node_id: str, center: Tuple[float, float]) -> None:
        locked_position = positions.get(locked_node_id)
        if locked_position is None:
            return
        shift_x = center[0] - locked_position[0]
        shift_y = center[1] - locked_position[1]
        if abs(shift_x) < 0.001 and abs(shift_y) < 0.001:
            return
        for node_id, (x, y) in list(positions.items()):
            positions[node_id] = (x + shift_x, y + shift_y)


class TheoryMapCanvas(tk.Frame):
    """Navigable visual map for a selected theory node."""

    def __init__(
        self,
        master: tk.Misc,
        controller: TheoryController,
        on_node_selected: Callable[[str], None],
        navigation_mode_var: Optional[tk.StringVar] = None,
        on_parent_requested: Optional[Callable[[], object]] = None,
        on_first_child_requested: Optional[Callable[[], object]] = None,
        on_previous_sibling_requested: Optional[Callable[[], object]] = None,
        on_next_sibling_requested: Optional[Callable[[], object]] = None,
        on_load_selected_requested: Optional[Callable[[], object]] = None,
        width: int = 760,
        height: int = 430,
        allow_fullscreen: bool = True,
        preview_piece_images: Optional[Mapping[str, tk.PhotoImage]] = None,
    ):
        super().__init__(master)
        self.controller = controller
        self.on_node_selected = on_node_selected
        self.navigation_mode_var = navigation_mode_var or tk.StringVar(self, value=NAVIGATION_FIXED)
        self.on_parent_requested = on_parent_requested
        self.on_first_child_requested = on_first_child_requested
        self.on_previous_sibling_requested = on_previous_sibling_requested
        self.on_next_sibling_requested = on_next_sibling_requested
        self.on_load_selected_requested = on_load_selected_requested
        self.preview_piece_images = dict(preview_piece_images or {})
        self.forward_depth = 4
        self.backward_depth = 2
        self.zoom = 1.0
        self.rotation_radians = 0.0
        self.auto_layout_var = tk.BooleanVar(value=False)
        self.auto_center_var = tk.BooleanVar(value=False)
        self.node_positions: Dict[str, Tuple[float, float]] = {}
        self.node_roles: Dict[str, str] = {}
        self._cached_view: Optional[TheoryMapView] = None
        self._cached_layout: Optional[GraphLayout] = None
        self.tooltip: Optional[tk.Toplevel] = None
        self._fullscreen_window: Optional[tk.Toplevel] = None
        self._allow_fullscreen = allow_fullscreen
        self._last_drag: Optional[Tuple[int, int]] = None
        self._right_drag: Optional[Tuple[int, int]] = None
        self._middle_drag: Optional[Tuple[int, int]] = None
        self._node_drag_id: Optional[str] = None
        self._node_drag_previous: Optional[Tuple[int, int]] = None
        self._subtree_drag_ids: set[str] = set()
        self._subtree_rotate_ids: set[str] = set()
        self._subtree_rotate_center: Optional[Tuple[float, float]] = None
        self._subtree_rotate_previous_angle: Optional[float] = None
        self._depths_loaded_for_book: Optional[str] = None

        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        controls = tk.Frame(self)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=2, pady=2)

        tk.Label(controls, text="Atrás:").grid(row=0, column=0, sticky="w", padx=2)
        self.backward_depth_var = tk.IntVar(value=self.backward_depth)
        self.backward_spinbox = tk.Spinbox(
            controls,
            from_=0,
            to=50,
            width=3,
            textvariable=self.backward_depth_var,
            command=self._on_depth_change,
        )
        self.backward_spinbox.grid(row=0, column=1, sticky="w", padx=2)

        tk.Label(controls, text="Adelante:").grid(row=0, column=2, sticky="w", padx=2)
        self.forward_depth_var = tk.IntVar(value=self.forward_depth)
        self.forward_spinbox = tk.Spinbox(
            controls,
            from_=1,
            to=50,
            width=3,
            textvariable=self.forward_depth_var,
            command=self._on_depth_change,
        )
        self.forward_spinbox.grid(row=0, column=3, sticky="w", padx=2)

        tk.Button(controls, text="Aplicar", command=self._on_depth_change).grid(row=0, column=4, padx=2)
        tk.Button(controls, text="Zoom +", command=self.zoom_in).grid(row=0, column=5, padx=2)
        tk.Button(controls, text="Zoom -", command=self.zoom_out).grid(row=0, column=6, padx=2)
        tk.Button(controls, text="Ajustar a vista", command=self.fit_to_view).grid(row=0, column=7, padx=2)
        tk.Button(controls, text="Centrar", command=self.center_selected).grid(row=0, column=8, padx=2)
        tk.Button(controls, text="↺", command=lambda: self.rotate_by(-math.radians(15))).grid(row=1, column=0, padx=2, pady=(2, 0))
        tk.Button(controls, text="↻", command=lambda: self.rotate_by(math.radians(15))).grid(row=1, column=1, padx=2, pady=(2, 0))
        tk.Button(controls, text="Recalcular", command=lambda: self.refresh(force_layout=True)).grid(row=1, column=2, padx=2, pady=(2, 0))
        self.auto_layout_check = tk.Checkbutton(
            controls,
            text="Autoordenar",
            variable=self.auto_layout_var,
            command=self._on_auto_layout_change,
        )
        self.auto_layout_check.grid(row=1, column=3, padx=2, pady=(2, 0))
        self.auto_center_check = tk.Checkbutton(
            controls,
            text="Autocentrar",
            variable=self.auto_center_var,
            command=lambda: self.refresh(force_layout=self.auto_layout_var.get()),
        )
        self.auto_center_check.grid(row=1, column=4, padx=2, pady=(2, 0))
        tk.Button(controls, text="Restablecer", command=self.reset_view).grid(row=1, column=5, padx=2, pady=(2, 0))
        if self._allow_fullscreen:
            tk.Button(controls, text="Pantalla completa", command=self.open_fullscreen).grid(row=1, column=6, padx=2, pady=(2, 0))

        self.mode_label_var = tk.StringVar(value="Modo: vista fija")
        tk.Label(controls, textvariable=self.mode_label_var, font=("Arial", 8)).grid(row=1, column=7, columnspan=3, padx=(8, 2), sticky="w")

        self.deep_graph_warning_var = tk.StringVar(value="")
        self.deep_graph_warning_label = tk.Label(
            self,
            textvariable=self.deep_graph_warning_var,
            anchor="w",
            foreground="#92400e",
            background="#fef3c7",
            font=("Arial", 8),
        )
        self.deep_graph_warning_label.grid(row=4, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 2))
        self.deep_graph_warning_label.grid_remove()

        self.legend_frame = tk.Frame(self)
        self.legend_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 2))
        tk.Label(self.legend_frame, text="Leyenda:", font=("Arial", 8, "bold")).pack(side="left", padx=(0, 6))
        self._add_legend_item("Seleccionado", "#fff1b8", "#cc7a00")
        self._add_legend_item("↑ padre", "#dbeafe", "#2563eb")
        self._add_legend_item("↓ hijos", "#dcfce7", "#16a34a")
        self._add_legend_item("←/→ hermanos", "#ede9fe", "#7c3aed")

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
        self.canvas.grid(row=2, column=0, sticky="nsew", padx=(2, 0), pady=(2, 0))

        self.vertical_scroll = tk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.vertical_scroll.grid(row=2, column=1, sticky="ns", pady=(2, 0))
        self.horizontal_scroll = tk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.horizontal_scroll.grid(row=3, column=0, sticky="ew", padx=(2, 0), pady=(0, 2))
        self.canvas.configure(
            xscrollcommand=self.horizontal_scroll.set,
            yscrollcommand=self.vertical_scroll.set,
        )
        self._bind_mouse_controls()
        self._bind_keyboard_controls()
        self.canvas.bind("<Configure>", lambda event: self.refresh(force_layout=True) if self.auto_layout_var.get() else None)
        self.bind_all("<F12>", lambda event: self.open_fullscreen() if self._allow_fullscreen else None)
        self.navigation_mode_var.trace_add("write", lambda *_args: self.on_navigation_mode_changed())
        self._sync_navigation_mode_defaults(force=True)

    def refresh(self, *, force_layout: bool = False) -> None:
        self._load_depths_from_selected_book_once()
        try:
            self.forward_depth = max(1, min(50, int(self.forward_depth_var.get())))
        except (tk.TclError, ValueError):
            self.forward_depth = 4
        try:
            self.backward_depth = max(0, min(50, int(self.backward_depth_var.get())))
        except (tk.TclError, ValueError):
            self.backward_depth = 2
        view = self._resolve_view(force_layout=force_layout)
        self._update_deep_graph_warning()
        self._render(view, reuse_layout=self._should_reuse_layout(force_layout))

    def force_recalculate(self) -> None:
        self.refresh(force_layout=True)

    def _load_depths_from_selected_book_once(self) -> None:
        book_id = self.controller.selected_book_id
        if book_id is None or book_id == self._depths_loaded_for_book:
            return
        backward_depth, forward_depth = self.controller.selected_book_map_depths()
        self.backward_depth_var.set(backward_depth)
        self.forward_depth_var.set(forward_depth)
        self._depths_loaded_for_book = book_id

    def on_navigation_mode_changed(self) -> None:
        self._sync_navigation_mode_defaults()
        self.refresh(force_layout=True)

    def set_navigation_mode(self, mode: str) -> None:
        if mode not in {NAVIGATION_FIXED, NAVIGATION_CONTEXTUAL}:
            mode = NAVIGATION_FIXED
        self.navigation_mode_var.set(mode)

    def _navigation_mode(self) -> str:
        mode = self.navigation_mode_var.get()
        return mode if mode in {NAVIGATION_FIXED, NAVIGATION_CONTEXTUAL} else NAVIGATION_FIXED

    def _sync_navigation_mode_defaults(self, *, force: bool = False) -> None:
        del force
        mode = self._navigation_mode()
        if mode == NAVIGATION_FIXED:
            self.mode_label_var.set("Modo: vista fija")
            self.auto_layout_var.set(False)
            self.auto_center_var.set(False)
        else:
            self.mode_label_var.set("Modo: contextual")
            self.auto_layout_var.set(True)
            self.auto_center_var.set(True)
        self._sync_auto_center_availability()

    def _on_auto_layout_change(self) -> None:
        if not self.auto_layout_var.get():
            self.auto_center_var.set(False)
        self._sync_auto_center_availability()
        self.refresh(force_layout=self.auto_layout_var.get())

    def _sync_auto_center_availability(self) -> None:
        if self.auto_layout_var.get():
            self.auto_center_check.config(state="normal")
        else:
            self.auto_center_check.config(state="disabled")

    def _resolve_view(self, *, force_layout: bool) -> TheoryMapView:
        if self._navigation_mode() == NAVIGATION_FIXED and not self.auto_layout_var.get() and not force_layout:
            if self._cached_view is not None:
                current_id = self.controller.selected_node_id
                cached_ids = {node.id for node in self._cached_view.nodes}
                if current_id is not None and current_id in cached_ids:
                    return self._with_current_selection(self._cached_view)
        view = self.controller.get_map_view(
            forward_depth=self.forward_depth,
            backward_depth=self.backward_depth,
        )
        self._cached_view = view
        self._cached_layout = None
        return view

    def _should_reuse_layout(self, force_layout: bool) -> bool:
        return self._navigation_mode() == NAVIGATION_FIXED and not self.auto_layout_var.get() and not force_layout

    def _with_current_selection(self, view: TheoryMapView) -> TheoryMapView:
        selected_id = self.controller.selected_node_id
        refreshed_nodes = []
        visible_ids = set()
        for node in view.nodes:
            current_node = self.controller.service.get_node(node.id)
            if current_node is None:
                continue
            label = current_node.name.strip() if current_node.name and current_node.name.strip() else node.label
            refreshed_nodes.append(
                replace(
                    node,
                    label=label,
                    fen=current_node.fen,
                    side_to_move=current_node.side_to_move,
                    evaluation=current_node.evaluation,
                    is_selected=(node.id == selected_id),
                    layout_x=current_node.layout_x,
                    layout_y=current_node.layout_y,
                )
            )
            visible_ids.add(node.id)
        refreshed_edges = tuple(
            edge
            for edge in view.edges
            if edge.parent_node_id in visible_ids and edge.child_node_id in visible_ids
        )
        return replace(
            view,
            selected_node_id=selected_id,
            nodes=tuple(refreshed_nodes),
            edges=refreshed_edges,
        )

    def _update_deep_graph_warning(self) -> None:
        if self._navigation_mode() != NAVIGATION_FIXED:
            self.deep_graph_warning_var.set("")
            self.deep_graph_warning_label.grid_remove()
            return
        max_depth = self.controller.selected_book_max_depth()
        if max_depth > 5:
            self.deep_graph_warning_var.set(
                f"Aviso: esta entrada tiene profundidad {max_depth}. "
                "Vista fija puede quedar estrecha; considera Teoría > Modo de navegación > Contextual."
            )
            self.deep_graph_warning_label.grid()
        else:
            self.deep_graph_warning_var.set("")
            self.deep_graph_warning_label.grid_remove()

    def zoom_in(self) -> None:
        self._set_zoom(self.zoom * 1.15)

    def zoom_out(self) -> None:
        self._set_zoom(self.zoom / 1.15)

    def reset_view(self) -> None:
        self.zoom = 1.0
        self.rotation_radians = 0.0
        self.refresh(force_layout=True)
        self.center_selected()

    def reset_zoom(self) -> None:
        self.reset_view()

    def rotate_by(self, angle_radians: float) -> None:
        self.rotation_radians = (self.rotation_radians + angle_radians) % (math.pi * 2)
        self.refresh(force_layout=True)

    def fit_to_view(self) -> None:
        bbox = self.canvas.bbox("graph") or self.canvas.bbox("all")
        if bbox is None:
            return
        canvas_width = max(self.canvas.winfo_width(), 1)
        canvas_height = max(self.canvas.winfo_height(), 1)
        graph_width = max(float(bbox[2] - bbox[0]), 1.0)
        graph_height = max(float(bbox[3] - bbox[1]), 1.0)
        scale = min(canvas_width * 0.86 / graph_width, canvas_height * 0.86 / graph_height)
        if scale <= 0:
            return
        self._set_zoom(self.zoom * scale, refresh=False)
        self.refresh(force_layout=True)
        self.center_selected()

    def center_selected(self) -> None:
        selected_id = self.controller.selected_node_id
        if selected_id is None or selected_id not in self.node_positions:
            return
        x, y = self.node_positions[selected_id]
        self._center_canvas_on(x, y)

    def open_fullscreen(self) -> None:
        if self._fullscreen_window is not None and self._fullscreen_window.winfo_exists():
            self._fullscreen_window.lift()
            return
        window = tk.Toplevel(self)
        self._fullscreen_window = window
        window.title("Mapa visual de teoría")
        window.attributes("-fullscreen", True)
        window.rowconfigure(0, weight=1)
        window.columnconfigure(0, weight=1)

        def select_from_fullscreen(node_id: str) -> None:
            self.on_node_selected(node_id)
            fullscreen_map.refresh()
            self.refresh()

        fullscreen_map = TheoryMapCanvas(
            window,
            self.controller,
            on_node_selected=select_from_fullscreen,
            navigation_mode_var=self.navigation_mode_var,
            on_parent_requested=self.on_parent_requested,
            on_first_child_requested=self.on_first_child_requested,
            on_previous_sibling_requested=self.on_previous_sibling_requested,
            on_next_sibling_requested=self.on_next_sibling_requested,
            on_load_selected_requested=self.on_load_selected_requested,
            allow_fullscreen=False,
            preview_piece_images=self.preview_piece_images,
        )
        fullscreen_map.zoom = self.zoom
        fullscreen_map.rotation_radians = self.rotation_radians
        fullscreen_map.auto_layout_var.set(self.auto_layout_var.get())
        fullscreen_map.auto_center_var.set(self.auto_center_var.get())
        fullscreen_map.forward_depth_var.set(self.forward_depth)
        fullscreen_map.backward_depth_var.set(self.backward_depth)
        fullscreen_map.grid(row=0, column=0, sticky="nsew")
        fullscreen_map.refresh(force_layout=True)
        window.after(50, fullscreen_map.activate_keyboard_focus)
        window.bind("<Escape>", lambda event: window.destroy())
        window.bind("<F12>", lambda event: window.destroy())
        window.protocol("WM_DELETE_WINDOW", window.destroy)

    def _on_depth_change(self) -> None:
        try:
            backward_depth = max(0, min(50, int(self.backward_depth_var.get())))
            forward_depth = max(1, min(50, int(self.forward_depth_var.get())))
        except (tk.TclError, ValueError):
            backward_depth, forward_depth = self.backward_depth, self.forward_depth
        self.backward_depth_var.set(backward_depth)
        self.forward_depth_var.set(forward_depth)
        self.controller.update_selected_book_map_depths(
            backward_depth=backward_depth,
            forward_depth=forward_depth,
        )
        self.refresh(force_layout=True)

    def _render(self, view: TheoryMapView, *, reuse_layout: bool = False) -> None:
        self._hide_tooltip()
        self.canvas.delete("all")
        self.node_positions.clear()
        self.node_roles.clear()

        width = max(self.canvas.winfo_width(), 1)
        height = max(self.canvas.winfo_height(), 1)
        if not view.nodes:
            self.canvas.create_text(
                width / 2,
                height / 2,
                text="Selecciona una entrada con nodo raíz para ver el mapa.",
                fill="#555555",
                tags=("graph",),
            )
            self.canvas.configure(scrollregion=(0, 0, width, height))
            return

        node_radius = self._node_radius()
        if reuse_layout and self._cached_layout is not None and self._layout_matches_view(self._cached_layout, view):
            layout = self._with_current_layout_selection(self._cached_layout, view.selected_node_id)
        else:
            center = self._current_view_center(width, height)
            engine = TheoryMapLayoutEngine(
                node_radius=node_radius,
                forward_step=max(node_radius * 3.2, 150.0 * self.zoom),
                backward_step=max(node_radius * 3.0, 135.0 * self.zoom),
                rotation_radians=self.rotation_radians,
                min_margin=max(22.0, 30.0 * self.zoom),
            )
            layout = engine.layout(view, selected_node_id=view.selected_node_id, center=center)
            self._cached_layout = layout
            self._persist_layout_if_fixed(view, layout)
        self.node_positions = {node_id: (node.x, node.y) for node_id, node in layout.nodes.items()}
        self.node_roles = self._classify_node_roles(view)

        nodes_by_id = {node.id: node for node in view.nodes}
        for edge in view.edges:
            if edge.parent_node_id not in self.node_positions or edge.child_node_id not in self.node_positions:
                continue
            self._draw_edge(
                self.node_positions[edge.parent_node_id],
                self.node_positions[edge.child_node_id],
                edge.move_san,
                node_radius,
            )

        for node in view.nodes:
            position = self.node_positions.get(node.id)
            if position is None:
                continue
            self._draw_node(node, *position)

        self._update_scrollregion(width, height, node_radius)
        if self.auto_layout_var.get() and self.auto_center_var.get():
            self.center_selected()

    def _persist_layout_if_fixed(self, view: TheoryMapView, layout: GraphLayout) -> None:
        if self._navigation_mode() != NAVIGATION_FIXED:
            return
        stored = {node.id: (node.layout_x, node.layout_y) for node in view.nodes}
        updates: dict[str, tuple[float, float]] = {}
        for node_id, layout_node in layout.nodes.items():
            previous = stored.get(node_id, (None, None))
            if previous[0] is None or previous[1] is None:
                updates[node_id] = (layout_node.x, layout_node.y)
        if updates:
            self.controller.update_node_layouts(updates)

    @staticmethod
    def _layout_matches_view(layout: GraphLayout, view: TheoryMapView) -> bool:
        return set(layout.nodes) == {node.id for node in view.nodes}

    @staticmethod
    def _with_current_layout_selection(layout: GraphLayout, selected_node_id: Optional[str]) -> GraphLayout:
        return GraphLayout(nodes=layout.nodes, center_node_id=selected_node_id)

    def _node_radius(self) -> float:
        return max(24.0, 38.0 * self.zoom)

    def _add_legend_item(self, label: str, fill: str, outline: str) -> None:
        swatch = tk.Canvas(self.legend_frame, width=14, height=14, highlightthickness=0)
        swatch.create_oval(2, 2, 12, 12, fill=fill, outline=outline, width=2)
        swatch.pack(side="left", padx=(0, 2))
        tk.Label(self.legend_frame, text=label, font=("Arial", 8)).pack(side="left", padx=(0, 10))

    @staticmethod
    def _node_style(role: str, is_selected: bool) -> Tuple[str, str, int]:
        if is_selected:
            return "#fff1b8", "#cc7a00", 3
        styles = {
            "ancestor": ("#dbeafe", "#2563eb", 2),
            "descendant": ("#dcfce7", "#16a34a", 2),
            "sibling": ("#ede9fe", "#7c3aed", 2),
            "context": ("#ffffff", "#303030", 1),
        }
        return styles.get(role, styles["context"])

    @staticmethod
    def _classify_node_roles(view: TheoryMapView) -> Dict[str, str]:
        selected_id = view.selected_node_id
        roles: Dict[str, str] = {}
        if selected_id is None:
            return roles

        node_ids = {node.id for node in view.nodes}
        children_by_parent: Dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        parent_by_child: Dict[str, str] = {}
        for edge in view.edges:
            if edge.parent_node_id in node_ids and edge.child_node_id in node_ids:
                children_by_parent.setdefault(edge.parent_node_id, []).append(edge.child_node_id)
                parent_by_child[edge.child_node_id] = edge.parent_node_id

        current_id = selected_id
        while current_id in parent_by_child:
            parent_id = parent_by_child[current_id]
            roles[parent_id] = "ancestor"
            current_id = parent_id

        def mark_descendants(node_id: str) -> None:
            for child_id in children_by_parent.get(node_id, []):
                if child_id == selected_id:
                    continue
                roles.setdefault(child_id, "descendant")
                mark_descendants(child_id)

        mark_descendants(selected_id)

        parent_id = parent_by_child.get(selected_id)
        if parent_id is not None:
            for sibling_id in children_by_parent.get(parent_id, []):
                if sibling_id == selected_id:
                    continue
                roles[sibling_id] = "sibling"

        roles[selected_id] = "selected"
        return roles

    def _current_view_center(self, width: int, height: int) -> Tuple[float, float]:
        left = self.canvas.canvasx(0)
        top = self.canvas.canvasy(0)
        return (left + width / 2, top + height / 2)

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
        start_x = x1 + ux * (node_radius + 3)
        start_y = y1 + uy * (node_radius + 3)
        end_x = x2 - ux * (node_radius + 5)
        end_y = y2 - uy * (node_radius + 5)
        self.canvas.create_line(start_x, start_y, end_x, end_y, arrow=tk.LAST, fill="#606060", width=1.5, tags=("graph",))

        label_x = (start_x + end_x) / 2
        label_y = (start_y + end_y) / 2
        # Text is intentionally not rotated. The graph can rotate, but labels
        # remain horizontal so the user does not need to turn their head.
        self.canvas.create_text(
            label_x,
            label_y,
            text=move_san,
            font=("Arial", max(8, int(9 * self.zoom)), "bold"),
            fill="#303030",
            tags=("graph",),
        )

    def _draw_node(self, node: TheoryMapNode, x: float, y: float) -> None:
        radius = self._node_radius()
        role = self.node_roles.get(node.id, "context")
        fill, outline, border_width = self._node_style(role, node.is_selected)
        tag = f"node:{node.id}"
        tags = ("graph", tag)
        self.canvas.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline=outline,
            width=border_width,
            tags=tags,
        )
        label = self._shorten(node.label, 12)
        evaluation = node.evaluation or "—"
        side = "B" if node.side_to_move == "white" else "N"
        self.canvas.create_text(
            x,
            y - 13 * self.zoom,
            text=label,
            font=("Arial", max(8, int(9 * self.zoom)), "bold"),
            tags=tags,
        )
        self.canvas.create_text(
            x,
            y + 2 * self.zoom,
            text=f"Turno: {side}",
            font=("Arial", max(7, int(8 * self.zoom))),
            tags=tags,
        )
        self.canvas.create_text(
            x,
            y + 17 * self.zoom,
            text=f"Eval: {evaluation}",
            font=("Arial", max(7, int(8 * self.zoom))),
            tags=tags,
        )
        self.canvas.tag_bind(tag, "<Button-1>", lambda event, node_id=node.id: self._on_node_click(event, node_id))
        self.canvas.tag_bind(tag, "<Double-ButtonPress-1>", lambda event, node_id=node.id: self._start_node_drag(event, node_id))
        self.canvas.tag_bind(tag, "<Control-ButtonPress-1>", lambda event, node_id=node.id: self._start_subtree_drag(event, node_id))
        self.canvas.tag_bind(tag, "<Control-ButtonPress-3>", lambda event, node_id=node.id: self._start_subtree_rotate(event, node_id))
        self.canvas.tag_bind(tag, "<Enter>", lambda event, node=node: self._show_tooltip(event, node))
        self.canvas.tag_bind(tag, "<Leave>", lambda event: self._hide_tooltip())

    def _on_node_click(self, event: tk.Event, node_id: str) -> None:
        del event
        self.activate_keyboard_focus()
        self.on_node_selected(node_id)

    def _update_scrollregion(self, width: int, height: int, node_radius: float) -> None:
        bbox = self.canvas.bbox("graph") or self.canvas.bbox("all")
        if bbox is None:
            self.canvas.configure(scrollregion=(0, 0, width, height))
            return
        # Keep a larger virtual world around the graph. This makes mouse pan
        # and rotation feel less boxed-in when the current subgraph is small.
        margin = int(max(node_radius + 180, width * 0.75, height * 0.75))
        x1, y1, x2, y2 = bbox
        self.canvas.configure(
            scrollregion=(
                min(-margin, x1 - margin),
                min(-margin, y1 - margin),
                max(width + margin, x2 + margin),
                max(height + margin, y2 + margin),
            )
        )

    def _center_canvas_on(self, x: float, y: float) -> None:
        bbox = self.canvas.cget("scrollregion")
        if not bbox:
            return
        left, top, right, bottom = [float(value) for value in bbox.split()]
        region_width = max(right - left, 1.0)
        region_height = max(bottom - top, 1.0)
        canvas_width = max(self.canvas.winfo_width(), 1)
        canvas_height = max(self.canvas.winfo_height(), 1)
        x_fraction = (x - left - canvas_width / 2) / max(region_width - canvas_width, 1.0)
        y_fraction = (y - top - canvas_height / 2) / max(region_height - canvas_height, 1.0)
        self.canvas.xview_moveto(max(0.0, min(1.0, x_fraction)))
        self.canvas.yview_moveto(max(0.0, min(1.0, y_fraction)))

    def _set_zoom(self, value: float, refresh: bool = True) -> None:
        self.zoom = max(0.15, min(4.5, value))
        if refresh:
            self.refresh(force_layout=False)
            if self._navigation_mode() == NAVIGATION_CONTEXTUAL or self.auto_center_var.get():
                self.center_selected()

    def _bind_mouse_controls(self) -> None:
        self.canvas.bind("<ButtonPress>", lambda event: self.activate_keyboard_focus(), add="+")
        # Left button drag: pan vertically/horizontally.
        self.canvas.bind("<ButtonPress-1>", self._on_left_button_press, add="+")
        self.canvas.bind("<B1-Motion>", self._on_left_drag, add="+")
        self.canvas.bind("<ButtonRelease-1>", lambda event: self._finish_left_interaction(), add="+")

        # Right button drag: rotate graph around the current view center.
        self.canvas.bind("<ButtonPress-3>", self._on_right_button_press)
        self.canvas.bind("<B3-Motion>", self._on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", lambda event: self._finish_right_interaction())

        # Middle button drag: zoom based on vertical movement.
        self.canvas.bind("<ButtonPress-2>", self._on_middle_button_press)
        self.canvas.bind("<B2-Motion>", self._on_middle_drag)
        self.canvas.bind("<ButtonRelease-2>", lambda event: self._clear_middle_drag())

        # Wheel zoom. Windows/macOS use MouseWheel. Linux/X11 often uses 4/5.
        self.canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.canvas.bind("<Button-4>", lambda event: self._zoom_from_wheel(1))
        self.canvas.bind("<Button-5>", lambda event: self._zoom_from_wheel(-1))

    def _bind_keyboard_controls(self) -> None:
        self.canvas.configure(takefocus=1)
        self.canvas.bind("<FocusIn>", lambda event: self.canvas.configure(highlightbackground="#2563eb", highlightcolor="#2563eb"))
        self.canvas.bind("<FocusOut>", lambda event: self.canvas.configure(highlightbackground="#b0b0b0", highlightcolor="#b0b0b0"))
        self.canvas.bind("<Up>", self._on_keyboard_parent)
        self.canvas.bind("<Down>", self._on_keyboard_first_child)
        self.canvas.bind("<Left>", self._on_keyboard_previous_sibling)
        self.canvas.bind("<Right>", self._on_keyboard_next_sibling)
        self.canvas.bind("<Return>", self._on_keyboard_load_selected)

    def activate_keyboard_focus(self) -> None:
        self.canvas.focus_set()

    def _on_keyboard_parent(self, event: tk.Event):
        del event
        if self.on_parent_requested is not None:
            self.on_parent_requested()
            self.refresh()
        return "break"

    def _on_keyboard_first_child(self, event: tk.Event):
        del event
        if self.on_first_child_requested is not None:
            self.on_first_child_requested()
            self.refresh()
        return "break"

    def _on_keyboard_previous_sibling(self, event: tk.Event):
        del event
        if self.on_previous_sibling_requested is not None:
            self.on_previous_sibling_requested()
            self.refresh()
        return "break"

    def _on_keyboard_next_sibling(self, event: tk.Event):
        del event
        if self.on_next_sibling_requested is not None:
            self.on_next_sibling_requested()
            self.refresh()
        return "break"

    def _on_keyboard_load_selected(self, event: tk.Event):
        del event
        if self.on_load_selected_requested is not None:
            self.on_load_selected_requested()
            self.refresh()
        return "break"

    def _on_left_button_press(self, event: tk.Event) -> None:
        if self._node_drag_id is not None or self._subtree_drag_ids:
            return
        self._last_drag = (event.x, event.y)
        self.canvas.scan_mark(event.x, event.y)

    def _on_left_drag(self, event: tk.Event) -> None:
        if self._node_drag_id is not None:
            self._drag_node_to(event)
            return
        if self._subtree_drag_ids:
            self._drag_subtree_to(event)
            return
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _finish_left_interaction(self) -> None:
        if self._node_drag_id is not None or self._subtree_drag_ids:
            self._persist_current_layout_positions()
        self._node_drag_id = None
        self._node_drag_previous = None
        self._subtree_drag_ids = set()
        self._clear_left_drag()

    def _clear_left_drag(self) -> None:
        self._last_drag = None

    def _on_right_button_press(self, event: tk.Event) -> None:
        self._right_drag = (event.x, event.y)

    def _on_right_drag(self, event: tk.Event) -> None:
        if self._subtree_rotate_ids:
            self._rotate_subtree_to(event)
            return
        if self._right_drag is None:
            self._right_drag = (event.x, event.y)
            return
        previous_x, previous_y = self._right_drag
        dx = event.x - previous_x
        dy = event.y - previous_y
        delta = dx * 0.008 - dy * 0.003
        if abs(delta) >= 0.001:
            self.rotation_radians = (self.rotation_radians + delta) % (math.pi * 2)
            self.refresh(force_layout=True)
        self._right_drag = (event.x, event.y)

    def _finish_right_interaction(self) -> None:
        if self._subtree_rotate_ids:
            self._persist_current_layout_positions()
        self._subtree_rotate_ids = set()
        self._subtree_rotate_center = None
        self._subtree_rotate_previous_angle = None
        self._clear_right_drag()

    def _clear_right_drag(self) -> None:
        self._right_drag = None


    def _start_node_drag(self, event: tk.Event, node_id: str) -> str:
        self.activate_keyboard_focus()
        self._node_drag_id = node_id
        self._node_drag_previous = (event.x, event.y)
        return "break"

    def _start_subtree_drag(self, event: tk.Event, node_id: str) -> str:
        self.activate_keyboard_focus()
        visible_ids = set(self.node_positions)
        self._subtree_drag_ids = self.controller.get_visible_subtree_ids(node_id, visible_ids)
        self._node_drag_previous = (event.x, event.y)
        return "break"

    def _start_subtree_rotate(self, event: tk.Event, node_id: str) -> str:
        self.activate_keyboard_focus()
        visible_ids = set(self.node_positions)
        self._subtree_rotate_ids = self.controller.get_visible_descendant_ids(node_id, visible_ids)
        if not self._subtree_rotate_ids:
            self._subtree_rotate_ids = set()
            return "break"
        self._subtree_rotate_center = self.node_positions.get(node_id)
        if self._subtree_rotate_center is None:
            self._subtree_rotate_ids = set()
            return "break"
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        cx, cy = self._subtree_rotate_center
        self._subtree_rotate_previous_angle = math.atan2(canvas_y - cy, canvas_x - cx)
        return "break"

    def _drag_node_to(self, event: tk.Event) -> None:
        if self._node_drag_id is None or self._node_drag_previous is None:
            return
        previous_x, previous_y = self._node_drag_previous
        dx = self.canvas.canvasx(event.x) - self.canvas.canvasx(previous_x)
        dy = self.canvas.canvasy(event.y) - self.canvas.canvasy(previous_y)
        self._move_visible_nodes({self._node_drag_id}, dx, dy)
        self._node_drag_previous = (event.x, event.y)

    def _drag_subtree_to(self, event: tk.Event) -> None:
        if not self._subtree_drag_ids or self._node_drag_previous is None:
            return
        previous_x, previous_y = self._node_drag_previous
        dx = self.canvas.canvasx(event.x) - self.canvas.canvasx(previous_x)
        dy = self.canvas.canvasy(event.y) - self.canvas.canvasy(previous_y)
        self._move_visible_nodes(self._subtree_drag_ids, dx, dy)
        self._node_drag_previous = (event.x, event.y)

    def _rotate_subtree_to(self, event: tk.Event) -> None:
        if not self._subtree_rotate_ids or self._subtree_rotate_center is None:
            return
        canvas_x = self.canvas.canvasx(event.x)
        canvas_y = self.canvas.canvasy(event.y)
        cx, cy = self._subtree_rotate_center
        angle = math.atan2(canvas_y - cy, canvas_x - cx)
        if self._subtree_rotate_previous_angle is None:
            self._subtree_rotate_previous_angle = angle
            return
        delta = angle - self._subtree_rotate_previous_angle
        if abs(delta) < 0.001:
            return
        cos_delta = math.cos(delta)
        sin_delta = math.sin(delta)
        for node_id in self._subtree_rotate_ids:
            x, y = self.node_positions.get(node_id, (cx, cy))
            rx = x - cx
            ry = y - cy
            self.node_positions[node_id] = (
                cx + rx * cos_delta - ry * sin_delta,
                cy + rx * sin_delta + ry * cos_delta,
            )
        self._sync_cached_layout_from_node_positions()
        self._redraw_current_cached_view()
        self._subtree_rotate_previous_angle = angle

    def _move_visible_nodes(self, node_ids: set[str], dx: float, dy: float) -> None:
        if not node_ids:
            return
        for node_id in node_ids:
            if node_id not in self.node_positions:
                continue
            x, y = self.node_positions[node_id]
            self.node_positions[node_id] = (x + dx, y + dy)
        self._sync_cached_layout_from_node_positions()
        self._redraw_current_cached_view()

    def _sync_cached_layout_from_node_positions(self) -> None:
        if self._cached_layout is None:
            return
        self._cached_layout = GraphLayout(
            nodes={
                node_id: GraphLayoutNode(
                    id=node_id,
                    x=position[0],
                    y=position[1],
                    depth=self._cached_layout.nodes[node_id].depth if node_id in self._cached_layout.nodes else 0,
                )
                for node_id, position in self.node_positions.items()
            },
            center_node_id=self._cached_layout.center_node_id,
        )

    def _redraw_current_cached_view(self) -> None:
        if self._cached_view is None:
            return
        self._render(self._with_current_selection(self._cached_view), reuse_layout=True)

    def _persist_current_layout_positions(self) -> None:
        if self._navigation_mode() != NAVIGATION_FIXED:
            return
        self.controller.update_node_layouts(dict(self.node_positions))

    def _on_middle_button_press(self, event: tk.Event) -> None:
        self._middle_drag = (event.x, event.y)

    def _on_middle_drag(self, event: tk.Event) -> None:
        if self._middle_drag is None:
            self._middle_drag = (event.x, event.y)
            return
        _, previous_y = self._middle_drag
        dy = previous_y - event.y
        if abs(dy) >= 2:
            factor = 1.0 + max(-0.35, min(0.35, dy / 220.0))
            self._set_zoom(self.zoom * factor)
        self._middle_drag = (event.x, event.y)

    def _clear_middle_drag(self) -> None:
        self._middle_drag = None

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        direction = 1 if event.delta > 0 else -1
        self._zoom_from_wheel(direction)

    def _zoom_from_wheel(self, direction: int) -> None:
        factor = 1.12 if direction > 0 else 1 / 1.12
        self._set_zoom(self.zoom * factor)

    def _show_tooltip(self, event: tk.Event, node: TheoryMapNode) -> None:
        self._hide_tooltip()
        self.tooltip = tk.Toplevel(self)
        self.tooltip.wm_overrideredirect(True)
        self.tooltip.wm_geometry(f"+{event.x_root + 14}+{event.y_root + 14}")
        frame = tk.Frame(self.tooltip, background="white", borderwidth=1, relief="solid")
        frame.pack()
        title = "Blancas" if node.side_to_move == "white" else "Negras"
        tk.Label(frame, text=f"Turno: {title}", background="white", font=("Arial", 9, "bold")).pack(fill="x")
        board = tk.Canvas(frame, width=160, height=160, background="white", highlightthickness=0)
        board.pack(padx=4, pady=(0, 4))
        self._draw_fen_preview(board, node.fen, 20)

    def _hide_tooltip(self) -> None:
        if self.tooltip is not None and self.tooltip.winfo_exists():
            self.tooltip.destroy()
        self.tooltip = None

    def _draw_fen_preview(self, canvas: tk.Canvas, fen: str, cell_size: int) -> None:
        placement = fen.split()[0]
        rows = placement.split("/")
        colors = ("#f0d9b5", "#b58863")
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
                cx = col_index * cell_size + cell_size / 2
                cy = row_index * cell_size + cell_size / 2
                piece_key = self._piece_key_from_fen_token(token)
                piece_image = self.preview_piece_images.get(piece_key)
                if piece_image is not None:
                    canvas.create_image(cx, cy, image=piece_image, anchor="center")
                else:
                    self._draw_preview_piece_fallback(canvas, token, cx, cy)
                col_index += 1

    @staticmethod
    def _piece_key_from_fen_token(token: str) -> str:
        side = "white" if token.isupper() else "black"
        piece_names = {
            "p": "pawn",
            "n": "knight",
            "b": "bishop",
            "r": "rook",
            "q": "queen",
            "k": "king",
        }
        return f"{side} {piece_names[token.lower()]}"

    @staticmethod
    def _draw_preview_piece_fallback(canvas: tk.Canvas, token: str, cx: float, cy: float) -> None:
        is_white = token.isupper()
        text_color = "#fdfdfd" if is_white else "#111111"
        outline_color = "#111111" if is_white else "#fdfdfd"
        canvas.create_text(cx + 1, cy + 1, text=PREVIEW_PIECE_SYMBOLS.get(token, token), fill=outline_color, font=("Arial", 10, "bold"))
        canvas.create_text(cx, cy, text=PREVIEW_PIECE_SYMBOLS.get(token, token), fill=text_color, font=("Arial", 10, "bold"))

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
