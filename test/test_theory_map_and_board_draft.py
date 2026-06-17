from pathlib import Path

from neuralcheck.application.game_controller import GameController
from neuralcheck.application.theory_controller import TheoryController


def test_theory_map_view_is_depth_limited(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Siciliana")
        root = theory_controller.create_root_from_current_position(book.id, name="Inicial")
        e4 = theory_controller.add_child_by_move(root.id, "e4", name="Peón rey")
        c5 = theory_controller.add_child_by_move(e4.node.id, "c5", name="Siciliana")
        theory_controller.add_child_by_move(c5.node.id, "Nf3", name="Abierta")
        theory_controller.add_child_by_move(c5.node.id, "c3", name="Alapín")

        theory_controller.select_node(root.id)
        shallow = theory_controller.get_map_view(depth=1)
        assert {node.label for node in shallow.nodes} == {"Inicial", "Peón rey"}
        assert [edge.move_san for edge in shallow.edges] == ["e4"]

        theory_controller.select_node(e4.node.id)
        deeper = theory_controller.get_map_view(depth=2)
        assert {node.label for node in deeper.nodes} == {"Peón rey", "Siciliana", "Abierta", "Alapín"}
        assert {edge.move_san for edge in deeper.edges} == {"c5", "Nf3", "c3"}
        assert any(node.is_selected and node.id == e4.node.id for node in deeper.nodes)
    finally:
        theory_controller.close()


def test_board_move_draft_can_be_committed_as_child(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Repertorio")
        root = theory_controller.create_root_from_current_position(book.id, name="Inicial")

        game_controller.click_square("e2")
        move_result = game_controller.click_square("e4")
        assert move_result.moved

        draft = theory_controller.create_move_draft_from_board_move(move_result.movement)
        assert draft.parent_node_id == root.id
        assert draft.move_san == "e4"
        assert draft.board_after_fen == game_controller.current_fen(include_state=True)

        branch = theory_controller.commit_move_draft(name="Avance central", evaluation="=")
        assert branch.edge.move_san == "e4"
        assert branch.node.name == "Avance central"
        assert branch.node.evaluation == "="
        assert theory_controller.get_move_draft() is None
        assert theory_controller.selected_node_id == branch.node.id
    finally:
        theory_controller.close()


def test_cancel_board_move_draft_restores_parent_position(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Repertorio")
        root = theory_controller.create_root_from_current_position(book.id, name="Inicial")
        root_fen = root.fen

        game_controller.click_square("e2")
        move_result = game_controller.click_square("e4")
        theory_controller.create_move_draft_from_board_move(move_result.movement)
        assert game_controller.current_fen(include_state=True) != root_fen

        validation = theory_controller.cancel_move_draft()
        assert validation.valid
        assert theory_controller.get_move_draft() is None
        assert theory_controller.selected_node_id == root.id
        assert game_controller.current_fen(include_state=True) == root_fen
    finally:
        theory_controller.close()


def test_default_theory_map_labels_use_side_and_move_number(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Repertorio")
        root = theory_controller.create_root_from_current_position(book.id)
        e4 = theory_controller.add_child_by_move(root.id, "e4")
        c5 = theory_controller.add_child_by_move(e4.node.id, "c5")

        theory_controller.select_node(root.id)
        view = theory_controller.get_map_view(depth=2)
        labels_by_id = {node.id: node.label for node in view.nodes}

        assert labels_by_id[root.id] == "w1"
        assert labels_by_id[e4.node.id] == "b1"
        assert labels_by_id[c5.node.id] == "w2"
    finally:
        theory_controller.close()
