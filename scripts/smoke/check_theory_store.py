from pathlib import Path
from tempfile import TemporaryDirectory

from neuralcheck.theory.service import TheoryService
from neuralcheck.theory.sqlite_store import SQLiteTheoryGraphStore

INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
AFTER_C5_FEN = "rnbqkbnr/pp1ppppp/8/2p5/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
AFTER_NF3_FEN = "rnbqkbnr/pp1ppppp/8/2p5/8/5N2/PPPPPPPP/RNBQKB1R b - - 0 1"
AFTER_E6_FEN = "rnbqkbnr/pppp1ppp/4p3/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"


def main() -> None:
    with TemporaryDirectory() as tmp_dir:
        store = SQLiteTheoryGraphStore(Path(tmp_dir) / "theory.db")
        try:
            service = TheoryService(store)
            book = service.create_book("Smoke Siciliana")
            root = service.create_root(book.id, INITIAL_FEN, name="Inicial")
            c5 = service.add_child(root.id, AFTER_C5_FEN, move_san="c5", name="Siciliana")
            service.add_child(c5.node.id, AFTER_NF3_FEN, move_san="Nf3", name="Abierta")
            service.add_child(root.id, AFTER_E6_FEN, move_san="e6", name="Francesa")

            children = service.get_children(root.id)
            assert [branch.edge.move_san for branch in children] == ["c5", "e6"]

            preview = service.preview_delete_subtree(c5.node.id)
            assert preview.node_count == 2
            service.delete_subtree(c5.node.id)
            assert [branch.edge.move_san for branch in service.get_children(root.id)] == ["e6"]
        finally:
            store.close()

    print("Theory store smoke passed")


if __name__ == "__main__":
    main()
