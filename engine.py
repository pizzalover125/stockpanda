import chess, random #type: ignore

# will add a real engine later, for now just pick a random legal move
def get_engine_move(board):
    return random.choice(list(board.legal_moves))