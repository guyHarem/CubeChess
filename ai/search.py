"""
Looking ahead: the computer tries its moves, the replies, its answers to those, and so on,
and picks the move whose worst outcome is best.

This is alpha-beta search (see the README for a plain description), with the usual helpers:
- deepening: search 1 move deep, then 2, then 3..., stopping when time runs out
- a memory of positions already searched (the "table"), so work is never done twice
- move ordering: the remembered best move, then captures of valuable pieces, then moves
  that refuted other lines, so that hopeless lines are cut off early
- quiescence: at the end of a line, keep following captures until the position is quiet
- searching unlikely moves less deeply, and only fully if they turn out well
"""
import time

from ai.board import SQUARE, KIND, EN_PASSANT, move_promotion
from ai.evaluate import evaluate, MATE, VALUES
from ai.tables import PAWN, KING, BLACK

INFINITY = MATE * 2
EXACT, AT_LEAST, AT_MOST = 0, 1, 2
MATE_BOUND = MATE - 1000          # scores beyond this are forced mates
TABLE_LIMIT = 1_500_000           # forget everything when the memory grows past this
QUIESCENCE_DEPTH = 6              # how many captures deep the end-of-line search follows
FUTILITY_MARGIN = (0, 250, 600)   # by remaining depth: skip quiet moves this far below the target
PIECE_VALUE = [0] * 32
for _piece, _value in VALUES.items():
    for _code in (_piece, _piece | 8, _piece | 16, _piece | 24):
        PIECE_VALUE[_code] = _value
PIECE_VALUE[KING] = PIECE_VALUE[KING | 8] = PIECE_VALUE[KING | 16] = PIECE_VALUE[KING | 24] = 20_000


# move >> 18 for the moves that are neither a promotion nor en passant: plain, double step, castling
QUIET_KINDS = (0, 8, 24)


class OutOfTime(Exception):
    pass


class Result:
    def __init__(self):
        self.move = None       # the move to play (a FastBoard move number), None if there is none
        self.score = 0         # for the player to move, in hundredths of a pawn
        self.depth = 0         # how many moves deep the search finished
        self.nodes = 0         # positions looked at
        self.seconds = 0.0
        self.scores = {}       # move -> score for every root move scored at the final depth
        self.line = []         # the expected continuation, starting with `move`

    @property
    def mate_in(self):
        """Moves until mate when the score is a forced mate (negative: being mated), else None"""
        if abs(self.score) < MATE_BOUND:
            return None
        moves = (MATE - abs(self.score) + 1) // 2
        return moves if self.score > 0 else -moves


class Search:
    def __init__(self, board, now=time.perf_counter, quiescence=QUIESCENCE_DEPTH):
        self.board = board
        self.now = now
        self.quiescence = quiescence   # 0: score lines where they end, without following captures
        self.table = {}
        self.history = {}
        self.killers = [[0, 0] for _ in range(128)]
        self.nodes = 0
        self.deadline = None
        self.node_limit = None
        # Draw rules only apply to real games, which have both kings
        self.rules = board.kings[0] >= 0 and board.kings[1] >= 0

    # ==================== ENTRY POINT ====================

    def run(self, max_depth=64, seconds=None, nodes=None, margin=0):
        """Search deeper and deeper until the depth, time or node budget runs out.
        margin: also score properly every root move within this many points of the best
        (the weaker levels pick among those); 0 scores only the best move exactly."""
        board = self.board
        result = Result()
        started = self.now()
        self.deadline = None if seconds is None else started + seconds
        self.node_limit = nodes
        self.nodes = 0

        moves = board.legal_moves()
        if not moves:
            return result
        in_check = board.in_check()
        result.move = moves[0]
        ordered = self._order(moves, self.table.get(board.key, (0, 0, 0, 0))[3], 0)

        for depth in range(1, max_depth + 1):
            scores = {}
            best_move, best_score = None, -INFINITY
            try:
                for move in ordered:
                    alpha = max(-INFINITY, best_score - margin - 1)
                    board.make(move)
                    gives_check = board.gives_check(move)
                    try:
                        score = -self._search(depth - 1, -INFINITY, -alpha, 1, gives_check)
                    finally:
                        board.unmake()
                    scores[move] = score
                    if score > best_score:
                        best_move, best_score = move, score
            except OutOfTime:
                # A half-finished pass still counts if it found something better than the
                # previous pass's choice, which is always searched first
                if best_move is not None and best_move != result.move and depth > 1:
                    result.move, result.score = best_move, best_score
                break
            result.move, result.score, result.depth, result.scores = best_move, best_score, depth, scores
            self.table[board.key] = (depth, EXACT, best_score, best_move)
            ordered.sort(key=lambda move: -scores[move])
            elapsed = self.now() - started
            if abs(best_score) >= MATE_BOUND and depth >= MATE - abs(best_score):
                break  # a forced mate has been found; deeper search cannot improve on it
            if len(moves) == 1 and depth >= 1 and margin == 0:
                break  # only one legal move: no need to think
            if seconds is not None and elapsed > seconds * 0.45:
                break  # the next pass would take several times longer than what is left
        result.nodes = self.nodes
        result.seconds = self.now() - started
        result.line = self._line(result.move)
        return result

    def _line(self, first, limit=8):
        """The expected continuation, read back from the table"""
        board = self.board
        line, move = [], first
        while move and len(line) < limit:
            if move not in board.legal_moves():
                break
            line.append(move)
            board.make(move)
            move = self.table.get(board.key, (0, 0, 0, 0))[3]
        for _ in line:
            board.unmake()
        return line

    # ==================== THE SEARCH ====================

    def _search(self, depth, alpha, beta, ply, in_check):
        """Best score the player to move can force, within the window alpha..beta"""
        board = self.board
        self.nodes += 1
        if self.nodes & 1023 == 0:
            if self.deadline is not None and self.now() >= self.deadline:
                raise OutOfTime
            if self.node_limit is not None and self.nodes >= self.node_limit:
                raise OutOfTime

        if self.rules:
            half = board.half
            # A position seen before is heading for a draw by repetition
            if half >= 4 and board.key in board.history[-half:]:
                return 0
            if half >= 2 * board.move_limit and not in_check:
                return 0
            if len(board.squares[0]) + len(board.squares[1]) <= 4 and board.insufficient(0) and board.insufficient(1):
                return 0

        if in_check and ply < 40:
            depth += 1  # never stop looking in the middle of a check
        if depth <= 0:
            return self._quiesce(alpha, beta, ply, 0, False)

        key = board.key
        entry = self.table.get(key)
        table_move = 0
        if entry is not None:
            entry_depth, flag, score, table_move = entry
            if entry_depth >= depth:
                if score >= MATE_BOUND:
                    score -= ply
                elif score <= -MATE_BOUND:
                    score += ply
                if flag == EXACT or (flag == AT_LEAST and score >= beta) or (flag == AT_MOST and score <= alpha):
                    return score

        static = None
        if not in_check and beta - alpha == 1:
            static = evaluate(board)
            # Already so far ahead that even giving up a margin keeps the opponent's line refuted
            if depth <= 2 and static - FUTILITY_MARGIN[depth] >= beta and abs(beta) < MATE_BOUND:
                return static
            # Null move: if passing the turn still beats beta, a real move will too
            if depth >= 3 and static >= beta and self._has_pieces(board.side):
                self._pass()
                try:
                    score = -self._search(depth - 3, -beta, -beta + 1, ply + 1, False)
                finally:
                    self._unpass()
                if score >= beta and score < MATE_BOUND:
                    return beta

        moves = self._order(board.pseudo_moves(), table_move, ply)
        cells = board.cells
        original_alpha = alpha
        best_score, best_move = -INFINITY, 0
        searched = 0
        skip_quiet = (static is not None and depth <= 2 and static + FUTILITY_MARGIN[depth] <= alpha
                      and abs(alpha) < MATE_BOUND)

        for move in moves:
            quiet = not cells[(move >> 9) & SQUARE] and move >> 18 in QUIET_KINDS
            if skip_quiet and quiet and searched:
                continue
            board.make(move)
            if board.exposes_king(move, in_check):
                board.unmake()
                continue
            gives_check = board.gives_check(move)
            try:
                if searched == 0:
                    score = -self._search(depth - 1, -beta, -alpha, ply + 1, gives_check)
                else:
                    # Late quiet moves are unlikely to be best: look less deeply first
                    reduction = 0
                    if depth >= 3 and quiet and not in_check and not gives_check and searched >= 4:
                        reduction = 1 if searched < 16 else 2
                    score = -self._search(depth - 1 - reduction, -alpha - 1, -alpha, ply + 1, gives_check)
                    if score > alpha and reduction:
                        score = -self._search(depth - 1, -alpha - 1, -alpha, ply + 1, gives_check)
                    if alpha < score < beta:
                        score = -self._search(depth - 1, -beta, -alpha, ply + 1, gives_check)
            finally:
                board.unmake()
            searched += 1

            if score > best_score:
                best_score, best_move = score, move
                if score > alpha:
                    alpha = score
                    if alpha >= beta:
                        if quiet:
                            killers = self.killers[ply]
                            if killers[0] != move:
                                killers[1] = killers[0]
                                killers[0] = move
                            index = move & 0x3FFFF | board.side << 15
                            self.history[index] = self.history.get(index, 0) + depth * depth
                        break

        if searched == 0:
            # No legal move at all: checkmate or stalemate
            return -MATE + ply if in_check else 0

        if len(self.table) > TABLE_LIMIT:
            self.table.clear()
        stored = best_score
        if stored >= MATE_BOUND:
            stored += ply
        elif stored <= -MATE_BOUND:
            stored -= ply
        flag = AT_LEAST if best_score >= beta else AT_MOST if best_score <= original_alpha else EXACT
        self.table[key] = (depth, flag, stored, best_move)
        return best_score

    def _quiesce(self, alpha, beta, ply, depth, in_check):
        """Follow captures until the position is quiet, then score it"""
        board = self.board
        self.nodes += 1
        stand = evaluate(board)
        if stand >= beta or depth >= self.quiescence:
            return stand
        if stand > alpha:
            alpha = stand

        cells = board.cells
        captures = board.captures()
        if not captures:
            return stand
        # Most valuable victim first, taken by the least valuable attacker
        captures.sort(key=lambda move: PIECE_VALUE[cells[move & SQUARE]] - 16 * PIECE_VALUE[cells[(move >> 9) & SQUARE]])
        for move in captures:
            gain = PIECE_VALUE[cells[(move >> 9) & SQUARE]]
            if move & KIND == EN_PASSANT:
                gain = PIECE_VALUE[PAWN]
            if move_promotion(move):
                gain += 900
            if stand + gain + 150 < alpha:
                continue  # even winning this piece for nothing would not be enough
            board.make(move)
            if board.exposes_king(move, in_check):
                board.unmake()
                continue
            try:
                score = -self._quiesce(-beta, -alpha, ply + 1, depth + 1, board.gives_check(move))
            finally:
                board.unmake()
            if score > alpha:
                alpha = score
                if alpha >= beta:
                    break
        return alpha

    # ==================== HELPERS ====================

    def _order(self, moves, table_move, ply):
        """Most promising first: the remembered best move, captures by what they win, moves
        that refuted sibling lines, then quiet moves by how often they have worked"""
        cells = self.board.cells
        history = self.history
        killer_one, killer_two = self.killers[ply] if ply < 128 else (0, 0)
        side = self.board.side << 15

        def promise(move):
            if move == table_move:
                return -10_000_000
            victim = cells[(move >> 9) & SQUARE]
            if victim:
                return -1_000_000 - 16 * PIECE_VALUE[victim] + PIECE_VALUE[cells[move & SQUARE]]
            if move >> 18 not in QUIET_KINDS:
                return -900_000
            if move == killer_one:
                return -800_000
            if move == killer_two:
                return -700_000
            return -history.get(move & 0x3FFFF | side, 0)

        moves.sort(key=promise)
        return moves

    def _has_pieces(self, side):
        """Does the player have anything besides king and pawns? (Passing is unsafe otherwise)"""
        counts = self.board.counts
        return counts[side | 2] + counts[side | 3] + counts[side | 4] + counts[side | 5] > 0

    def _pass(self):
        """Give the turn to the opponent without moving (search trick only)"""
        board = self.board
        board._undo.append((board.ep, board.ep_pawn, board.key, board.half))
        board.history.append(board.key)
        board.ep = board.ep_pawn = -1
        board.side ^= BLACK
        board.half = 0
        board.key = board._full_key(0)

    def _unpass(self):
        board = self.board
        board.ep, board.ep_pawn, board.key, board.half = board._undo.pop()
        board.history.pop()
        board.side ^= BLACK

