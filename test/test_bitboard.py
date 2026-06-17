import numpy as np

from neuralcheck.bitboard import ChessBitboard


def test_get_bitboard_position():
    bitboard = ChessBitboard()
    assert bitboard.get_bitboard_position("e4") == (1 << (3 + 3 * 8))


def test_bitboard_initialize_from_initial_board():
    numboard = np.array([
        [-4, -2, -3, -5, -6, -3, -2, -4],
        [-1, -1, -1, -1, -1, -1, -1, -1],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [1, 1, 1, 1, 1, 1, 1, 1],
        [4, 2, 3, 5, 6, 3, 2, 4],
    ])

    bitboard = ChessBitboard(numboard)

    assert bitboard.masks["K"] == 0x0800000000000008
    assert bitboard.masks["Q"] == 0x1000000000000010
    assert bitboard.masks["B"] == 0x2400000000000024
    assert bitboard.masks["N"] == 0x4200000000000042
    assert bitboard.masks["R"] == 0x8100000000000081
    assert bitboard.masks["P"] == 0x00FF00000000FF00
    assert bitboard.masks["white"] == 0x000000000000FFFF
    assert bitboard.masks["black"] == 0xFFFF000000000000


def test_bitboard_flips_are_stable():
    ruy_lopez = 13832560274236045305
    bitboard = ChessBitboard()

    assert bitboard.flip_horizontal(ruy_lopez) == 18297848286656130975
    assert bitboard.flip_vertical(ruy_lopez) == 18011869668307957695
    assert bitboard.flip_horizontal(bitboard.flip_horizontal(ruy_lopez)) == ruy_lopez
    assert bitboard.flip_vertical(bitboard.flip_vertical(ruy_lopez)) == ruy_lopez
    assert bitboard.flip_vertical(bitboard.flip_horizontal(ruy_lopez)) == 11524465224858267645
