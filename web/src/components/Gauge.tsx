import type { Motor } from '../data'
import { pct } from '../data'

// The "how sure" dial: where this motor's damage estimate sits against its own line and 'ask a person' zone.
export function Gauge({ m, size = 190 }: { m: Motor; size?: number }) {
  if (m.p_median == null || m.line == null || m.band == null) {
    return <p className="small muted">Too few usable recordings for an estimate: shown as 'ask a person'.</p>
  }
  const w = size, h = size * 0.62, cx = w / 2, cy = h - 8, r = size * 0.42
  const ang = (p: number) => Math.PI * (1 - p)
  const pt = (p: number, rr = r) => [cx + rr * Math.cos(ang(p)), cy - rr * Math.sin(ang(p))]
  const arc = (a: number, b: number, color: string) => {
    const [x1, y1] = pt(a), [x2, y2] = pt(b)
    return <path d={`M${x1},${y1} A${r},${r} 0 0 1 ${x2},${y2}`} stroke={color} strokeWidth={size * 0.085} fill="none" />
  }
  const z0 = Math.max(0, m.line - m.band), z1 = Math.min(1, m.line + m.band)
  const [nx, ny] = pt(Math.min(Math.max(m.p_median, 0.003), 0.997), r * 0.92)
  return (
    <svg viewBox={`0 0 ${w} ${h + 20}`} width={w} role="img"
      aria-label={`Damage estimate ${pct(m.p_median)}; ask-a-person zone ${pct(z0)} to ${pct(z1)}`}>
      {arc(0, z0, 'var(--ok)')}
      {arc(z0, z1, 'var(--ask)')}
      {arc(z1, 1, 'var(--check)')}
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="var(--ink)" strokeWidth={3} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={6} fill="var(--ink)" />
      <text x={6} y={h + 16} fontSize="11.5" fill="var(--ink-2)">healthy</text>
      <text x={w - 6} y={h + 16} fontSize="11.5" fill="var(--ink-2)" textAnchor="end">damaged</text>
      <text x={cx} y={cy - r * 0.35} fontSize="15" fontWeight={800} fill="var(--ink)" textAnchor="middle">{pct(m.p_median)}</text>
    </svg>
  )
}
