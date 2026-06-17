"""Storage port for opening-theory graph backends.

The application talks to this Protocol. Local SQLite, future Neo4j adapters or a
remote FastAPI client must implement this same contract.
"""

from __future__ import annotations

from typing import Optional, Protocol, Tuple

from neuralcheck.theory.models import (
    DeletePreview,
    TheoryBook,
    TheoryBranch,
    TheoryEdge,
    TheoryNode,
)


class TheoryGraphStore(Protocol):
    """Backend-agnostic contract for tree-shaped theory graphs."""

    def create_book(
        self,
        name: str,
        source_type: str = "independent_position",
        initial_moves: Tuple[str, ...] = (),
    ) -> TheoryBook: ...

    def update_book(
        self,
        book_id: str,
        *,
        name: Optional[str] = None,
    ) -> TheoryBook: ...

    def update_book_source(
        self,
        book_id: str,
        source_type: str,
        initial_moves: Tuple[str, ...] = (),
    ) -> TheoryBook: ...

    def update_book_map_depths(
        self,
        book_id: str,
        *,
        backward_depth: int,
        forward_depth: int,
    ) -> TheoryBook: ...

    def list_books(self) -> list[TheoryBook]: ...

    def get_book(self, book_id: str) -> Optional[TheoryBook]: ...

    def delete_book(self, book_id: str) -> bool: ...

    def create_root(
        self,
        book_id: str,
        fen: str,
        side_to_move: str,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryNode: ...

    def get_root(self, book_id: str) -> Optional[TheoryNode]: ...

    def get_node(self, node_id: str) -> Optional[TheoryNode]: ...

    def update_node(
        self,
        node_id: str,
        *,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryNode: ...

    def update_node_layout(
        self,
        node_id: str,
        *,
        layout_x: Optional[float],
        layout_y: Optional[float],
    ) -> TheoryNode: ...

    def update_node_layouts(
        self,
        positions: dict[str, tuple[float, float]],
    ) -> None: ...

    def add_child(
        self,
        parent_node_id: str,
        fen: str,
        side_to_move: str,
        move_san: str,
        move_uci: Optional[str] = None,
        mover_color: Optional[str] = None,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryBranch: ...

    def get_children(self, node_id: str) -> list[TheoryBranch]: ...

    def get_parent_branch(self, node_id: str) -> Optional[TheoryBranch]: ...

    def preview_delete_subtree(self, node_id: str) -> DeletePreview: ...

    def delete_subtree(self, node_id: str) -> DeletePreview: ...

    def close(self) -> None: ...
