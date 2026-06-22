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
    THEORY_SOURCE_SYNCHRONIZED,
)
from neuralcheck.theory.store import TheoryGraphStore


class TheoryService:
    """Business rules above the graph persistence adapter."""

    def __init__(self, store: TheoryGraphStore):
        self.store = store
        self._resolved_fen_cache: dict[str, str] = {}

    def _clear_resolved_fen_cache(self) -> None:
        self._resolved_fen_cache.clear()

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
        updated = self.store.update_book_source(book_id, source_type, initial_moves)
        self._clear_resolved_fen_cache()
        return updated

    def update_book_map_depths(
        self,
        book_id: str,
        *,
        backward_depth: int,
        forward_depth: int,
    ) -> TheoryBook:
        return self.store.update_book_map_depths(
            book_id,
            backward_depth=backward_depth,
            forward_depth=forward_depth,
        )

    def list_books(self) -> list[TheoryBook]:
        return self.store.list_books()

    def get_book(self, book_id: str) -> Optional[TheoryBook]:
        return self.store.get_book(book_id)

    def delete_book(self, book_id: str) -> bool:
        deleted = self.store.delete_book(book_id)
        if deleted:
            self._clear_resolved_fen_cache()
        return deleted

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
        self._clear_resolved_fen_cache()
        self._resolved_fen_cache[root.id] = normalized_fen
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

    def update_node_layout(
        self,
        node_id: str,
        *,
        layout_x: Optional[float],
        layout_y: Optional[float],
    ) -> TheoryNode:
        return self.store.update_node_layout(node_id, layout_x=layout_x, layout_y=layout_y)

    def update_node_layouts(self, positions: dict[str, tuple[float, float]]) -> None:
        self.store.update_node_layouts(positions)

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
        branch = self.store.add_child(
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
        if self._fen_has_en_passant_target(normalized_fen):
            self._resolved_fen_cache[branch.node.id] = normalized_fen
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
        """Create a child by replaying ``move_san`` from the parent FEN.

        This keeps theory nodes synchronized with relation moves. The saved FEN
        comes from the rule engine, not from a possibly stale board widget.
        """
        parent, clean_move, normalized_fen, side_to_move = self.preview_child_by_move(parent_node_id, move_san)
        branch = self.store.add_child(
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
        self._resolved_fen_cache[branch.node.id] = normalized_fen
        return branch

    def preview_child_by_move(self, parent_node_id: str, move_san: str) -> tuple[TheoryNode, str, str, str]:
        """Return the position that would result from a child move without saving it."""
        parent = self.store.get_node(parent_node_id)
        if parent is None:
            raise KeyError(f"Unknown parent node: {parent_node_id}")

        clean_move = self._clean_move_text(move_san)
        board = ChessBoard()
        board.set_position_from_fen(self.resolve_node_fen(parent.id), clear_history=True)
        white_player = board.white_turn
        move_without_promotion, promote_to = self._extract_promotion(clean_move, white_player)
        piece, origin, target = board.read_move(move_without_promotion, white_player)
        moved, _ = board.make_move(
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
        return parent, clean_move, normalized_fen, side_to_move

    def resolve_node_fen(self, node_id: str) -> str:
        """Return a node FEN with transient state restored efficiently.

        New nodes store the en-passant target directly in FEN. Legacy theory
        nodes may have the correct piece placement but a missing fourth FEN
        field. Recover that state from the immediate parent edge whenever
        possible, then cache the result for the service lifetime. Full path
        replay is kept only as a fallback for unusual synchronized/legacy cases.
        """
        cached = self._resolved_fen_cache.get(node_id)
        if cached is not None:
            return cached

        node = self.store.get_node(node_id)
        if node is None:
            raise KeyError(f"Unknown theory node: {node_id}")

        try:
            resolved = self._resolve_node_fen_fast(node)
        except Exception:
            try:
                resolved = self._resolve_node_fen_from_path(node)
            except Exception:
                resolved = node.fen

        normalized_fen, _ = self._validate_and_normalize_fen(resolved)
        self._resolved_fen_cache[node_id] = normalized_fen
        return normalized_fen

    def _resolve_node_fen_fast(self, node: TheoryNode) -> str:
        """Resolve a node without replaying the whole branch when possible."""
        if self._fen_has_en_passant_target(node.fen):
            return node.fen

        parent_branch = self.store.get_parent_branch(node.id)
        if parent_branch is None:
            book = self.store.get_book(node.book_id)
            if book is not None and book.source_type == THEORY_SOURCE_SYNCHRONIZED and book.initial_moves:
                return self._resolve_node_fen_from_path(node)
            return node.fen

        recovered = self._resolve_node_fen_from_parent_edge(node, parent_branch)
        return recovered if recovered is not None else node.fen

    def _resolve_node_fen_from_parent_edge(
        self,
        node: TheoryNode,
        parent_branch: TheoryBranch,
    ) -> Optional[str]:
        """Replay only the immediate parent edge and compare it with ``node``.

        This recovers transient state such as en-passant after a double pawn
        move, without paying for a replay from the root on every node load.
        """
        parent_fen = self.resolve_node_fen(parent_branch.edge.parent_node_id)
        board = ChessBoard()
        board.set_position_from_fen(parent_fen, clear_history=True)
        self._replay_move_on_board(board, parent_branch.edge.move_san)
        candidate = board.export_fen(include_state=True)

        if self._same_visible_position(candidate, node.fen):
            return candidate
        return None

    def _resolve_node_fen_from_path(self, node: TheoryNode) -> str:
        book = self.store.get_book(node.book_id)
        root = self.store.get_root(node.book_id)
        if root is None:
            return node.fen

        path = self._path_to_node(node.id)
        board = ChessBoard()

        if book is not None and book.source_type == THEORY_SOURCE_SYNCHRONIZED:
            for move in book.initial_moves:
                self._replay_move_on_board(board, move)
        else:
            board.set_position_from_fen(root.fen, clear_history=True)

        for branch in path:
            self._replay_move_on_board(board, branch.edge.move_san)

        return board.export_fen(include_state=True)

    def _path_to_node(self, node_id: str) -> list[TheoryBranch]:
        path: list[TheoryBranch] = []
        current_id = node_id
        seen: set[str] = set()
        while current_id not in seen:
            seen.add(current_id)
            branch = self.store.get_parent_branch(current_id)
            if branch is None:
                break
            path.append(branch)
            current_id = branch.edge.parent_node_id
        return list(reversed(path))

    @staticmethod
    def _fen_has_en_passant_target(fen: str) -> bool:
        fields = fen.strip().split()
        return len(fields) >= 4 and fields[3] != "-"

    @staticmethod
    def _same_visible_position(left_fen: str, right_fen: str) -> bool:
        left = left_fen.strip().split()
        right = right_fen.strip().split()
        if not left or not right:
            return False
        left_active = left[1] if len(left) >= 2 else "w"
        right_active = right[1] if len(right) >= 2 else "w"
        return left[0] == right[0] and left_active == right_active

    def _replay_move_on_board(self, board: ChessBoard, move_san: str) -> None:
        clean_move = self._clean_move_text(move_san)
        white_player = board.white_turn
        board.possible_moves = board.calculate_possible_moves()
        move_without_promotion, promote_to = self._extract_promotion(clean_move, white_player)
        piece, origin, target = board.read_move(move_without_promotion, white_player)
        moved, _ = board.make_move(
            piece,
            origin,
            target,
            promote2=promote_to,
            add2history=False,
        )
        if not moved:
            raise ValueError(f"La jugada no es legal al reconstruir teoría: {move_san}")

    def get_children(self, node_id: str) -> list[TheoryBranch]:
        return self.store.get_children(node_id)

    def get_parent_branch(self, node_id: str) -> Optional[TheoryBranch]:
        return self.store.get_parent_branch(node_id)

    def preview_delete_subtree(self, node_id: str) -> DeletePreview:
        return self.store.preview_delete_subtree(node_id)

    def delete_subtree(self, node_id: str) -> DeletePreview:
        deleted = self.store.delete_subtree(node_id)
        self._clear_resolved_fen_cache()
        return deleted

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
