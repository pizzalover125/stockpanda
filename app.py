from flask import Flask, jsonify, request, render_template #type: ignore
import chess #type: ignore
from engine import get_engine_move

app = Flask(__name__)
board = chess.Board()

# show index.html
@app.route("/")
def index(): return render_template("index.html")

# get game state
@app.route("/state")
def state(): return jsonify(fen=board.fen(), over=board.is_game_over())

# get all legal moves
@app.route("/legal")
def legal():
    sq = chess.parse_square(request.args.get("square"))
    moves = [chess.square_name(m.to_square) for m in board.legal_moves if m.from_square == sq]
    return jsonify(moves=moves)

@app.route("/move", methods=["POST"])
def move():
    # get move from request
    uci = request.json.get("move")

    # handle promotion moves
    if len(uci) == 4:
        m = chess.Move.from_uci(uci)
        if board.piece_at(m.from_square) and \
           board.piece_at(m.from_square).piece_type == chess.PAWN and \
           chess.square_rank(m.to_square) in (0, 7):
            uci += request.json.get("promotion", "q")
    m = chess.Move.from_uci(uci)

    # check if move is legal
    if m not in board.legal_moves:
        return jsonify(error="illegal"), 400

    # make the move
    board.push(m)

    # if game not over, get engine move
    if not board.is_game_over():
        board.push(get_engine_move(board))

    return jsonify(fen=board.fen(), over=board.is_game_over())

# reset the game
@app.route("/reset", methods=["POST"])
def reset():
    board.reset(); return jsonify(fen=board.fen(), over=False)

if __name__ == "__main__": app.run(debug=True)