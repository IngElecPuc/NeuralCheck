import numpy as np

from neuralcheck.logic import ChessBoard


def board_from_pieces(pieces, white_turn=True):
    board = ChessBoard(np.zeros((8, 8), dtype=np.int64), white_turn=white_turn)
    for piece, position in pieces:
        board.set_piece(piece, position)
    board.refresh_state()
    return board


def test_pinned_piece_can_only_move_along_pin_line():
    board = board_from_pieces(
        [
            ("white king", "e1"),
            ("white rook", "e2"),
            ("black rook", "e8"),
            ("black king", "a8"),
        ]
    )

    assert "a2" not in board.possible_moves["white"]["e2"]
    assert "e3" in board.possible_moves["white"]["e2"]
    assert "e8" in board.possible_moves["white"]["e2"]
    assert board.make_move("white rook", "e2", "a2") == (False, "")


def test_piece_can_block_single_check():
    board = board_from_pieces(
        [
            ("white king", "e1"),
            ("white bishop", "c1"),
            ("black rook", "e8"),
            ("black king", "a8"),
        ]
    )

    assert board.assess_king_status(True) == 1
    assert board.possible_moves["white"]["c1"] == ["e3"]
    assert board.make_move("white bishop", "c1", "e3") == (True, "Be3")


def test_king_cannot_move_into_attacked_square():
    board = board_from_pieces(
        [
            ("white king", "e1"),
            ("black king", "a8"),
            ("black rook", "e8"),
        ]
    )

    assert "e2" not in board.possible_moves["white"].get("e1", [])
    assert board.make_move("white king", "e1", "e2") == (False, "")


def test_castling_requires_safe_path_and_existing_rook():
    board = board_from_pieces(
        [
            ("white king", "e1"),
            ("white rook", "h1"),
            ("black bishop", "c4"),
            ("black king", "e8"),
        ]
    )

    assert "g1" not in board.possible_moves["white"].get("e1", [])
    assert board.make_move("white king", "e1", "g1") == (False, "")

    board = board_from_pieces(
        [
            ("white king", "e1"),
            ("black king", "e8"),
        ]
    )

    assert "g1" not in board.possible_moves["white"].get("e1", [])
    assert "c1" not in board.possible_moves["white"].get("e1", [])


def test_castling_moves_king_and_rook_and_updates_rights():
    board = board_from_pieces(
        [
            ("white king", "e1"),
            ("white rook", "h1"),
            ("black king", "e8"),
        ]
    )

    assert "g1" in board.possible_moves["white"]["e1"]
    assert board.make_move("white king", "e1", "g1") == (True, "O-O")
    assert board.what_in("g1") == "white king"
    assert board.what_in("f1") == "white rook"
    assert board.castle_flags["white king moved"] is True


def test_en_passant_requires_immediate_double_pawn_move():
    board = board_from_pieces(
        [
            ("white king", "e1"),
            ("black king", "e8"),
            ("white pawn", "e5"),
            ("black pawn", "d5"),
        ]
    )

    assert "d6" not in board.possible_moves["white"].get("e5", [])

    board.last_turn = ("black pawn", "d7", "d5")
    board.refresh_state()
    assert "d6" in board.possible_moves["white"]["e5"]
    assert board.make_move("white pawn", "e5", "d6") == (True, "exd6")
    assert board.what_in("d5").startswith("Empty")
    assert board.what_in("d6") == "white pawn"


def test_promotion_is_mandatory_and_validates_piece_color():
    board = board_from_pieces(
        [
            ("white king", "e1"),
            ("black king", "e8"),
            ("white pawn", "a7"),
        ]
    )

    assert "a8" in board.possible_moves["white"]["a7"]
    assert board.make_move("white pawn", "a7", "a8") == (False, "")
    assert board.make_move("white pawn", "a7", "a8", promote2="black queen") == (False, "")
    assert board.make_move("white pawn", "a7", "a8", promote2="white queen") == (True, "a8=Q+")
    assert board.what_in("a8") == "white queen"


def test_san_disambiguation_reads_origin_file_for_ambiguous_knights():
    board = ChessBoard()
    board.set_position_from_fen(
        "r1bqkbnr/pp1npppp/2p5/8/3PN3/5N2/PPP2PPP/R1BQKB1R b - - 0 1",
        clear_history=True,
    )

    assert board.notation_from_move("black knight", "g8", "f6") == "Ngf6"
    assert board.read_move("Ngf6", white_player=False) == ("black knight", "g8", "f6")
    assert board.read_move("Ndf6", white_player=False) == ("black knight", "d7", "f6")


def test_san_disambiguation_rejects_wrong_origin_file_for_ambiguous_knights():
    board = ChessBoard()
    board.set_position_from_fen(
        "r1bqkbnr/pp1npppp/2p5/8/3PN3/5N2/PPP2PPP/R1BQKB1R b - - 0 1",
        clear_history=True,
    )

    try:
        board.read_move("Ncf6", white_player=False)
    except ValueError as exc:
        assert "disambiguation" in str(exc)
    else:
        raise AssertionError("Ncf6 should not resolve when no knight on c-file can move to f6")


def test_fen_en_passant_target_enables_white_capture():
    board = ChessBoard()
    board.set_position_from_fen(
        "rnbqkbnr/1pp1pppp/p7/3pP3/8/8/PPPP1PPP/RNBQKBNR w - d6 0 1",
        clear_history=True,
    )

    assert board.en_passant_target == "d6"
    assert "d6" in board.possible_moves["white"]["e5"]
    assert board.read_move("exd6", white_player=True) == ("white pawn", "e5", "d6")
    assert board.make_move("white pawn", "e5", "d6") == (True, "exd6")
    assert board.what_in("d5").startswith("Empty")
    assert board.what_in("d6") == "white pawn"
    assert board.en_passant_target is None
    assert board.export_fen(include_state=True).endswith(" b - - 0 1")


def test_fen_en_passant_target_enables_black_capture():
    board = ChessBoard()
    board.set_position_from_fen(
        "rnbqkbnr/pppp1ppp/8/8/3pP3/8/PPP2PPP/RNBQKBNR b - e3 0 1",
        clear_history=True,
    )

    assert board.en_passant_target == "e3"
    assert "e3" in board.possible_moves["black"]["d4"]
    assert board.read_move("dxe3", white_player=False) == ("black pawn", "d4", "e3")
    assert board.make_move("black pawn", "d4", "e3") == (True, "dxe3")
    assert board.what_in("e4").startswith("Empty")
    assert board.what_in("e3") == "black pawn"


def test_double_pawn_push_exports_en_passant_target_and_clears_after_next_move():
    board = ChessBoard()

    assert board.make_move("white pawn", "e2", "e4") == (True, "e4")
    assert board.en_passant_target == "e3"
    assert board.export_fen(include_state=True) == (
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b - e3 0 1"
    )

    assert board.make_move("black knight", "g8", "f6") == (True, "Nf6")
    assert board.en_passant_target is None
    assert board.export_fen(include_state=True).endswith(" w - - 0 1")
