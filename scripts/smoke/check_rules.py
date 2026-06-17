"""Non-destructive smoke test for the chess rule pipeline."""

import numpy as np

from neuralcheck.logic import ChessBoard


def build_board(pieces, white_turn=True):
    board = ChessBoard(np.zeros((8, 8), dtype=np.int64), white_turn=white_turn)
    for piece, square in pieces:
        board.set_piece(piece, square)
    board.refresh_state()
    return board


def main() -> None:
    board = ChessBoard()
    assert board.possible_moves["white"]["e2"] == ["e3", "e4"]

    board = build_board(
        [
            ("white king", "e1"),
            ("white rook", "e2"),
            ("black rook", "e8"),
            ("black king", "a8"),
        ]
    )
    assert "a2" not in board.possible_moves["white"].get("e2", [])
    assert board.make_move("white rook", "e2", "a2") == (False, "")

    board = build_board(
        [
            ("white king", "e1"),
            ("white rook", "h1"),
            ("black king", "e8"),
        ]
    )
    assert board.make_move("white king", "e1", "g1") == (True, "O-O")
    assert board.what_in("f1") == "white rook"

    print("Rules smoke passed")


if __name__ == "__main__":
    main()
