import chess #type: ignore

DEPTH = 4

# piece values
# note: most engines use 330 for bishops, but i prefer 350 to make them more important
PIECE_VALUES = {
    chess.PAWN:   100,
    chess.KNIGHT: 320,
    chess.BISHOP: 350,
    chess.ROOK:   500,
    chess.QUEEN:  900,
    chess.KING:     0, # 0 because king is invaluable
}

# piece square tables to evaluate position of pieces
PST = {
    chess.PAWN: [
         0,  0,  0,  0,  0,  0,  0,  0,  # 0 because not possible
        50, 50, 50, 50, 50, 50, 50, 50,  # almost promoting
        10, 10, 20, 30, 30, 20, 10, 10,  
         5,  5, 10, 25, 25, 10,  5,  5,  
         0,  0,  0, 20, 20,  0,  0,  0,  
         5, -5,-10,  0,  0,-10, -5,  5, # encourages pawn to e4/d4
         5, 10, 10,-20,-20, 10, 10,  5,  
         0,  0,  0,  0,  0,  0,  0,  0,  # 0 because not possible
    ],
    chess.KNIGHT: [ # edges bad; center good
        -50,-40,-30,-30,-30,-30,-40,-50, 
        -40,-20,  0,  0,  0,  0,-20,-40,
        -30,  0, 10, 15, 15, 10,  0,-30,
        -30,  5, 15, 20, 20, 15,  5,-30,
        -30,  0, 15, 20, 20, 15,  0,-30,
        -30,  5, 10, 15, 15, 10,  5,-30,
        -40,-20,  0,  5,  5,  0,-20,-40,
        -50,-40,-30,-30,-30,-30,-40,-50,
    ],
    chess.BISHOP: [ # center good
        -20,-10,-10,-10,-10,-10,-10,-20,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -10,  0,  5, 10, 10,  5,  0,-10,
        -10,  5,  5, 10, 10,  5,  5,-10,
        -10,  0, 10, 10, 10, 10,  0,-10,
        -10, 10, 10, 10, 10, 10, 10,-10,
        -10,  5,  0,  0,  0,  0,  5,-10,
        -20,-10,-10,-10,-10,-10,-10,-20,
    ],
    chess.ROOK: [ 
         0,  0,  0,  0,  0,  0,  0,  0,
         5, 10, 10, 10, 10, 10, 10,  5, # 7th rank good for rook
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
        -5,  0,  0,  0,  0,  0,  0, -5,
         0,  0,  0,  5,  5,  0,  0,  0,
    ],
    chess.QUEEN: [ # center good
        -20,-10,-10, -5, -5,-10,-10,-20,
        -10,  0,  0,  0,  0,  0,  0,-10,
        -10,  0,  5,  5,  5,  5,  0,-10,
         -5,  0,  5,  5,  5,  5,  0, -5,
          0,  0,  5,  5,  5,  5,  0, -5,
        -10,  5,  5,  5,  5,  5,  0,-10,
        -10,  0,  5,  0,  0,  0,  0,-10,
        -20,-10,-10, -5, -5,-10,-10,-20,
    ],
    chess.KING: [ # stay in corner
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -30,-40,-40,-50,-50,-40,-40,-30,
        -20,-30,-30,-40,-40,-30,-30,-20,
        -10,-20,-20,-20,-20,-20,-20,-10,
         20, 20,  0,  0,  0,  0, 20, 20,
         20, 30, 10,  0,  0, 10, 30, 20,
    ],
}

# get piece-square table score for a piece on a square and flip for black
def _pst_score(piece_type, square, color):
    table = PST[piece_type]

    if color == chess.WHITE:
        rank = 7 - (square // 8)
    else:
        rank = square // 8
    file = square % 8
    return table[rank * 8 + file]

# evaluate board position based on material and piece-square tables
def evaluate(board):
    score = 0
    for piece_type, value in PIECE_VALUES.items():
        for sq in board.pieces(piece_type, chess.WHITE):
            score += value + _pst_score(piece_type, sq, chess.WHITE)
        for sq in board.pieces(piece_type, chess.BLACK):
            score -= value + _pst_score(piece_type, sq, chess.BLACK)
    return score

# basic minimax
def minimax(board, depth, maximizing):
    if depth == 0 or board.is_game_over():
        return evaluate(board), None

    best_move = None
    if maximizing:
        best_score = float("-inf")
        for move in board.legal_moves:
            board.push(move)
            score, _ = minimax(board, depth - 1, False)
            board.pop()
            if score > best_score:
                best_score, best_move = score, move
    else:
        best_score = float("inf")
        for move in board.legal_moves:
            board.push(move)
            score, _ = minimax(board, depth - 1, True)
            board.pop()
            if score < best_score:
                best_score, best_move = score, move

    return best_score, best_move

# get best move for current position using minimax at specified depth
def get_engine_move(board, depth=DEPTH):
    _, move = minimax(board, depth, board.turn == chess.WHITE)
    return move