from pathlib import Path

import pytest

from neuralcheck.application.game_controller import GameController
from neuralcheck.application.theory_controller import TheoryController
from neuralcheck.theory.service import TheoryService
from neuralcheck.theory.sqlite_store import SQLiteTheoryGraphStore


INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
AFTER_E4_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b - - 0 1"
AFTER_C5_FEN = "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w - - 0 1"
AFTER_NF3_FEN = "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b - - 0 1"
AFTER_C3_FEN = "rnbqkbnr/pp1ppppp/8/2p5/4P3/2P5/PP1P1PPP/RNBQKBNR b - - 0 1"
AFTER_E6_FEN = "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w - - 0 1"


@pytest.fixture()
def service(tmp_path: Path) -> TheoryService:
    store = SQLiteTheoryGraphStore(tmp_path / "theory.db")
    try:
        yield TheoryService(store)
    finally:
        store.close()


def test_create_book_root_and_children(service: TheoryService):
    book = service.create_book("Siciliana")
    root = service.create_root(book.id, INITIAL_FEN, name="Inicial")

    c5 = service.add_child(root.id, AFTER_C5_FEN, move_san="c5", name="Siciliana")
    c3 = service.add_child(c5.node.id, AFTER_C3_FEN, move_san="c3", name="Alapín")
    nf3 = service.add_child(c5.node.id, AFTER_NF3_FEN, move_san="Nf3", name="Abierta")
    e6 = service.add_child(root.id, AFTER_E6_FEN, move_san="e6", name="Francesa")

    children = service.get_children(root.id)
    assert [branch.edge.move_san for branch in children] == ["c5", "e6"]
    assert children[0].edge.mover_color == "white"
    assert children[0].node.side_to_move == "white"

    sicilian_children = service.get_children(c5.node.id)
    assert {branch.edge.move_san for branch in sicilian_children} == {"c3", "Nf3"}
    assert c3.edge.mover_color == "white"
    assert nf3.edge.mover_color == "white"
    assert e6.node.name == "Francesa"


def test_delete_preview_and_subtree_delete(service: TheoryService):
    book = service.create_book("Siciliana")
    root = service.create_root(book.id, INITIAL_FEN, name="Inicial")
    c5 = service.add_child(root.id, AFTER_C5_FEN, move_san="c5", name="Siciliana")
    service.add_child(c5.node.id, AFTER_C3_FEN, move_san="c3", name="Alapín")
    service.add_child(c5.node.id, AFTER_NF3_FEN, move_san="Nf3", name="Abierta")
    service.add_child(root.id, AFTER_E6_FEN, move_san="e6", name="Francesa")

    preview = service.preview_delete_subtree(c5.node.id)
    assert preview.node_count == 3
    assert preview.edge_count == 2
    assert "Siciliana" in preview.labels
    assert "Alapín" in preview.labels

    deleted = service.delete_subtree(c5.node.id)
    assert deleted.node_count == 3
    children = service.get_children(root.id)
    assert [branch.edge.move_san for branch in children] == ["e6"]
    assert service.get_node(c5.node.id) is None


def test_rejects_invalid_theory_data(service: TheoryService):
    book = service.create_book("Siciliana")
    root = service.create_root(book.id, INITIAL_FEN)

    with pytest.raises(ValueError):
        service.create_book("  ")

    with pytest.raises(ValueError):
        service.create_root(book.id, INITIAL_FEN)

    with pytest.raises(ValueError):
        service.add_child(root.id, AFTER_C5_FEN, move_san="  ")

    with pytest.raises(ValueError):
        service.add_child(root.id, "not-a-fen", move_san="c5")


def test_theory_controller_uses_current_board_position(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )

    book = theory_controller.create_book("Repertorio")
    root = theory_controller.create_root_from_current_position(book.id, name="Inicial")

    game_controller.click_square("e2")
    game_controller.click_square("e4")
    branch = theory_controller.add_child_from_current_position(root.id, move_san="e4", name="Avance central")

    assert branch.node.side_to_move == "black"
    assert theory_controller.select_node(root.id) is not None
    validation = theory_controller.load_node_to_board(branch.node.id)
    assert validation.valid
    assert game_controller.current_fen(include_state=True) == branch.node.fen


def test_create_root_marks_synchronized_line_from_visible_history(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )

    game_controller.click_square("e2")
    game_controller.click_square("e4")
    game_controller.click_square("e7")
    game_controller.click_square("e5")

    book = theory_controller.create_book("Italiana")
    theory_controller.create_root_from_current_position(book.id, name="Después de e4 e5")

    stored_book = theory_controller.service.get_book(book.id)
    assert stored_book is not None
    assert stored_book.source_type == "synchronized_line"
    assert stored_book.initial_moves == ("e4", "e5")


def test_create_root_marks_manual_position_as_independent(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    validation = game_controller.apply_fen_position(
        "4k3/8/8/8/8/8/8/4K3 b - - 0 1"
    )
    assert validation.valid

    book = theory_controller.create_book("Puzzle")
    theory_controller.create_root_from_current_position(book.id, name="Custom")

    stored_book = theory_controller.service.get_book(book.id)
    assert stored_book is not None
    assert stored_book.source_type == "independent_position"
    assert stored_book.initial_moves == ()


def test_add_child_by_move_generates_child_fen_from_parent(service: TheoryService):
    book = service.create_book("Italiana")
    root = service.create_root(book.id, INITIAL_FEN, name="Inicial")

    e4 = service.add_child_by_move(root.id, "e4", name="Peón rey")
    e5 = service.add_child_by_move(e4.node.id, "e5", name="Respuesta simétrica")
    nf3 = service.add_child_by_move(e5.node.id, "Nf3", name="Caballo rey")
    nc6 = service.add_child_by_move(nf3.node.id, "Nc6", name="Caballo dama")
    bc4 = service.add_child_by_move(nc6.node.id, "Bc4", name="Italiana")

    assert e4.node.fen == AFTER_E4_FEN
    assert e5.node.fen == "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w - - 0 1"
    assert bc4.node.side_to_move == "black"
    assert bc4.node.fen == "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b - - 0 1"


def test_load_synchronized_theory_node_reconstructs_history(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )

    game_controller.click_square("e2")
    game_controller.click_square("e4")
    game_controller.click_square("e7")
    game_controller.click_square("e5")
    book = theory_controller.create_book("Italiana")
    root = theory_controller.create_root_from_current_position(book.id, name="Después de e4 e5")
    nf3 = theory_controller.add_child_by_move(root.id, "Nf3", name="Caballo rey")
    nc6 = theory_controller.add_child_by_move(nf3.node.id, "Nc6", name="Caballo dama")
    bc4 = theory_controller.add_child_by_move(nc6.node.id, "Bc4", name="Italiana")

    game_controller.new_game()
    validation = theory_controller.load_node_to_board(bc4.node.id)

    assert validation.valid
    assert game_controller.current_fen(include_state=True) == bc4.node.fen
    rows = game_controller.history_rows()
    assert rows[0].white_move == "e4"
    assert rows[0].black_move == "e5"
    assert rows[2].white_move == "Bc4"
    assert game_controller.white_turn is False


def test_theory_controller_close_releases_sqlite_database(tmp_path: Path):
    db_path = tmp_path / "theory.db"
    theory_controller = TheoryController.with_sqlite(db_path, game_controller=GameController())
    book = theory_controller.create_book("Cierre")
    theory_controller.create_root_from_current_position(book.id, name="Inicial")

    theory_controller.close()
    db_path.unlink()

    assert not db_path.exists()


def test_independent_source_label_is_explicit(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(tmp_path / "theory.db", game_controller=game_controller)
    try:
        validation = game_controller.apply_fen_position("4k3/8/8/8/8/8/8/4K3 b - - 0 1")
        assert validation.valid
        book = theory_controller.create_book("Puzzle")
        theory_controller.create_root_from_current_position(book.id, name="Custom")

        assert "Posición independiente" in theory_controller.selected_book_source_label()
        assert "sin reconstruir" in theory_controller.selected_book_source_label()
    finally:
        theory_controller.close()
