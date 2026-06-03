# notes about chess engines

## basics

- engine needs eval function to rate a position
- engine uses eval function to create a tree of possible moves

## eval function

- each piece given a value (pawn = 1, knight/bishop = 3, rook = 5, queen = 9)
- piece square tables
  - bonus/penalty based on where piece is
    - ex: knight on edge is lot worse than knight in center

## search algorithms + techniques

- minimax
  - try every move
  - opponents also pick best move
  - do 3-6 times (more times = more time)
  - take best end outcome

- alpha-beta pruning
  - skips branches that are bad
  - ex if on first move you become -4, then just give up the branch

- iterative deepening
  - search depth = 1, 2, 3, etc
  - stop when allotted time runs out
  - can be faster bc alpha pruning removes bad moves immedietaly

- opening book
  - precompiled list of best opening moves

- endgame tablebase
  - precompiled list of how to win endgames with 7 pieces or less

## course of action

- board
- Web UI support
- legal move generation
- minimax
- alpha-beta pruning
- iterative deepening
- opening book / tablebase
- Terminal support
- Lichess support

## credits

learned a lot from https://www.youtube.com/watch?v=U4ogK0MIzqk and https://www.chessprogramming.org/Main_Page.
