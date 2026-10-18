import type { Motor } from '../data'

// Where the detector put this motor: three zones and five steps, from the verdict and 'how sure' words only.
// No number is shown: on unseen bearings the detector's percentage did not mean what it says (FR-001).
const STEPS = [
  { key: 'healthy|high', label: 'healthy, how sure: high' },
  { key: 'healthy|medium', label: 'healthy, how sure: medium' },
  { key: 'ask a person', label: 'ask a person, how sure: low' },
  { key: 'check bearing|medium', label: 'check bearing, how sure: medium' },
  { key: 'check bearing|high', label: 'check bearing, how sure: high' },
]

function stepOf(m: Motor): number {
  if (m.plant_word === 'ask a person') return 2
  const i = STEPS.findIndex(s => s.key === `${m.plant_word}|${m.how_sure}`)
  return i < 0 ? 2 : i
}

export function VerdictBar({ m }: { m: Motor }) {
  const at = stepOf(m)
  const pos = (i: number) => `${10 + i * 20}%`
  return (
    <div className="vbar" role="img"
      aria-label={`${m.motor_name}: detector says ${STEPS[at].label}`}>
      <div className="vbar-track">
        <span className="vbar-zone ok" style={{ width: '40%' }}>healthy</span>
        <span className="vbar-zone ask" style={{ width: '20%' }}>ask a person</span>
        <span className="vbar-zone check" style={{ width: '40%' }}>check bearing</span>
        <span className="vbar-dot" style={{ left: pos(at) }} />
      </div>
      <div className="vbar-steps">
        {STEPS.map((s, i) => (
          <span key={s.key} style={{ left: pos(i) }} className={i === at ? 'on' : ''}>{s.label}</span>
        ))}
      </div>
    </div>
  )
}
