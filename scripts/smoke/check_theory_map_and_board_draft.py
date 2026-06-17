from pathlib import Path
from tempfile import TemporaryDirectory

from neuralcheck.application.game_controller import GameController
from neuralcheck.application.theory_controller import TheoryController


def main():
    with TemporaryDirectory() as tmp_dir:
        game = GameController()
        controller = TheoryController.with_sqlite(Path(tmp_dir) / "theory.db", game_controller=game)
        try:
            book = controller.create_book("Mapa")
            root = controller.create_root_from_current_position(book.id, name="Inicial")
            game.click_square("e2")
            move_result = game.click_square("e4")
            controller.create_move_draft_from_board_move(move_result.movement)
            branch = controller.commit_move_draft(name="Peón rey")
            controller.add_child_by_move(branch.node.id, "c5", name="Siciliana")
            controller.add_child_by_move(branch.node.id, "e5", name="Abierta")

            game.new_game()
            unnamed_book = controller.create_book("Etiquetas")
            unnamed_root = controller.create_root_from_current_position(unnamed_book.id)
            unnamed_e4 = controller.add_child_by_move(unnamed_root.id, "e4")
            controller.add_child_by_move(unnamed_e4.node.id, "c5")

            controller.select_node(root.id)
            map_view = controller.get_map_view(depth=2)
            assert len(map_view.nodes) == 4
            assert {edge.move_san for edge in map_view.edges} == {"e4", "c5", "e5"}

            controller.select_node(unnamed_root.id)
            label_view = controller.get_map_view(depth=2)
            labels = {node.label for node in label_view.nodes}
            assert {"w1", "b1", "w2"}.issubset(labels)
        finally:
            controller.close()

    print("Theory map and board draft smoke passed")


if __name__ == "__main__":
    main()
