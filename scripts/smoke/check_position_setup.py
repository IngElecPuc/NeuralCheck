"""Non-destructive smoke check for manual position setup.

Run from the repository root with:
    $env:PYTHONPATH = (Resolve-Path ".\\src").Path
    python .\\scripts\\smoke\\check_position_setup.py
"""

from neuralcheck.application.game_controller import GameController


def main() -> None:
    controller = GameController()
    result = controller.apply_manual_position(
        {
            "e1": "white king",
            "e8": "black king",
            "d4": "white queen",
        },
        white_turn=False,
    )
    if not result.valid:
        raise AssertionError("Expected manual position to be valid: " + "; ".join(result.errors))

    if controller.piece_at("d4") != "white queen":
        raise AssertionError("Expected white queen at d4")

    if controller.active_color != "black":
        raise AssertionError("Expected black to move after applying manual position")

    invalid = controller.apply_manual_position(
        {
            "e1": "white king",
            "a8": "white pawn",
            "e8": "black king",
        },
        white_turn=True,
    )
    if invalid.valid:
        raise AssertionError("Expected pawn on a8 to be rejected")

    print("Position setup smoke passed")


if __name__ == "__main__":
    main()
