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


def test_map_view_can_include_ancestor_context(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Italiana")
        root = theory_controller.create_root_from_current_position(book.id, name="Inicial")
        e4 = theory_controller.add_child_by_move(root.id, "e4", name="Peón rey")
        e5 = theory_controller.add_child_by_move(e4.node.id, "e5", name="Respuesta")
        nf3 = theory_controller.add_child_by_move(e5.node.id, "Nf3", name="Caballo")
        theory_controller.add_child_by_move(nf3.node.id, "Nc6", name="Natural")

        theory_controller.select_node(nf3.node.id)
        view = theory_controller.get_map_view(forward_depth=1, backward_depth=2)
        ids = {node.id for node in view.nodes}

        assert nf3.node.id in ids
        assert e5.node.id in ids
        assert e4.node.id in ids
        assert root.id not in ids
        assert any(edge.parent_node_id == e5.node.id and edge.child_node_id == nf3.node.id for edge in view.edges)
        assert any(edge.parent_node_id == nf3.node.id for edge in view.edges)
        assert any(node.id == e5.node.id and node.depth == -1 for node in view.nodes)
        assert any(node.id == e4.node.id and node.depth == -2 for node in view.nodes)
    finally:
        theory_controller.close()


def test_layout_engine_keeps_nodes_separated():
    from neuralcheck.theory.models import TheoryMapEdge, TheoryMapNode, TheoryMapView
    from neuralcheck.ui_theory_map import TheoryMapLayoutEngine

    nodes = tuple(
        TheoryMapNode(
            id=f"n{index}",
            label=f"n{index}",
            fen="8/8/8/8/8/8/8/8 w - - 0 1",
            side_to_move="white",
            evaluation=None,
            depth=1,
            is_selected=(index == 0),
        )
        for index in range(9)
    )
    edges = tuple(TheoryMapEdge("n0", f"n{index}", f"m{index}") for index in range(1, 9))
    view = TheoryMapView("n0", "n0", nodes, edges, 2)
    engine = TheoryMapLayoutEngine(
        node_radius=40,
        forward_step=130,
        backward_step=120,
        rotation_radians=0.0,
        min_margin=26,
    )
    layout = engine.layout(view, selected_node_id="n0", center=(400, 300))
    positions = [(node.x, node.y) for node in layout.nodes.values()]
    min_distance = 40 * 2 + 26 - 0.01

    for left_index, (x1, y1) in enumerate(positions):
        for x2, y2 in positions[left_index + 1 :]:
            assert ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 >= min_distance

def test_map_view_keeps_siblings_visible_from_selected_branch(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Italiana")
        root = theory_controller.create_root_from_current_position(book.id, name="Base")
        e4 = theory_controller.add_child_by_move(root.id, "e4", name="Peón rey")
        e5 = theory_controller.add_child_by_move(e4.node.id, "e5", name="Principal")
        c5 = theory_controller.add_child_by_move(e4.node.id, "c5", name="Siciliana")
        theory_controller.add_child_by_move(c5.node.id, "Nf3", name="Abierta")
        theory_controller.add_child_by_move(e5.node.id, "Nf3", name="Italiana")

        theory_controller.select_node(e5.node.id)
        view = theory_controller.get_map_view(forward_depth=2, backward_depth=1)
        ids = {node.id for node in view.nodes}

        assert e4.node.id in ids
        assert e5.node.id in ids
        assert c5.node.id in ids
        assert any(edge.parent_node_id == e4.node.id and edge.child_node_id == c5.node.id for edge in view.edges)
    finally:
        theory_controller.close()


def test_layout_engine_positions_lateral_context_nodes():
    from neuralcheck.theory.models import TheoryMapEdge, TheoryMapNode, TheoryMapView
    from neuralcheck.ui_theory_map import TheoryMapLayoutEngine

    nodes = (
        TheoryMapNode("parent", "parent", "8/8/8/8/8/8/8/8 w - - 0 1", "white", None, -1, False),
        TheoryMapNode("selected", "selected", "8/8/8/8/8/8/8/8 w - - 0 1", "white", None, 0, True),
        TheoryMapNode("sibling", "sibling", "8/8/8/8/8/8/8/8 w - - 0 1", "white", None, 0, False),
    )
    edges = (
        TheoryMapEdge("parent", "selected", "e5"),
        TheoryMapEdge("parent", "sibling", "c5"),
    )
    view = TheoryMapView("selected", "selected", nodes, edges, 2)
    engine = TheoryMapLayoutEngine(
        node_radius=40,
        forward_step=130,
        backward_step=120,
        rotation_radians=0.0,
        min_margin=26,
    )

    layout = engine.layout(view, selected_node_id="selected", center=(400, 300))

    assert set(layout.nodes) == {"parent", "selected", "sibling"}


def test_selected_book_max_depth_detects_deep_theory_tree(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Profunda")
        current = theory_controller.create_root_from_current_position(book.id, name="Base")
        for move in ("e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"):
            current = theory_controller.add_child_by_move(current.id, move).node

        theory_controller.select_book(book.id)
        assert theory_controller.selected_book_max_depth() == 6
    finally:
        theory_controller.close()


def test_fixed_navigation_map_view_can_keep_selected_node_inside_existing_projection(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Vista fija")
        root = theory_controller.create_root_from_current_position(book.id, name="Base")
        e4 = theory_controller.add_child_by_move(root.id, "e4", name="Peón rey")
        e5 = theory_controller.add_child_by_move(e4.node.id, "e5", name="Principal")
        c5 = theory_controller.add_child_by_move(e4.node.id, "c5", name="Siciliana")

        theory_controller.select_node(e5.node.id)
        frozen_view = theory_controller.get_map_view(forward_depth=2, backward_depth=1)
        frozen_ids = {node.id for node in frozen_view.nodes}
        assert c5.node.id in frozen_ids

        theory_controller.select_node(c5.node.id)
        assert theory_controller.selected_node_id in frozen_ids
    finally:
        theory_controller.close()
