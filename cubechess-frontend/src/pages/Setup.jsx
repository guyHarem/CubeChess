import { useState } from 'react'
import CubeBoard from '../components/CubeBoard.jsx'
import Logo from '../components/Logo.jsx'
import { api } from '../lib/api.js'
import { START_BOARD } from '../lib/chess.js'
import { navigate } from '../lib/router.js'
import { loadSettings, saveSettings } from '../lib/settings.js'

function Choice({ selected, disabled, onClick, title, hint, children }) {
  return (
    <button
      type="button"
      className={`choice ${selected ? 'is-selected' : ''}`}
      aria-pressed={selected}
      disabled={disabled}
      onClick={onClick}
    >
      {children ?? title}
      {hint && <small>{hint}</small>}
    </button>
  )
}

function Switch({ label, checked, onChange }) {
  return (
    <button type="button" className="switch" role="switch" aria-checked={checked} onClick={() => onChange(!checked)}>
      {label}
      <span className="switch-track">
        <span className="switch-knob" />
      </span>
    </button>
  )
}

export default function Setup() {
  const [settings, setSettings] = useState(loadSettings)
  const [sideChoice, setSideChoice] = useState(settings.side)
  const [error, setError] = useState(null)
  const [starting, setStarting] = useState(false)
  const set = (patch) => setSettings((current) => ({ ...current, ...patch }))

  const limit = Number(settings.moveLimit)
  const limitValid = Number.isInteger(limit) && limit >= 10 && limit <= 200
  const previewSide = sideChoice === 'black' ? 'black' : 'white'
  const previewBoard = settings.rocks
    ? START_BOARD
    : Object.fromEntries(Object.entries(START_BOARD).filter(([, value]) => value !== 'Rock'))

  async function start() {
    setStarting(true)
    const side = sideChoice === 'random' ? (Math.random() < 0.5 ? 'white' : 'black') : sideChoice
    try {
      const data = await api('/game/new', { rocks: settings.rocks, move_limit: limit })
      if (!data.success) throw new Error(data.error)
      saveSettings({ ...settings, side, moveLimit: limit })
      navigate('/game')
    } catch (problem) {
      setError(
        problem instanceof TypeError || problem instanceof SyntaxError
          ? 'Cannot reach the game server. Start it with: python api/app.py'
          : problem.message,
      )
      setStarting(false)
    }
  }

  return (
    <div className="page">
      <header className="bar">
        <Logo />
        <a className="bar-link" href="#/">
          Back to home
        </a>
      </header>

      <main className="setup-main">
        <div className="setup-form">
          <h1>New game</h1>

          <fieldset>
            <legend>Opponent</legend>
            <div className="choices choices-3">
              <Choice selected title="Two players" hint="Same screen, take turns" />
              <Choice disabled title="Computer" hint="Not built yet" />
              <Choice disabled title="Online" hint="Not built yet" />
            </div>
          </fieldset>

          <fieldset>
            <legend>Side nearest you</legend>
            <div className="choices">
              <Choice selected={sideChoice === 'white'} onClick={() => setSideChoice('white')}>
                <i className="chip chip-white" />
                White
              </Choice>
              <Choice selected={sideChoice === 'black'} onClick={() => setSideChoice('black')}>
                <i className="chip chip-black" />
                Black
              </Choice>
              <Choice selected={sideChoice === 'random'} onClick={() => setSideChoice('random')} title="Random" />
            </div>
          </fieldset>

          <fieldset>
            <legend>Rules and help</legend>
            <div className="switches">
              <Switch label="Rocks in the dungeon" checked={settings.rocks} onChange={(rocks) => set({ rocks })} />
              <Switch
                label="Show legal moves"
                checked={settings.showLegalMoves}
                onChange={(showLegalMoves) => set({ showLegalMoves })}
              />
              <Switch label="Allow undo" checked={settings.allowUndo} onChange={(allowUndo) => set({ allowUndo })} />
              <div className="field">
                <label htmlFor="quiet">Draw after quiet moves</label>
                <input
                  id="quiet"
                  type="number"
                  min="10"
                  max="200"
                  value={settings.moveLimit}
                  aria-invalid={!limitValid}
                  aria-describedby="quiet-help"
                  onChange={(event) => set({ moveLimit: event.target.value })}
                />
              </div>
            </div>
            <p id="quiet-help" className={`help ${limitValid ? '' : 'help-error'}`}>
              {limitValid
                ? 'A quiet move has no capture and no pawn move. The game is drawn when both players make this many in a row.'
                : 'Enter a whole number from 10 to 200.'}
            </p>
          </fieldset>

          {error && <p className="banner-error">{error}</p>}

          <div className="setup-actions">
            <button type="button" className="button button-primary button-large" disabled={!limitValid || starting} onClick={start}>
              {starting ? 'Starting' : 'Start game'}
            </button>
            <a className="bar-link" href="#/">
              Cancel
            </a>
          </div>
        </div>

        <aside className="setup-preview">
          <div className="setup-picture">
            <CubeBoard interactive={false} board={previewBoard} side={previewSide} />
          </div>
          <p className="setup-summary">
            <strong>Two players on this screen</strong>
            {sideChoice === 'random' ? 'A coin flip decides which side sits nearest.' : `${previewSide === 'white' ? 'White' : 'Black'} sits nearest. White moves first.`}
            <br />
            {settings.rocks ? 'Rocks on.' : 'Rocks off.'} {settings.allowUndo ? 'Undo allowed.' : 'No undo.'}
          </p>
        </aside>
      </main>
    </div>
  )
}
