import numpy as np
#from neuralcheck.bitboard import get_bitboard_position
from neuralcheck.bitboard import ChessBitboard

"""

def test_get_bitboard_position():
    assert get_bitboard_position("e4") == (1 << (4 + 3 * 8)), 'Error de prueba unitaria'  # Verificar si la posición es correcta
    print('Prueba unitaria exitosa')
"""
    
def test_bitboard_initialize():
    numboard = np.array([[-4, -2, -3, -5, -6, -3, -2, -4],
                        [-1, -1, -1, -1, -1, -1, -1, -1],
                        [ 0,  0,  0,  0,  0,  0,  0,  0],
                        [ 0,  0,  0,  0,  0,  0,  0,  0],
                        [ 0,  0,  0,  0,  0,  0,  0,  0],
                        [ 0,  0,  0,  0,  0,  0,  0,  0],
                        [ 1,  1,  1,  1,  1,  1,  1,  1],
                        [ 4,  2,  3,  5,  6,  3,  2,  4]])
    
    bitboard = ChessBitboard(numboard)

    kings   = 0x0800000000000008
    queens  = 0x1000000000000010
    bishops = 0x2400000000000024
    knights = 0x4200000000000042
    rooks   = 0x8100000000000081
    pawns   = 0x00FF00000000FF00
    white   = 0x000000000000FFFF
    black   = 0xFFFF000000000000

    assert bitboard.masks['K'] == kings, 'Error de prueba unitaria'
    assert bitboard.masks['Q'] == queens, 'Error de prueba unitaria'
    assert bitboard.masks['B'] == bishops, 'Error de prueba unitaria'
    assert bitboard.masks['N'] == knights, 'Error de prueba unitaria'
    assert bitboard.masks['R'] == rooks, 'Error de prueba unitaria'
    assert bitboard.masks['P'] == pawns, 'Error de prueba unitaria'
    assert bitboard.masks['white'] == white, 'Error de prueba unitaria'
    assert bitboard.masks['black'] == black, 'Error de prueba unitaria'
    
    print('Prueba unitaria exitosa')