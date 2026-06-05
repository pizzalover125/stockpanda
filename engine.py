import chess #type: ignore
import chess.polyglot #type: ignore
import time

MAX_DEPTH = 5         # max search depth 
TIME_LIMIT = 4.0      # seconds per move
MATE_SCORE = 1000000  # large enough to always outweigh any material eval

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

# raised deep in the search once we pass the time budget
class SearchTimeout(Exception):
    pass


# order moves for more cutoffs: tt move first, then captures (mvv-lva), then promotions
def _order_moves(board, tt_move):
    def move_score(move):
        if move == tt_move:
            return 1_000_000
        if board.is_capture(move):
            victim = board.piece_at(move.to_square)
            attacker = board.piece_at(move.from_square)

            victim_val = PIECE_VALUES[victim.piece_type] if victim else PIECE_VALUES[chess.PAWN]
            attacker_val = PIECE_VALUES[attacker.piece_type]
            return 100_000 + victim_val * 10 - attacker_val
        if move.promotion:
            return 90_000 + PIECE_VALUES.get(move.promotion, 0)
        return 0

    return sorted(board.legal_moves, key=move_score, reverse=True)

# minimax with alpha-beta pruning
def minimax(board, depth, alpha, beta, maximizing, deadline, tt):
    # bail out if we're over the time budget
    if time.time() >= deadline:
        raise SearchTimeout

    # checkmate: the side to move has lost. score from white's perspective,
    # offset by depth so faster mates rank higher (and slower losses rank less bad)
    if board.is_checkmate():
        if board.turn == chess.WHITE:
            return -(MATE_SCORE + depth), None  # white is mated -> bad for white
        else:
            return MATE_SCORE + depth, None     # black is mated -> good for white
    # any other game-over state (stalemate, insufficient material, repetition, 75-move) is a draw
    if board.is_game_over():
        return 0, None
    # depth exhausted on a non-terminal position: fall back to static eval
    if depth == 0:
        return evaluate(board), None

    key = chess.polyglot.zobrist_hash(board)
    tt_move = tt.get(key)  # from a previous iteration, or none
    best_move = None
    if maximizing:
        best_score = float("-inf")
        for move in _order_moves(board, tt_move):
            board.push(move)
            score, _ = minimax(board, depth - 1, alpha, beta, False, deadline, tt)
            board.pop()
            if score > best_score:
                best_score, best_move = score, move
            alpha = max(alpha, best_score)
            if alpha >= beta:
                break  # beta cutoff: minimizer above won't allow this line 
    else:
        best_score = float("inf")
        for move in _order_moves(board, tt_move):
            board.push(move)
            score, _ = minimax(board, depth - 1, alpha, beta, True, deadline, tt)
            board.pop()
            if score < best_score:
                best_score, best_move = score, move
            beta = min(beta, best_score)
            if beta <= alpha:
                break  # alpha cutoff: maximizer above won't allow this line

    # remember the best move so the next iteration tries it first
    if best_move is not None:
        tt[key] = best_move

    return best_score, best_move

# iterative-deepening: search increasing depths until time runs out
def get_engine_move(board, max_depth=MAX_DEPTH, time_limit=TIME_LIMIT):
    deadline = time.time() + time_limit 
    tt = {}  # fresh per move, shared across iterations
    maximizing = board.turn == chess.WHITE
    best_move, best_score, completed_depth = None, 0, 0
    root_stack_len = len(board.move_stack)

    for depth in range(1, max_depth + 1):
        try:
            score, move = minimax(board, depth, float("-inf"), float("inf"),
                                   maximizing, deadline, tt)
        except SearchTimeout:
            # undo any moves the aborted search left on the board
            while len(board.move_stack) > root_stack_len:
                board.pop()
            break  # keep the last finished depth's move 

        if move is not None:
            best_move, best_score, completed_depth = move, score, depth

        # forced mate found; deeper search can't beat it
        if abs(score) >= MATE_SCORE:
            break

    # if depth 1 didn't finish: grab any legal move (this would only happen if the time limit is very low or the position has a huge branching factor)
    if best_move is None:
        best_move = next(iter(board.legal_moves), None)

    # debug line 
    print(f"[engine] depth {completed_depth}  eval {best_score / 100:+.2f} (white's view)  move {best_move}")
    return best_move 
