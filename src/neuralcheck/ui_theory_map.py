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
from neuralcheck.theory.move_visuals import MoveVisualHint


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
        on_parent_requested: Optional[Callable[[], object]] = None,
        on_first_child_requested: Optional[Callable[[], object]] = None,
        on_previous_sibling_requested: Optional[Callable[[], object]] = None,
        on_next_sibling_requested: Optional[Callable[[], object]] = None,
        on_load_selected_requested: Optional[Callable[[], object]] = None,
        on_node_edit_requested: Optional[Callable[[str], object]] = None,
        width: int = 760,
        height: int = 430,
        allow_fullscreen: bool = True,
        preview_piece_images: Optional[Mapping[str, tk.PhotoImage]] = None,
        board_rotation: bool = False,
    ):
        super().__init__(master)
        self.controller = controller
        self.on_node_selected = on_node_selected
        self.on_parent_requested = on_parent_requested
        self.on_first_child_requested = on_first_child_requested
        self.on_previous_sibling_requested = on_previous_sibling_requested
        self.on_next_sibling_requested = on_next_sibling_requested
        self.on_load_selected_requested = on_load_selected_requested
        self.on_node_edit_requested = on_node_edit_requested
        self.preview_piece_images = dict(preview_piece_images or {})
        self.board_rotation = bool(board_rotation)
        self.forward_depth = 4
        self.backward_depth = 2
        self.zoom = 1.0
        self.rotation_radians = 0.0
        self.camera_x = 0.0
        self.camera_y = 0.0
        self._camera_initialized = False
        self._world_bounds: Tuple[float, float, float, float] = (-1000.0, -1000.0, 1000.0, 1000.0)
        self._undo_stack: list[Dict[str, Tuple[float, float]]] = []
        self._redo_stack: list[Dict[str, Tuple[float, float]]] = []
        self._layout_dirty = False
        self._force_auto_layout = False
        self._auto_save_layout = False
        self.layout_status_var = tk.StringVar(value="")
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
        self._pending_node_click_after_id: Optional[str] = None
        self._pending_node_click_id: Optional[str] = None
        self._subtree_drag_ids: set[str] = set()
        self._subtree_rotate_ids: set[str] = set()
        self._subtree_rotate_center: Optional[Tuple[float, float]] = None
        self._subtree_rotate_previous_angle: Optional[float] = None
        self._depths_loaded_for_book: Optional[str] = None

        self.rowconfigure(2, weight=1)
        self.columnconfigure(0, weight=1)

        controls = tk.Frame(self)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", padx=2, pady=2)
        controls.columnconfigure(0, weight=1)

        compact_controls = tk.Frame(controls)
        compact_controls.grid(row=0, column=0, sticky="w")
        tk.Label(compact_controls, text="Atrás").grid(row=0, column=0, sticky="w", padx=(0, 2))
        self.backward_depth_var = tk.IntVar(value=self.backward_depth)
        self.backward_spinbox = tk.Spinbox(
            compact_controls,
            from_=0,
            to=50,
            width=3,
            textvariable=self.backward_depth_var,
            command=self._on_depth_change,
        )
        self.backward_spinbox.grid(row=0, column=1, sticky="w", padx=2)

        tk.Label(compact_controls, text="Adel.").grid(row=0, column=2, sticky="w", padx=(6, 2))
        self.forward_depth_var = tk.IntVar(value=self.forward_depth)
        self.forward_spinbox = tk.Spinbox(
            compact_controls,
            from_=1,
            to=50,
            width=3,
            textvariable=self.forward_depth_var,
            command=self._on_depth_change,
        )
        self.forward_spinbox.grid(row=0, column=3, sticky="w", padx=2)
        tk.Button(compact_controls, text="Aplicar", command=self._on_depth_change).grid(row=0, column=4, padx=(4, 10))

        tk.Button(compact_controls, text="+", width=3, command=self.zoom_in).grid(row=0, column=5, padx=1)
        tk.Button(compact_controls, text="-", width=3, command=self.zoom_out).grid(row=0, column=6, padx=1)
        tk.Button(compact_controls, text="Encajar", command=self.fit_to_view).grid(row=0, column=7, padx=1)
        tk.Button(compact_controls, text="Centro", command=self.center_selected).grid(row=0, column=8, padx=(1, 6))
        tk.Button(compact_controls, text="↺", width=3, command=lambda: self.rotate_by(-math.radians(15))).grid(row=0, column=9, padx=1)
        tk.Button(compact_controls, text="↻", width=3, command=lambda: self.rotate_by(math.radians(15))).grid(row=0, column=10, padx=(1, 8))
        tk.Button(compact_controls, text="Ordenar", command=self.reorder_layout).grid(row=0, column=11, padx=1)
        self.save_layout_button = tk.Button(compact_controls, text="Guardar", command=self.save_layout, state="disabled")
        self.save_layout_button.grid(row=0, column=12, padx=1)
        self.discard_layout_button = tk.Button(compact_controls, text="Descartar", command=self.discard_layout, state="disabled")
        self.discard_layout_button.grid(row=0, column=13, padx=1)
        self.undo_layout_button = tk.Button(compact_controls, text="↶", width=3, command=self.undo_layout, state="disabled")
        self.undo_layout_button.grid(row=0, column=14, padx=1)
        self.redo_layout_button = tk.Button(compact_controls, text="↷", width=3, command=self.redo_layout, state="disabled")
        self.redo_layout_button.grid(row=0, column=15, padx=1)
        if self._allow_fullscreen:
            tk.Button(compact_controls, text="⛶", width=3, command=self.open_fullscreen).grid(row=0, column=16, padx=(4, 1))
        tk.Label(compact_controls, textvariable=self.layout_status_var, font=("Arial", 8), foreground="#92400e").grid(row=0, column=17, padx=(8, 0), sticky="w")

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

        self.vertical_scroll = tk.Scrollbar(self, orient="vertical", command=self._yscroll)
        self.vertical_scroll.grid(row=2, column=1, sticky="ns", pady=(2, 0))
        self.horizontal_scroll = tk.Scrollbar(self, orient="horizontal", command=self._xscroll)
        self.horizontal_scroll.grid(row=3, column=0, sticky="ew", padx=(2, 0), pady=(0, 2))
        self.canvas.configure(scrollregion=(0, 0, width, height))
        self._bind_mouse_controls()
        self._bind_keyboard_controls()
        self.bind_all("<F12>", lambda event: self.open_fullscreen() if self._allow_fullscreen else None)
        self._sync_layout_buttons()

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
        self._sync_layout_buttons()

    def force_recalculate(self) -> None:
        self.reorder_layout()

    def _load_depths_from_selected_book_once(self) -> None:
        book_id = self.controller.selected_book_id
        if book_id is None or book_id == self._depths_loaded_for_book:
            return
        backward_depth, forward_depth = self.controller.selected_book_map_depths()
        self.backward_depth_var.set(backward_depth)
        self.forward_depth_var.set(forward_depth)
        self._depths_loaded_for_book = book_id

    def set_board_rotation(self, rotation: bool) -> None:
        self.board_rotation = bool(rotation)

    def set_auto_save_layout(self, enabled: bool) -> None:
        self._auto_save_layout = bool(enabled)

    def _base_node_radius(self) -> float:
        return 38.0

    def _zoom_value(self) -> float:
        return max(self.zoom, 0.001)

    def _viewport_size(self) -> Tuple[float, float]:
        return float(max(self.canvas.winfo_width(), 1)), float(max(self.canvas.winfo_height(), 1))

    def _to_screen(self, x: float, y: float) -> Tuple[float, float]:
        width, height = self._viewport_size()
        dx = x - self.camera_x
        dy = y - self.camera_y
        cos_angle = math.cos(self.rotation_radians)
        sin_angle = math.sin(self.rotation_radians)
        rotated_x = dx * cos_angle - dy * sin_angle
        rotated_y = dx * sin_angle + dy * cos_angle
        zoom = self._zoom_value()
        return width / 2 + rotated_x * zoom, height / 2 + rotated_y * zoom

    def _to_world(self, x: float, y: float) -> Tuple[float, float]:
        width, height = self._viewport_size()
        zoom = self._zoom_value()
        sx = (x - width / 2) / zoom
        sy = (y - height / 2) / zoom
        cos_angle = math.cos(self.rotation_radians)
        sin_angle = math.sin(self.rotation_radians)
        world_dx = sx * cos_angle + sy * sin_angle
        world_dy = -sx * sin_angle + sy * cos_angle
        return self.camera_x + world_dx, self.camera_y + world_dy

    def _screen_delta_to_world(self, dx: float, dy: float) -> Tuple[float, float]:
        zoom = self._zoom_value()
        sx = dx / zoom
        sy = dy / zoom
        cos_angle = math.cos(self.rotation_radians)
        sin_angle = math.sin(self.rotation_radians)
        return sx * cos_angle + sy * sin_angle, -sx * sin_angle + sy * cos_angle

    def _set_camera_for_world_at_screen(
        self,
        world_x: float,
        world_y: float,
        screen_x: float,
        screen_y: float,
    ) -> None:
        width, height = self._viewport_size()
        zoom = self._zoom_value()
        sx = (screen_x - width / 2) / zoom
        sy = (screen_y - height / 2) / zoom
        cos_angle = math.cos(self.rotation_radians)
        sin_angle = math.sin(self.rotation_radians)
        world_offset_x = sx * cos_angle + sy * sin_angle
        world_offset_y = -sx * sin_angle + sy * cos_angle
        self.camera_x = world_x - world_offset_x
        self.camera_y = world_y - world_offset_y

    def _resolve_view(self, *, force_layout: bool) -> TheoryMapView:
        if not force_layout and self._cached_view is not None:
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
        return not force_layout

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
        return

    def zoom_in(self) -> None:
        self._set_zoom_around_view_center(self.zoom * 1.15)

    def zoom_out(self) -> None:
        self._set_zoom_around_view_center(self.zoom / 1.15)

    def reset_view(self) -> None:
        """Compatibility hook: reset view transform without recalculating layout."""
        self.zoom = 1.0
        self.rotation_radians = 0.0
        self.refresh(force_layout=False)

    def reset_zoom(self) -> None:
        self.reset_view()

    def rotate_by(self, angle_radians: float) -> None:
        self.rotation_radians = (self.rotation_radians + angle_radians) % (math.pi * 2)
        self.refresh(force_layout=False)

    def fit_to_view(self) -> None:
        if not self.node_positions:
            return
        radius = self._base_node_radius() + 32.0
        xs = [position[0] for position in self.node_positions.values()]
        ys = [position[1] for position in self.node_positions.values()]
        left = min(xs) - radius
        right = max(xs) + radius
        top = min(ys) - radius
        bottom = max(ys) + radius
        width, height = self._viewport_size()
        graph_width = max(right - left, 1.0)
        graph_height = max(bottom - top, 1.0)
        scale = min(width * 0.86 / graph_width, height * 0.86 / graph_height)
        if scale <= 0:
            return
        self.zoom = max(0.15, min(4.5, scale))
        self.camera_x = (left + right) / 2
        self.camera_y = (top + bottom) / 2
        self._camera_initialized = True
        self.refresh(force_layout=False)

    def center_selected(self) -> None:
        selected_id = self.controller.selected_node_id
        if selected_id is None or selected_id not in self.node_positions:
            return
        x, y = self.node_positions[selected_id]
        self._center_canvas_on(x, y)

    def reorder_layout(self) -> None:
        self._record_layout_undo()
        self._force_auto_layout = True
        try:
            self.refresh(force_layout=True)
        finally:
            self._force_auto_layout = False
        self._mark_layout_dirty()

    def save_layout(self) -> None:
        if not self.node_positions:
            return
        self.controller.update_node_layouts(dict(self.node_positions))
        self._layout_dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._cached_view = None
        self._cached_layout = None
        self.refresh(force_layout=False)

    def discard_layout(self) -> None:
        self._layout_dirty = False
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._cached_view = None
        self._cached_layout = None
        self.refresh(force_layout=True)

    def undo_layout(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._snapshot_layout())
        snapshot = self._undo_stack.pop()
        self._apply_layout_snapshot(snapshot)
        self._layout_dirty = True
        self._sync_layout_buttons()

    def redo_layout(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._snapshot_layout())
        snapshot = self._redo_stack.pop()
        self._apply_layout_snapshot(snapshot)
        self._layout_dirty = True
        self._sync_layout_buttons()

    def _snapshot_layout(self) -> Dict[str, Tuple[float, float]]:
        return dict(self.node_positions)

    def _record_layout_undo(self) -> None:
        snapshot = self._snapshot_layout()
        if self._undo_stack and self._undo_stack[-1] == snapshot:
            return
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()
        self._sync_layout_buttons()

    def _apply_layout_snapshot(self, snapshot: Dict[str, Tuple[float, float]]) -> None:
        self.node_positions = dict(snapshot)
        self._sync_cached_layout_from_node_positions()
        self._redraw_current_cached_view()

    def _mark_layout_dirty(self) -> None:
        self._layout_dirty = True
        self._sync_layout_buttons()

    def _sync_layout_buttons(self) -> None:
        if not hasattr(self, "save_layout_button"):
            return
        dirty_state = "normal" if self._layout_dirty else "disabled"
        self.save_layout_button.config(state=dirty_state)
        self.discard_layout_button.config(state=dirty_state)
        self.undo_layout_button.config(state="normal" if self._undo_stack else "disabled")
        self.redo_layout_button.config(state="normal" if self._redo_stack else "disabled")
        self.layout_status_var.set("Layout sin guardar" if self._layout_dirty else "")

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
            on_parent_requested=self.on_parent_requested,
            on_first_child_requested=self.on_first_child_requested,
            on_previous_sibling_requested=self.on_previous_sibling_requested,
            on_next_sibling_requested=self.on_next_sibling_requested,
            on_load_selected_requested=self.on_load_selected_requested,
            on_node_edit_requested=self.on_node_edit_requested,
            allow_fullscreen=False,
            preview_piece_images=self.preview_piece_images,
            board_rotation=self.board_rotation,
        )
        fullscreen_map.zoom = self.zoom
        fullscreen_map.rotation_radians = self.rotation_radians
        fullscreen_map.camera_x = self.camera_x
        fullscreen_map.camera_y = self.camera_y
        fullscreen_map._camera_initialized = self._camera_initialized
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
        self._cached_view = None
        self._cached_layout = None
        self.refresh(force_layout=False)

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

        node_radius_world = self._base_node_radius()
        node_radius = self._node_radius()
        if reuse_layout and self._cached_layout is not None and self._layout_matches_view(self._cached_layout, view):
            layout = self._with_current_layout_selection(self._cached_layout, view.selected_node_id)
        else:
            center = self._current_view_center(width, height)
            engine = TheoryMapLayoutEngine(
                node_radius=node_radius_world,
                forward_step=max(node_radius_world * 3.2, 150.0),
                backward_step=max(node_radius_world * 3.0, 135.0),
                rotation_radians=0.0,
                min_margin=30.0,
            )
            layout_view = self._view_without_layouts(view) if self._force_auto_layout else view
            layout = engine.layout(layout_view, selected_node_id=view.selected_node_id, center=center)
            self._cached_layout = layout
            self._persist_layout_if_fixed(view, layout)
        self.node_positions = {node_id: (node.x, node.y) for node_id, node in layout.nodes.items()}
        if not self._camera_initialized:
            selected_id = view.selected_node_id
            if selected_id is not None and selected_id in self.node_positions:
                self.camera_x, self.camera_y = self.node_positions[selected_id]
            elif self.node_positions:
                xs = [position[0] for position in self.node_positions.values()]
                ys = [position[1] for position in self.node_positions.values()]
                self.camera_x = (min(xs) + max(xs)) / 2
                self.camera_y = (min(ys) + max(ys)) / 2
            self._camera_initialized = True
        self.node_roles = self._classify_node_roles(view)

        nodes_by_id = {node.id: node for node in view.nodes}
        for edge in view.edges:
            if edge.parent_node_id not in self.node_positions or edge.child_node_id not in self.node_positions:
                continue
            parent_node = nodes_by_id.get(edge.parent_node_id)
            mover_color = parent_node.side_to_move if parent_node is not None else "black"
            self._draw_edge(
                self.node_positions[edge.parent_node_id],
                self.node_positions[edge.child_node_id],
                edge.move_san,
                node_radius,
                mover_color,
            )

        for node in view.nodes:
            position = self.node_positions.get(node.id)
            if position is None:
                continue
            self._draw_node(node, *position)

        self._update_scrollregion(width, height, node_radius)

    @staticmethod
    def _view_without_layouts(view: TheoryMapView) -> TheoryMapView:
        return replace(
            view,
            nodes=tuple(replace(node, layout_x=None, layout_y=None) for node in view.nodes),
        )

    def _persist_layout_if_fixed(self, view: TheoryMapView, layout: GraphLayout) -> None:
        del view, layout
        return

    @staticmethod
    def _layout_matches_view(layout: GraphLayout, view: TheoryMapView) -> bool:
        return set(layout.nodes) == {node.id for node in view.nodes}

    @staticmethod
    def _with_current_layout_selection(layout: GraphLayout, selected_node_id: Optional[str]) -> GraphLayout:
        return GraphLayout(nodes=layout.nodes, center_node_id=selected_node_id)

    def _node_radius(self) -> float:
        return max(14.0, self._base_node_radius() * self._zoom_value())

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

        parent_id = parent_by_child.get(selected_id)
        if parent_id is not None:
            roles[parent_id] = "ancestor"
            for sibling_id in children_by_parent.get(parent_id, []):
                if sibling_id != selected_id:
                    roles[sibling_id] = "sibling"

        for child_id in children_by_parent.get(selected_id, []):
            roles[child_id] = "descendant"

        roles[selected_id] = "selected"
        return roles

    def _current_view_center(self, width: int, height: int) -> Tuple[float, float]:
        del width, height
        return self.camera_x, self.camera_y

    @staticmethod
    def _edge_label_style(mover_color: str) -> Tuple[str, str]:
        if mover_color == "white":
            return "#111111", "#ffffff"
        return "#ffffff", "#111111"

    def _draw_edge(
        self,
        source: Tuple[float, float],
        target: Tuple[float, float],
        move_san: str,
        node_radius: float,
        mover_color: str,
    ) -> None:
        x1, y1 = self._to_screen(source[0], source[1])
        x2, y2 = self._to_screen(target[0], target[1])
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
        label_fill, label_background = self._edge_label_style(mover_color)
        label_item = self.canvas.create_text(
            label_x,
            label_y,
            text=move_san,
            font=("Arial", max(8, int(9 * self.zoom)), "bold"),
            fill=label_fill,
            tags=("graph", "edge-label"),
        )
        bbox = self.canvas.bbox(label_item)
        if bbox is not None:
            pad_x = 3
            pad_y = 1
            background = self.canvas.create_rectangle(
                bbox[0] - pad_x,
                bbox[1] - pad_y,
                bbox[2] + pad_x,
                bbox[3] + pad_y,
                fill=label_background,
                outline=label_background,
                tags=("graph", "edge-label-bg"),
            )
            self.canvas.tag_lower(background, label_item)

    def _draw_node(self, node: TheoryMapNode, x: float, y: float) -> None:
        x, y = self._to_screen(x, y)
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
        self.canvas.tag_bind(tag, "<Double-Button-3>", lambda event, node_id=node.id: self._on_node_edit(event, node_id))
        self.canvas.tag_bind(tag, "<Enter>", lambda event, node=node: self._show_tooltip(event, node))
        self.canvas.tag_bind(tag, "<Leave>", lambda event: self._hide_tooltip())

    def _on_node_click(self, event: tk.Event, node_id: str) -> str:
        del event
        self.activate_keyboard_focus()
        self._cancel_pending_node_click()
        self._pending_node_click_id = node_id
        # Defer the single-click selection briefly so a double-click-hold can
        # start the legacy node-drag gesture without the first click refreshing
        # and replacing the canvas item under the pointer.
        self._pending_node_click_after_id = self.after(180, self._commit_pending_node_click)
        return "break"

    def _commit_pending_node_click(self) -> None:
        node_id = self._pending_node_click_id
        self._pending_node_click_after_id = None
        self._pending_node_click_id = None
        if node_id is not None:
            self.on_node_selected(node_id)

    def _cancel_pending_node_click(self) -> None:
        if self._pending_node_click_after_id is not None:
            try:
                self.after_cancel(self._pending_node_click_after_id)
            except tk.TclError:
                pass
        self._pending_node_click_after_id = None
        self._pending_node_click_id = None

    def _on_node_edit(self, event: tk.Event, node_id: str) -> str:
        del event
        self.activate_keyboard_focus()
        self._cancel_pending_node_click()
        if self.on_node_edit_requested is not None:
            self.on_node_edit_requested(node_id)
        return "break"

    def _update_scrollregion(self, width: int, height: int, node_radius: float) -> None:
        del width, height
        if not self.node_positions:
            self._world_bounds = (-1000.0, -1000.0, 1000.0, 1000.0)
        else:
            xs = [position[0] for position in self.node_positions.values()]
            ys = [position[1] for position in self.node_positions.values()]
            viewport_width, viewport_height = self._viewport_size()
            margin = max(node_radius / self._zoom_value() + 260.0, viewport_width / self._zoom_value(), viewport_height / self._zoom_value())
            self._world_bounds = (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)
        viewport_width, viewport_height = self._viewport_size()
        self.canvas.configure(scrollregion=(0, 0, int(viewport_width), int(viewport_height)))
        self._sync_scrollbars()

    def _center_canvas_on(self, x: float, y: float, *, refresh: bool = True) -> None:
        self.camera_x = float(x)
        self.camera_y = float(y)
        self._camera_initialized = True
        if refresh:
            self.refresh(force_layout=False)
        else:
            self._sync_scrollbars()

    def _set_zoom(self, value: float, refresh: bool = True) -> None:
        self._set_zoom_around_view_center(value, refresh=refresh)

    def _set_zoom_around_view_center(self, value: float, *, refresh: bool = True) -> None:
        self.zoom = max(0.15, min(4.5, value))
        if refresh:
            self.refresh(force_layout=False)

    def _set_zoom_around_screen_point(self, value: float, screen_x: float, screen_y: float, *, refresh: bool = True) -> None:
        anchor_world = self._to_world(screen_x, screen_y)
        self.zoom = max(0.15, min(4.5, value))
        self._set_camera_for_world_at_screen(anchor_world[0], anchor_world[1], screen_x, screen_y)
        if refresh:
            self.refresh(force_layout=False)

    def _sync_scrollbars(self) -> None:
        left, top, right, bottom = self._world_bounds
        region_width = max(right - left, 1.0)
        region_height = max(bottom - top, 1.0)
        viewport_width, viewport_height = self._viewport_size()
        half_width = viewport_width / (2 * self._zoom_value())
        half_height = viewport_height / (2 * self._zoom_value())
        view_left = self.camera_x - half_width
        view_right = self.camera_x + half_width
        view_top = self.camera_y - half_height
        view_bottom = self.camera_y + half_height
        self.horizontal_scroll.set(
            max(0.0, min(1.0, (view_left - left) / region_width)),
            max(0.0, min(1.0, (view_right - left) / region_width)),
        )
        self.vertical_scroll.set(
            max(0.0, min(1.0, (view_top - top) / region_height)),
            max(0.0, min(1.0, (view_bottom - top) / region_height)),
        )

    def _xscroll(self, *args: str) -> None:
        self._scroll_camera("x", *args)

    def _yscroll(self, *args: str) -> None:
        self._scroll_camera("y", *args)

    def _scroll_camera(self, axis: str, *args: str) -> None:
        if not args:
            return
        left, top, right, bottom = self._world_bounds
        viewport_width, viewport_height = self._viewport_size()
        if axis == "x":
            region_start, region_end = left, right
            viewport_size = viewport_width / self._zoom_value()
            current_center = self.camera_x
        else:
            region_start, region_end = top, bottom
            viewport_size = viewport_height / self._zoom_value()
            current_center = self.camera_y
        region_size = max(region_end - region_start, 1.0)
        if args[0] == "moveto" and len(args) >= 2:
            fraction = max(0.0, min(1.0, float(args[1])))
            new_center = region_start + fraction * region_size + viewport_size / 2
        elif args[0] == "scroll" and len(args) >= 3:
            amount = int(args[1])
            unit = args[2]
            step = viewport_size * (0.85 if unit == "pages" else 0.12)
            new_center = current_center + amount * step
        else:
            return
        min_center = region_start + viewport_size / 2
        max_center = region_end - viewport_size / 2
        if min_center <= max_center:
            new_center = max(min_center, min(max_center, new_center))
        if axis == "x":
            self.camera_x = new_center
        else:
            self.camera_y = new_center
        self._camera_initialized = True
        self.refresh(force_layout=False)

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
        self.canvas.bind("<Button-4>", lambda event: self._zoom_from_wheel(1, event.x, event.y))
        self.canvas.bind("<Button-5>", lambda event: self._zoom_from_wheel(-1, event.x, event.y))

    def _bind_keyboard_controls(self) -> None:
        self.canvas.configure(takefocus=1)
        self.canvas.bind("<FocusIn>", lambda event: self.canvas.configure(highlightbackground="#2563eb", highlightcolor="#2563eb"))
        self.canvas.bind("<FocusOut>", lambda event: self.canvas.configure(highlightbackground="#b0b0b0", highlightcolor="#b0b0b0"))
        self.canvas.bind("<Up>", self._on_keyboard_parent)
        self.canvas.bind("<Down>", self._on_keyboard_first_child)
        self.canvas.bind("<Left>", self._on_keyboard_previous_sibling)
        self.canvas.bind("<Right>", self._on_keyboard_next_sibling)
        self.canvas.bind("<Return>", self._on_keyboard_load_selected)
        self.canvas.bind("<Control-z>", lambda event: (self.undo_layout(), "break")[1])
        self.canvas.bind("<Control-y>", lambda event: (self.redo_layout(), "break")[1])

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

    def _on_left_drag(self, event: tk.Event) -> None:
        if self._node_drag_id is not None:
            self._drag_node_to(event)
            return
        if self._subtree_drag_ids:
            self._drag_subtree_to(event)
            return
        if self._last_drag is None:
            self._last_drag = (event.x, event.y)
            return
        previous_x, previous_y = self._last_drag
        dx_world, dy_world = self._screen_delta_to_world(event.x - previous_x, event.y - previous_y)
        self.camera_x -= dx_world
        self.camera_y -= dy_world
        self._camera_initialized = True
        self._last_drag = (event.x, event.y)
        self.refresh(force_layout=False)

    def _finish_left_interaction(self) -> None:
        edited_layout = self._node_drag_id is not None or bool(self._subtree_drag_ids)
        self._node_drag_id = None
        self._node_drag_previous = None
        self._subtree_drag_ids = set()
        self._clear_left_drag()
        if edited_layout and self._auto_save_layout and self._layout_dirty:
            self.save_layout()

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
            anchor_world = self._to_world(self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2)
            self.rotation_radians = (self.rotation_radians + delta) % (math.pi * 2)
            self._set_camera_for_world_at_screen(anchor_world[0], anchor_world[1], self.canvas.winfo_width() / 2, self.canvas.winfo_height() / 2)
            self.refresh(force_layout=False)
        self._right_drag = (event.x, event.y)

    def _finish_right_interaction(self) -> None:
        self._subtree_rotate_ids = set()
        self._subtree_rotate_center = None
        self._subtree_rotate_previous_angle = None
        self._clear_right_drag()

    def _clear_right_drag(self) -> None:
        self._right_drag = None


    def _start_node_drag(self, event: tk.Event, node_id: str) -> str:
        self.activate_keyboard_focus()
        self._cancel_pending_node_click()
        self._clear_left_drag()
        self._record_layout_undo()
        self._node_drag_id = node_id
        self._node_drag_previous = (event.x, event.y)
        return "break"

    def _start_subtree_drag(self, event: tk.Event, node_id: str) -> str:
        self.activate_keyboard_focus()
        self._cancel_pending_node_click()
        self._clear_left_drag()
        self._record_layout_undo()
        visible_ids = set(self.node_positions)
        self._subtree_drag_ids = self.controller.get_visible_subtree_ids(node_id, visible_ids)
        self._node_drag_previous = (event.x, event.y)
        return "break"

    def _start_subtree_rotate(self, event: tk.Event, node_id: str) -> str:
        self.activate_keyboard_focus()
        self._cancel_pending_node_click()
        self._record_layout_undo()
        visible_ids = set(self.node_positions)
        self._subtree_rotate_ids = self.controller.get_visible_descendant_ids(node_id, visible_ids)
        if not self._subtree_rotate_ids:
            self._subtree_rotate_ids = set()
            return "break"
        self._subtree_rotate_center = self.node_positions.get(node_id)
        if self._subtree_rotate_center is None:
            self._subtree_rotate_ids = set()
            return "break"
        canvas_x, canvas_y = self._to_world(event.x, event.y)
        cx, cy = self._subtree_rotate_center
        self._subtree_rotate_previous_angle = math.atan2(canvas_y - cy, canvas_x - cx)
        return "break"

    def _drag_node_to(self, event: tk.Event) -> None:
        if self._node_drag_id is None or self._node_drag_previous is None:
            return
        previous_x, previous_y = self._node_drag_previous
        dx, dy = self._screen_delta_to_world(event.x - previous_x, event.y - previous_y)
        self._move_visible_nodes({self._node_drag_id}, dx, dy)
        self._node_drag_previous = (event.x, event.y)

    def _drag_subtree_to(self, event: tk.Event) -> None:
        if not self._subtree_drag_ids or self._node_drag_previous is None:
            return
        previous_x, previous_y = self._node_drag_previous
        dx, dy = self._screen_delta_to_world(event.x - previous_x, event.y - previous_y)
        self._move_visible_nodes(self._subtree_drag_ids, dx, dy)
        self._node_drag_previous = (event.x, event.y)

    def _rotate_subtree_to(self, event: tk.Event) -> None:
        if not self._subtree_rotate_ids or self._subtree_rotate_center is None:
            return
        canvas_x, canvas_y = self._to_world(event.x, event.y)
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
        self._mark_layout_dirty()
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
        self._mark_layout_dirty()
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
        self._mark_layout_dirty()

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
            self._set_zoom_around_screen_point(self.zoom * factor, event.x, event.y)
        self._middle_drag = (event.x, event.y)

    def _clear_middle_drag(self) -> None:
        self._middle_drag = None

    def _on_mouse_wheel(self, event: tk.Event) -> None:
        direction = 1 if event.delta > 0 else -1
        self._zoom_from_wheel(direction, event.x, event.y)

    def _zoom_from_wheel(self, direction: int, x: Optional[int] = None, y: Optional[int] = None) -> None:
        factor = 1.12 if direction > 0 else 1 / 1.12
        if x is None or y is None:
            width, height = self._viewport_size()
            x, y = int(width / 2), int(height / 2)
        self._set_zoom_around_screen_point(self.zoom * factor, float(x), float(y))

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
        self._draw_fen_preview(board, node.fen, 20, self._move_hint_for_node(node.id))

    def _move_hint_for_node(self, node_id: str) -> MoveVisualHint:
        try:
            return self.controller.move_hint_for_node(node_id)
        except Exception:
            return MoveVisualHint(None, None)

    def _hide_tooltip(self) -> None:
        if self.tooltip is not None and self.tooltip.winfo_exists():
            self.tooltip.destroy()
        self.tooltip = None

    def _draw_fen_preview(self, canvas: tk.Canvas, fen: str, cell_size: int, hint: Optional[MoveVisualHint] = None) -> None:
        placement = fen.split()[0]
        rows = placement.split("/")
        colors = ("#f0d9b5", "#b58863")
        if len(rows) != 8:
            return

        board_tokens: list[list[Optional[str]]] = [[None for _ in range(8)] for _ in range(8)]
        for fen_row_index, row_value in enumerate(rows):
            fen_col_index = 0
            for token in row_value:
                if token.isdigit():
                    fen_col_index += int(token)
                    continue
                if 0 <= fen_col_index < 8:
                    board_tokens[fen_row_index][fen_col_index] = token
                fen_col_index += 1

        highlight_squares = {square for square in (hint.from_square if hint else None, hint.to_square if hint else None) if square}

        for display_row in range(8):
            for display_col in range(8):
                if self.board_rotation:
                    fen_row = 7 - display_row
                    fen_col = 7 - display_col
                else:
                    fen_row = display_row
                    fen_col = display_col
                token = board_tokens[fen_row][fen_col]
                logic_square = f"{chr(ord('a') + fen_col)}{8 - fen_row}"
                TheoryMapCanvas._draw_preview_square(
                    canvas,
                    display_row,
                    display_col,
                    cell_size,
                    colors,
                    highlight=logic_square in highlight_squares,
                )
                if token is None:
                    continue
                cx = display_col * cell_size + cell_size / 2
                cy = display_row * cell_size + cell_size / 2
                piece_key = self._piece_key_from_fen_token(token)
                piece_image = self.preview_piece_images.get(piece_key)
                if piece_image is not None:
                    canvas.create_image(cx, cy, image=piece_image, anchor="center")
                else:
                    self._draw_preview_piece_fallback(canvas, token, cx, cy)

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
    def _draw_preview_square(canvas: tk.Canvas, row: int, col: int, cell_size: int, colors: Tuple[str, str], highlight: bool = False) -> None:
        x1 = col * cell_size
        y1 = row * cell_size
        x2 = x1 + cell_size
        y2 = y1 + cell_size
        canvas.create_rectangle(x1, y1, x2, y2, fill=colors[(row + col) % 2], outline="")
        if highlight:
            canvas.create_rectangle(x1, y1, x2, y2, fill="#f7d774", outline="")

    @staticmethod
    def _shorten(value: str, max_len: int) -> str:
        return value if len(value) <= max_len else value[: max_len - 1] + "…"
