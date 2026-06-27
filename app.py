import os
from flask import Flask, jsonify, request, render_template, session #type: ignore
import chess #type: ignore
from engine import get_engine_move, evaluate

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", os.urandom(24).hex())

def get_board():
    fen = session.get("fen", chess.STARTING_FEN)
    return chess.Board(fen)

def save_board(b):
    session["fen"] = b.fen()

def get_game_over_reason(b):
    if b.is_checkmate():
        winner = "Black" if b.turn == chess.WHITE else "White"
        return f"{winner} won by checkmate"
    elif b.is_stalemate():
        return "Draw by stalemate"
    elif b.is_insufficient_material():
        return "Draw by insufficient material"
    elif hasattr(b, "is_fivefold_repetition") and b.is_fivefold_repetition():
        return "Draw by repetition"
    elif hasattr(b, "is_fifty_moves") and b.is_fifty_moves():
        return "Draw by fifty-move rule"
    elif b.is_game_over():
        return "Draw"
    return ""

# show index.html
@app.route("/")
def index():
    return render_template("index.html")

# get state of game in FEN and whether it's over
@app.route("/state")
def state():
    b = get_board()
    return jsonify(
        fen=b.fen(),
        over=b.is_game_over(),
        score=evaluate(b)
    )

# get all possible legal moves
@app.route("/legal")
def legal():
    b = get_board()
    square_arg = request.args.get("square")
    if square_arg:
        sq = chess.parse_square(square_arg)
        moves = [chess.square_name(m.to_square) for m in b.legal_moves if m.from_square == sq]
        return jsonify(moves=moves)
    else:
        moves_dict = {}
        for m in b.legal_moves:
            from_sq = chess.square_name(m.from_square)
            to_sq = chess.square_name(m.to_square)
            moves_dict.setdefault(from_sq, []).append(to_sq)
        return jsonify(moves=moves_dict)

# handle moves
@app.route("/move", methods=["POST"])
def move():
    b = get_board()
    uci = request.json.get("move")

    # handle promotion
    if len(uci) == 4:
        m = chess.Move.from_uci(uci)
        if b.piece_at(m.from_square) and \
           b.piece_at(m.from_square).piece_type == chess.PAWN and \
           chess.square_rank(m.to_square) in (0, 7):
            uci += request.json.get("promotion", "q")
    m = chess.Move.from_uci(uci)

    if m not in b.legal_moves:
        return jsonify(error="illegal"), 400

    is_capture = b.is_capture(m)
    is_castling = b.is_castling(m)
    is_promotion = m.promotion is not None
    san = b.san(m)

    # apply player's move and return immediately so the UI can render it
    b.push(m)
    save_board(b)
    
    is_check = b.is_check()
    is_checkmate = b.is_checkmate()
    is_draw = b.is_game_over() and not is_checkmate
    score = evaluate(b)
    reason = get_game_over_reason(b) if b.is_game_over() else ""

    return jsonify(
        fen=b.fen(),
        over=b.is_game_over(),
        is_capture=is_capture,
        is_castling=is_castling,
        is_promotion=is_promotion,
        is_check=is_check,
        is_checkmate=is_checkmate,
        is_draw=is_draw,
        score=score,
        reason=reason,
        san=san
    )

@app.route("/engine_move", methods=["POST"])
def engine_move():
    b = get_board()
    if b.is_game_over():
        save_board(b)
        return jsonify(fen=b.fen(), over=True)

    data = request.get_json(silent=True) or {}
    difficulty = data.get("difficulty", "medium")
    m, score = get_engine_move(b, difficulty=difficulty)
    is_capture = b.is_capture(m)
    is_castling = b.is_castling(m)
    is_promotion = m.promotion is not None
    san = b.san(m)

    b.push(m)
    save_board(b)

    is_check = b.is_check()
    is_checkmate = b.is_checkmate()
    is_draw = b.is_game_over() and not is_checkmate
    reason = get_game_over_reason(b) if b.is_game_over() else ""

    return jsonify(
        fen=b.fen(),
        over=b.is_game_over(),
        is_capture=is_capture,
        is_castling=is_castling,
        is_promotion=is_promotion,
        is_check=is_check,
        is_checkmate=is_checkmate,
        is_draw=is_draw,
        score=score,
        reason=reason,
        san=san
    )

# reset the game
@app.route("/reset", methods=["POST"])
def reset():
    b = chess.Board()
    save_board(b)
    return jsonify(
        fen=b.fen(),
        over=False,
        score=evaluate(b)
    )

if __name__ == "__main__":
    app.run(debug=True, port=5004)
