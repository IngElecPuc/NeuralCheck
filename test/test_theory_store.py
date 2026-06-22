from pathlib import Path

import pytest

from neuralcheck.application.game_controller import GameController
from neuralcheck.application.theory_controller import TheoryController
from neuralcheck.theory.service import TheoryService
from neuralcheck.theory.sqlite_store import SQLiteTheoryGraphStore


INITIAL_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
AFTER_E4_FEN = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b - e3 0 1"
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
    assert e5.node.fen == "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w - e6 0 1"
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


def test_update_book_and_node_metadata(service: TheoryService):
    book = service.create_book("Italiana")
    renamed = service.update_book(book.id, name="Giuoco Piano")
    assert renamed.name == "Giuoco Piano"

    root = service.create_root(book.id, INITIAL_FEN, name="Inicial")
    updated = service.update_node(
        root.id,
        name="Posición inicial",
        evaluation="=",
        captured_pieces="ninguna",
    )

    assert updated.name == "Posición inicial"
    assert updated.evaluation == "="
    assert updated.captured_pieces == "ninguna"

    with pytest.raises(ValueError):
        service.update_book(book.id, name="  ")


def test_controller_local_view_exposes_path_parent_children_and_siblings(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        game_controller.click_square("e2")
        game_controller.click_square("e4")
        book = theory_controller.create_book("Siciliana")
        root = theory_controller.create_root_from_current_position(book.id, name="Después de e4")
        c5 = theory_controller.add_child_by_move(root.id, "c5", name="Siciliana")
        e6 = theory_controller.add_child_by_move(root.id, "e6", name="Francesa")
        nf3 = theory_controller.add_child_by_move(c5.node.id, "Nf3", name="Abierta")
        c3 = theory_controller.add_child_by_move(c5.node.id, "c3", name="Alapín")

        theory_controller.select_node(nf3.node.id)
        view = theory_controller.get_local_view()

        assert view.book is not None
        assert view.book.name == "Siciliana"
        assert view.current_node is not None
        assert view.current_node.name == "Abierta"
        assert view.parent_branch is not None
        assert view.parent_branch.node.name == "Siciliana"
        assert [branch.edge.move_san for branch in view.path] == ["c5", "Nf3"]
        assert [branch.edge.move_san for branch in view.siblings] == ["c3", "Nf3"]
        assert view.children == ()

        theory_controller.select_sibling(-1)
        assert theory_controller.get_selected_node().name == "Alapín"

        theory_controller.select_node(root.id)
        assert [branch.edge.move_san for branch in theory_controller.get_local_view().children] == ["c5", "e6"]
    finally:
        theory_controller.close()


def test_controller_updates_selected_node_metadata(tmp_path: Path):
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=GameController(),
    )
    try:
        book = theory_controller.create_book("Repertorio")
        root = theory_controller.create_root_from_current_position(book.id, name="Inicial")
        theory_controller.select_node(root.id)

        updated = theory_controller.update_selected_node(
            name="Inicial editada",
            evaluation="+=",
            captured_pieces="sin capturas",
        )

        assert updated.name == "Inicial editada"
        assert updated.evaluation == "+="
        assert updated.captured_pieces == "sin capturas"
    finally:
        theory_controller.close()


def test_add_child_by_move_preserves_en_passant_in_theory_nodes(service: TheoryService):
    book = service.create_book("En passant")
    root = service.create_root(book.id, INITIAL_FEN, name="Inicial")

    e4 = service.add_child_by_move(root.id, "e4")
    a6 = service.add_child_by_move(e4.node.id, "a6")
    e5 = service.add_child_by_move(a6.node.id, "e5")
    d5 = service.add_child_by_move(e5.node.id, "d5")
    exd6 = service.add_child_by_move(d5.node.id, "exd6")

    assert d5.node.fen == "rnbqkbnr/1pp1pppp/p7/3pP3/8/8/PPPP1PPP/RNBQKBNR w - d6 0 1"
    assert exd6.node.fen == "rnbqkbnr/1pp1pppp/p2P4/8/8/8/PPPP1PPP/RNBQKBNR b - - 0 1"
    assert exd6.edge.move_san == "exd6"

CUSTOM_EP_ROOT_FEN = "r1b1k2r/p2p1ppp/1qp1p3/3nP3/1bP1NP2/8/PP2K1PP/R1BQ1B1R b - - 0 1"
CUSTOM_AFTER_F5_LEGACY_FEN = "r1b1k2r/p2p2pp/1qp1p3/3nPp2/1bP1NP2/8/PP2K1PP/R1BQ1B1R w - - 0 1"
CUSTOM_AFTER_F5_STATE_FEN = "r1b1k2r/p2p2pp/1qp1p3/3nPp2/1bP1NP2/8/PP2K1PP/R1BQ1B1R w - f6 0 1"
CUSTOM_AFTER_EXF6_FEN = "r1b1k2r/p2p2pp/1qp1pP2/3n4/1bP1NP2/8/PP2K1PP/R1BQ1B1R b - - 0 1"


def test_theory_resolves_legacy_child_en_passant_from_parent_edge(service: TheoryService):
    book = service.create_book("Lasker custom")
    root = service.create_root(book.id, CUSTOM_EP_ROOT_FEN, name="Antes de f5")
    f5 = service.add_child(root.id, CUSTOM_AFTER_F5_LEGACY_FEN, move_san="f5", name="f5 legacy")

    assert f5.node.fen == CUSTOM_AFTER_F5_LEGACY_FEN
    assert service.resolve_node_fen(f5.node.id) == CUSTOM_AFTER_F5_STATE_FEN

    exf6 = service.add_child_by_move(f5.node.id, "exf6")

    assert exf6.node.fen == CUSTOM_AFTER_EXF6_FEN
    assert exf6.edge.move_san == "exf6"


def test_theory_controller_loads_independent_legacy_en_passant_state(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Lasker custom")
        root = theory_controller.service.create_root(book.id, CUSTOM_EP_ROOT_FEN, name="Antes de f5")
        f5 = theory_controller.service.add_child(root.id, CUSTOM_AFTER_F5_LEGACY_FEN, move_san="f5")

        validation = theory_controller.load_node_to_board(f5.node.id)

        assert validation.valid
        assert game_controller.current_fen(include_state=True) == CUSTOM_AFTER_F5_STATE_FEN
        assert "f6" in game_controller.legal_targets("e5")
    finally:
        theory_controller.close()


def test_theory_resolves_legacy_en_passant_without_full_path_replay(service: TheoryService, monkeypatch):
    book = service.create_book("Fast en passant")
    root = service.create_root(book.id, CUSTOM_EP_ROOT_FEN, name="Antes de f5")
    f5 = service.add_child(root.id, CUSTOM_AFTER_F5_LEGACY_FEN, move_san="f5", name="f5 legacy")

    def fail_full_path(_node):
        raise AssertionError("full path replay should not be needed for local en-passant repair")

    monkeypatch.setattr(service, "_resolve_node_fen_from_path", fail_full_path)

    assert service.resolve_node_fen(f5.node.id) == CUSTOM_AFTER_F5_STATE_FEN
    exf6 = service.add_child_by_move(f5.node.id, "exf6")
    assert exf6.node.fen == CUSTOM_AFTER_EXF6_FEN


def test_theory_resolved_fen_cache_avoids_replaying_parent_edge(service: TheoryService, monkeypatch):
    book = service.create_book("Cached en passant")
    root = service.create_root(book.id, CUSTOM_EP_ROOT_FEN, name="Antes de f5")
    f5 = service.add_child(root.id, CUSTOM_AFTER_F5_LEGACY_FEN, move_san="f5", name="f5 legacy")

    assert service.resolve_node_fen(f5.node.id) == CUSTOM_AFTER_F5_STATE_FEN

    def fail_parent_edge(*_args, **_kwargs):
        raise AssertionError("cached FEN should avoid another parent-edge replay")

    monkeypatch.setattr(service, "_resolve_node_fen_from_parent_edge", fail_parent_edge)
    assert service.resolve_node_fen(f5.node.id) == CUSTOM_AFTER_F5_STATE_FEN
