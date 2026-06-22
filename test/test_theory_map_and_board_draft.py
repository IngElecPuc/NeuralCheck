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


def test_theory_book_map_depths_are_persisted(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Profundidades")
        theory_controller.select_book(book.id)
        updated = theory_controller.update_selected_book_map_depths(
            backward_depth=12,
            forward_depth=30,
        )
        assert updated is not None
        assert updated.map_backward_depth == 12
        assert updated.map_forward_depth == 30
        assert theory_controller.selected_book_map_depths() == (12, 30)
    finally:
        theory_controller.close()


def test_theory_node_layout_positions_are_persisted(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Layout")
        root = theory_controller.create_root_from_current_position(book.id, name="Base")
        child = theory_controller.add_child_by_move(root.id, "e4", name="Peón rey")

        theory_controller.update_node_layout(root.id, 120.5, 240.25)
        theory_controller.update_node_layouts({child.node.id: (300.0, 350.0)})

        root_again = theory_controller.service.get_node(root.id)
        child_again = theory_controller.service.get_node(child.node.id)
        assert root_again is not None
        assert child_again is not None
        assert root_again.layout_x == 120.5
        assert root_again.layout_y == 240.25
        assert child_again.layout_x == 300.0
        assert child_again.layout_y == 350.0

        theory_controller.select_node(root.id)
        view = theory_controller.get_map_view(forward_depth=1, backward_depth=0)
        layouts = {node.id: (node.layout_x, node.layout_y) for node in view.nodes}
        assert layouts[root.id] == (120.5, 240.25)
        assert layouts[child.node.id] == (300.0, 350.0)
    finally:
        theory_controller.close()


def test_move_visual_hint_detects_simple_move_and_capture():
    from neuralcheck.theory.move_visuals import detect_move_visual_hint

    parent = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w - - 0 1"
    child = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b - - 0 1"
    hint = detect_move_visual_hint(parent, child)
    assert hint.from_square == "e2"
    assert hint.to_square == "e4"

    parent_capture = "8/8/8/3p4/4P3/8/8/8 w - - 0 1"
    child_capture = "8/8/8/3P4/8/8/8/8 b - - 0 1"
    capture_hint = detect_move_visual_hint(parent_capture, child_capture)
    assert capture_hint.from_square == "e4"
    assert capture_hint.to_square == "d5"


def test_move_visual_hint_uses_king_move_for_castling():
    from neuralcheck.theory.move_visuals import detect_move_visual_hint

    parent = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
    child = "r3k2r/8/8/8/8/8/8/R4RK1 b kq - 1 1"
    hint = detect_move_visual_hint(parent, child)
    assert hint.from_square == "e1"
    assert hint.to_square == "g1"


def test_theory_controller_reports_direct_continuation_hints(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Flechas")
        root = theory_controller.create_root_from_current_position(book.id, name="Base")
        e4 = theory_controller.add_child_by_move(root.id, "e4", name="Peón rey")
        theory_controller.select_node(root.id)

        hints = theory_controller.continuation_move_hints()
        assert len(hints) == 1
        child_id, move_san, hint = hints[0]
        assert child_id == e4.node.id
        assert move_san == "e4"
        assert hint.from_square == "e2"
        assert hint.to_square == "e4"
    finally:
        theory_controller.close()


def test_map_role_classification_is_strict_one_hop():
    from neuralcheck.theory.models import TheoryMapEdge, TheoryMapNode, TheoryMapView
    from neuralcheck.ui_theory_map import TheoryMapCanvas

    fen = "8/8/8/8/8/8/8/8 w - - 0 1"
    nodes = (
        TheoryMapNode("parent", "parent", fen, "white", None, -1, False),
        TheoryMapNode("selected", "selected", fen, "black", None, 0, True),
        TheoryMapNode("child", "child", fen, "white", None, 1, False),
        TheoryMapNode("sibling", "sibling", fen, "black", None, 0, False),
        TheoryMapNode("cousin", "cousin", fen, "white", None, 1, False),
    )
    edges = (
        TheoryMapEdge("parent", "selected", "e4"),
        TheoryMapEdge("selected", "child", "e5"),
        TheoryMapEdge("parent", "sibling", "c5"),
        TheoryMapEdge("sibling", "cousin", "Nf3"),
    )
    roles = TheoryMapCanvas._classify_node_roles(TheoryMapView("selected", "selected", nodes, edges, 2))
    assert roles["selected"] == "selected"
    assert roles["parent"] == "ancestor"
    assert roles["child"] == "descendant"
    assert roles["sibling"] == "sibling"
    assert roles.get("cousin") is None


def test_theory_board_draft_accepts_ambiguous_knight_move_from_board(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        karpov_fen = "r1bqkbnr/pp1npppp/2p5/8/3PN3/8/PPP2PPP/R1BQKBNR w - - 0 1"
        after_nfg_fen = "r1bqkb1r/pp1npppp/2p2n2/8/3PN3/5N2/PPP2PPP/R1BQKB1R w - - 0 1"

        book = theory_controller.create_book("Karpov")
        game_controller.apply_fen_position(karpov_fen)
        root = theory_controller.create_root_from_current_position(book.id, name="Karpov")
        theory_controller.load_node_to_board(root.id)

        game_controller.click_square("g1")
        white_move = game_controller.click_square("f3")
        assert white_move.movement == "Nf3"
        theory_controller.create_move_draft_from_board_move(white_move.movement)
        nf3 = theory_controller.commit_move_draft(name="Nf3")

        game_controller.click_square("g8")
        black_move = game_controller.click_square("f6")
        assert black_move.movement == "Ngf6"
        draft = theory_controller.create_move_draft_from_board_move(black_move.movement)
        assert draft.parent_node_id == nf3.node.id
        assert draft.move_san == "Ngf6"
        assert draft.board_after_fen == after_nfg_fen
    finally:
        theory_controller.close()


def test_map_edge_label_style_distinguishes_move_color():
    from neuralcheck.ui_theory_map import TheoryMapCanvas

    assert TheoryMapCanvas._edge_label_style("white") == ("#111111", "#ffffff")
    assert TheoryMapCanvas._edge_label_style("black") == ("#ffffff", "#111111")



def test_theory_controller_finds_existing_child_by_board_move_suffix(tmp_path: Path):
    game_controller = GameController()
    theory_controller = TheoryController.with_sqlite(
        tmp_path / "theory.db",
        game_controller=game_controller,
    )
    try:
        book = theory_controller.create_book("Sufijos")
        root = theory_controller.create_root_from_current_position(book.id, name="Base")
        child = theory_controller.add_child_by_move(root.id, "e4", name="Peón rey")
        theory_controller.select_node(root.id)

        assert theory_controller.find_child_by_move("e4") == child
        assert theory_controller.find_child_by_move("e4+") == child
        assert theory_controller.find_child_by_move("e4#") == child
        assert theory_controller.find_child_by_move("d4") is None
    finally:
        theory_controller.close()
