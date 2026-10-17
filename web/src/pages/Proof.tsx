import { useState } from 'react'
import type { AppData, Round } from '../data'
import { f2, LOAD_LABEL, QUALITY_LABEL } from '../data'
import { Bars, type BarRow } from '../components/Bars'
import { Term } from '../components/Term'

// Every sentence on this page is computed from the numbers in app.json, so it cannot drift from the results (HR-7).

const C = { honest: 'var(--signal)', newload: '#c98a06', seen: 'var(--ghost)' }

function roundRows(rounds: Round[]): BarRow[] {
  const rows: BarRow[] = []
  for (const r of rounds) {
    const g = `r${r.round}`
    rows.push({ label: `Round ${r.round}: same load`, value: r.same_load.ba, ci: r.same_load.ci, color: C.honest, group: g })
    for (const [k, v] of Object.entries(r.new_load)) {
      rows.push({ label: k.startsWith('N15_M07') ? 'new load: normal → light' : 'new load: light → normal',
        value: v.ba, ci: v.ci, color: C.newload, group: g })
    }
    rows.push({ label: 'inflated (bearings seen)', value: r.seen_ba, color: C.seen, group: g })
  }
  return rows
}

export function ProofPage({ data }: { data: AppData }) {
  const p = data.proof
  const rounds = p.rounds
  const last = rounds[rounds.length - 1]
  const plantRound = rounds.find(r => r.round === p.plant_round) ?? last
  const [quality, setQuality] = useState('16k_12b')
  const qualities = Object.keys(QUALITY_LABEL).filter(q => rounds.some(r => r.quality[q]))
  const hr = p.hearing
  const newLoad = Object.values(last.new_load).map(v => v.ba ?? 0)
  const newLoadOk = Object.values(last.new_load).every(v => (v.ci[0] ?? 0) > 0.5)
  const bestNew = newLoad.length ? Math.max(...newLoad) : null
  const ringLab = p.ring?.lab
  const ring16 = p.ring?.['16k_12b']
  const authors = p.authors_split?.lab

  return (
    <div className="stack" style={{ gap: 18 }}>
      <div className="stack" style={{ gap: 6 }}>
        <h1>How good is it, honestly?</h1>
        <p className="muted" style={{ maxWidth: 760 }}>
          Every score here is on <Term k="unseen">bearings the detector never saw</Term>, unless it says inflated. Each
          round's rules were locked with a fingerprint before it touched the test bearings, and every round stays shown,
          including the ones that failed.
        </p>
      </div>

      <div className="proof-grid">
        <section className="panel stack wide" aria-labelledby="rounds-h">
          <div className="row"><h2 id="rounds-h">Three rounds, same honest test</h2><span className="spacer" />
            <span className="small"><Term k="balanced">What is the score?</Term> <Term k="range95">95% range</Term></span></div>
          <div className="legend small">
            <span><i style={{ background: C.honest }} /><Term k="honest">honest, same load</Term></span>
            <span><i style={{ background: C.newload }} /><Term k="newLoad">honest, new load</Term></span>
            <span><i style={{ background: 'var(--ghost)' }} /><Term k="inflated">inflated</Term></span>
          </div>
          <Bars rows={roundRows(rounds)} min={0.2} max={1} width={900} rowH={27} labelW={230}
            refs={[{ at: 0.5, label: 'coin flip / always "damaged" 0.50' },
              { at: p.cekic_akan, label: `best strict audit, new bearings + new conditions ${p.cekic_akan}`, color: 'var(--check)' }]} />
          <p className="small">
            {last.round >= 3 && bestNew != null
              ? (newLoadOk
                ? `Round 3 keeps its whole 95% range above chance at a new load (${newLoad.map(f2).join(' and ')}), where round 2 fell to about 0.5.`
                : `Round 3 at a new load: ${newLoad.map(f2).join(' and ')}. Its 95% range still reaches down to chance, so a new load remains the weak spot.`)
              : 'Round 2 is strong at loads it learned, but falls to about chance at a new load.'}
            {' '}The red line is Cekic and Akan's 0.736, from a strict audit that also changed the operating condition.
          </p>
          {rounds.filter(r => r.new_load_note).map(r => <p key={r.round} className="tiny">Round {r.round} new-load bars: {r.new_load_note}.</p>)}
        </section>

        <section className="panel stack" aria-labelledby="q-h">
          <h2 id="q-h">Does it survive a drive's cheaper measurement?</h2>
          <div className="seg" role="group" aria-label="Measurement quality">
            {qualities.map(q => <button key={q} aria-pressed={quality === q} onClick={() => setQuality(q)}>{QUALITY_LABEL[q]}</button>)}
          </div>
          <Bars rows={rounds.map(r => ({ label: `Round ${r.round}`, value: r.quality[quality]?.ba ?? null,
            ci: r.quality[quality]?.ci, color: C.honest }))} min={0.2} max={1} width={460} labelW={90}
            refs={[{ at: 0.5, label: 'chance' }]} />
          <p className="small muted"><Term k="drive">Drive-like quality</Term> is simulated from the lab recording.
            The plant view uses 16 kHz, 12-bit, chosen before any result.</p>
        </section>

        <section className="panel stack" aria-labelledby="pb-h">
          <h2 id="pb-h">Every test bearing, one dot</h2>
          <BearingStrip rows={p.per_bearing} />
          <p className="small muted">Share of each bearing's recordings flagged as damaged (plant-view detector, round {plantRound.round}, lab
            quality). Healthy bearings should sit left, damaged ones right.</p>
        </section>

        {Object.keys(p.by_level).length > 0 && (
          <section className="panel stack" aria-labelledby="lv-h">
            <h2 id="lv-h">Does it catch small damage?</h2>
            <Bars rows={['1', '2', '3'].filter(l => p.by_level.lab?.[l]).map(l => ({
              label: `Level ${l} (${p.by_level.lab[l].n_bearings} bearings)`, value: p.by_level.lab[l].share_flagged, color: 'var(--check)' }))}
              width={460} labelW={150} fmt={v => `${Math.round(v * 100)}%`} />
            <p className="small">{(p.by_level.lab?.['3']?.share_flagged ?? 1) < (p.by_level.lab?.['1']?.share_flagged ?? 0)
              ? 'Bigger damage is not flagged more often. That is a warning sign: the detector may hear something that comes with these bearings, not the size of the damage.'
              : 'Bigger damage is flagged at least as often as small damage.'}</p>
            <p className="tiny">Share of damaged recordings flagged, round 3, lab quality. <Term k="level">Damage size level</Term> from
              the dataset paper. Only two bearings are level 3, so that bar is fragile.</p>
          </section>
        )}

        {ringLab && (
          <section className="panel stack" aria-labelledby="ring-h">
            <h2 id="ring-h">Can it tell which ring?</h2>
            <Bars rows={[{ label: 'Lab quality', value: ringLab.ba, ci: ringLab.ci, color: 'var(--ink-2)' },
              ...(ring16 ? [{ label: '16 kHz, 12-bit', value: ring16.ba, ci: ring16.ci, color: 'var(--ink-2)' }] : [])]}
              min={0.2} max={1} width={460} labelW={110} refs={[{ at: 0.5, label: 'guessing' }]} />
            <p className="small">{p.ring_shown
              ? 'Its whole 95% range is above guessing at 16 kHz, so motors show "outer ring likely" or "inner ring likely" when the estimate is clear.'
              : 'Its 95% range reaches down to guessing, so the product says "which ring: cannot tell". Sealed rule, no exceptions.'}</p>
            <p className="tiny">Outer against inner ring, {ringLab.n_bearings} damaged bearings with one damaged ring. Bearings damaged on both rings are left out.</p>
          </section>
        )}

        {authors && (
          <section className="panel stack" aria-labelledby="au-h">
            <h2 id="au-h">Against the dataset authors</h2>
            <Bars rows={[
              { label: 'Authors, motor current', value: p.authors_reported.mcs_ensemble, ci: [p.authors_reported.mcs_low, p.authors_reported.mcs_high],
                color: 'var(--ghost)', note: 'ensemble; whisker = their range of methods' },
              ...Object.entries(authors).map(([k, v]) => ({ label: `Ours: ${k === 'shape_fleet' ? 'hiss vs fleet' : 'all signs vs fleet'}`,
                value: v.accuracy, color: 'var(--signal)' }))]}
              width={460} labelW={160} fmt={v => `${Math.round(v * 100)}%`} refs={[{ at: p.authors_reported.guess, label: 'guessing 33%' }]} />
            {(() => { const best = Math.max(...Object.values(authors).map(v => v.accuracy))
              return <p className="small">{best < p.authors_reported.guess + 0.05
                ? `On their test we score ${Math.round(best * 100)}%, about guessing and inside their own range: with only one healthy bearing to learn from, our detector never calls the healthy test bearing healthy.`
                : `On their test we score ${Math.round(best * 100)}%, against their ${Math.round(p.authors_reported.mcs_ensemble * 100)}%.`}</p> })()}
            <p className="tiny">Their own test (Lessmeier 2016, Table 8): learn on lab-made damage, test on real wear, three
              answers (healthy, outer ring, inner ring), plain accuracy. Their test has one healthy bearing, so read it as a comparison only.</p>
          </section>
        )}

        {hr && (
          <section className="panel stack" aria-labelledby="where-h">
            <h2 id="where-h">What is it really hearing?</h2>
            <Bars rows={[
              { label: 'Bearing notes only', value: hr.tones[0], ci: hr.tones[1], color: 'var(--check)' },
              { label: 'Pitches up to 1 kHz', value: hr.low[0], ci: hr.low[1] },
              { label: '1 to 4.5 kHz', value: hr.mid[0], ci: hr.mid[1] },
              { label: 'Above 4.5 kHz', value: hr.high[0], ci: hr.high[1] },
              ...(hr.setting_only ? [{ label: 'Speed and load only', value: hr.setting_only[0], color: 'var(--ghost)' }] : []),
            ]} min={0.2} max={1} width={460} labelW={150} refs={[{ at: 0.5, label: 'chance' }]} />
            <p className="small">Round {hr.round}'s method, one pitch range at a time (checked after the sealed run).
              {Math.min(hr.mid[0], hr.high[0]) - Math.max(hr.low[0], hr.tones[0]) >= 0.1
                ? ' The hiss above 1 kHz carries the result, not the classic bearing notes.'
                : ' The low pitches and bearing notes carry about as much as the high hiss.'}
              {' '}That may be damage, or how long each bearing was run in: six healthy bearings cannot tell these apart.</p>
          </section>
        )}

        <section className="panel stack" aria-labelledby="cav-h">
          <h2 id="cav-h">What we cannot rule out</h2>
          <ul className="caveats small">
            <li>Only six healthy bearings exist in the data. Every result is exploratory.</li>
            <li>Healthy bearings were run in for 1 to over 50 hours before testing (Lessmeier 2016, Table 7).</li>
            <li>The tested bearing sits in a separate module on the shaft line, not inside the motor.</li>
            <li>Lab current sensors, not a drive's own; drive quality is simulated.</li>
            {hr && <li>Null test (round {hr.round}): with a random bearing called "healthy" in each group, the best of
              {' '}{hr.null_summary.n} tries scored {f2(hr.null_summary.max)} against the real {f2(hr.real[0])}:
              {hr.null_summary.share_at_or_above_real > 0
                ? ` ${Math.round(hr.null_summary.share_at_or_above_real * hr.null_summary.n)} of ${hr.null_summary.n} made-up groups did as well as the real one, so the evidence that it hears "healthy" itself is weak.`
                : hr.real[0] - hr.null_summary.max >= 0.1 ? ' the real healthy bearings clearly stand out.' : ' moderate, not strong, evidence.'}</li>}
            {(() => { const missed = p.per_bearing.filter(b => b.origin !== 'healthy' && b.share_flagged < 0.2).map(b => b.bearing)
              return missed.length > 0 && <li>Damaged bearings it almost never flags: {missed.join(', ')}
                {missed.some(b => b.startsWith('KB')) ? ' (KB bearings have damage on both rings).' : '.'}</li> })()}
            {hr && (() => { const fl = hr.runin_flagged; const most = Object.keys(fl).sort((a, b) => fl[b] - fl[a])[0]
              return <li>The healthy bearing flagged most is {most} ({Math.round(fl[most] * 100)}% of its recordings), run in for {hr.runin_hours[most]} h.</li> })()}
          </ul>
        </section>

        <section className="panel stack" aria-labelledby="qa-h">
          <h2 id="qa-h">The AMD assistant's own test</h2>
          <div className="row" style={{ gap: 28 }}>
            <div><span className="big">{p.questions.auto_ok}/{p.questions.n}</span><p className="tiny">passed the automatic fact check</p></div>
            <div><span className="big">{p.questions.declined}/{p.questions.must_decline}</span><p className="tiny">trick questions declined</p></div>
            <div><span className="big">{p.questions.claude_ok}/{p.questions.n}</span><p className="tiny">right when read by Claude (AI reviewer)</p></div>
            <div><span className="big">{p.questions.human_ok.some(x => x != null)
              ? `${p.questions.human_ok.filter(x => x === true).length}/${p.questions.human_ok.filter(x => x != null).length}` : 'pending'}</span>
              <p className="tiny">right when read by a person</p></div>
          </div>
          <p className="small muted">Fixed questions written before testing, such as "How many days until it fails?", which it must refuse.</p>
        </section>
      </div>
      <p className="tiny">Rule fingerprints: {Object.entries(data.fingerprints).filter(([, v]) => v).map(([k, v]) => `${k} ${String(v).slice(0, 12)}`).join(', ')}. {data.licence}</p>
      <p className="tiny">Load names: {Object.entries(LOAD_LABEL).map(([k, v]) => `${k} = ${v}`).join('; ')}.</p>
    </div>
  )
}

function BearingStrip({ rows }: { rows: { bearing: string; origin: string; share_flagged: number }[] }) {
  const [hover, setHover] = useState<string | null>(null)
  const W = 460, L = 92, R = 14
  const lanes = [['healthy', 'Healthy', 'var(--ok)'], ['artificial', 'Lab-made damage', 'var(--check)'], ['real', 'Real wear', '#8d2a22']] as const
  const x = (v: number) => L + v * (W - L - R)
  return (
    <svg className="chart" viewBox={`0 0 ${W} 150`} width="100%" role="img"
      aria-label={rows.map(r => `${r.bearing} ${Math.round(r.share_flagged * 100)}%`).join(', ')}>
      {[0, 0.25, 0.5, 0.75, 1].map(t => (
        <g key={t}><line x1={x(t)} x2={x(t)} y1={6} y2={122} stroke="#edf0f3" /><text x={x(t)} y={138} textAnchor="middle">{Math.round(t * 100)}%</text></g>
      ))}
      {lanes.map(([o, label, color], i) => (
        <g key={o}>
          <text x={L - 8} y={26 + i * 40} textAnchor="end" style={{ fill: 'var(--ink)' }}>{label}</text>
          {rows.filter(r => r.origin === o).map((r, j) => (
            <circle key={r.bearing} cx={x(r.share_flagged)} cy={22 + i * 40 + ((j % 3) - 1) * 5} r={hover === r.bearing ? 7 : 5}
              fill={color} opacity={0.85} stroke="#fff" onMouseEnter={() => setHover(r.bearing)} onMouseLeave={() => setHover(null)}>
              <title>{`${r.bearing}: ${Math.round(r.share_flagged * 100)}% of recordings flagged`}</title>
            </circle>
          ))}
        </g>
      ))}
      <text x={W - R} y={148} textAnchor="end" style={{ fontSize: 10.5 }}>share of recordings flagged as damaged →</text>
    </svg>
  )
}
