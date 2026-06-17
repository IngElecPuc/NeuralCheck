"""Use cases for opening-theory trees."""

from __future__ import annotations

from typing import Optional, Tuple

from neuralcheck.logic import ChessBoard
from neuralcheck.theory.models import (
    DeletePreview,
    TheoryBook,
    TheoryBranch,
    TheoryNode,
    THEORY_SOURCE_INDEPENDENT,
)
from neuralcheck.theory.store import TheoryGraphStore


class TheoryService:
    """Business rules above the graph persistence adapter."""

    def __init__(self, store: TheoryGraphStore):
        self.store = store

    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> "TheoryService":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        self.close()

    def create_book(
        self,
        name: str,
        source_type: str = THEORY_SOURCE_INDEPENDENT,
        initial_moves: Tuple[str, ...] = (),
    ) -> TheoryBook:
        return self.store.create_book(name, source_type=source_type, initial_moves=initial_moves)

    def update_book(
        self,
        book_id: str,
        *,
        name: Optional[str] = None,
    ) -> TheoryBook:
        return self.store.update_book(book_id, name=name)

    def update_book_source(
        self,
        book_id: str,
        source_type: str,
        initial_moves: Tuple[str, ...] = (),
    ) -> TheoryBook:
        return self.store.update_book_source(book_id, source_type, initial_moves)

    def list_books(self) -> list[TheoryBook]:
        return self.store.list_books()

    def get_book(self, book_id: str) -> Optional[TheoryBook]:
        return self.store.get_book(book_id)

    def delete_book(self, book_id: str) -> bool:
        return self.store.delete_book(book_id)

    def create_root(
        self,
        book_id: str,
        fen: str,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
        source_type: str = THEORY_SOURCE_INDEPENDENT,
        initial_moves: Tuple[str, ...] = (),
    ) -> TheoryNode:
        normalized_fen, side_to_move = self._validate_and_normalize_fen(fen)
        root = self.store.create_root(
            book_id=book_id,
            fen=normalized_fen,
            side_to_move=side_to_move,
            name=name,
            evaluation=evaluation,
            captured_pieces=captured_pieces,
        )
        self.store.update_book_source(book_id, source_type=source_type, initial_moves=initial_moves)
        return root

    def get_root(self, book_id: str) -> Optional[TheoryNode]:
        return self.store.get_root(book_id)

    def get_node(self, node_id: str) -> Optional[TheoryNode]:
        return self.store.get_node(node_id)

    def update_node(
        self,
        node_id: str,
        *,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryNode:
        return self.store.update_node(
            node_id,
            name=name,
            evaluation=evaluation,
            captured_pieces=captured_pieces,
        )

    def add_child(
        self,
        parent_node_id: str,
        fen: str,
        move_san: str,
        move_uci: Optional[str] = None,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryBranch:
        parent = self.store.get_node(parent_node_id)
        if parent is None:
            raise KeyError(f"Unknown parent node: {parent_node_id}")
        normalized_fen, side_to_move = self._validate_and_normalize_fen(fen)
        return self.store.add_child(
            parent_node_id=parent_node_id,
            fen=normalized_fen,
            side_to_move=side_to_move,
            move_san=move_san,
            move_uci=move_uci,
            mover_color=parent.side_to_move,
            name=name,
            evaluation=evaluation,
            captured_pieces=captured_pieces,
        )

    def add_child_by_move(
        self,
        parent_node_id: str,
        move_san: str,
        move_uci: Optional[str] = None,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryBranch:
        """Create a child by replaying ``move_san`` from the parent FEN.

        This keeps theory nodes synchronized with relation moves. The saved FEN
        comes from the rule engine, not from a possibly stale board widget.
        """
        parent = self.store.get_node(parent_node_id)
        if parent is None:
            raise KeyError(f"Unknown parent node: {parent_node_id}")

        clean_move = self._clean_move_text(move_san)
        board = ChessBoard()
        board.set_position_from_fen(parent.fen, clear_history=True)
        white_player = board.white_turn
        move_without_promotion, promote_to = self._extract_promotion(clean_move, white_player)
        piece, origin, target = board.read_move(move_without_promotion, white_player)
        moved, movement = board.make_move(
            piece,
            origin,
            target,
            promote2=promote_to,
            add2history=False,
        )
        if not moved:
            raise ValueError(f"La jugada no es legal desde el nodo padre: {move_san}")

        normalized_fen = board.export_fen(include_state=True)
        side_to_move = "white" if board.white_turn else "black"
        return self.store.add_child(
            parent_node_id=parent_node_id,
            fen=normalized_fen,
            side_to_move=side_to_move,
            move_san=clean_move,
            move_uci=move_uci,
            mover_color=parent.side_to_move,
            name=name,
            evaluation=evaluation,
            captured_pieces=captured_pieces,
        )

    def get_children(self, node_id: str) -> list[TheoryBranch]:
        return self.store.get_children(node_id)

    def get_parent_branch(self, node_id: str) -> Optional[TheoryBranch]:
        return self.store.get_parent_branch(node_id)

    def preview_delete_subtree(self, node_id: str) -> DeletePreview:
        return self.store.preview_delete_subtree(node_id)

    def delete_subtree(self, node_id: str) -> DeletePreview:
        return self.store.delete_subtree(node_id)

    def _validate_and_normalize_fen(self, fen: str) -> tuple[str, str]:
        if not isinstance(fen, str) or not fen.strip():
            raise ValueError("FEN is required")

        board = ChessBoard()
        board.set_position_from_fen(fen.strip(), clear_history=True)
        normalized_fen = board.export_fen(include_state=True)
        side_to_move = "white" if board.white_turn else "black"
        return normalized_fen, side_to_move

    @staticmethod
    def _clean_move_text(move_san: str) -> str:
        if not isinstance(move_san, str) or not move_san.strip():
            raise ValueError("move_san is required")
        return move_san.strip()

    @staticmethod
    def _extract_promotion(move: str, white_player: bool) -> tuple[str, Optional[str]]:
        if "=" not in move:
            return move, None

        move_without_promotion, promotion_suffix = move.split("=", 1)
        promotion_code = promotion_suffix.replace("+", "").replace("#", "")[:1]
        promotion_map = {"Q": "queen", "R": "rook", "N": "knight", "B": "bishop"}
        promotion_piece = promotion_map.get(promotion_code)
        if promotion_piece is None:
            return move_without_promotion, None

        color = "white" if white_player else "black"
        return move_without_promotion, f"{color} {promotion_piece}"
