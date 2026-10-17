import { forwardRef, useState } from 'react'
import type { Hiss } from '../data'

// The "hiss picture": how loud a motor's current is in each pitch slice, against the healthy lab bearings.
// Every value is from app.json (median of the motor's own recordings at the plant setting).

export interface HissProps {
  hiss: Hiss
  values: number[]
  color?: string
  showHealthy?: boolean
  showNotes?: boolean
  showListen?: boolean
  compact?: boolean
  diff?: boolean
  width?: number
  height?: number
  title?: string
}

const fmtHz = (x: number) => (x >= 1000 ? `${(x / 1000).toFixed(x >= 10000 ? 0 : 1)} kHz` : `${Math.round(x)} Hz`)

export const HissChart = forwardRef<SVGSVGElement, HissProps>(function HissChart(
  { hiss, values, color = 'var(--signal)', showHealthy = true, showNotes = true, showListen = true, compact = false, diff = false,
    width = 860, height = 300, title }, ref) {
  const [hover, setHover] = useState<number | null>(null)
  const m = compact ? { l: 4, r: 4, t: 4, b: 4 } : { l: 52, r: 16, t: 26, b: showListen ? 74 : 40 }
  const W = width - m.l - m.r
  const H = height - m.t - m.b
  const lo = Math.log10(hiss.edges[0])
  const hi = Math.log10(hiss.edges[hiss.edges.length - 1])
  const x = (hz: number) => m.l + ((Math.log10(hz) - lo) / (hi - lo)) * W
  // diff: show every value as its difference from the healthy median, so 1 to 2 dB shifts become visible.
  const base = diff ? hiss.healthy_median : hiss.healthy_median.map(() => 0)
  values = values.map((v, i) => v - base[i])
  const hLow = hiss.healthy_low.map((v, i) => v - base[i])
  const hHigh = hiss.healthy_high.map((v, i) => v - base[i])
  const hMed = hiss.healthy_median.map((v, i) => v - base[i])
  const all = [...values, ...hLow, ...hHigh]
  const step = diff ? 1 : 5
  const ymin = Math.floor(Math.min(...all) / step) * step - (diff ? 0.5 : 2)
  const ymax = Math.ceil(Math.max(...all) / step) * step + (diff ? 0.5 : 2)
  const y = (db: number) => m.t + (1 - (db - ymin) / (ymax - ymin)) * H
  const n = values.length
  const centers = Array.from({ length: n }, (_, i) => Math.sqrt(hiss.edges[i] * hiss.edges[i + 1]))
  const line = (vals: number[]) => vals.map((v, i) => `${i ? 'L' : 'M'}${x(centers[i]).toFixed(1)},${y(v).toFixed(1)}`).join('')
  const area = `${hHigh.map((v, i) => `${i ? 'L' : 'M'}${x(centers[i])},${y(v)}`).join('')}` +
    hLow.map((_, j) => { const i = n - 1 - j; return `L${x(centers[i])},${y(hLow[i])}` }).join('') + 'Z'
  const maxW = Math.max(...hiss.listening)
  const ticks = [10, 30, 100, 300, 1000, 3000].filter(t => t >= hiss.edges[0] && t <= hiss.edges[n])
  const tickStep = diff ? (ymax - ymin > 8 ? 2 : 1) : 10
  const yTicks: number[] = []
  for (let v = Math.ceil(ymin / tickStep) * tickStep; v <= ymax; v += tickStep) yTicks.push(v)
  const notes = Object.entries(hiss.bearing_pitches)

  return (
    <svg ref={ref} className="chart" viewBox={`0 0 ${width} ${height}`} width="100%" role="img"
      aria-label={title ?? 'How loud the current is at each pitch, compared with healthy bearings'}
      onMouseLeave={() => setHover(null)} style={{ display: 'block', background: '#fff' }}>
      {!compact && (
        <g className="grid">
          {yTicks.map(t => <line key={t} x1={m.l} x2={m.l + W} y1={y(t)} y2={y(t)} />)}
        </g>
      )}
      {showListen && !compact && hiss.listening.map((w, i) => (
        <rect key={i} x={x(hiss.edges[i])} width={x(hiss.edges[i + 1]) - x(hiss.edges[i])} y={m.t} height={H}
          fill="var(--listen)" opacity={(w / maxW) * 0.45} />
      ))}
      {showHealthy && <path d={area} fill="var(--ghost)" opacity={compact ? 0.45 : 0.55} />}
      {showHealthy && !compact && <path d={line(hMed)} fill="none" stroke="#8795a3" strokeWidth={1.5} strokeDasharray="4 4" />}
      {showNotes && notes.map(([name, hz]) => (
        <g key={name}>
          <line x1={x(hz)} x2={x(hz)} y1={m.t} y2={m.t + H} stroke="var(--check)" strokeWidth={compact ? 1 : 1.5} strokeDasharray="3 3" />
          {!compact && <text x={x(hz) + 4} y={m.t + 12} style={{ fill: 'var(--check)', fontWeight: 700 }}>{name}</text>}
        </g>
      ))}
      {!compact && (
        <g>
          <line x1={x(hiss.main_tone_hz)} x2={x(hiss.main_tone_hz)} y1={m.t + 18} y2={m.t + H} stroke="var(--ink-3)" strokeWidth={1} />
          <text x={x(hiss.main_tone_hz) + 4} y={m.t + H - 6}>main hum (left out)</text>
        </g>
      )}
      <path d={line(values)} fill="none" stroke={color} strokeWidth={compact ? 2 : 2.75} strokeLinejoin="round" />
      {!compact && values.map((v, i) => (
        <circle key={i} cx={x(centers[i])} cy={y(v)} r={hover === i ? 5.5 : 3} fill={color} />
      ))}
      {!compact && values.map((_, i) => (
        <rect key={i} x={x(hiss.edges[i])} width={x(hiss.edges[i + 1]) - x(hiss.edges[i])} y={m.t} height={H}
          fill="transparent" onMouseEnter={() => setHover(i)} />
      ))}
      {!compact && (
        <g className="axis">
          <line x1={m.l} x2={m.l + W} y1={m.t + H} y2={m.t + H} />
          {ticks.map(t => <text key={t} x={x(t)} y={m.t + H + 16} textAnchor="middle">{fmtHz(t)}</text>)}
          {yTicks.map(t => <text key={t} x={m.l - 8} y={y(t) + 4} textAnchor="end">{diff ? (t > 0 ? '+' : '') + t : Math.round(t)}</text>)}
          <text x={m.l} y={14} style={{ fontWeight: 700, fill: 'var(--ink)' }}>{diff ? 'louder than healthy ↑ (dB)' : 'louder ↑ (dB below the main hum)'}</text>
          <text x={m.l + W} y={m.t + H + 32} textAnchor="end">pitch →</text>
          {showListen && (
            <g>
              <text x={m.l} y={m.t + H + 50} style={{ fontWeight: 700, fill: 'var(--ink)' }}>where the detector listens</text>
              {hiss.listening.map((w, i) => (
                <rect key={i} x={x(hiss.edges[i]) + 0.5} width={Math.max(1, x(hiss.edges[i + 1]) - x(hiss.edges[i]) - 1)}
                  y={m.t + H + 56 + 14 - (w / maxW) * 14} height={(w / maxW) * 14} fill="#c9a227" />
              ))}
            </g>
          )}
        </g>
      )}
      {hover != null && !compact && (
        <g pointerEvents="none">
          <rect x={Math.min(x(centers[hover]) + 8, width - 346)} y={m.t + 18} width={338} height={58} rx={6} fill="var(--ink)" />
          <text x={Math.min(x(centers[hover]) + 18, width - 336)} y={m.t + 36} style={{ fill: '#fff', fontWeight: 700 }}>
            {fmtHz(hiss.edges[hover])} to {fmtHz(hiss.edges[hover + 1])}
          </text>
          <text x={Math.min(x(centers[hover]) + 18, width - 336)} y={m.t + 53} style={{ fill: '#dce6fb' }}>
            this motor {(values[hover] + base[hover] - hiss.healthy_median[hover]).toFixed(1)} dB vs healthy middle; healthy spread {(hiss.healthy_low[hover] - hiss.healthy_median[hover]).toFixed(1)} to +{(hiss.healthy_high[hover] - hiss.healthy_median[hover]).toFixed(1)}
          </text>
          <text x={Math.min(x(centers[hover]) + 18, width - 336)} y={m.t + 69} style={{ fill: '#f3d77a' }}>
            detector weight {(hiss.listening[hover] * 100).toFixed(1)}% of its attention
          </text>
        </g>
      )}
    </svg>
  )
})

// Turn the chart into a PNG so the AMD vision model can read exactly what the trainee sees (FR-022).
export async function svgToPng(svg: SVGSVGElement, scale = 1.5): Promise<string> {
  const clone = svg.cloneNode(true) as SVGSVGElement
  const vb = svg.viewBox.baseVal
  clone.setAttribute('width', String(vb.width))
  clone.setAttribute('height', String(vb.height))
  const css = getComputedStyle(document.documentElement)
  let text = new XMLSerializer().serializeToString(clone)
  text = text.replace(/var\(--([a-z0-9-]+)\)/g, (_, v) => css.getPropertyValue(`--${v}`).trim() || '#000')
  text = text.replace('<svg', '<svg font-family="Arial, sans-serif" font-size="12"')
  const img = new Image()
  img.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(text)
  await img.decode()
  const canvas = document.createElement('canvas')
  canvas.width = vb.width * scale
  canvas.height = vb.height * scale
  const ctx = canvas.getContext('2d')!
  ctx.fillStyle = '#fff'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height)
  return canvas.toDataURL('image/png')
}
