#engine.py
import chess #type: ignore
import chess.polyglot #type: ignore
import chess.syzygy #type: ignore
import time

MAX_DEPTH = 5         # max search depth 
TIME_LIMIT = 4.0      # seconds per move
MATE_SCORE = 1000000  # large enough to always outweigh any material eval

BOOK_PATH = "pc2500.bin"    # set to None to disable
BOOK_MAX_PLY = 20           # stop using the book after this many plies

TABLEBASE_DIR = "syzygy/"   # set to None to disable; place .rtbw/.rtbz files here

TT_EXACT = 0
TT_LOWER = 1
TT_UPPER = 2

class TTEntry:
    __slots__ = ('depth', 'score', 'flag', 'best_move')
    def __init__(self, depth, score, flag, best_move):
        self.depth = depth
        self.score = score
        self.flag = flag
        self.best_move = best_move

class TranspositionTable:
    def __init__(self):
        self.table = {}

    def get(self, key):
        return self.table.get(key)

    def set(self, key, depth, score, flag, best_move):
        existing = self.table.get(key)
        if existing is None or depth >= existing.depth:
            self.table[key] = TTEntry(depth, score, flag, best_move)

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

# order just the captures by mvv-lva (used inside quiescence; no tt move here)
def _order_captures(board):
    def cap_score(move):
        victim = board.piece_at(move.to_square)
        attacker = board.piece_at(move.from_square)
        victim_val = PIECE_VALUES[victim.piece_type] if victim else PIECE_VALUES[chess.PAWN]  # en passant victim is a pawn
        attacker_val = PIECE_VALUES[attacker.piece_type]
        return victim_val * 10 - attacker_val
    return sorted(board.generate_legal_captures(), key=cap_score, reverse=True)

# quiescence search
def quiescence(board, alpha, beta, maximizing, deadline):
    if time.time() >= deadline:        # respect the time budget
        raise SearchTimeout

    stand_pat = evaluate(board)        # score if the side to move just declines to capture

    if maximizing:
        if stand_pat >= beta:          # already good enough; minimizer above avoids this line
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat
        best = stand_pat               # capturing is optional, so eval is a floor
        for move in _order_captures(board):
            board.push(move)
            score = quiescence(board, alpha, beta, False, deadline)
            board.pop()
            if score > best:
                best = score
            alpha = max(alpha, best)
            if alpha >= beta:          # beta cutoff
                break
    else:
        if stand_pat <= alpha:         # already bad enough; maximizer above avoids this line
            return stand_pat
        if stand_pat < beta:
            beta = stand_pat
        best = stand_pat               # eval is a ceiling for the minimizer
        for move in _order_captures(board):
            board.push(move)
            score = quiescence(board, alpha, beta, True, deadline)
            board.pop()
            if score < best:
                best = score
            beta = min(beta, best)
            if beta <= alpha:          # alpha cutoff
                break

    return best

# minimax with alpha-beta pruning and transposition table
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
    # depth exhausted on a non-terminal position: resolve captures with quiescence instead of a raw eval 
    if depth == 0:
        return quiescence(board, alpha, beta, maximizing, deadline), None

    key = chess.polyglot.zobrist_hash(board)
    tt_entry = tt.get(key)
    tt_move = tt_entry.best_move if tt_entry else None  # from a previous iteration, or none

    # tt cutoff: if we've already searched this position >= this depth, use the stored result
    if tt_entry and tt_entry.depth >= depth:
        score = tt_entry.score if maximizing else -tt_entry.score
        if tt_entry.flag == TT_EXACT:
            return score, tt_entry.best_move
        if tt_entry.flag == TT_LOWER:
            if maximizing:
                alpha = max(alpha, score)
            else:
                beta = min(beta, score)
        elif tt_entry.flag == TT_UPPER:
            if maximizing:
                beta = min(beta, score)
            else:
                alpha = max(alpha, score)
        if alpha >= beta:
            return score, tt_entry.best_move

    original_alpha = alpha
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

    # determine tt flag and store
    if maximizing:
        tt_score = best_score
        if best_score >= beta:
            flag = TT_LOWER  # fail-high: score is a lower bound
        elif best_score <= original_alpha:
            flag = TT_UPPER  # fail-low: score is an upper bound
        else:
            flag = TT_EXACT  # exact score
    else:
        tt_score = -best_score
        if best_score <= original_alpha:
            flag = TT_LOWER  # fail-high from minimizer's pov
        elif best_score >= beta:
            flag = TT_UPPER  # fail-low from minimizer's pov
        else:
            flag = TT_EXACT

    tt.set(key, depth, tt_score, flag, best_move)

    return best_score, best_move

# look up current position in the polyglot opening book; returns None if out of book
def get_book_move(board):
    if BOOK_PATH is None or len(board.move_stack) >= BOOK_MAX_PLY:
        return None
    try:
        with chess.polyglot.open_reader(BOOK_PATH) as reader:
            try:
                entry = reader.weighted_choice(board)
                return entry.move
            except IndexError:
                return None  # position not in book
    except FileNotFoundError:
        return None  # book file not found; fall through to engine search

_tablebase = None

def _init_tablebase():
    global _tablebase
    if TABLEBASE_DIR is None:
        return None
    if _tablebase is not None:
        return _tablebase
    try:
        tb = chess.syzygy.Tablebase()
        n = tb.add_directory(TABLEBASE_DIR)
        if n > 0:
            _tablebase = tb
            print(f"[tablebase] loaded {n} files from {TABLEBASE_DIR}")
            return tb
        tb.close()
    except Exception:
        pass
    return None

# probe the syzygy tablebase for the best move; returns None if unavailable
def get_tablebase_move(board):
    tb = _init_tablebase()
    if tb is None:
        return None

    best_move, best_score = None, -10**9

    for move in board.legal_moves:
        board.push(move)
        try:
            dtz = tb.probe_dtz(board)
        except (KeyError, ValueError):
            board.pop()
            continue
        board.pop()

        # dtz from opponent's perspective after our move:
        #   dtz < 0 → opponent losing → we're winning (good)
        #   dtz == 0 → draw
        #   dtz > 0 → opponent winning → we're losing (bad)
        if dtz < 0:        # we win
            score = 2_000_000 + dtz   # dtz is negative, smaller |dtz| = better
        elif dtz == 0:      # draw
            score = 1_000_000
        else:               # we lose
            score = -dtz    # larger dtz = longer loss = "better" among losses

        if score > best_score:
            best_score = score
            best_move = move

    if best_move is not None:
        print(f"[tablebase] move {best_move}")
    return best_move

# iterative-deepening: search increasing depths until time runs out
def get_engine_move(board, max_depth=MAX_DEPTH, time_limit=TIME_LIMIT):
    book_move = get_book_move(board)
    if book_move is not None:
        print(f"[book] {book_move}")
        return book_move

    tb_move = get_tablebase_move(board)
    if tb_move is not None:
        return tb_move

    deadline = time.time() + time_limit
    tt = TranspositionTable()
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

