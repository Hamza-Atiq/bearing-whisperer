// A horizontal bar chart with 95% whiskers and labelled reference lines. Values are scores from app.json.

export interface BarRow {
  label: string
  value: number | null
  ci?: (number | null)[]
  color?: string
  note?: string
  group?: string
}

export interface RefLine { at: number; label: string; color?: string }

export function Bars({ rows, min = 0, max = 1, refs = [], width = 520, rowH = 30, labelW = 190, fmt }: {
  rows: BarRow[]; min?: number; max?: number; refs?: RefLine[]; width?: number; rowH?: number; labelW?: number;
  fmt?: (v: number) => string
}) {
  const f = fmt ?? ((v: number) => v.toFixed(2))
  const top = 24, right = 46
  const groups = rows.reduce((n, r, i) => n + (i > 0 && r.group && r.group !== rows[i - 1].group ? 1 : 0), 0)
  const h = top + rows.length * rowH + groups * 12 + 22
  const x = (v: number) => labelW + ((v - min) / (max - min)) * (width - labelW - right)
  let yAcc = top
  const ys = rows.map((r, i) => {
    if (i > 0 && r.group && r.group !== rows[i - 1].group) yAcc += 12
    const y = yAcc
    yAcc += rowH
    return y
  })
  const ticks = Array.from({ length: 6 }, (_, i) => min + ((max - min) * i) / 5)
  return (
    <svg className="chart" viewBox={`0 0 ${width} ${h}`} width="100%" role="img"
      aria-label={rows.map(r => `${r.label}: ${r.value == null ? 'n/a' : f(r.value)}`).join('; ')}>
      {ticks.map(t => (
        <g key={t}>
          <line x1={x(t)} x2={x(t)} y1={top - 4} y2={h - 18} stroke="#edf0f3" />
          <text x={x(t)} y={h - 4} textAnchor="middle">{f(t)}</text>
        </g>
      ))}
      {refs.map((r, i) => (
        <g key={r.label}>
          <line x1={x(r.at)} x2={x(r.at)} y1={top - 6} y2={h - 18} stroke={r.color ?? 'var(--ink-2)'} strokeDasharray="4 3" strokeWidth={1.5} />
          <text x={x(r.at) > width * 0.6 ? x(r.at) - 3 : x(r.at) + 3} y={10 + (i % 2) * 11}
            textAnchor={x(r.at) > width * 0.6 ? 'end' : 'start'}
            style={{ fill: r.color ?? 'var(--ink-2)', fontWeight: 700, fontSize: 11 }}>{r.label}</text>
        </g>
      ))}
      {rows.map((r, i) => {
        const y = ys[i]
        const bh = rowH * 0.56
        return (
          <g key={r.label + i}>
            <text x={labelW - 8} y={y + bh / 2 + 4} textAnchor="end" style={{ fill: 'var(--ink)' }}>{r.label}</text>
            {r.value != null && (
              <>
                <rect x={x(min)} y={y} width={Math.max(0, x(r.value) - x(min))} height={bh} rx={2} fill={r.color ?? 'var(--signal)'} />
                {r.ci && r.ci[0] != null && r.ci[1] != null && (
                  <g stroke="var(--ink)" strokeWidth={1.5}>
                    <line x1={x(r.ci[0])} x2={x(r.ci[1])} y1={y + bh / 2} y2={y + bh / 2} />
                    <line x1={x(r.ci[0])} x2={x(r.ci[0])} y1={y + 3} y2={y + bh - 3} />
                    <line x1={x(r.ci[1])} x2={x(r.ci[1])} y1={y + 3} y2={y + bh - 3} />
                  </g>
                )}
                <text x={Math.max(x(r.value), r.ci?.[1] != null ? x(r.ci[1] as number) : 0) + 5} y={y + bh / 2 + 4}
                  style={{ fill: 'var(--ink)', fontWeight: 700 }}>{f(r.value)}</text>
              </>
            )}
            {r.value == null && <text x={x(min) + 4} y={y + bh / 2 + 4}>not run</text>}
            {r.note && <text x={labelW - 8} y={y + bh + 9} textAnchor="end" style={{ fontSize: 10.5, fill: 'var(--ink-3)' }}>{r.note}</text>}
          </g>
        )
      })}
    </svg>
  )
}
