from tempfile import TemporaryDirectory
from pathlib import Path

from neuralcheck.application.game_controller import GameController
from neuralcheck.application.theory_controller import TheoryController


def main():
    with TemporaryDirectory() as tmp_dir:
        controller = TheoryController.with_sqlite(
            Path(tmp_dir) / "theory.db",
            game_controller=GameController(),
        )
        try:
            game = controller.game_controller
            game.click_square("e2")
            game.click_square("e4")
            book = controller.create_book("Siciliana")
            controller.update_book(book.id, name="Defensa Siciliana")
            root = controller.create_root_from_current_position(book.id, name="Después de e4")
            c5 = controller.add_child_by_move(root.id, "c5", name="Siciliana")
            controller.add_child_by_move(root.id, "e6", name="Francesa")
            nf3 = controller.add_child_by_move(c5.node.id, "Nf3", name="Abierta")
            controller.add_child_by_move(c5.node.id, "c3", name="Alapín")

            controller.select_node(nf3.node.id)
            controller.update_selected_node(name="Siciliana abierta", evaluation="=")
            view = controller.get_local_view()

            assert view.book is not None
            assert view.book.name == "Defensa Siciliana"
            assert view.current_node is not None
            assert view.current_node.name == "Siciliana abierta"
            assert view.parent_branch is not None
            assert view.parent_branch.node.name == "Siciliana"
            assert [branch.edge.move_san for branch in view.path] == ["c5", "Nf3"]
            assert [branch.edge.move_san for branch in view.siblings] == ["c3", "Nf3"]

            controller.select_sibling(-1)
            assert controller.get_selected_node().name == "Alapín"
            controller.select_first_child()
        finally:
            controller.close()

    print("Theory CRUD navigation smoke passed")


if __name__ == "__main__":
    main()
