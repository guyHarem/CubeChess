# CubeChess 🎮♟️

A 3D chess variant on a 5-layer cube board. This is a **work in progress (WIP)**.

## Project Status: Phase 1 Complete ✅

### Phase 1: Backend Engine & API (COMPLETE)
- ✅ **Chess Engine** (`engine/`) — Full 3D chess rules
  - All piece movements (Pawn, Rook, Knight, Bishop, Queen, King)
  - Special moves: Castling, En Passant, Pawn Promotion
  - Check, Checkmate, Stalemate detection
  - Undo/Move history
  - Draw detection (insufficient material)
  
- ✅ **Flask API** (`api/`) — RESTful backend
  - GameManager wrapper layer
  - 6 API endpoints for game management
  - JSON serialization utilities
  - CORS enabled for frontend

### Phase 2: Frontend UI (WIP)
- 🔄 React + Vite scaffolding (created)
- ⏳ 2D board visualization
- ⏳ Three.js 3D rendering
- ⏳ Move execution UI
- ⏳ Game state display

### Phase 3: Polish & Deployment (Not Started)
- ⏳ Testing suite
- ⏳ Deployment

---

## Board Layout

**5 Layers (Z-axis):**
- Z=-2: Abyss (bottom)
- Z=-1: Dungeon
- Z=0: Surface (starting layer)
- Z=1: Sky
- Z=2: Sky High (top)

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

# Run Flask server
cd api
python app.py
# Server runs on http://localhost:5000
```

### Frontend
```bash
cd cubechess-frontend
npm install
npm run dev
# App runs on http://localhost:5173
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/game/new` | POST | Start new game |
| `/api/game/state` | GET | Get current board state |
| `/api/game/move` | POST | Execute a move |
| `/api/game/legal-moves` | GET | Get legal moves for piece |
| `/api/game/promote` | POST | Promote pawn |
| `/api/game/undo` | POST | Undo last move |

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
├── cubechess-frontend/    # React + Vite frontend
│   └── src/
│       ├── components/   # React components
│       └── hooks/        # Custom hooks (API calls)
├── tests/                # Test suite
└── IMPLEMENTATION_GUIDE.md # Detailed specs
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
