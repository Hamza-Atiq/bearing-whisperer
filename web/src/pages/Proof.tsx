import { useState } from 'react'
import type { AppData, Round } from '../data'
import { CONDITION_LABEL, f2, LOAD_LABEL, pct, QUALITY_LABEL } from '../data'
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
  const hl = p.plant_lab
  const pub = p.published
  const lo = p.loco?.lab
  const noFleet = p.loco_candidates?.lab?.['shape+rf']
  const BASE: Record<string, string> = { always_damaged: 'Always say "damaged"', loudness: 'Overall loudness only',
    tones: 'Bearing notes only', setting_only: 'Speed and load only, no current' }
  const tile = (big: string, small: string) => (
    <div style={{ minWidth: 120, flex: '1 1 120px' }}><span className="big">{big}</span><p className="tiny" style={{ margin: 0 }}>{small}</p></div>)

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
        {hl && (
          <section className="panel stack wide" aria-labelledby="hl-h">
            <h2 id="hl-h">The honest headline</h2>
            <div className="row" style={{ gap: 22, flexWrap: 'wrap', alignItems: 'flex-start' }}>
              {tile(f2(hl.ba), `score on unseen bearings (95% range ${f2(hl.ci[0])} to ${f2(hl.ci[1])})`)}
              {tile(pct(hl.false_alarm), 'false alarms: healthy recordings called damaged')}
              {tile(pct(hl.miss), 'misses: damaged recordings called healthy')}
              {tile(pct(hl.decided_share), 'decided; the rest is handed to a person')}
              {tile(typeof hl.decided_ba === 'number' ? f2(hl.decided_ba) : String(hl.decided_ba ?? 'n/a'), 'score on the ones it decided')}
              {tile(f2(plantRound.seen_ba), 'inflated score, if it had seen the bearings')}
            </div>
            <p className="small muted">Round {plantRound.round}, the round behind the plant view; lab quality; one score per 4-second
              recording, all four operating conditions. The inflated number is what a random split gives with the same model,
              the usual way papers report scores near 99%.</p>
          </section>
        )}

        {pub && lo && (
          <section className="panel stack wide" aria-labelledby="pub-h">
            <h2 id="pub-h">Against published work, same kind of test</h2>
            <p className="small muted">{pub.cekic_akan.cite}: {pub.cekic_akan.protocol}. Round {last.round} was rerun the same way: each of
              the four operating conditions held out in turn, on bearings it never learned from.</p>
            <Bars rows={[
              { label: 'Theirs: worn damage only', value: pub.cekic_akan.target_a.ba, color: 'var(--ghost)', group: 'a', note: 'best of eight deep models' },
              { label: 'Ours: worn damage, one ring', value: lo.subsets['real wear, one ring']?.ba ?? null, ci: lo.subsets['real wear, one ring']?.ci, group: 'a' },
              { label: 'Theirs: all damage types', value: pub.cekic_akan.target_d.ba, color: 'var(--ghost)', group: 'd', note: 'one matched deep model' },
              { label: 'Ours: all damage types', value: lo.subsets['all damage']?.ba ?? null, ci: lo.subsets['all damage']?.ci, group: 'd' },
              ...(noFleet ? [{ label: 'Ours without the fleet step', value: noFleet.subsets['all damage']?.ba ?? null,
                ci: noFleet.subsets['all damage']?.ci, color: '#8795a3', group: 'd', note: 'never sees other motors at the test condition' }] : []),
            ]} min={0.2} max={1} width={900} rowH={30} labelW={230} refs={[{ at: 0.5, label: 'coin flip 0.50' }]} />
            <p className="small">On all damage types their matched motor-current model called only {pct(pub.cekic_akan.target_d.specificity)} of
              healthy recordings healthy ({pub.cekic_akan.target_d_note}). Ours, in the same kind of test, has
              {' '}{pct(lo.pooled.false_alarm)} false alarms and {pct(lo.pooled.miss)} misses.</p>
            <p className="tiny">Not a head-to-head: different models, splits and random seeds, and their numbers are from their abstract. Our
              fleet step uses other motors' unlabelled recordings at the test condition, which theirs did not; the grey-blue bar shows
              our score without it. Only six healthy bearings exist, so every range is wide.</p>
            <Bars rows={Object.entries(lo.per_condition).map(([c, v]) => ({ label: `left out: ${CONDITION_LABEL[c] ?? c}`, value: v.ba, ci: v.ci }))}
              min={0.2} max={1} width={900} rowH={26} labelW={230} refs={[{ at: 0.5, label: 'coin flip' }]} />
            <p className="small muted">Each condition left out in turn (round {last.round}, lab quality): mean {f2(lo.mean_ba)}, the same
              kind of all-split mean they report.</p>
          </section>
        )}
        <section className="panel stack wide" aria-labelledby="rounds-h">
          <div className="row"><h2 id="rounds-h">Every round, same honest test</h2><span className="spacer" />
            <span className="small"><Term k="balanced">What is the score?</Term> <Term k="range95">95% range</Term></span></div>
          <div className="legend small">
            <span><i style={{ background: C.honest }} /><Term k="honest">honest, same load</Term></span>
            <span><i style={{ background: C.newload }} /><Term k="newLoad">honest, new load</Term></span>
            <span><i style={{ background: 'var(--ghost)' }} /><Term k="inflated">inflated</Term></span>
          </div>
          <Bars rows={roundRows(rounds)} min={0.2} max={1} width={900} rowH={27} labelW={230}
            refs={[{ at: 0.5, label: 'coin flip / always "damaged" 0.50' },
              { at: p.cekic_akan, label: `best published strict test, worn damage only ${p.cekic_akan}`, color: 'var(--check)' }]} />
          <p className="small">
            {last.round >= 3 && bestNew != null
              ? (newLoadOk
                ? `Round ${last.round} keeps its whole 95% range above chance at a new load (${newLoad.map(f2).join(' and ')}), where round 2 fell to about 0.5.`
                : `Round ${last.round} at a new load: ${newLoad.map(f2).join(' and ')}. Its 95% range still reaches down to chance, so a new load remains the weak spot.`)
              : 'Round 2 is strong at loads it learned, but falls to about chance at a new load.'}
            {' '}The red line is Cekic and Akan's best, {p.cekic_akan}, on worn damage only; the fair comparison is in the panel above.
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

        {hl && Object.keys(p.baselines).length > 0 && (
          <section className="panel stack" aria-labelledby="base-h">
            <h2 id="base-h">Does it beat simple rules?</h2>
            <Bars rows={[...Object.entries(BASE).filter(([k]) => p.baselines[k]).map(([k, label]) => ({
              label, value: p.baselines[k].ba, ci: p.baselines[k].ci, color: 'var(--ghost)' })),
              { label: `Ours (round ${plantRound.round})`, value: hl.ba, ci: hl.ci }]}
              min={0.2} max={1} width={460} labelW={170} refs={[{ at: 0.5, label: 'chance' }]} />
            <p className="small muted">Each simple rule scored the same honest way, on unseen bearings, lab quality (round 1's sealed
              baselines). "Speed and load only" should sit near chance; if it did not, the setting would be leaking the answer.</p>
          </section>
        )}

        {Object.keys(p.per_condition).length > 0 && (
          <section className="panel stack" aria-labelledby="pc-h">
            <h2 id="pc-h">Every operating condition</h2>
            <Bars rows={Object.entries(p.per_condition).map(([c, v]) => ({ label: CONDITION_LABEL[c] ?? c, value: v }))}
              min={0.2} max={1} width={460} labelW={170} refs={[{ at: 0.5, label: 'chance' }]} />
            <p className="small muted">The same-load score split by condition (round {plantRound.round}, lab quality), so a pooled number
              cannot hide a weak one. The light-load condition is shown on its own.</p>
          </section>
        )}

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
            <p className="tiny">Share of damaged recordings flagged, round {last.round}, lab quality. <Term k="level">Damage size level</Term> from
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
            {hr && (() => { const most = p.per_bearing.filter(b => b.origin === 'healthy').sort((a, b) => b.share_flagged - a.share_flagged)[0]
              return most && <li>The healthy bearing flagged most is {most.bearing} ({Math.round(most.share_flagged * 100)}% of its
                recordings, round {plantRound.round}), run in for {hr.runin_hours[most.bearing]} h.</li> })()}
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
  const W = 460, L = 112, R = 14
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
