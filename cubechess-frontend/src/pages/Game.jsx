import { useState } from 'react'
import CubeBoard from '../components/CubeBoard.jsx'
import Dialog from '../components/Dialog.jsx'
import LayerMap from '../components/LayerMap.jsx'
import Logo from '../components/Logo.jsx'
import MoveList from '../components/MoveList.jsx'
import PlayerCard from '../components/PlayerCard.jsx'
import { FULL_BOARD, LAYERS, capturedBy, keyOf, layerOf, materialOf, otherColor, parsePiece } from '../lib/chess.js'
import { loadSettings } from '../lib/settings.js'
import { useGame } from '../lib/useGame.js'

const NAMES = { white: 'White', black: 'Black' }
const PROMOTIONS = ['Queen', 'Rook', 'Bishop', 'Knight']

// How the game ended, as a headline and one line of detail. null while it is still going.
function outcomeOf(game, local) {
  if (local?.kind === 'resigned') {
    return { title: `${NAMES[otherColor(local.by)]} wins`, detail: `${NAMES[local.by]} resigned.` }
  }
  if (local?.kind === 'agreed') return { title: 'Draw', detail: 'Both players agreed to a draw.' }
  if (!game) return null
  if (game.status === 'checkmate') {
    return { title: `${NAMES[otherColor(game.current_player)]} wins`, detail: 'Checkmate.' }
  }
  const reasons = {
    stalemate: `${NAMES[game.current_player]} has no legal move and is not in check.`,
    repetition: 'The same position came up three times.',
    move_limit: `Both players made ${game.move_limit} moves with no capture and no pawn move.`,
    insufficient_material: 'Neither side has enough pieces left to checkmate.',
  }
  return game.draw_reason ? { title: 'Draw', detail: reasons[game.draw_reason] } : null
}

export default function Game() {
  const { game, selected, legalMoves, error, clickCell, newGame, undo, promote } = useGame()
  const [settings] = useState(loadSettings)
  const [side, setSide] = useState(settings.side)
  const [activeLayer, setActiveLayer] = useState(0)
  const [spread, setSpread] = useState(false)
  const [solo, setSolo] = useState(false)
  const [command, setCommand] = useState(null)
  const [asking, setAsking] = useState(null) // 'resign' | 'draw'
  const [local, setLocal] = useState(null) // an ending the server does not know about
  const [resultSeen, setResultSeen] = useState(false)

  const board = game?.board ?? {}
  const history = game?.move_history ?? []
  const player = game?.current_player ?? 'white'
  const outcome = outcomeOf(game, local)
  const material = materialOf(board)
  const captured = capturedBy(history)
  const quiet = game ? Math.floor(game.halfmove_clock / 2) : 0

  const send = (type, direction) => setCommand({ id: Date.now(), type, direction })

  function onCellClick(coord) {
    if (outcome) return
    // Picking up a piece on another layer brings that layer forward
    const piece = parsePiece(board[keyOf(coord)])
    const isTarget = legalMoves.some((move) => keyOf(move) === keyOf(coord))
    if (!isTarget && piece?.color === player) setActiveLayer(coord[2])
    clickCell(coord)
  }

  function restart() {
    setLocal(null)
    setResultSeen(false)
    setAsking(null)
    newGame({ rocks: settings.rocks, move_limit: settings.moveLimit })
  }

  function takeBack() {
    setLocal(null)
    setResultSeen(false)
    undo()
  }

  const card = (color) => (
    <PlayerCard
      color={color}
      name={color === 'white' ? 'Player 1' : 'Player 2'}
      toMove={!outcome && player === color}
      note={!outcome && player === color && game?.status === 'check' ? 'Your move, in check' : undefined}
      material={material[color]}
      lead={material[color] - material[otherColor(color)]}
      captured={captured[color]}
    />
  )

  return (
    <div className="game">
      <header className="bar">
        <Logo />
        <div className={`turn turn-${outcome ? 'over' : player}`} aria-live="polite">
          {!outcome && <i className={`chip chip-${player}`} />}
          {outcome ? outcome.title : `${NAMES[player]} to move`}
          {!outcome && game?.status === 'check' && <span className="turn-check">Check</span>}
        </div>
        <div className="bar-actions">
          <button type="button" className="button" onClick={restart}>
            New game
          </button>
          <a className="button" href="#/">
            Exit
          </a>
        </div>
      </header>

      <main className="game-main">
        <aside className="game-left">
          {card(otherColor(side))}

          <div className="game-actions">
            <div className="button-grid">
              <button type="button" className="button" disabled={!settings.allowUndo || history.length === 0} onClick={takeBack}>
                Undo move
              </button>
              <button type="button" className="button" disabled={!!outcome} onClick={() => setAsking('draw')}>
                Offer draw
              </button>
              <button type="button" className="button" disabled={!!outcome} onClick={() => setAsking('resign')}>
                Resign
              </button>
              <button type="button" className="button" onClick={() => setSide(otherColor(side))}>
                Flip side
              </button>
            </div>
            <p className="quiet">
              {quiet} of {game?.move_limit ?? settings.moveLimit} quiet moves. The game is drawn at the limit, when
              nobody captures or moves a pawn.
            </p>
            {error && <p className="banner-error">{error}</p>}
          </div>

          {card(side)}
        </aside>

        <section className="game-centre">
          <div className="layer-picker" role="group" aria-label="Current layer">
            {LAYERS.map((layer) => (
              <button
                key={layer.z}
                type="button"
                className={`button layer-button ${activeLayer === layer.z ? 'is-selected' : ''}`}
                aria-pressed={activeLayer === layer.z}
                style={activeLayer === layer.z ? { background: layer.light, borderColor: layer.light } : undefined}
                onClick={() => setActiveLayer(layer.z)}
              >
                <i className="swatch" style={{ background: layer.dark }} />
                {layer.name}
              </button>
            ))}
          </div>

          <div className="board-frame">
            <CubeBoard
              board={board}
              size={FULL_BOARD.size}
              layers={FULL_BOARD.layers}
              activeLayer={activeLayer}
              selected={selected}
              legalMoves={legalMoves}
              showMoveBalls={settings.showLegalMoves}
              spread={spread}
              solo={solo}
              side={side}
              command={command}
              onCellClick={onCellClick}
            />

            {game?.pending_promotion && (
              <Dialog
                title="Promote your pawn"
                actions={PROMOTIONS.map((type) => (
                  <button key={type} type="button" className="button" onClick={() => promote(type)}>
                    {type}
                  </button>
                ))}
              >
                <p>Choose the piece it becomes.</p>
              </Dialog>
            )}

            {asking === 'resign' && (
              <Dialog
                title={`${NAMES[player]}, resign this game?`}
                actions={
                  <>
                    <button
                      type="button"
                      className="button button-danger"
                      onClick={() => {
                        setLocal({ kind: 'resigned', by: player })
                        setAsking(null)
                      }}
                    >
                      Resign
                    </button>
                    <button type="button" className="button" onClick={() => setAsking(null)}>
                      Keep playing
                    </button>
                  </>
                }
              >
                <p>{NAMES[otherColor(player)]} will win.</p>
              </Dialog>
            )}

            {asking === 'draw' && (
              <Dialog
                title={`${NAMES[player]} offers a draw`}
                actions={
                  <>
                    <button
                      type="button"
                      className="button button-primary"
                      onClick={() => {
                        setLocal({ kind: 'agreed' })
                        setAsking(null)
                      }}
                    >
                      Accept draw
                    </button>
                    <button type="button" className="button" onClick={() => setAsking(null)}>
                      Decline
                    </button>
                  </>
                }
              >
                <p>{NAMES[otherColor(player)]}, do you accept?</p>
              </Dialog>
            )}

            {outcome && !resultSeen && !asking && (
              <Dialog
                title={outcome.title}
                actions={
                  <>
                    <button type="button" className="button button-primary" onClick={restart}>
                      New game
                    </button>
                    <button type="button" className="button" onClick={() => setResultSeen(true)}>
                      Look at the board
                    </button>
                  </>
                }
              >
                <p>{outcome.detail}</p>
              </Dialog>
            )}
          </div>

          <div className="view-controls">
            <button type="button" className="button" onClick={() => send('turn', -1)}>
              Turn left
            </button>
            <button type="button" className="button" onClick={() => send('turn', 1)}>
              Turn right
            </button>
            <button type="button" className="button" onClick={() => send('reset')}>
              Reset view
            </button>
            <button type="button" className={`button ${spread ? 'is-on' : ''}`} aria-pressed={spread} onClick={() => setSpread(!spread)}>
              Spread layers
            </button>
            <button type="button" className={`button ${solo ? 'is-on' : ''}`} aria-pressed={solo} onClick={() => setSolo(!solo)}>
              Only this layer
            </button>
          </div>
        </section>

        <aside className="game-right">
          <section>
            <h2>{layerOf(activeLayer).name}, seen from above</h2>
            <LayerMap
              board={board}
              size={FULL_BOARD.size}
              z={activeLayer}
              side={side}
              selected={selected}
              legalMoves={legalMoves}
              showMoves={settings.showLegalMoves}
              onCellClick={onCellClick}
            />
          </section>
          <MoveList history={history} currentPlayer={player} finished={!!outcome} />
        </aside>
      </main>
    </div>
  )
}
