from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import yaml
from logic import ChessBoard

app = FastAPI()

class MoveRequest(BaseModel):
    piece: str
    initial_position: str
    end_position: str
    promote2: Optional[str] = None

class GameState(BaseModel):
    board: List[List[int]]
    history: List[List[str]]
    white_turn: bool    

game = ChessBoard()

@app.post("/new_game")
def new_game():
    game.clear_board()
    game.load_position("config/initial_position.yaml")
    return {"message": "Nueva partida iniciada"}

@app.post("/move")
def make_move(move: MoveRequest):
    valid, notation = game.make_move(
        move.piece, 
        move.initial_position, 
        move.end_position, 
        promote2=move.promote2
    )
    if not valid:
        raise HTTPException(status_code=400, detail="Movimiento inválido")
    return {"notation": notation, "state": game.board.tolist()}

@app.get("/state", response_model=GameState)
def get_state():
    return GameState(
        board=game.board.tolist(),
        history=game.history,
        white_turn=game.white_turn
    )