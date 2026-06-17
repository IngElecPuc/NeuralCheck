"""Non-destructive smoke check for the desktop application controller.

Run from the repository root with:
    $env:PYTHONPATH = (Resolve-Path ".\\src").Path
    python .\\scripts\\smoke\\check_controller.py
"""

from neuralcheck.application.game_controller import GameController


def main() -> None:
    controller = GameController()

    if controller.active_color != "white":
        raise AssertionError("Initial active color should be white")

    if controller.legal_targets("e2") != ["e3", "e4"]:
        raise AssertionError("White pawn at e2 should expose e3/e4")

    selected = controller.click_square("e2")
    if not selected.selected:
        raise AssertionError("Expected e2 to be selected")

    moved = controller.click_square("e4")
    if not moved.moved:
        raise AssertionError("Expected e2-e4 to be accepted")

    if controller.piece_at("e4") != "white pawn":
        raise AssertionError("Expected white pawn at e4 after move")

    print("Controller smoke passed")


if __name__ == "__main__":
    main()
