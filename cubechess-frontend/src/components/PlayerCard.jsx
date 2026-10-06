import PieceIcon from './PieceIcon.jsx'
import { otherColor } from '../lib/chess.js'

export default function PlayerCard({ color, name, toMove, material, lead, captured, note }) {
  return (
    <section className={`player ${toMove ? 'is-to-move' : ''}`}>
      <div className="player-top">
        <span className="player-name">
          <i className={`chip chip-${color}`} />
          {color === 'white' ? 'White' : 'Black'}
        </span>
        <span className="player-note">{note ?? (toMove ? 'Your move' : name)}</span>
      </div>
      <div className="player-row">
        <span>Material</span>
        <span className="player-material">
          {lead > 0 && <span className="lead">+{lead}</span>}
          <strong>{material}</strong>
        </span>
      </div>
      <div className="player-row">
        <span>Captured</span>
        <span className="player-captured">
          {captured.length === 0 && <span className="player-none">none</span>}
          {captured.map((type, i) => (
            <PieceIcon key={i} type={type} color={otherColor(color)} size={24} />
          ))}
        </span>
      </div>
    </section>
  )
}
