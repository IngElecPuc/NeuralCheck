from pathlib import Path
from tempfile import TemporaryDirectory

from neuralcheck.application.clock import ChessClock
from neuralcheck.application.game_controller import GameController
from neuralcheck.application.theory_controller import TheoryController


def main() -> None:
    clock = ChessClock.rapid_3_0()
    assert clock.tick(white_turn=True).white_seconds == 179
    clock.set_correspondence()
    snapshot = clock.tick(white_turn=False)
    assert not snapshot.visible
    assert snapshot.black_seconds == 0

    with TemporaryDirectory() as tmp_dir:
        game_controller = GameController()
        theory_controller = TheoryController.with_sqlite(
            Path(tmp_dir) / "theory.db",
            game_controller=game_controller,
        )
        try:
            game_controller.click_square("e2")
            game_controller.click_square("e4")
            game_controller.click_square("e7")
            game_controller.click_square("e5")
            book = theory_controller.create_book("Smoke Italiana")
            root = theory_controller.create_root_from_current_position(book.id, name="Después de e4 e5")
            nf3 = theory_controller.add_child_by_move(root.id, "Nf3", name="Caballo rey")
            nc6 = theory_controller.add_child_by_move(nf3.node.id, "Nc6", name="Caballo dama")
            bc4 = theory_controller.add_child_by_move(nc6.node.id, "Bc4", name="Italiana")

            stored_book = theory_controller.service.get_book(book.id)
            assert stored_book is not None
            assert stored_book.source_type == "synchronized_line"
            assert stored_book.initial_moves == ("e4", "e5")

            game_controller.new_game()
            validation = theory_controller.load_node_to_board(bc4.node.id)
            assert validation.valid
            assert game_controller.current_fen(include_state=True) == bc4.node.fen
            assert game_controller.white_turn is False
        finally:
            theory_controller.close()

    print("Theory sync and clock smoke passed")


if __name__ == "__main__":
    main()
