# CubeChess 🎮♟️

A 3D chess variant on a 5-layer cube board. This is a **work in progress (WIP)**.

## Project Status: Phase 1 Complete ✅

### Phase 1: Backend Engine & API (COMPLETE)
- ✅ **Chess Engine** (`engine/`) — Full 3D chess rules
  - All piece movements (Pawn, Rook, Knight, Bishop, Queen, King)
  - Special moves: Castling, En Passant, Pawn Promotion
  - Check, Checkmate, Stalemate detection
  - Undo/Move history
  - Draw detection (stalemate, threefold repetition, 50-move limit, insufficient material)
  - Any board size from 4×4 to 8×8 with 1 to 5 layers
  
- ✅ **Computer player** (`ai/`) — three levels, see "Computer opponent" below

- ✅ **Flask API** (`api/`) — RESTful backend
  - GameManager wrapper layer
  - 6 API endpoints for game management
  - JSON serialization utilities
  - CORS enabled for frontend

### Phase 2: Frontend UI (WIP)
- ✅ Home page, game setup and the game screen (local two-player)
- ✅ Three.js 3D board: cube-shaped cells, 3D pieces, layer tools, camera controls
- ✅ Move list, captured material, chess clock with increment, undo, resign and draw by agreement
- ✅ Lesson player: nine lessons on a 5×5 three-layer board (`cubechess-frontend/src/lessons.json`)
- ✅ Scenario player: 30 checkmate puzzles in four tiers (`cubechess-frontend/src/scenarios.json`)
- ✅ Play against the computer (easy, medium, hard), with the last move marked on the board
- ⏳ Online play
- 🔧 Developer test bench at `#/bench` for checking backend behavior

### Phase 3: Polish & Deployment (Not Started)
- 🔄 Testing suite (engine + API covered in `tests/`)
- ⏳ Deployment

---

## Board Layout

**5 Layers (Z-axis):**
- Z=-2: Abyss (bottom)
- Z=-1: Dungeon
- Z=0: Ground (starting layer)
- Z=1: Sky
- Z=2: Space (top)

**Board Dimensions:** 8×8 per layer (standard chess board per layer)

**Two-Axis Rule:** No piece moves all 3 axes simultaneously (except Pawn captures in 3D context)

---

## Setup

### Backend
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run Flask server (from the project root)
python api/app.py
# Server runs on http://localhost:5001 (set PORT to change it;
# macOS reserves 5000 for AirPlay Receiver)

# Run the tests
python -m unittest discover -s tests
```

### Frontend
```bash
cd cubechess-frontend
npm install
npm run dev
# App runs on http://localhost:5173 (Vite picks the next free port if that one is taken)
```

### Computer opponent

The computer is not trained; it plays like a classic chess program (`ai/`):

1. It copies the position onto a compact board (`ai/board.py`) that lists moves about a
   thousand times faster than the rules engine. `tests/test_fast_board.py` holds the two to
   the same rules move for move.
2. It looks ahead: its moves, your replies, its answers (`ai/search.py`, alpha-beta search).
   Lines that are already worse than one it has found are dropped, and at the end of a line
   it follows captures until the position is quiet.
3. It scores the positions it reaches by material and placement (`ai/evaluate.py`). The piece
   values are first guesses for 3D (pawn 1, knight 4.8, bishop 5, rook 5.4, queen 11.5).

| Level | Looks ahead | Picks |
|---|---|---|
| Easy | 1 move | at random among moves within 1.5 pawns of the best |
| Medium | 2 moves, following captures | at random among moves within 0.3 pawns |
| Hard | as deep as 3 seconds allow (usually 4 to 5 moves) | the best move |

`python tools/play_match.py` plays the levels against each other (hard beat medium 40-0 and
medium beat easy 20-0), and is the way to check that a change makes the computer stronger.
The server does the thinking in a worker process (`api/thinker.py`).

The scenarios are generated, not hand-written: `python tools/generate_scenarios.py` searches
random positions for ones where White has exactly one way to force mate, and rewrites
`scenarios.json`. `tests/test_scenarios.py` re-checks every puzzle against the engine.

Pages (hash routes): `#/` home, `#/setup` new game, `#/game` the board, `#/learn` lessons,
`#/scenarios` puzzles, `#/bench` the developer test bench. The frontend needs the backend running; Vite proxies `/api` to port 5001.

The layers are named, top to bottom: Space, Sky, Ground, Dungeon, Abyss. Move notation is
standard chess notation plus a layer mark for moves that land off the Ground:
`↑1` Sky, `↑2` Space, `↓1` Dungeon, `↓2` Abyss (for example `Nb6↑1`).

The test bench edits positions through sandbox endpoints that are for testing only:
`/api/debug/setup`, `/api/debug/place`, `/api/debug/remove`, `/api/debug/turn`, `/api/debug/rocks`.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/game/new` | POST | Start new game. Optional body: `{"rocks": true, "move_limit": 50, "clock": {"initial": 600, "increment": 5}, "computer": {"color": "black", "level": "hard"}}` |
| `/api/game/state` | GET | Get current board state |
| `/api/game/move` | POST | Execute a move |
| `/api/game/legal-moves` | GET | Get legal moves for piece |
| `/api/game/computer-move` | POST | The computer thinks and plays (only on its turn) |
| `/api/game/promote` | POST | Promote pawn |
| `/api/game/undo` | POST | Undo last move (also reopens a game ended by resignation, agreement or timeout) |
| `/api/game/resign` | POST | Resign. Optional body: `{"color": "white"}`; default is the player to move |
| `/api/game/draw` | POST | Both players agreed to a draw |

Coordinates are `[x, y, z]` lists. Every game-state response carries `current_player`,
`board` (`{"[4, 0, 0]": "King(white)", ...}`), `status` (`ongoing`, `check`, `checkmate`,
`stalemate`, `draw`, `resigned`, `agreed_draw`, `timeout`), `winner`, `draw_reason`,
`halfmove_clock`, `move_limit`, `clock`, `board_size`, `pending_promotion` and `move_history`. Failed requests return
HTTP 400 with `success: false` and an `error` message.

**Move history:** each entry has `from`, `to`, `moving_piece`, `captured_piece`,
`promotion_piece`, `special_move` (`castling`, `en_passant`, `promotion` or `null`), `check`
(`check`, `checkmate` or `null`) and `ambiguous_from`: the squares of other pieces of the same
kind and color that could legally have made the same move. Move notation uses it to say which
piece moved (as in `Nbd2`).

**Draws:** `draw_reason` is `null` or one of `stalemate`, `repetition` (the same position
occurred three times), `move_limit` (`move_limit` moves by each player, 50 by default, with
no capture and no pawn move; `halfmove_clock` counts the single moves so far) or
`insufficient_material`. A player's material is insufficient when it could never checkmate a
bare king: a lone king, king and one knight, bishop or rook, or king and bishops on one square
color. A bishop's square color counts the layer too (`x + y + z` odd or even), because a
bishop can change layers. The rook is on that list because a king that can step to another layer always escapes it
(`tools/check_mating_material.py` checks every position); on a flat one-layer board a rook is
enough. The game is drawn when both players are in that state. The draw rules only apply while both kings are on the board, so
practice positions without kings never end in a draw.

**Game over:** once the game has ended (checkmate, any draw, resignation, agreement or
timeout), moving, promoting, resigning and offering a draw are refused with
`"The game is over"`, and `legal-moves` returns an empty list. Undo reopens the game.

**Computer:** `computer` is `null` for two human players, otherwise `{"color", "level"}` with
level `easy`, `medium` or `hard`. The page calls `computer-move` when it is the computer's
turn; the answer is the game after its move plus `thought` (`score`, `depth`, `nodes`,
`seconds`, `mate_in`). `/move` refuses moves for the computer's side. If the game changes
while the computer thinks (undo, new game), its move is dropped and the call fails with
`"The position changed while the computer was thinking"`. Undo takes back the computer's
reply together with your move. `/draw` is an offer the computer may refuse: the call then
fails with `draw_declined: true`. `/resign` without a color is the human's resignation.

**Two games:** the server keeps a `main` game and a separate `practice` game used by the
lessons. Every endpoint works on `main` unless the request adds `?game=practice`.

**Clock:** `clock` is `null` for an untimed game, otherwise
`{"initial", "increment", "white", "black", "running"}` in seconds. A player's clock runs only
on their turn and starts after White's first move; `increment` is added after each timed move.
When the player to move runs out, `status` becomes `timeout` and the opponent is the `winner`.
If that opponent could never checkmate (see below), the game is drawn instead: `winner` is `null` and `draw_reason`
is `timeout_insufficient_material`.
Undo puts the clocks back to where they were before that turn.

**Board size:** the engine works on any board from 4×4 to 8×8 with layers between -2 and 2.
`board_size` is `{"size", "z_min", "z_max"}`. A normal game is always 8, -2, 2; smaller boards
(5, -1, 1 for lessons) start empty and are filled through `/api/debug/setup`, which accepts
`size`, `z_min` and `z_max`.

**Promotion:** when a pawn reaches the last rank, `pending_promotion` holds its coordinate
and the turn does not pass until `/api/game/promote` is called with
`{"coord": [x, y, z], "piece_type": "Queen" | "Rook" | "Bishop" | "Knight"}`.
Undoing a promotion takes back the pawn move as well.

---

## Project Structure

```
CubeChess/
├── engine/                 # Game engine (Python)
│   ├── pieces.py          # Piece classes & movement rules
│   ├── board.py           # Board storage & operations
│   └── game_state.py      # Game logic & validation
├── ai/                    # Computer player
│   ├── tables.py         # Move tables for a board size
│   ├── board.py          # FastBoard: the compact board it thinks on
│   ├── evaluate.py       # Scoring a position
│   ├── search.py         # Looking ahead (alpha-beta)
│   └── levels.py         # Easy, medium, hard
├── api/                   # Flask backend
│   ├── app.py            # HTTP routes
│   ├── game_manager.py   # Business logic wrapper
│   ├── clock.py          # Chess clock
│   ├── thinker.py        # Runs the computer's thinking in a worker process
│   └── utils.py          # JSON serialization
├── cubechess-frontend/    # React + Vite + Three.js frontend
│   ├── src/
│   │   ├── pages/        # Home, Setup, Game
│   │   ├── components/   # CubeBoard (3D), LayerMap, MoveList, PlayerCard...
│   │   ├── lib/          # API calls, game hook, notation, settings
│   │   ├── bench/        # Developer test bench
│   │   └── pieces3d.js   # Procedural 3D piece models
│   └── dev/              # Sprite renderer used for the design artboards
├── tools/                # Scenario generator, level matches, mating-material check
├── tests/                # Test suite
└── IMPLEMENTATION_GUIDE.md # Original planning notes
```

---

## Technologies

- **Backend:** Python 3.x, Flask, Flask-CORS
- **Frontend:** React, Vite, Axios, Three.js (upcoming)
- **Version Control:** Git

---

## Learning Focus

This project is built with a learning-first approach:
- Understanding full-stack architecture
- Backend: Engine → Manager → API layer pattern
- Frontend: Component composition, API integration, 3D rendering
- Proper separation of concerns

---

## Next Steps

1. ✅ Build basic 2D board display (React)
2. ✅ Connect API for move execution
3. ✅ Test all game logic through UI
4. ✅ Add Three.js for 3D visualization
5. ✅ Polish UI/UX

---

## Notes

See [IMPLEMENTATION_GUIDE.md](IMPLEMENTATION_GUIDE.md) for detailed technical specifications.

---

**Status:** Phase 1 (Backend) complete. Phase 2 (Frontend) in progress.
