// Game state from the backend plus the local selection (which piece is picked up)
import { useCallback, useEffect, useState } from 'react'
import { api, legalMovesOf } from './api.js'
import { keyOf, parsePiece, sameCoord } from './chess.js'

const OFFLINE = 'Cannot reach the game server. Start it with: python api/app.py'

// which: 'main' for the real game, 'practice' for the lesson board
export function useGame(which = 'main') {
  const [game, setGame] = useState(null)
  const [selected, setSelected] = useState(null)
  const [legalMoves, setLegalMoves] = useState([])
  const [error, setError] = useState(null)

  const clearSelection = useCallback(() => {
    setSelected(null)
    setLegalMoves([])
  }, [])

  // Every state-changing endpoint answers with the whole game
  const call = useCallback(async (path, body) => {
    try {
      const data = await api(path, body, which)
      if (data.board) setGame({ ...data, receivedAt: performance.now() })
      // A declined draw offer is an answer, not a fault: the page shows it its own way
      setError(data.success || data.draw_declined ? null : data.error)
      setSelected(null)
      setLegalMoves([])
      return data
    } catch {
      setError(OFFLINE)
      return null
    }
  }, [which])

  useEffect(() => {
    api('/game/state', undefined, which)
      .then((data) => {
        setGame({ ...data, receivedAt: performance.now() })
        setError(null)
      })
      .catch(() => setError(OFFLINE))
  }, [which])

  // Re-read the game without touching the selection (used when a clock runs out)
  const refresh = useCallback(async () => {
    try {
      const data = await api('/game/state', undefined, which)
      setGame({ ...data, receivedAt: performance.now() })
    } catch {
      setError(OFFLINE)
    }
  }, [which])

  // Ask the computer to think and play. A refusal still carries the current game, and is
  // normal when the position changed while it thought (undo, new game), so it shows no error.
  const computerMove = useCallback(async () => {
    try {
      const data = await api('/game/computer-move', {}, which)
      if (data.board) setGame({ ...data, receivedAt: performance.now() })
      return data
    } catch {
      setError(OFFLINE)
      return null
    }
  }, [which])

  const select = useCallback(async (coord) => {
    try {
      const data = await legalMovesOf(coord, which)
      setSelected(coord)
      setLegalMoves(data.legal_moves ?? [])
    } catch {
      setError(OFFLINE)
    }
  }, [which])

  // One click on a cell: play the move if it is legal, otherwise pick up or put down a piece
  const clickCell = useCallback(
    (coord) => {
      if (!game || game.pending_promotion) return
      if (selected && legalMoves.some((move) => sameCoord(move, coord))) {
        call('/game/move', { from: selected, to: coord })
        return
      }
      const piece = parsePiece(game.board[keyOf(coord)])
      if (piece?.color === game.current_player && !sameCoord(selected, coord)) select(coord)
      else clearSelection()
    },
    [game, selected, legalMoves, call, select, clearSelection],
  )

  return {
    game,
    selected,
    legalMoves,
    error,
    clickCell,
    clearSelection,
    select,
    refresh,
    computerMove,
    setup: (position) => call('/debug/setup', position),
    move: (from, to) => call('/game/move', { from, to }),
    resign: (color) => call('/game/resign', { color }),
    agreeDraw: () => call('/game/draw', {}),
    newGame: (options) => call('/game/new', options ?? {}),
    undo: () => call('/game/undo', {}),
    promote: (pieceType) => call('/game/promote', { coord: game.pending_promotion, piece_type: pieceType }),
  }
}
