from pathlib import Path
from tempfile import TemporaryDirectory

from neuralcheck.application.game_controller import GameController
from neuralcheck.application.theory_controller import TheoryController
from neuralcheck.theory.models import TheoryMapEdge, TheoryMapNode, TheoryMapView
from neuralcheck.ui_theory_map import TheoryMapLayoutEngine, TheoryMapCanvas
from neuralcheck.theory.move_visuals import detect_move_visual_hint


def main():
    with TemporaryDirectory() as tmp_dir:
        game = GameController()
        controller = TheoryController.with_sqlite(Path(tmp_dir) / "theory.db", game_controller=game)
        try:
            book = controller.create_book("Mapa avanzado")
            root = controller.create_root_from_current_position(book.id, name="Inicial")
            e4 = controller.add_child_by_move(root.id, "e4", name="Peón rey")
            e5 = controller.add_child_by_move(e4.node.id, "e5", name="Respuesta")
            nf3 = controller.add_child_by_move(e5.node.id, "Nf3", name="Caballo")
            nc6 = controller.add_child_by_move(nf3.node.id, "Nc6", name="Natural")
            controller.add_child_by_move(nf3.node.id, "d6", name="Philidor")

            controller.select_node(nf3.node.id)
            assert controller.selected_book_max_depth() >= 4
            view = controller.get_map_view(forward_depth=1, backward_depth=2)
            ids = {node.id for node in view.nodes}
            assert nf3.node.id in ids
            assert e5.node.id in ids
            assert e4.node.id in ids
            assert root.id not in ids
            assert {edge.move_san for edge in view.edges}.issuperset({"e5", "Nf3", "Nc6", "d6"})
            hints = controller.continuation_move_hints(nf3.node.id)
            assert {move for _node_id, move, _hint in hints}.issuperset({"Nc6", "d6"})
            assert all(hint.complete for _node_id, _move, hint in hints)
            move_hint = controller.move_hint_for_node(nc6.node.id)
            assert move_hint.from_square and move_hint.to_square
        finally:
            controller.close()

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
        for index in range(8)
    )
    edges = tuple(TheoryMapEdge("n0", f"n{index}", f"m{index}") for index in range(1, 8))
    layout = TheoryMapLayoutEngine(
        node_radius=38,
        forward_step=125,
        backward_step=110,
        rotation_radians=0.5,
        min_margin=24,
    ).layout(TheoryMapView("n0", "n0", nodes, edges, 2), selected_node_id="n0", center=(300, 240))
    positions = [(node.x, node.y) for node in layout.nodes.values()]
    min_distance = 38 * 2 + 24 - 0.01
    for left_index, (x1, y1) in enumerate(positions):
        for x2, y2 in positions[left_index + 1 :]:
            assert ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 >= min_distance

    roles = TheoryMapCanvas._classify_node_roles(TheoryMapView("n0", "n0", nodes, edges, 2))
    assert roles["n1"] == "descendant"
    assert detect_move_visual_hint(
        "8/8/8/8/8/8/4P3/8 w - - 0 1",
        "8/8/8/8/4P3/8/8/8 b - - 0 1",
    ).to_square == "e4"

    print("Theory advanced map smoke passed")


if __name__ == "__main__":
    main()
