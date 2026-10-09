"""
Tune the computer player's scoring numbers by self-play.

    venv/bin/python tools/tune.py games --count 2000          # 1. the computer plays itself
    venv/bin/python tools/tune.py fit                          # 2. fit the numbers to who won
    venv/bin/python tools/tune.py match --a tools/data/tuned.json   # 3. new numbers v current ones

Step 1 saves the quiet positions of every game with the game's result. Step 2 looks for the
parameters (see ai/evaluate.py) whose score best predicts those results, staying close to
the current values unless the games say otherwise. Step 3 is the proof: only numbers that
win a match against the current ones should be kept (copy them into DEFAULT_PARAMS).

Everything is written under tools/data/, which is not part of the repository.
"""
import argparse
import json
import math
import multiprocessing
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai.board import FastBoard, move_promotion, SQUARE
from ai.evaluate import DEFAULT_PARAMS, FIRST_GUESSES, FIXED_PARAMS, PARAM_NAMES, position_features
from ai.search import Search, MATE_BOUND
from api.game_manager import GameManager
from engine import pieces

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
MAX_PLIES = 400
TUNED = [name for name in PARAM_NAMES if name not in FIXED_PARAMS]


def load_params(path):
    if path in (None, "default"):
        return dict(DEFAULT_PARAMS)
    if path == "first-guesses":
        return dict(FIRST_GUESSES)
    with open(path, encoding="utf-8") as f:
        return {**DEFAULT_PARAMS, **json.load(f)}


# ==================== 1. SELF-PLAY ====================

def play_one(job):
    """One game between two sets of parameters. Returns (White's result 1 / 0.5 / 0, single
    moves played, [feature rows of the quiet positions]) ."""
    seed, white, black, depth, nodes, margin, opening, record = job
    rng = random.Random(seed)
    manager = GameManager()
    params = {"white": white, "black": black}
    rows = []
    for ply in range(MAX_PLIES):
        color = manager.game.current_player
        board = FastBoard.from_game_state(manager.game, params[color])
        if ply < opening:
            move = rng.choice(board.legal_moves())   # a random start, so no two games are alike
        else:
            result = Search(board).run(max_depth=depth, nodes=nodes, margin=margin)
            move = result.move
            if margin and result.scores:
                best = max(result.scores.values())
                if best < MATE_BOUND:
                    close = [(m, s) for m, s in result.scores.items() if s >= best - margin]
                    move = rng.choices([m for m, _ in close], [1 / (1 + (best - s) / (margin / 3)) for _, s in close])[0]
            quiet = not board.cells[(move >> 9) & SQUARE] and not move_promotion(move) and move >> 21 != 2
            if record and quiet and abs(result.score) < MATE_BOUND and not board.in_check():
                features = position_features(board)
                rows.append([round(features[name], 3) for name in PARAM_NAMES])
        from_coord, to_coord, promotion = board.describe(move)
        response = manager.make_move(from_coord, to_coord)
        if response["success"] and response["pending_promotion"] is not None:
            response = manager.promote_pawn(to_coord, getattr(pieces, promotion)(color))
        if not response["success"]:
            raise RuntimeError(f"illegal move {from_coord}->{to_coord}: {response['error']}")
        if response["status"] not in ("ongoing", "check"):
            winner = response["winner"]
            return (1.0 if winner == "white" else 0.0 if winner == "black" else 0.5), ply + 1, rows
    return 0.5, MAX_PLIES, rows


def games(args):
    os.makedirs(DATA, exist_ok=True)
    params = load_params(args.params)
    jobs = [(args.seed + i, params, params, args.depth, args.nodes, args.margin, args.opening, True)
            for i in range(args.count)]
    started = time.perf_counter()
    results = {1.0: 0, 0.5: 0, 0.0: 0}
    positions = plies = 0
    with multiprocessing.Pool() as pool, open(args.out, "a", encoding="utf-8") as out:
        for done, (result, length, rows) in enumerate(pool.imap_unordered(play_one, jobs), 1):
            out.write(json.dumps({"result": result, "positions": rows}) + "\n")
            results[result] += 1
            positions += len(rows)
            plies += length
            if done % 100 == 0 or done == args.count:
                print(f"{done} games, {positions} positions, {time.perf_counter() - started:.0f}s", flush=True)
    print(f"White won {results[1.0]}, drew {results[0.5]}, lost {results[0.0]}; "
          f"average game {plies / args.count / 2:.0f} moves each. Saved to {args.out}")


# ==================== 2. FITTING ====================

_rows = None


def _load_chunk(path, part, parts, held_out):
    """Worker start-up: keep every `parts`-th game in memory"""
    global _rows
    _rows = []
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f):
            if number % parts != part:
                continue
            game = json.loads(line)
            training = number % 10 != 9          # every tenth game is kept aside to check the fit
            if training != held_out:
                _rows.extend((row, game["result"]) for row in game["positions"])


def _loss_and_gradient(job):
    """Log-loss of predicting results from the score, and its slope in every parameter"""
    weights, k = job
    loss = 0.0
    gradient = [0.0] * len(weights)
    gradient_k = 0.0
    for row, result in _rows:
        score = 0.0
        for w, f in zip(weights, row):
            score += w * f
        x = k * score / 100
        p = 1 / (1 + math.exp(-x)) if x > -30 else 1e-13
        p = min(max(p, 1e-13), 1 - 1e-13)
        loss -= result * math.log(p) + (1 - result) * math.log(1 - p)
        error = p - result
        gradient_k += error * score / 100
        error *= k / 100
        for i, f in enumerate(row):
            if f:
                gradient[i] += error * f
    return loss, gradient, gradient_k, len(_rows)


class Dataset:
    def __init__(self, path, held_out=False):
        workers = multiprocessing.cpu_count()
        self.pools = [multiprocessing.Pool(1, _load_chunk, (path, part, workers, held_out)) for part in range(workers)]
        self.count = 0

    def measure(self, weights, k):
        answers = [pool.apply_async(_loss_and_gradient, ((weights, k),)) for pool in self.pools]
        loss, gradient, gradient_k, count = 0.0, [0.0] * len(weights), 0.0, 0
        for answer in answers:
            part_loss, part_gradient, part_k, part_count = answer.get()
            loss += part_loss
            gradient = [a + b for a, b in zip(gradient, part_gradient)]
            gradient_k += part_k
            count += part_count
        self.count = count
        return loss / count, [g / count for g in gradient], gradient_k / count

    def close(self):
        for pool in self.pools:
            pool.terminate()


def feature_spread(path):
    """How much each feature varies across positions (so every parameter is tuned at a similar pace)"""
    total = [0.0] * len(PARAM_NAMES)
    count = 0
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f):
            if number % 5:
                continue
            for row in json.loads(line)["positions"]:
                count += 1
                for i, value in enumerate(row):
                    total[i] += value * value
    return [math.sqrt(t / max(count, 1)) or 1.0 for t in total], count * 5


def fit(args):
    start = load_params(args.params)
    spread, estimate = feature_spread(args.data)
    print(f"about {estimate} positions")
    training, held_out = Dataset(args.data), Dataset(args.data, held_out=True)
    tuned = [i for i, name in enumerate(PARAM_NAMES) if name not in FIXED_PARAMS]

    weights = [float(start[name]) for name in PARAM_NAMES]
    # First find the scale that turns the current scores into the best win predictions
    # (k is how much one pawn of score counts; the error has a single lowest point in k)
    low, high = 0.01, 3.0
    for _ in range(30):
        third = (high - low) / 3
        if training.measure(weights, low + third)[0] < training.measure(weights, high - third)[0]:
            high -= third
        else:
            low += third
    k = (low + high) / 2
    before = held_out.measure(weights, k)[0]
    print(f"scale k = {k:.3f}; error on held-out games before tuning {before:.5f}")

    # Adam, on parameters measured in "pawns of score they move in a typical position"
    first = [0.0] * len(weights)
    second = [0.0] * len(weights)
    first_k = second_k = 0.0
    origin = list(weights)
    for step in range(1, args.steps + 1):
        loss, slope, slope_k = training.measure(weights, k)
        for i in tuned:
            # Stay near the starting value unless the games pull away from it
            drift = (weights[i] - origin[i]) * spread[i] / 100
            g = (slope[i] + 2 * args.hold * drift * spread[i] / 100) / spread[i] * 100
            first[i] = 0.9 * first[i] + 0.1 * g
            second[i] = 0.999 * second[i] + 0.001 * g * g
            stride = args.rate * (first[i] / (1 - 0.9 ** step)) / (math.sqrt(second[i] / (1 - 0.999 ** step)) + 1e-9)
            weights[i] -= stride / spread[i] * 100
        first_k = 0.9 * first_k + 0.1 * slope_k
        second_k = 0.999 * second_k + 0.001 * slope_k * slope_k
        k -= args.rate * (first_k / (1 - 0.9 ** step)) / (math.sqrt(second_k / (1 - 0.999 ** step)) + 1e-9)
        if step % 25 == 0 or step == args.steps:
            print(f"step {step}: training error {loss:.5f}, held-out {held_out.measure(weights, k)[0]:.5f}", flush=True)
    after = held_out.measure(weights, k)[0]
    training.close()
    held_out.close()

    result = {name: round(weights[i], 2 if abs(weights[i]) < 20 else 0) for i, name in enumerate(PARAM_NAMES)}
    print(f"\nheld-out error {before:.5f} -> {after:.5f}\n")
    print(f"{'parameter':18} {'before':>8} {'after':>8}")
    for name in PARAM_NAMES:
        print(f"{name:18} {start[name]:>8} {result[name]:>8}")
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {args.out}")


# ==================== 3. THE PROOF ====================

def match(args):
    a, b = load_params(args.a), load_params(args.b)
    jobs = []
    for pair in range(args.games // 2):
        # Each random opening is played twice, with the sides swapped
        seed = args.seed + pair
        jobs.append((seed, a, b, args.depth, args.nodes, args.margin, args.opening, False))
        jobs.append((seed, b, a, args.depth, args.nodes, args.margin, args.opening, False))
    wins = draws = losses = 0
    started = time.perf_counter()
    with multiprocessing.Pool() as pool:
        for number, (result, _, _) in enumerate(pool.imap(play_one, jobs)):
            for_a = result if number % 2 == 0 else 1 - result
            wins += for_a == 1
            draws += for_a == 0.5
            losses += for_a == 0
    played = wins + draws + losses
    points = (wins + draws / 2) / played
    # How far from 50% chance alone would put the score, with this many games
    noise = math.sqrt(0.25 / played)
    print(f"{args.a} v {args.b}: {wins} wins, {draws} draws, {losses} losses "
          f"({points:.1%} of the points, chance alone gives 50% +/- {2 * noise:.1%}) in {time.perf_counter() - started:.0f}s")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)

    def playing_options(command, depth, nodes):
        command.add_argument("--depth", type=int, default=depth, help="moves to look ahead")
        command.add_argument("--nodes", type=int, default=nodes, help="positions to search per move at most")
        command.add_argument("--margin", type=int, default=20, help="pick at random among moves this close to the best")
        command.add_argument("--opening", type=int, default=6, help="random single moves at the start of each game")
        command.add_argument("--seed", type=int, default=1)

    command = commands.add_parser("games", help="self-play, saving positions and results")
    command.add_argument("--count", type=int, default=2000)
    command.add_argument("--params", default="default")
    command.add_argument("--out", default=os.path.join(DATA, "games.jsonl"))
    playing_options(command, 2, None)
    command.set_defaults(run=games)

    command = commands.add_parser("fit", help="fit the parameters to the saved games")
    command.add_argument("--data", default=os.path.join(DATA, "games.jsonl"))
    command.add_argument("--params", default="default", help="starting values")
    command.add_argument("--out", default=os.path.join(DATA, "tuned.json"))
    command.add_argument("--steps", type=int, default=300)
    command.add_argument("--rate", type=float, default=0.02)
    command.add_argument("--hold", type=float, default=0.002, help="how strongly to stay near the starting values")
    command.set_defaults(run=fit)

    command = commands.add_parser("match", help="play two sets of parameters against each other")
    command.add_argument("--a", required=True)
    command.add_argument("--b", default="default")
    command.add_argument("--games", type=int, default=200)
    playing_options(command, 64, 15000)
    command.set_defaults(run=match)

    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
