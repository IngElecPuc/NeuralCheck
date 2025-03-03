import os
import random
import yaml
import numpy as np
from src.neuralcheck.logic import ChessBoard
from prettytable import PrettyTable

def test_read_move(**kwargs):
    path = 'test/test_games'
    filename = kwargs.get("filename", None)
    history = kwargs.get("history", [])
    one_random = kwargs.get("random", False)
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

    #Si recibí un filename uso eso
    #Si no recibí un filename veo si tengo un history
    #Si no tengo ninguno carga uno aleatorio

    def test_one(history):
        #TODO transformar en test unitario
        board = ChessBoard()
        generated_history = []
        observed_history = []
        white_turn = True
    
        try:
            for (white_move, black_move), (white_fen, black_fen) in history:
                #breakpoint()
                piece, initial_position, end_position = board.read_move(white_move, white_turn)
                notation = board.notation_from_move(piece, initial_position, end_position)
                generated_history.append([notation])
                observed_history.append([white_move])
                #white_turn = not white_turn
                #board.board = board.fen2numpy(white_fen)
                board.make_move(piece, initial_position, end_position)
                if black_move == 'quit':
                    break
                piece, initial_position, end_position = board.read_move(black_move, white_turn)
                notation = board.notation_from_move(piece, initial_position, end_position)
                generated_history[-1].append(notation)
                observed_history[-1].append(black_move)
                #white_turn = not white_turn
                #board.board = board.fen2numpy(black_fen)
                board.make_move(piece, initial_position, end_position)
        except Exception as e:
            if '=' not in white_move+black_move:
                print(e)
                breakpoint()

        generated_history   = [item for sublist in generated_history for item in sublist]
        generated_history   = np.array(generated_history)
        observed_history    = [item for sublist in observed_history for item in sublist]
        observed_history    = np.array(observed_history)
        precision           = np.sum(observed_history == generated_history) / len(observed_history)

        return precision, board

    if filename is not None:
        if path not in filename:
            filename = os.path.join(path, filename)
        with open(filename, "r", encoding="utf-8") as file:
            history = yaml.safe_load(file)
        if len(history[-1][0]) == 1:
            history[-1][0].append('quit')
        precision, board = test_one(history)
        print(f'Testing {filename}')
        print(f'Precision: {precision:.2%}')
        #print(board.board)
        #print(history)

    elif one_random:
        selected_file = random.choice(files)
        filename = os.path.join(path, selected_file)
        with open(filename, "r", encoding="utf-8") as file:
            history = yaml.safe_load(file)
        if len(history[-1][0]) == 1:
            history[-1][0].append('quit')
        precision, board = test_one(history)
        print(f'Testing {filename}')
        print(f'Precision: {precision:.2%}')
        #print(board.board)
        #0print(history)
    
    else:
        table = PrettyTable()
        table.field_names = ['File', 'Precision']
        for file in files:
            filename = os.path.join(path, file)
            with open(filename, "r", encoding="utf-8") as file:
                history = yaml.safe_load(file)
            if len(history[-1][0]) == 1:
                history[-1][0].append('quit')
            precision, board = test_one(history)
            table.add_row([file, f'{precision:.2%}'])
        print(table)

def test_make_move(**kwargs):
    path = 'test/test_games'
    filename = kwargs.get("filename", None)
    history = kwargs.get("history", [])
    one_random = kwargs.get("random", False)
    files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]
    do_them_all = False

    #Si recibí un filename uso eso
    #Si no recibí un filename veo si tengo un history
    #Si no tengo ninguno carga uno aleatorio

    def test_one(history):
        #TODO transformar en test unitario
        board = ChessBoard()
        generated_history = []
        observed_history = []
    
        try:
            for (white_move, black_move), (white_fen, black_fen) in history:
                piece, initial_position, end_position = board.read_move(white_move, board.white_turn)
                result, notation = board.make_move(piece, initial_position, end_position)
                generated_history.append([notation])
                observed_history.append([white_move])
                if not result:
                    break
                if black_move == 'quit':
                    break
                piece, initial_position, end_position = board.read_move(black_move, board.white_turn)
                result, notation = board.make_move(piece, initial_position, end_position)
                generated_history[-1].append(notation)
                observed_history[-1].append(black_move)
                if not result:
                    break
        except:
            if '=' not in white_move+black_move:
                breakpoint()

        generated_history   = [item for sublist in generated_history for item in sublist]
        generated_history   = np.array(generated_history)
        observed_history    = [item for sublist in observed_history for item in sublist]
        observed_history    = np.array(observed_history)
        precision           = np.sum(observed_history == generated_history) / len(observed_history)

        return precision, board

    if filename is not None:
        if path not in filename:
            filename = os.path.join(path, filename)
        with open(filename, "r", encoding="utf-8") as file:
            history = yaml.safe_load(file)
        if len(history[-1][0]) == 1:
            history[-1][0].append('quit')
        precision, board = test_one(history)
        print(f'Testing {filename}')
        print(f'Precision: {precision:.2%}')
        #print(board.board)
        #print(history)

    elif one_random:
        selected_file = random.choice(files)
        filename = os.path.join(path, selected_file)
        with open(filename, "r", encoding="utf-8") as file:
            history = yaml.safe_load(file)
        if len(history[-1][0]) == 1:
            history[-1][0].append('quit')
        precision, board = test_one(history)
        print(f'Testing {filename}')
        print(f'Precision: {precision:.2%}')
        #print(board.board)
        #0print(history)
    
    else:
        table = PrettyTable()
        table.field_names = ['File', 'Precision']
        for file in files:
            filename = os.path.join(path, file)
            with open(filename, "r", encoding="utf-8") as file:
                history = yaml.safe_load(file)
            if len(history[-1][0]) == 1:
                history[-1][0].append('quit')
            precision, board = test_one(history)
            table.add_row([file, f'{precision:.2%}'])
        print(table)
        
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
            if len(history[-1][0]) == 1:
                history[-1][0].append('q')
        for (white_move, black_move), (white_fen, black_fen) in history:
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
    tabla = PrettyTable()
    tabla.field_names = ['Feature', 'Contains', 'Not contains', 'Total']
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

def make_moves(board:ChessBoard, sequence):
    if len(sequence[-1]) == 1:
            sequence[-1].append('quit')
    for white_move, black_move in sequence:
        piece, initial_position, end_position = board.read_move(white_move, board.white_turn)
        notation = board.notation_from_move(piece, initial_position, end_position)
        board.make_move(piece, initial_position, end_position)
        if black_move == 'quit':
            break
        piece, initial_position, end_position = board.read_move(black_move, board.white_turn)
        notation = board.notation_from_move(piece, initial_position, end_position)
        board.make_move(piece, initial_position, end_position)

"""
from test.test_logic import *
self = ChessBoard()
#make_moves(self, [['e4', 'e5'], ['Nf3', 'Nc6'], ['Bc4', 'Nf6'], ['Ng5', 'Bc5'], ['Bf7+']]) #Italiana hasta jaque del alfil
#make_moves(self, [['e4', 'e6'], ['d4', 'd5'], ['e5', 'f6'], ['Nf3', 'fxe5'], ['Nxe5', 'Nc6'], ['Qh5+']]) #Francesa hasta jaque de la reina
make_moves(self, [['e4', 'd5'], ['exd5', 'Qxd5'], ['Nc3', 'Qe5+']]) #Escandinaba con jaque de la reina
self.possible_moves
"""

#from test.test_logic import *
#interesting, not_interesting = check_for(promotion=True, ambiguity=True, enpassant=True, scastle=True, lcastle=True)
"""
from test.test_logic import *
interesting, not_interesting = check_for(ambiguity=True)
interesting, not_interesting = check_for(scastle=True, check_list=not_interesting)
#board = test_read_move(history=[['g3', 'd5'], ['Bg2', 'c5'], ['d3', 'Nc6'], ['Nc3', 'Nf6'], ['Nf3', 'e5'], ['O-O', 'Bd6'], ['Bg5', 'Be6'], ['Bxf6', 'Qxf6'], ['Nh4', 'g5'], ['Nf3', 'h5'], ['Qc1', 'Be7'], ['e4', 'h4'], ['exd5', 'Nd4'], ['Nxd4', 'cxd4'], ['Ne4', 'Qf5'], ['dxe6', 'fxe6'], ['Qd1']])
#Justo antes del jate, de aquí jugar: 'Nd6+' y luego comprobar jaque.
board = test_read_move(history=[['g3', 'd5'], ['Bg2', 'c5'], ['d3', 'Nc6'], ['Nc3', 'Nf6'], ['Nf3', 'e5'], ['O-O', 'Bd6'], ['Bg5', 'Be6'], ['Bxf6', 'Qxf6'], ['Nh4', 'g5'], ['Nf3', 'h5'], ['Qc1', 'Be7'], ['e4', 'h4'], ['exd5', 'Nd4'], ['Nxd4', 'cxd4'], ['Ne4', 'Qf5'], ['dxe6', 'fxe6'], ['Qd1', 'O-O-O'], ['a3', 'hxg3'], ['fxg3', 'Qg6'], ['Qf3', 'Rh5']])
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