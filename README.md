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
- ⏳ Scenarios, computer opponent, online play
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
# App runs on http://localhost:5173
```

Pages (hash routes): `#/` home, `#/setup` new game, `#/game` the board, `#/learn` lessons,
`#/bench` the developer test bench. The frontend needs the backend running; Vite proxies `/api` to port 5001.

The layers are named, top to bottom: Space, Sky, Ground, Dungeon, Abyss. Move notation is
standard chess notation plus a layer mark for moves that land off the Ground:
`↑1` Sky, `↑2` Space, `↓1` Dungeon, `↓2` Abyss (for example `Nb6↑1`).

The test bench edits positions through sandbox endpoints that are for testing only:
`/api/debug/setup`, `/api/debug/place`, `/api/debug/remove`, `/api/debug/turn`, `/api/debug/rocks`.

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/game/new` | POST | Start new game. Optional body: `{"rocks": true, "move_limit": 50, "clock": {"initial": 600, "increment": 5}}` |
| `/api/game/state` | GET | Get current board state |
| `/api/game/move` | POST | Execute a move |
| `/api/game/legal-moves` | GET | Get legal moves for piece |
| `/api/game/promote` | POST | Promote pawn |
| `/api/game/undo` | POST | Undo last move (also reopens a game ended by resignation, agreement or timeout) |
| `/api/game/resign` | POST | Resign. Optional body: `{"color": "white"}`; default is the player to move |
| `/api/game/draw` | POST | Both players agreed to a draw |

Coordinates are `[x, y, z]` lists. Every game-state response carries `current_player`,
`board` (`{"[4, 0, 0]": "King(white)", ...}`), `status` (`ongoing`, `check`, `checkmate`,
`stalemate`, `draw`, `resigned`, `agreed_draw`, `timeout`), `winner`, `draw_reason`,
`halfmove_clock`, `move_limit`, `clock`, `board_size`, `pending_promotion` and `move_history`. Failed requests return
HTTP 400 with `success: false` and an `error` message.

**Draws:** `draw_reason` is `null` or one of `stalemate`, `repetition` (the same position
occurred three times), `move_limit` (`move_limit` moves by each player, 50 by default, with
no capture and no pawn move; `halfmove_clock` counts the single moves so far) or
`insufficient_material`. Draws are reported automatically; the engine itself does not block
further moves after one, so the UI decides when to stop the game.

**Two games:** the server keeps a `main` game and a separate `practice` game used by the
lessons. Every endpoint works on `main` unless the request adds `?game=practice`.

**Clock:** `clock` is `null` for an untimed game, otherwise
`{"initial", "increment", "white", "black", "running"}` in seconds. A player's clock runs only
on their turn and starts after White's first move; `increment` is added after each timed move.
When the player to move runs out, `status` becomes `timeout` and the opponent is the `winner`.
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
├── api/                   # Flask backend
│   ├── app.py            # HTTP routes
│   ├── game_manager.py   # Business logic wrapper
│   └── utils.py          # JSON serialization
├── cubechess-frontend/    # React + Vite + Three.js frontend
│   ├── src/
│   │   ├── pages/        # Home, Setup, Game
│   │   ├── components/   # CubeBoard (3D), LayerMap, MoveList, PlayerCard...
│   │   ├── lib/          # API calls, game hook, notation, settings
│   │   ├── bench/        # Developer test bench
│   │   └── pieces3d.js   # Procedural 3D piece models
│   └── dev/              # Sprite renderer used for the design artboards
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
