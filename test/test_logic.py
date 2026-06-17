import numpy as np

from neuralcheck.logic import ChessBoard


def test_chess_board_starts_from_initial_position():
    board = ChessBoard()

    assert board.board.shape == (8, 8)
    assert board.white_turn is True
    assert board.what_in("e1") == "white king"
    assert board.what_in("e8") == "black king"
    assert board.what_in("a1") == "white rook"
    assert board.what_in("a8") == "black rook"


def test_initial_possible_moves_contract_is_color_partitioned():
    board = ChessBoard()

    assert set(board.possible_moves.keys()) == {"white", "black"}
    assert board.possible_moves["white"]["e2"] == ["e3", "e4"]
    assert board.possible_moves["black"]["e7"] == ["e6", "e5"]


def test_basic_move_updates_board_turn_history_and_bitboard():
    board = ChessBoard()

    result, notation = board.make_move("white pawn", "e2", "e4")

    assert result is True
    assert notation == "e4"
    assert board.white_turn is False
    assert board.what_in("e2").startswith("Empty")
    assert board.what_in("e4") == "white pawn"
    assert board.history[-1][0] == ["e4"]
    assert board.bitboard.masks["white"] > 0


def test_can_instantiate_from_numpy_position_without_loading_yaml():
    base = ChessBoard()
    copied = ChessBoard(base.board.copy(), white_turn=False)

    assert copied.white_turn is False
    assert np.array_equal(copied.board, base.board)
    assert copied.what_in("e8") == "black king"
