from neuralcheck.bitboard import get_bitboard_position

def test_get_bitboard_position():
    assert get_bitboard_position("e4") == (1 << (4 + 3 * 8))  # Verificar si la posición es correcta
