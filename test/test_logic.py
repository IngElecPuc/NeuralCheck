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
    
    with open(filename, "r", encoding="utf-8") as file:
        history = yaml.safe_load(file)
    
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
