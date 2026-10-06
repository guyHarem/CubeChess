// Game setup choices. Kept for the browser tab only: nothing is saved between visits yet.

export const DEFAULT_SETTINGS = {
  opponent: 'local', // only local two-player exists so far
  side: 'white', // which colour sits nearest the camera
  rocks: true,
  showLegalMoves: true,
  allowUndo: true,
  moveLimit: 50,
}

const KEY = 'cubechess.settings'

export function loadSettings() {
  try {
    return { ...DEFAULT_SETTINGS, ...JSON.parse(sessionStorage.getItem(KEY) ?? '{}') }
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

export function saveSettings(settings) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(settings))
  } catch {
    // Storage can be unavailable (private windows); the game still works with defaults
  }
}
