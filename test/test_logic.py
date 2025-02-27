import os
import random
import yaml
from src.neuralcheck.logic import ChessBoard

def test_read_move(**kwargs):
    path = 'test/test_games'
    filename = kwargs.get("filename", None)
    history = kwargs.get("history", [])

    #Si recibí un filename uso eso
    #Si no recibí un filename veo si tengo un history
    #Si no tengo ninguno carga uno aleatorio

    if filename is not None:
        if path not in filename:
            filename = os.path.join(path, filename)
        with open(filename, "r", encoding="utf-8") as file:
            history = yaml.safe_load(file)

    elif len(history) == 0:
        archivos = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
        archivo_seleccionado = random.choice(archivos)
        filename = os.path.join(path, archivo_seleccionado)
        with open(filename, "r", encoding="utf-8") as file:
            history = yaml.safe_load(file)
    
    if len(history[-1]) == 1:
            history[-1].append('quit')    
    
    board = ChessBoard()
    print(f'Testing {filename}')
    for white_move, black_move in history:
        print(f'Attempting to do {white_move} in {"white" if board.white_turn else "black"} turn')
        piece, initial_position, end_position = board.read_move(white_move, board.white_turn)
        result, notation = board.make_move(piece, initial_position, end_position)
        #assert notation == white_move, 'Error, movimiento no corresponde, buscar ambigüedades'
        if notation != white_move:
            print('Error, movimiento no corresponde, buscar ambigüedades')
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
        #assert notation == black_move, 'Error, movimiento no corresponde, buscar ambigüedades'
        if notation != black_move:
            print('Error, movimiento no corresponde, buscar ambigüedades')
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

def check_for(**kwargs):
    path = 'test/test_games'
    archivos = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    pieces = ['K', 'Q', 'B', 'N', 'R']
    cols = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']
    rows = ['1', '2', '3', '4', '5', '6', '7', '8']
    promotion = kwargs.get('promotion', False)
    ambiguity = kwargs.get('ambiguity', False)
    enpassant = kwargs.get('enpassant', False)
    scastle = kwargs.get('scastle', False)
    lcastle = kwargs.get('lcastle', False)
    move = kwargs.get('move', False)
    check_list = kwargs.get('check_list', [])

    if len(check_list) > 0:
        archivos = check_list
    
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
                #breakpoint()
                white_move_stripped = white_move.replace('+', '').replace('#', '')#.replace('x', '')
                black_move_stripped = black_move.replace('+', '').replace('#', '')#.replace('x', '')
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

def check_database():
    from prettytable import PrettyTable
    tabla = PrettyTable()
    tabla.field_names = ['Feature', 'Contiene', 'No contiene', 'Total']
    co, nc = check_for(promotion=True)
    tabla.add_row(['promotion', len(co), len(nc), len(co) + len(nc)])
    co, nc = check_for(ambiguity=True)
    tabla.add_row(['ambiguity', len(co), len(nc), len(co) + len(nc)])
    co, nc = check_for(enpassant=True)
    tabla.add_row(['enpassant', len(co), len(nc), len(co) + len(nc)])
    co, nc = check_for(scastle=True)
    tabla.add_row(['scastle', len(co), len(nc), len(co) + len(nc)])
    co, nc = check_for(lcastle=True)
    tabla.add_row(['lcastle', len(co), len(nc), len(co) + len(nc)])

    print(tabla)


#from test.test_logic import *
#interesting, not_interesting = check_for(promotion=True, ambiguity=True, enpassant=True, scastle=True, lcastle=True)
"""
from test.test_logic import *
interesting, not_interesting = check_for(ambiguity=True)
interesting, not_interesting = check_for(scastle=True, check_list=not_interesting)
#board = test_read_move(history=[['g3', 'd5'], ['Bg2', 'c5'], ['d3', 'Nc6'], ['Nc3', 'Nf6'], ['Nf3', 'e5'], ['O-O', 'Bd6'], ['Bg5', 'Be6'], ['Bxf6', 'Qxf6'], ['Nh4', 'g5'], ['Nf3', 'h5'], ['Qc1', 'Be7'], ['e4', 'h4'], ['exd5', 'Nd4'], ['Nxd4', 'cxd4'], ['Ne4', 'Qf5'], ['dxe6', 'fxe6'], ['Qd1']])
board = test_read_move(history=[['e4', 'c6'], ['d4', 'Nf6'], ['e5', 'Nd5'], ['Nf3', 'd6'], ['Be2', 'Qa5+'], ['c3', 'f6']])
move = 'O-O-O'
piece, initial_position, end_position = board.read_move(move, board.white_turn)
result, notation = board.make_move(piece, initial_position, end_position)
        
board = ChessBoard()
board = test_read_move(filename=interesting[2])
board = test_read_move(filename='Defensa Nimzoindia - 0-0 - n°2.yaml')
"""
#Ambigüedad test_read_move(filename='test/test_games\Apertura Inglesa - 0-1 - n°1.yaml')
#check_for(check_list=['Apertura Inglesa - 0-1 - n°1.yaml'], ambiguity=True)
"""
filename = 'test/test_games/'+interesting[2]
with open(filename, "r", encoding="utf-8") as file:
    history = yaml.safe_load(file)
"""