"""SQLite implementation of the theory graph store.

This adapter stores the graph as explicit node and edge tables. It does not leak
SQL to callers, so a future Neo4j or remote API adapter can replace it behind the
same ``TheoryGraphStore`` contract.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple
from uuid import uuid4

from neuralcheck.theory.models import (
    DeletePreview,
    TheoryBook,
    TheoryBranch,
    TheoryEdge,
    TheoryNode,
    THEORY_SOURCE_INDEPENDENT,
    THEORY_SOURCE_TYPES,
)


class SQLiteTheoryGraphStore:
    """Local graph persistence backed by SQLite."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self.database_path))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._closed = False
        self._create_schema()

    def close(self) -> None:
        if self._closed:
            return
        self._connection.close()
        self._closed = True

    def __enter__(self) -> "SQLiteTheoryGraphStore":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        del exc_type, exc, traceback
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def create_book(
        self,
        name: str,
        source_type: str = THEORY_SOURCE_INDEPENDENT,
        initial_moves: Tuple[str, ...] = (),
    ) -> TheoryBook:
        clean_name = self._require_text(name, "book name")
        clean_source = self._require_source_type(source_type)
        clean_initial_moves = self._serialize_initial_moves(initial_moves)
        now = self._now()
        book_id = self._new_id()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO theory_books (
                    id, name, source_type, initial_moves,
                    map_backward_depth, map_forward_depth, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (book_id, clean_name, clean_source, clean_initial_moves, 2, 4, now, now),
            )
        book = self.get_book(book_id)
        if book is None:
            raise RuntimeError("Created theory book could not be read back")
        return book


    def update_book(
        self,
        book_id: str,
        *,
        name: Optional[str] = None,
    ) -> TheoryBook:
        self._require_existing_book(book_id)
        clean_name = self._require_text(name, "book name")
        now = self._now()
        try:
            with self._connection:
                self._connection.execute(
                    """
                    UPDATE theory_books
                    SET name = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (clean_name, now, book_id),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Could not update theory book: {exc}") from exc
        book = self.get_book(book_id)
        if book is None:
            raise RuntimeError("Updated theory book could not be read back")
        return book

    def update_book_source(
        self,
        book_id: str,
        source_type: str,
        initial_moves: Tuple[str, ...] = (),
    ) -> TheoryBook:
        self._require_existing_book(book_id)
        clean_source = self._require_source_type(source_type)
        clean_initial_moves = self._serialize_initial_moves(initial_moves)
        now = self._now()
        with self._connection:
            self._connection.execute(
                """
                UPDATE theory_books
                SET source_type = ?, initial_moves = ?, updated_at = ?
                WHERE id = ?
                """,
                (clean_source, clean_initial_moves, now, book_id),
            )
        book = self.get_book(book_id)
        if book is None:
            raise RuntimeError("Updated theory book could not be read back")
        return book

    def update_book_map_depths(
        self,
        book_id: str,
        *,
        backward_depth: int,
        forward_depth: int,
    ) -> TheoryBook:
        self._require_existing_book(book_id)
        clean_backward = self._require_depth(backward_depth, "backward_depth")
        clean_forward = self._require_depth(forward_depth, "forward_depth")
        now = self._now()
        with self._connection:
            self._connection.execute(
                """
                UPDATE theory_books
                SET map_backward_depth = ?, map_forward_depth = ?, updated_at = ?
                WHERE id = ?
                """,
                (clean_backward, clean_forward, now, book_id),
            )
        book = self.get_book(book_id)
        if book is None:
            raise RuntimeError("Updated theory book could not be read back")
        return book

    def list_books(self) -> list[TheoryBook]:
        rows = self._connection.execute(
            """
            SELECT b.*, br.node_id AS root_node_id
            FROM theory_books b
            LEFT JOIN theory_book_roots br ON br.book_id = b.id
            ORDER BY lower(b.name), b.created_at
            """
        ).fetchall()
        return [self._book_from_row(row) for row in rows]

    def get_book(self, book_id: str) -> Optional[TheoryBook]:
        row = self._connection.execute(
            """
            SELECT b.*, br.node_id AS root_node_id
            FROM theory_books b
            LEFT JOIN theory_book_roots br ON br.book_id = b.id
            WHERE b.id = ?
            """,
            (book_id,),
        ).fetchone()
        return self._book_from_row(row) if row else None

    def delete_book(self, book_id: str) -> bool:
        with self._connection:
            cursor = self._connection.execute("DELETE FROM theory_books WHERE id = ?", (book_id,))
        return cursor.rowcount > 0

    def create_root(
        self,
        book_id: str,
        fen: str,
        side_to_move: str,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryNode:
        self._require_existing_book(book_id)
        if self.get_root(book_id) is not None:
            raise ValueError("Theory book already has a root position")

        node = self._insert_node(
            book_id=book_id,
            fen=fen,
            side_to_move=side_to_move,
            name=name,
            evaluation=evaluation,
            captured_pieces=captured_pieces,
        )
        with self._connection:
            self._connection.execute(
                "INSERT INTO theory_book_roots (book_id, node_id) VALUES (?, ?)",
                (book_id, node.id),
            )
        return node

    def get_root(self, book_id: str) -> Optional[TheoryNode]:
        row = self._connection.execute(
            """
            SELECT n.*
            FROM theory_book_roots br
            JOIN theory_nodes n ON n.id = br.node_id
            WHERE br.book_id = ?
            """,
            (book_id,),
        ).fetchone()
        return self._node_from_row(row) if row else None

    def get_node(self, node_id: str) -> Optional[TheoryNode]:
        row = self._connection.execute(
            "SELECT * FROM theory_nodes WHERE id = ?",
            (node_id,),
        ).fetchone()
        return self._node_from_row(row) if row else None

    def update_node(
        self,
        node_id: str,
        *,
        name: Optional[str] = None,
        evaluation: Optional[str] = None,
        captured_pieces: Optional[str] = None,
    ) -> TheoryNode:
        self._require_existing_node(node_id)
        now = self._now()
        with self._connection:
            self._connection.execute(
                """
                UPDATE theory_nodes
                SET name = ?, evaluation = ?, captured_pieces = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    self._clean_optional_text(name),
                    self._clean_optional_text(evaluation),
                    self._clean_optional_text(captured_pieces),
                    now,
                    node_id,
                ),
            )
        node = self.get_node(node_id)
        if node is None:
            raise RuntimeError("Updated theory node could not be read back")
        return node

    def update_node_layout(
        self,
        node_id: str,
        *,
        layout_x: Optional[float],
        layout_y: Optional[float],
    ) -> TheoryNode:
        self._require_existing_node(node_id)
        clean_x = self._clean_optional_float(layout_x, "layout_x")
        clean_y = self._clean_optional_float(layout_y, "layout_y")
        now = self._now()
        with self._connection:
            self._connection.execute(
                """
                UPDATE theory_nodes
                SET layout_x = ?, layout_y = ?, updated_at = ?
                WHERE id = ?
                """,
                (clean_x, clean_y, now, node_id),
            )
        node = self.get_node(node_id)
        if node is None:
            raise RuntimeError("Updated theory node layout could not be read back")
        return node

    def update_node_layouts(self, positions: dict[str, tuple[float, float]]) -> None:
        if not positions:
            return
        now = self._now()
        with self._connection:
            for node_id, (layout_x, layout_y) in positions.items():
                self._require_existing_node(node_id)
                self._connection.execute(
                    """
                    UPDATE theory_nodes
                    SET layout_x = ?, layout_y = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        self._clean_optional_float(layout_x, "layout_x"),
                        self._clean_optional_float(layout_y, "layout_y"),
                        now,
                        node_id,
                    ),
                )

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
    ) -> TheoryBranch:
        parent = self._require_existing_node(parent_node_id)
        clean_move = self._require_text(move_san, "move_san")
        child = self._insert_node(
            book_id=parent.book_id,
            fen=fen,
            side_to_move=side_to_move,
            name=name,
            evaluation=evaluation,
            captured_pieces=captured_pieces,
        )
        edge_id = self._new_id()
        now = self._now()
        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO theory_edges (
                        id, book_id, parent_node_id, child_node_id,
                        move_san, move_uci, mover_color, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        edge_id,
                        parent.book_id,
                        parent_node_id,
                        child.id,
                        clean_move,
                        self._clean_optional_text(move_uci),
                        self._clean_optional_text(mover_color),
                        now,
                    ),
                )
        except sqlite3.IntegrityError as exc:
            with self._connection:
                self._connection.execute("DELETE FROM theory_nodes WHERE id = ?", (child.id,))
            raise ValueError(f"Could not create child branch: {exc}") from exc

        edge = self._require_existing_edge(edge_id)
        return TheoryBranch(edge=edge, node=child)

    def get_children(self, node_id: str) -> list[TheoryBranch]:
        rows = self._connection.execute(
            """
            SELECT
                e.id AS edge_id,
                e.book_id AS edge_book_id,
                e.parent_node_id,
                e.child_node_id,
                e.move_san,
                e.move_uci,
                e.mover_color,
                e.created_at AS edge_created_at,
                n.id AS node_id,
                n.book_id AS node_book_id,
                n.fen,
                n.side_to_move,
                n.name,
                n.evaluation,
                n.captured_pieces,
                n.layout_x AS node_layout_x,
                n.layout_y AS node_layout_y,
                n.created_at AS node_created_at,
                n.updated_at AS node_updated_at
            FROM theory_edges e
            JOIN theory_nodes n ON n.id = e.child_node_id
            WHERE e.parent_node_id = ?
            ORDER BY lower(e.move_san), e.created_at
            """,
            (node_id,),
        ).fetchall()
        return [self._branch_from_joined_row(row) for row in rows]

    def get_parent_branch(self, node_id: str) -> Optional[TheoryBranch]:
        row = self._connection.execute(
            """
            SELECT
                e.id AS edge_id,
                e.book_id AS edge_book_id,
                e.parent_node_id,
                e.child_node_id,
                e.move_san,
                e.move_uci,
                e.mover_color,
                e.created_at AS edge_created_at,
                n.id AS node_id,
                n.book_id AS node_book_id,
                n.fen,
                n.side_to_move,
                n.name,
                n.evaluation,
                n.captured_pieces,
                n.layout_x AS node_layout_x,
                n.layout_y AS node_layout_y,
                n.created_at AS node_created_at,
                n.updated_at AS node_updated_at
            FROM theory_edges e
            JOIN theory_nodes n ON n.id = e.parent_node_id
            WHERE e.child_node_id = ?
            """,
            (node_id,),
        ).fetchone()
        return self._branch_from_joined_row(row) if row else None

    def preview_delete_subtree(self, node_id: str) -> DeletePreview:
        self._require_existing_node(node_id)
        node_rows = self._connection.execute(
            """
            WITH RECURSIVE subtree(id) AS (
                SELECT ?
                UNION ALL
                SELECT e.child_node_id
                FROM theory_edges e
                JOIN subtree s ON e.parent_node_id = s.id
            )
            SELECT n.id, n.name, n.fen
            FROM theory_nodes n
            JOIN subtree s ON s.id = n.id
            ORDER BY n.created_at
            """,
            (node_id,),
        ).fetchall()
        node_ids = tuple(row["id"] for row in node_rows)
        edge_rows = self._connection.execute(
            self._sql_with_in_clause(
                "SELECT id FROM theory_edges WHERE parent_node_id IN ({}) ORDER BY created_at",
                node_ids,
            ),
            node_ids,
        ).fetchall() if node_ids else []
        edge_ids = tuple(row["id"] for row in edge_rows)
        labels = tuple(
            (row["name"] or row["fen"].split()[0])
            for row in node_rows
        )
        return DeletePreview(
            root_node_id=node_id,
            node_ids=node_ids,
            edge_ids=edge_ids,
            node_count=len(node_ids),
            edge_count=len(edge_ids),
            labels=labels,
        )

    def delete_subtree(self, node_id: str) -> DeletePreview:
        preview = self.preview_delete_subtree(node_id)
        if not preview.node_ids:
            return preview

        with self._connection:
            self._connection.execute(
                self._sql_with_in_clause(
                    "DELETE FROM theory_book_roots WHERE node_id IN ({})",
                    preview.node_ids,
                ),
                preview.node_ids,
            )
            self._connection.execute(
                self._sql_with_in_clause(
                    "DELETE FROM theory_edges WHERE parent_node_id IN ({}) OR child_node_id IN ({})",
                    preview.node_ids,
                    repeat=2,
                ),
                preview.node_ids + preview.node_ids,
            )
            self._connection.execute(
                self._sql_with_in_clause(
                    "DELETE FROM theory_nodes WHERE id IN ({})",
                    preview.node_ids,
                ),
                preview.node_ids,
            )
        return preview

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS theory_books (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    source_type TEXT NOT NULL DEFAULT 'independent_position',
                    initial_moves TEXT NOT NULL DEFAULT '[]',
                    map_backward_depth INTEGER NOT NULL DEFAULT 2,
                    map_forward_depth INTEGER NOT NULL DEFAULT 4,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    CHECK (source_type IN ('synchronized_line', 'independent_position')),
                    CHECK (map_backward_depth BETWEEN 0 AND 50),
                    CHECK (map_forward_depth BETWEEN 1 AND 50)
                );

                CREATE TABLE IF NOT EXISTS theory_nodes (
                    id TEXT PRIMARY KEY,
                    book_id TEXT NOT NULL,
                    fen TEXT NOT NULL,
                    side_to_move TEXT NOT NULL,
                    name TEXT,
                    evaluation TEXT,
                    captured_pieces TEXT,
                    layout_x REAL,
                    layout_y REAL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (book_id) REFERENCES theory_books(id) ON DELETE CASCADE,
                    CHECK (length(trim(fen)) > 0),
                    CHECK (side_to_move IN ('white', 'black'))
                );

                CREATE TABLE IF NOT EXISTS theory_edges (
                    id TEXT PRIMARY KEY,
                    book_id TEXT NOT NULL,
                    parent_node_id TEXT NOT NULL,
                    child_node_id TEXT NOT NULL UNIQUE,
                    move_san TEXT NOT NULL,
                    move_uci TEXT,
                    mover_color TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (book_id) REFERENCES theory_books(id) ON DELETE CASCADE,
                    FOREIGN KEY (parent_node_id) REFERENCES theory_nodes(id) ON DELETE CASCADE,
                    FOREIGN KEY (child_node_id) REFERENCES theory_nodes(id) ON DELETE CASCADE,
                    CHECK (length(trim(move_san)) > 0),
                    CHECK (mover_color IS NULL OR mover_color IN ('white', 'black')),
                    UNIQUE (parent_node_id, move_san)
                );

                CREATE TABLE IF NOT EXISTS theory_book_roots (
                    book_id TEXT PRIMARY KEY,
                    node_id TEXT NOT NULL UNIQUE,
                    FOREIGN KEY (book_id) REFERENCES theory_books(id) ON DELETE CASCADE,
                    FOREIGN KEY (node_id) REFERENCES theory_nodes(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_theory_nodes_book ON theory_nodes(book_id);
                CREATE INDEX IF NOT EXISTS idx_theory_edges_parent ON theory_edges(parent_node_id);
                CREATE INDEX IF NOT EXISTS idx_theory_edges_child ON theory_edges(child_node_id);
                """
            )
            self._ensure_book_source_columns()

    def _insert_node(
        self,
        *,
        book_id: str,
        fen: str,
        side_to_move: str,
        name: Optional[str],
        evaluation: Optional[str],
        captured_pieces: Optional[str],
    ) -> TheoryNode:
        clean_fen = self._require_text(fen, "fen")
        clean_side = self._require_side(side_to_move)
        node_id = self._new_id()
        now = self._now()
        with self._connection:
            self._connection.execute(
                """
                INSERT INTO theory_nodes (
                    id, book_id, fen, side_to_move, name,
                    evaluation, captured_pieces, layout_x, layout_y, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node_id,
                    book_id,
                    clean_fen,
                    clean_side,
                    self._clean_optional_text(name),
                    self._clean_optional_text(evaluation),
                    self._clean_optional_text(captured_pieces),
                    None,
                    None,
                    now,
                    now,
                ),
            )
        node = self.get_node(node_id)
        if node is None:
            raise RuntimeError("Created theory node could not be read back")
        return node

    def _require_existing_book(self, book_id: str) -> TheoryBook:
        book = self.get_book(book_id)
        if book is None:
            raise KeyError(f"Unknown theory book: {book_id}")
        return book

    def _require_existing_node(self, node_id: str) -> TheoryNode:
        node = self.get_node(node_id)
        if node is None:
            raise KeyError(f"Unknown theory node: {node_id}")
        return node

    def _require_existing_edge(self, edge_id: str) -> TheoryEdge:
        row = self._connection.execute(
            "SELECT * FROM theory_edges WHERE id = ?",
            (edge_id,),
        ).fetchone()
        if row is None:
            raise KeyError(f"Unknown theory edge: {edge_id}")
        return self._edge_from_row(row)

    def _ensure_book_source_columns(self) -> None:
        book_columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(theory_books)").fetchall()
        }
        node_columns = {
            row["name"]
            for row in self._connection.execute("PRAGMA table_info(theory_nodes)").fetchall()
        }
        with self._connection:
            if "source_type" not in book_columns:
                self._connection.execute(
                    "ALTER TABLE theory_books "
                    "ADD COLUMN source_type TEXT NOT NULL DEFAULT 'independent_position'"
                )
            if "initial_moves" not in book_columns:
                self._connection.execute(
                    "ALTER TABLE theory_books "
                    "ADD COLUMN initial_moves TEXT NOT NULL DEFAULT '[]'"
                )
            if "map_backward_depth" not in book_columns:
                self._connection.execute(
                    "ALTER TABLE theory_books "
                    "ADD COLUMN map_backward_depth INTEGER NOT NULL DEFAULT 2"
                )
            if "map_forward_depth" not in book_columns:
                self._connection.execute(
                    "ALTER TABLE theory_books "
                    "ADD COLUMN map_forward_depth INTEGER NOT NULL DEFAULT 4"
                )
            if "layout_x" not in node_columns:
                self._connection.execute("ALTER TABLE theory_nodes ADD COLUMN layout_x REAL")
            if "layout_y" not in node_columns:
                self._connection.execute("ALTER TABLE theory_nodes ADD COLUMN layout_y REAL")

    @staticmethod
    def _require_source_type(value: str) -> str:
        clean_value = SQLiteTheoryGraphStore._require_text(value, "source_type")
        if clean_value not in THEORY_SOURCE_TYPES:
            raise ValueError(
                "source_type must be 'synchronized_line' or 'independent_position'"
            )
        return clean_value

    @staticmethod
    def _require_depth(value: int, label: str) -> int:
        try:
            clean_value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be an integer") from exc
        minimum = 0 if label == "backward_depth" else 1
        if clean_value < minimum or clean_value > 50:
            raise ValueError(f"{label} must be between {minimum} and 50")
        return clean_value

    @staticmethod
    def _clean_optional_float(value: Optional[float], label: str) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be numeric") from exc

    @staticmethod
    def _serialize_initial_moves(initial_moves: Tuple[str, ...]) -> str:
        if initial_moves is None:
            return "[]"
        clean_moves = [str(move).strip() for move in initial_moves if str(move).strip()]
        return json.dumps(clean_moves, ensure_ascii=False)

    @staticmethod
    def _deserialize_initial_moves(raw_value: str) -> Tuple[str, ...]:
        if not raw_value:
            return ()
        try:
            value = json.loads(raw_value)
        except json.JSONDecodeError:
            return ()
        if not isinstance(value, list):
            return ()
        return tuple(str(move) for move in value if str(move).strip())

    @staticmethod
    def _new_id() -> str:
        return uuid4().hex

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    @staticmethod
    def _require_text(value: str, label: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} is required")
        return value.strip()

    @staticmethod
    def _require_side(value: str) -> str:
        clean_value = SQLiteTheoryGraphStore._require_text(value, "side_to_move")
        if clean_value not in {"white", "black"}:
            raise ValueError("side_to_move must be 'white' or 'black'")
        return clean_value

    @staticmethod
    def _clean_optional_text(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        clean_value = str(value).strip()
        return clean_value or None

    def _book_from_row(self, row: sqlite3.Row) -> TheoryBook:
        return TheoryBook(
            id=row["id"],
            name=row["name"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            root_node_id=row["root_node_id"],
            source_type=row["source_type"] if "source_type" in row.keys() else THEORY_SOURCE_INDEPENDENT,
            initial_moves=self._deserialize_initial_moves(
                row["initial_moves"] if "initial_moves" in row.keys() else "[]"
            ),
            map_backward_depth=int(row["map_backward_depth"]) if "map_backward_depth" in row.keys() else 2,
            map_forward_depth=int(row["map_forward_depth"]) if "map_forward_depth" in row.keys() else 4,
        )

    @staticmethod
    def _node_from_row(row: sqlite3.Row) -> TheoryNode:
        return TheoryNode(
            id=row["id"],
            book_id=row["book_id"],
            fen=row["fen"],
            side_to_move=row["side_to_move"],
            name=row["name"],
            evaluation=row["evaluation"],
            captured_pieces=row["captured_pieces"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            layout_x=row["layout_x"] if "layout_x" in row.keys() else None,
            layout_y=row["layout_y"] if "layout_y" in row.keys() else None,
        )

    @staticmethod
    def _edge_from_row(row: sqlite3.Row) -> TheoryEdge:
        return TheoryEdge(
            id=row["id"],
            book_id=row["book_id"],
            parent_node_id=row["parent_node_id"],
            child_node_id=row["child_node_id"],
            move_san=row["move_san"],
            move_uci=row["move_uci"],
            mover_color=row["mover_color"],
            created_at=row["created_at"],
        )

    @classmethod
    def _branch_from_joined_row(cls, row: sqlite3.Row) -> TheoryBranch:
        edge = TheoryEdge(
            id=row["edge_id"],
            book_id=row["edge_book_id"],
            parent_node_id=row["parent_node_id"],
            child_node_id=row["child_node_id"],
            move_san=row["move_san"],
            move_uci=row["move_uci"],
            mover_color=row["mover_color"],
            created_at=row["edge_created_at"],
        )
        node = TheoryNode(
            id=row["node_id"],
            book_id=row["node_book_id"],
            fen=row["fen"],
            side_to_move=row["side_to_move"],
            name=row["name"],
            evaluation=row["evaluation"],
            captured_pieces=row["captured_pieces"],
            created_at=row["node_created_at"],
            updated_at=row["node_updated_at"],
            layout_x=row["node_layout_x"] if "node_layout_x" in row.keys() else None,
            layout_y=row["node_layout_y"] if "node_layout_y" in row.keys() else None,
        )
        return TheoryBranch(edge=edge, node=node)

    @staticmethod
    def _sql_with_in_clause(template: str, values: Sequence[str], repeat: int = 1) -> str:
        if not values:
            raise ValueError("IN clause values cannot be empty")
        placeholders = ", ".join("?" for _ in values)
        if repeat == 1:
            return template.format(placeholders)
        return template.format(*([placeholders] * repeat))
