import numpy as np
from src.neuralcheck.logic import ChessBoard
from typing import Tuple

class DeductiveEvaluator:
    def __init__(self):
        pass

    def value_function(self, board:np.array) -> float:
        """
        Computes board evaluation from simple huristics

        Parameters:
            board: A 8x8 np array with a board representation from logic module
        """

        mapper = {6 : 0, 5: 9, 4: 5, 3: 3, 2: 3, 1: 1, 0: 1}
        mapped = map(lambda x: np.sign(x) * mapper[abs(x)], board.flatten())
        mapped = np.array(list(mapped))
        mapped = mapped.reshape(board.shape)
        return mapped.sum()
    
    def minimax(self, position, depth:int, white_turn:bool) -> Tuple[str, float]:
        
        if depth == 0 or '#' in position: #Corregir, busco la condición de juego ganado
            return self.value_function(position)
        
        if white_turn:
            max_eval = -np.inf
            for child in position: 
                eval = self.minimax(child, depth - 1, False)
                max_eval = max(max_eval, eval)

        else:
            min_eval = np.inf
            for child in position: 
                eval = self.minimax(child, depth - 1, True)
                min_eval = min(min_eval, eval)

class TestMinimax:
    def __init__(self):
        pass

    def value_function(self, position, white_turn):
        pass        

    def minimax(self, position, depth:int, white_turn:bool) -> Tuple[str, float]:
        
        if depth == 0 or '#' in position: #Corregir, busco la condición de juego ganado
            #return self.value_function(position, white_turn)
            return position
        
        if white_turn:
            max_eval = -np.inf
            for child in position: 
                eval = self.minimax(child, depth - 1, False)
                max_eval = max(max_eval, eval)
            return max_eval

        else:
            min_eval = np.inf
            for child in position: 
                eval = self.minimax(child, depth - 1, True)
                min_eval = min(min_eval, eval)
            return min_eval

    def minimax_ab(self, position, depth:int, alpha:float, beta:float, white_turn:bool) -> Tuple[str, float]:
        
        if depth == 0 or '#' in position: #Corregir, busco la condición de juego ganado
            #return self.value_function(position, white_turn)
            return position
        
        if white_turn:
            max_eval = -np.inf
            for child in position: 
                eval = self.minimax_ab(child, depth - 1, alpha, beta, False)
                max_eval = max(max_eval, eval)
                alpha = max(alpha, eval)
                if beta <= alpha: #beta pruning
                    break
            return max_eval

        else:
            min_eval = np.inf
            for child in position: 
                eval = self.minimax_ab(child, depth - 1, alpha, beta, True)
                min_eval = min(min_eval, eval)
                beta = min(beta, eval)
                if alpha <= beta: #alpha pruning
                    break
            return min_eval

        #Al utilizar pruning el orden de la búsqueda importa pues ejercerá efecto en la cantidad de elementos que se terminarán buscando
        #Si 

"""
position = [[[-1,3], [5,1]], [[-6,-4], [0, 9]]] 
tester.minimax(position, 3, True) #Resultado es 3
tester.minimax_ab(position, 3, -np.inf, np.inf, True) #Resultado es 3, pero en menos casos
"""            