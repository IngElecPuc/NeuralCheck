"""Stable DTOs for opening-theory trees.

These dataclasses are intentionally storage-agnostic. The UI and application
controllers should depend on them, not on SQLite rows, Neo4j objects or HTTP
payloads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

THEORY_SOURCE_SYNCHRONIZED = "synchronized_line"
THEORY_SOURCE_INDEPENDENT = "independent_position"
THEORY_SOURCE_TYPES = (THEORY_SOURCE_SYNCHRONIZED, THEORY_SOURCE_INDEPENDENT)


@dataclass(frozen=True)
class TheoryBook:
    """A named opening-theory tree, for example 'Siciliana'."""

    id: str
    name: str
    created_at: str
    updated_at: str
    root_node_id: Optional[str] = None
    source_type: str = THEORY_SOURCE_INDEPENDENT
    initial_moves: Tuple[str, ...] = ()

    @property
    def is_synchronized_line(self) -> bool:
        return self.source_type == THEORY_SOURCE_SYNCHRONIZED


@dataclass(frozen=True)
class TheoryNode:
    """A chess position node in a theory tree."""

    id: str
    book_id: str
    fen: str
    side_to_move: str
    name: Optional[str]
    evaluation: Optional[str]
    captured_pieces: Optional[str]
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TheoryEdge:
    """Directed relation between two positions.

    The relation owns the move that produced the child position.
    """

    id: str
    book_id: str
    parent_node_id: str
    child_node_id: str
    move_san: str
    move_uci: Optional[str]
    mover_color: Optional[str]
    created_at: str


@dataclass(frozen=True)
class TheoryBranch:
    """Convenience view for a child relation and its target node."""

    edge: TheoryEdge
    node: TheoryNode


@dataclass(frozen=True)
class DeletePreview:
    """Subtree impact report used before destructive deletes."""

    root_node_id: str
    node_ids: Tuple[str, ...]
    edge_ids: Tuple[str, ...]
    node_count: int
    edge_count: int
    labels: Tuple[str, ...]
