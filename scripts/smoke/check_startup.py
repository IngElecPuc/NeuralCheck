"""Non-destructive startup smoke check for the desktop chess core.

Run from the repository root with:
    $env:PYTHONPATH = (Resolve-Path ".\\src").Path
    python .\\scripts\\smoke\\check_startup.py
"""

from neuralcheck.logic import ChessBoard


def main() -> None:
    board = ChessBoard()
    required = {
        "e1": "white king",
        "e8": "black king",
        "d1": "white queen",
        "d8": "black queen",
    }

    for square, expected_piece in required.items():
        observed_piece = board.what_in(square)
        if observed_piece != expected_piece:
            raise AssertionError(f"{square}: expected {expected_piece}, observed {observed_piece}")

    if board.possible_moves["white"].get("e2") != ["e3", "e4"]:
        raise AssertionError("white pawn at e2 does not expose e3/e4 from the initial position")

    print("Startup smoke passed")


if __name__ == "__main__":
    main()
