"""
Can king + one piece FORCE checkmate against a bare king?

Solved exactly, by working backwards from every checkmate position until nothing changes
(an endgame tablebase). Only small boards are within reach: the 5x5 three-layer lesson
board takes about 20 seconds per piece, the full board would take days in Python.

    venv/bin/python tools/forced_mate.py Rook 5 -1 1      # piece, size, lowest layer, highest layer

On that board a rook, bishop or knight forces mate only from the few positions that are
already one move from it (0.1%), and a queen always does, in at most 9 moves. This is what
GameState.has_insufficient_material relies on.
"""
import os
import sys
import time
from array import array

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ai.board import FastBoard
from ai.tables import KING, ROOK, BISHOP, KNIGHT, QUEEN, BLACK

name, size, z_min, z_max = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
PIECE = {"Rook": ROOK, "Bishop": BISHOP, "Knight": KNIGHT, "Queen": QUEEN}[name]
b = FastBoard(size, z_min, z_max)
n = b.t.n
index = lambda wk, bk, pc: (wk * n + bk) * n + pc
total = n * n * n

def place(wk, bk, pc, side):
    for colour in (0, 1):
        for sq in b.squares[colour]:
            b.cells[sq] = 0
        b.squares[colour].clear()
    b.cells[wk] = KING; b.cells[bk] = KING | BLACK; b.cells[pc] = PIECE
    b.squares[0].update((wk, pc)); b.squares[1].add(bk)
    b.kings[0], b.kings[1] = wk, bk
    b.side = side
    b.ep = b.ep_pawn = -1

started = time.time()
# For each position: is it legal, and where does each legal move lead?
white_next = [None] * total      # white to move: list of black-to-move positions
black_next = [None] * total      # black to move: list of white-to-move positions (-1 = the piece was taken: draw)
mated = array("b", [0]) * total
for wk in range(n):
    for bk in range(n):
        if bk == wk or bk in b.t.king_attacks[wk]:
            continue
        for pc in range(n):
            if pc == wk or pc == bk:
                continue
            i = index(wk, bk, pc)
            place(wk, bk, pc, 0)
            if not b.in_check(BLACK):          # with White to move, Black may not be in check
                out = []
                for m in b.legal_moves():
                    f, t = m & 511, (m >> 9) & 511
                    if t == bk:
                        continue
                    out.append(index(t, bk, pc) if f == wk else index(wk, bk, t))
                white_next[i] = out
            place(wk, bk, pc, BLACK)
            out = [(-1 if ((m >> 9) & 511) == pc else index(wk, (m >> 9) & 511, pc)) for m in b.legal_moves()]
            black_next[i] = out
            if not out and b.in_check(BLACK):
                mated[i] = 1
    if wk % 15 == 0:
        print(f"  built {wk + 1}/{n} king squares, {time.time() - started:.0f}s", flush=True)

legal_white = sum(1 for x in white_next if x is not None)
print(f"{name} on {size}x{size}, layers {z_min}..{z_max}: {legal_white} legal positions with White to move, "
      f"{sum(mated)} checkmates")

# Work backwards: lost[i] = Black to move and gets mated however it plays; won[i] = White to move and can force it
lost = array("b", mated)
won = array("b", [0]) * total
depth = 0
changed = True
while changed:
    changed = False
    depth += 1
    for i in range(total):
        nxt = white_next[i]
        if nxt and not won[i]:
            for j in nxt:
                if lost[j]:
                    won[i] = 1; changed = True
                    break
    for i in range(total):
        nxt = black_next[i]
        if nxt and not lost[i]:
            for j in nxt:
                if j < 0 or not won[j]:
                    break
            else:
                lost[i] = 1; changed = True
    print(f"  pass {depth}: White wins from {sum(won)} positions", flush=True)

wins = sum(won)
print(f"RESULT {name}: White to move can force mate from {wins} of {legal_white} positions ({wins / legal_white:.1%}), "
      f"longest win about {depth - 1} moves, {time.time() - started:.0f}s")
