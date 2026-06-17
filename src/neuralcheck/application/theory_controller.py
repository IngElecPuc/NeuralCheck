"""Application controller for theory-tree workflows."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from neuralcheck.application.game_controller import GameController, PositionValidationResult
from neuralcheck.theory.models import (
    DeletePreview,
    TheoryBook,
    TheoryBranch,
    TheoryLocalView,
    TheoryNode,
    THEORY_SOURCE_INDEPENDENT,
    THEORY_SOURCE_SYNCHRONIZED,
)
from neuralcheck.theory.service import TheoryService
from neuralcheck.theory.sqlite_store import SQLiteTheoryGraphStore


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_THEORY_DB = PROJECT_ROOT / "data" / "theory" / "neuralcheck_theory.db"


class TheoryController:
    """Facade used by the desktop theory UI.

    It coordinates the current board position with the theory service. Storage is
    still injected through ``TheoryService``, so the UI is not tied to SQLite.
    """

    def __init__(self, service: TheoryService, game_controller: Optional[GameController] = None):
        self.service = service
        self.game_controller = game_controller
        self._selected_book_id: Optional[str] = None
        self._selected_node_id: Optional[str] = None

    @classmethod
    def with_sqlite(
        cls,
        database_path: str | Path = DEFAULT_THEORY_DB,
        game_controller: Optional[GameController] = None,
    ) -> "TheoryController":
        store = SQLiteTheoryGraphStore(database_path)
        return cls(TheoryService(store), game_controller=game_controller)

    def close(self) -> None:
        self.service.close()

    def __enter__(self) -> "TheoryController":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        self.close()

    @property
    def selected_book_id(self) -> Optional[str]:
        return self._selected_book_id

    @property
    def selected_node_id(self) -> Optional[str]:
        return self._selected_node_id

    def select_book(self, book_id: str) -> Optional[TheoryNode]:
        book = self.service.get_book(book_id)
        if book is None:
            self._selected_book_id = None
            self._selected_node_id = None
            return None

        self._selected_book_id = book_id
        root = self.service.get_root(book_id)
        self._selected_node_id = root.id if root else None
        return root

    def select_node(self, node_id: str) -> Optional[TheoryNode]:
        node = self.service.get_node(node_id)
        if node is None:
            self._selected_node_id = None
            return None

        self._selected_book_id = node.book_id
        self._selected_node_id = node.id
        return node

    def list_books(self) -> list[TheoryBook]:
        return self.service.list_books()

    def get_selected_book(self) -> Optional[TheoryBook]:
        if self._selected_book_id is None:
            return None
        return self.service.get_book(self._selected_book_id)

    def create_book(self, name: str) -> TheoryBook:
        book = self.service.create_book(name)
        self._selected_book_id = book.id
        self._selected_node_id = None
        return book

    def update_book(self, book_id: str, *, name: str) -> TheoryBook:
        book = self.service.update_book(book_id, name=name)
        self._selected_book_id = book.id
        return book

    def delete_book(self, book_id: str) -> bool:
        deleted = self.service.delete_book(book_id)
        if deleted and self._selected_book_id == book_id:
            self._selected_book_id = None
            self._selected_node_id = None
        return deleted

    def create_root_from_current_position(
        self,
        book_id: str,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryNode:
        fen = self._current_board_fen()
        source_context = self._current_source_context()
        root = self.service.create_root(
            book_id=book_id,
            fen=fen,
            name=name,
            evaluation=evaluation,
            captured_pieces=captured_pieces,
            source_type=source_context.source_type,
            initial_moves=source_context.initial_moves,
        )
        self._selected_book_id = book_id
        self._selected_node_id = root.id
        return root

    def add_child_from_current_position(
        self,
        parent_node_id: str,
        move_san: str,
        move_uci: Optional[str] = None,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryBranch:
        fen = self._current_board_fen()
        branch = self.service.add_child(
            parent_node_id=parent_node_id,
            fen=fen,
            move_san=move_san,
            move_uci=move_uci,
            name=name,
            evaluation=evaluation,
            captured_pieces=captured_pieces,
        )
        self._selected_book_id = branch.node.book_id
        self._selected_node_id = branch.node.id
        return branch

    def add_child_by_move(
        self,
        parent_node_id: str,
        move_san: str,
        move_uci: Optional[str] = None,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryBranch:
        branch = self.service.add_child_by_move(
            parent_node_id=parent_node_id,
            move_san=move_san,
            move_uci=move_uci,
            name=name,
            evaluation=evaluation,
            captured_pieces=captured_pieces,
        )
        self._selected_book_id = branch.node.book_id
        self._selected_node_id = branch.node.id
        return branch

    def get_selected_node(self) -> Optional[TheoryNode]:
        if self._selected_node_id is None:
            return None
        return self.service.get_node(self._selected_node_id)

    def update_selected_node(
        self,
        *,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryNode:
        if self._selected_node_id is None:
            raise ValueError("No theory node selected")
        node = self.service.update_node(
            self._selected_node_id,
            name=name,
            evaluation=evaluation,
            captured_pieces=captured_pieces,
        )
        self._selected_book_id = node.book_id
        self._selected_node_id = node.id
        return node

    def get_local_view(self) -> TheoryLocalView:
        book = self.get_selected_book()
        current = self.get_selected_node()
        if current is None:
            return TheoryLocalView(
                book=book,
                current_node=None,
                parent_branch=None,
                children=(),
                siblings=(),
                path=(),
            )

        parent = self.service.get_parent_branch(current.id)
        children = tuple(self.service.get_children(current.id))
        siblings: tuple[TheoryBranch, ...] = ()
        if parent is not None:
            siblings = tuple(self.service.get_children(parent.edge.parent_node_id))
        path = tuple(self._path_to_node(current.id))
        return TheoryLocalView(
            book=book,
            current_node=current,
            parent_branch=parent,
            children=children,
            siblings=siblings,
            path=path,
        )

    def select_first_child(self) -> Optional[TheoryNode]:
        children = self.get_children()
        if not children:
            return None
        return self.select_node(children[0].node.id)

    def select_sibling(self, offset: int) -> Optional[TheoryNode]:
        node = self.get_selected_node()
        if node is None:
            return None
        parent = self.get_parent_branch(node.id)
        if parent is None:
            return node
        siblings = self.get_children(parent.edge.parent_node_id)
        if not siblings:
            return node
        ids = [branch.node.id for branch in siblings]
        try:
            index = ids.index(node.id)
        except ValueError:
            return node
        next_index = max(0, min(len(siblings) - 1, index + offset))
        return self.select_node(siblings[next_index].node.id)

    def get_children(self, node_id: Optional[str] = None) -> list[TheoryBranch]:
        target_node_id = node_id or self._selected_node_id
        if target_node_id is None:
            return []
        return self.service.get_children(target_node_id)

    def get_parent_branch(self, node_id: Optional[str] = None) -> Optional[TheoryBranch]:
        target_node_id = node_id or self._selected_node_id
        if target_node_id is None:
            return None
        return self.service.get_parent_branch(target_node_id)

    def load_node_to_board(self, node_id: Optional[str] = None) -> PositionValidationResult:
        if self.game_controller is None:
            raise RuntimeError("TheoryController has no game controller")
        target_node_id = node_id or self._selected_node_id
        if target_node_id is None:
            raise ValueError("No theory node selected")

        node = self.service.get_node(target_node_id)
        if node is None:
            raise KeyError(f"Unknown theory node: {target_node_id}")

        book = self.service.get_book(node.book_id)
        if book is not None and book.source_type == THEORY_SOURCE_SYNCHRONIZED:
            line = self._line_to_node(book, node.id)
            validation = self.game_controller.load_line_from_initial(line)
        else:
            validation = self.game_controller.apply_fen_position(node.fen)

        if validation.valid:
            self.select_node(node.id)
        return validation

    def preview_delete_subtree(self, node_id: Optional[str] = None) -> DeletePreview:
        target_node_id = node_id or self._selected_node_id
        if target_node_id is None:
            raise ValueError("No theory node selected")
        return self.service.preview_delete_subtree(target_node_id)

    def delete_subtree(self, node_id: Optional[str] = None) -> DeletePreview:
        target_node_id = node_id or self._selected_node_id
        if target_node_id is None:
            raise ValueError("No theory node selected")

        preview = self.service.delete_subtree(target_node_id)
        if self._selected_node_id in preview.node_ids:
            self._selected_node_id = None
        return preview

    def selected_book_source_label(self) -> str:
        book = self.get_selected_book()
        if book is None:
            return "Sin entrada seleccionada"
        if book.source_type == THEORY_SOURCE_SYNCHRONIZED:
            if book.initial_moves:
                return "Línea sincronizada: " + " ".join(book.initial_moves)
            return "Línea sincronizada desde la posición inicial"
        return "Posición independiente: se carga como FEN, sin reconstruir línea desde el inicio"

    def _current_board_fen(self) -> str:
        if self.game_controller is None:
            raise RuntimeError("TheoryController has no game controller")
        return self.game_controller.current_fen(include_state=True)

    def _current_source_context(self):
        if self.game_controller is None:
            return type(
                "SourceContext",
                (),
                {"source_type": THEORY_SOURCE_INDEPENDENT, "initial_moves": ()},
            )()
        return self.game_controller.current_position_source_context()

    def _line_to_node(self, book: TheoryBook, node_id: str) -> list[str]:
        moves = list(book.initial_moves)
        moves.extend(branch.edge.move_san for branch in self._path_to_node(node_id))
        return moves

    def _path_to_node(self, node_id: str) -> list[TheoryBranch]:
        path_moves = []
        current_id = node_id
        while True:
            branch = self.service.get_parent_branch(current_id)
            if branch is None:
                break
            path_moves.append(branch)
            current_id = branch.edge.parent_node_id
        return list(reversed(path_moves))
