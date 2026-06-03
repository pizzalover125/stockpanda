from flask import Flask, jsonify, request, render_template #type: ignore
import chess #type: ignore
from engine import get_engine_move

app = Flask(__name__)
board = chess.Board()

# show index.html
@app.route("/")
def index(): return render_template("index.html")

# get state of game in FEN and whether it's over
@app.route("/state")
def state(): return jsonify(fen=board.fen(), over=board.is_game_over())

# get all possible legal moves
@app.route("/legal")
def legal():
    sq = chess.parse_square(request.args.get("square"))
    moves = [chess.square_name(m.to_square) for m in board.legal_moves if m.from_square == sq]
    return jsonify(moves=moves)

# handle moves
@app.route("/move", methods=["POST"])
def move():
    uci = request.json.get("move")

    # handle promotion
    if len(uci) == 4:
        m = chess.Move.from_uci(uci)
        if board.piece_at(m.from_square) and \
           board.piece_at(m.from_square).piece_type == chess.PAWN and \
           chess.square_rank(m.to_square) in (0, 7):
            uci += request.json.get("promotion", "q")
    m = chess.Move.from_uci(uci)

    if m not in board.legal_moves:
        return jsonify(error="illegal"), 400

    # apply player's move and return immediately so the UI can render it
    board.push(m)
    return jsonify(fen=board.fen(), over=board.is_game_over())

@app.route("/engine_move", methods=["POST"])
def engine_move():
    if board.is_game_over():
        return jsonify(fen=board.fen(), over=True)

    board.push(get_engine_move(board))
    return jsonify(fen=board.fen(), over=board.is_game_over())

# reset the game
@app.route("/reset", methods=["POST"])
def reset():
    board.reset(); return jsonify(fen=board.fen(), over=False)

if __name__ == "__main__": app.run(debug=True)

# what is quintessence search?