// Board knowledge shared by every view: layers, colours, piece values, notation

// Top to bottom. `mark` is what move notation appends for a move landing on that layer.
export const LAYERS = [
  { z: 2, name: 'Space', dark: '#4A78D6', light: '#86A8EC', side: '#3A5FB0', mark: '↑2' },
  { z: 1, name: 'Sky', dark: '#7EC3F2', light: '#BFE3FA', side: '#5FA3D4', mark: '↑1' },
  { z: 0, name: 'Ground', dark: '#86CF7A', light: '#C4EBB9', side: '#66B25B', mark: '' },
  { z: -1, name: 'Dungeon', dark: '#B49AE8', light: '#D9CBF6', side: '#9479CC', mark: '↓1' },
  { z: -2, name: 'Abyss', dark: '#6B4FB8', light: '#9A82D6', side: '#523A96', mark: '↓2' },
]
export const FULL_BOARD = { size: 8, layers: [2, 1, 0, -1, -2] }
export const SMALL_BOARD = { size: 5, layers: [1, 0, -1] }

export const layerOf = (z) => LAYERS.find((layer) => layer.z === z)

// Standard chess values. Piece strength is probably different in 3D; retune after playtesting.
export const PIECE_VALUES = { Pawn: 1, Knight: 3, Bishop: 3, Rook: 5, Queen: 9, King: 0 }
const LETTERS = { King: 'K', Queen: 'Q', Rook: 'R', Bishop: 'B', Knight: 'N', Pawn: '' }
const FILES = 'abcdefgh'

export const keyOf = (coord) => `[${coord.join(', ')}]`
export const sameCoord = (a, b) => !!a && !!b && a[0] === b[0] && a[1] === b[1] && a[2] === b[2]
export const otherColor = (color) => (color === 'white' ? 'black' : 'white')

// "Pawn(white)" → { type: "Pawn", color: "white" }, "Rock" → { type: "Rock" }
export function parsePiece(str) {
  if (!str) return null
  const match = str.match(/^(\w+)\((\w+)\)$/)
  return match ? { type: match[1], color: match[2] } : { type: str }
}

// The API board ({"[4, 0, 0]": "King(white)"}) as a list of { key, coord, type, color }
export function boardItems(board) {
  return Object.entries(board ?? {}).map(([key, value]) => ({ key, coord: JSON.parse(key), ...parsePiece(value) }))
}

export function materialOf(board) {
  const totals = { white: 0, black: 0 }
  for (const item of boardItems(board)) {
    if (item.color) totals[item.color] += PIECE_VALUES[item.type] ?? 0
  }
  return totals
}

// Piece types each side has captured, most valuable first
export function capturedBy(history) {
  const taken = { white: [], black: [] }
  for (const move of history ?? []) {
    const victim = parsePiece(move.captured_piece)
    const mover = parsePiece(move.moving_piece)
    if (victim && mover) taken[mover.color].push(victim.type)
  }
  for (const list of Object.values(taken)) list.sort((a, b) => PIECE_VALUES[b] - PIECE_VALUES[a])
  return taken
}

const squareName = ([x, y]) => `${FILES[x]}${y + 1}`

// Move history → score-sheet rows: [{ number, white: move, black: move }]
// A move is { text, mark, z, suffix }: standard chess notation, then the layer mark
// (nothing on the Ground), then + or #.
export function scoreSheet(history) {
  const moves = []
  for (const entry of history ?? []) {
    const piece = parsePiece(entry.moving_piece)
    const suffix = entry.check === 'checkmate' ? '#' : entry.check === 'check' ? '+' : ''

    if (entry.special_move === 'promotion') {
      // The engine records a promotion as its own entry right after the pawn move
      const last = moves[moves.length - 1]
      if (last) {
        last.text += `=${LETTERS[parsePiece(entry.promotion_piece).type]}`
        last.suffix = suffix
      }
      continue
    }

    let text
    if (entry.special_move === 'castling') {
      text = entry.to[0] > entry.from[0] ? 'O-O' : 'O-O-O'
    } else {
      const takes = entry.captured_piece ? 'x' : ''
      const from = piece.type === 'Pawn' && takes ? FILES[entry.from[0]] : ''
      text = `${LETTERS[piece.type]}${from}${takes}${squareName(entry.to)}`
    }
    const z = entry.to[2]
    moves.push({ color: piece.color, text, z, mark: layerOf(z)?.mark ?? '', suffix })
  }

  const rows = []
  for (const move of moves) {
    const last = rows[rows.length - 1]
    if (move.color === 'black' && last && last.white && !last.black) last.black = move
    else rows.push({ number: rows.length + 1, [move.color]: move })
  }
  return rows
}

// ---------- positions for pictures (home page cards) ----------

const BACK_RANK = ['Rook', 'Knight', 'Bishop', 'Queen', 'King', 'Bishop', 'Knight', 'Rook']
const ROCKS = [
  [2, 2, -1], [5, 2, -1], [3, 3, -1], [4, 3, -1], [3, 4, -1], [4, 4, -1], [2, 5, -1], [5, 5, -1],
  [3, 2, -2], [4, 2, -2], [2, 3, -2], [5, 3, -2], [2, 4, -2], [5, 4, -2], [3, 5, -2], [4, 5, -2],
]

function makeBoard(pieces, rocks = []) {
  const board = {}
  for (const coord of rocks) board[keyOf(coord)] = 'Rock'
  for (const [type, color, ...coord] of pieces) board[keyOf(coord)] = `${type}(${color})`
  return board
}

export const START_BOARD = makeBoard(
  BACK_RANK.flatMap((type, x) => [
    [type, 'white', x, 0, 0], ['Pawn', 'white', x, 1, 0], ['Pawn', 'black', x, 6, 0], [type, 'black', x, 7, 0],
  ]),
  ROCKS,
)
export const PUZZLE_BOARD = makeBoard(
  [
    ['King', 'black', 7, 7, 0], ['Pawn', 'black', 6, 6, 0], ['Pawn', 'black', 7, 6, 0], ['Rook', 'black', 5, 7, 0],
    ['Queen', 'white', 3, 3, 1], ['Rook', 'white', 7, 0, 2], ['King', 'white', 1, 0, 0],
    ['Pawn', 'white', 0, 1, 0], ['Pawn', 'white', 1, 1, 0],
  ],
  ROCKS,
)
export const LESSON_BOARD = makeBoard([['Knight', 'white', 2, 2, 0]])
export const LESSON_MOVES = [
  [4, 3, 0], [4, 1, 0], [0, 3, 0], [0, 1, 0], [3, 4, 0], [3, 0, 0], [1, 4, 0], [1, 0, 0],
  [4, 2, 1], [0, 2, 1], [2, 4, 1], [2, 0, 1], [4, 2, -1], [0, 2, -1], [2, 4, -1], [2, 0, -1],
]
