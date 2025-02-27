import os
import random
import yaml
from src.neuralcheck.logic import ChessBoard
import pdb


def test_read_move(filename):
    path = 'test/test_games'
    archivos = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    archivo_seleccionado = random.choice(archivos)
    if filename is None: 
        filename = os.path.join(path, archivo_seleccionado)
    elif path not in filename:
        filename = os.path.join(path, filename)
    
    with open(filename, "r", encoding="utf-8") as file:
        history = yaml.safe_load(file)
        if len(history[-1]) == 1:
            history[-1].append('quit')
    board = ChessBoard()
    print(f'Testing {filename}')
    #pdb.set_trace()
    for white_move, black_move in history:
        print(f'Attempting to do {white_move} in {"white" if board.white_turn else "black"} turn')
        piece, initial_position, end_position = board.read_move(white_move, board.white_turn)
        result, notation = board.make_move(piece, initial_position, end_position)
        if result:
            print(f'{notation} success!')
        else:
            print("Error!")
            break
        if black_move == 'quit':
            break
        print(f'Attempting to do {black_move} in {"white" if board.white_turn else "black"} turn')
        piece, initial_position, end_position = board.read_move(black_move, board.white_turn)
        result, notation = board.make_move(piece, initial_position, end_position)
        if result:
            print(f'{notation} success!')
        else:
            print("Error!")
            break
    print(board.board)
    print(history)
    return board

"""
array([[-4,  0, -3, -5, -6,  0, -2, -4],
       [ 0, -1, -1,  0,  0, -1, -1, -1],
       [-1,  0, -2, -1,  0,  0,  0,  0],
       [ 0,  3, -3,  0, -1,  0,  0,  0],
       [ 0,  0,  0,  0,  1,  0,  0,  0],
       [ 0,  0,  1,  0,  0,  2,  0,  1],
       [ 1,  1,  0,  1,  0,  1,  1,  0],
       [ 4,  2,  3,  5,  6,  0,  0,  4]])
"""

def check_for(promotion=False, ambiguity=False, enpassant=False, scastle=False, lcastle=False, move=None):
    path = 'test/test_games'
    archivos = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    pieces = ['K', 'Q', 'B', 'N', 'R']
    cols = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    rows = ['1', '2', '3', '4', '5', '6', '7', '8']
    interesting = []
    not_interesting = []
    for archivo in archivos:
        filename = os.path.join(path, archivo)
        with open(filename, "r", encoding="utf-8") as file:
            history = yaml.safe_load(file)
            if len(history[-1]) == 1:
                history[-1].append('q')
        for white_move, black_move in history:
            if scastle and (white_move == 'O-O' or black_move == 'O-O') and archivo not in interesting:
                #breakpoint()
                interesting.append(archivo)
            elif lcastle and (white_move == 'O-O-O' or black_move == 'O-O-O') and archivo not in interesting:
                interesting.append(archivo)
            elif enpassant and ('x' in white_move or 'x' in black_move) and archivo not in interesting:
                #if white_move[0] not in pieces and black_move[0] not in pieces:
                last_black = last_black.replace('+', '').replace('#', '').replace('x', '')
                white_move_stripped = white_move.replace('+', '').replace('#', '').replace('x', '')
                black_move_stripped = black_move.replace('+', '').replace('#', '').replace('x', '')
                if last_black[-1] == '5' and white_move_stripped[-1] == '6' and white_move[0] not in pieces:
                    interesting.append(archivo) #Ojo que pueden haber movimientos de peones que no cumplan, por lo que esto va a capturar todos los en passant, pero no todo lo capturado tiene en passant
                if white_move[-1] == '4' and black_move_stripped[-1] == '3' and black_move[0] not in pieces:
                    interesting.append(archivo) #Idem
            elif ambiguity and archivo not in interesting:
                white_move_stripped = white_move.replace('+', '').replace('#', '').replace('x', '')
                black_move_stripped = black_move.replace('+', '').replace('#', '').replace('x', '')
                if len(white_move_stripped) > 2:
                    if white_move_stripped[-3] in cols or white_move_stripped[-3] in rows:
                        interesting.append(archivo)
                if len(black_move_stripped) > 2:
                    if black_move_stripped[-3] in cols or black_move_stripped[-3] in rows:
                        interesting.append(archivo)
            elif promotion and ('=' in white_move or '=' in black_move) and archivo not in interesting:
                interesting.append(archivo)
            elif (white_move == move or black_move == move) and archivo not in interesting:
                interesting.append(archivo)
            last_white = white_move
            last_black = black_move

    for archivo in archivos:
        if archivo in interesting:
            continue
        not_interesting.append(archivo)

    return interesting, not_interesting
#from test.test_logic import *
#interesting, not_interesting = check_for(promotion=True, ambiguity=True, enpassant=True, scastle=True, lcastle=True)