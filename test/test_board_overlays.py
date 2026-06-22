import pytest

from neuralcheck.board_overlays import BoardArrow, arrow_style_for_squares, is_knight_jump, square_delta


def test_board_overlay_detects_knight_geometry():
    assert is_knight_jump("g1", "f3") is True
    assert is_knight_jump("b4", "d3") is True
    assert is_knight_jump("e5", "d7") is True
    assert arrow_style_for_squares("g1", "f3") == "knight_l"


def test_board_overlay_keeps_non_knight_arrows_straight():
    assert is_knight_jump("e2", "e4") is False
    assert is_knight_jump("a1", "h8") is False
    assert arrow_style_for_squares("e2", "e4") == "straight"
    assert BoardArrow("e2", "e4").style == "straight"


def test_board_overlay_square_delta_uses_chess_coordinates():
    assert square_delta("g1", "f3") == (-1, 2)
    assert square_delta("b4", "d3") == (2, -1)


def test_board_overlay_rejects_invalid_square():
    with pytest.raises(ValueError):
        is_knight_jump("i1", "f3")
