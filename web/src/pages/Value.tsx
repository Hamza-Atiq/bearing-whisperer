import { useState } from 'react'
import type { AppData } from '../data'
import { Term } from '../components/Term'

// FR-019: an ILLUSTRATIVE yearly value. Same formula as bearing/business.py; the rates are measured, the rest is assumed.
function value(n: number, fault: number, c: number, fa: number, ho: number, brk: number, chk: number, rounds: number) {
  const faulty = n * fault, healthy = n - faulty, caught = faulty * c
  const wasted = healthy * (fa + ho) * rounds
  return { caught, wasted, net: caught * (brk - chk) - wasted * chk, allCaught: faulty, allWasted: healthy * rounds,
    allNet: faulty * (brk - chk) - healthy * rounds * chk }
}

const usd = (x: number) => `${x < 0 ? '−' : ''}$${Math.abs(Math.round(x)).toLocaleString('en-US')}`

export function ValuePage({ data }: { data: AppData }) {
  const p = data.proof.plant
  const [n, setN] = useState(100)
  const [fault, setFault] = useState(0.05)
  const [brk, setBrk] = useState(20000)
  const [chk, setChk] = useState(150)
  const [rounds, setRounds] = useState(4)
  const v = value(n, fault, p.catch_rate, p.false_alarm_rate, p.handoff_healthy, brk, chk, rounds)
  const max = Math.max(Math.abs(v.net), Math.abs(v.allNet), 1)
  const slider = (id: string, label: string, val: number, set: (x: number) => void, min: number, max: number, step: number, show: string) => (
    <div className="field">
      <label htmlFor={id}>{label}</label>
      <span className="big" style={{ fontSize: 24 }}>{show}</span>
      <input id={id} type="range" min={min} max={max} step={step} value={val} onChange={e => set(+e.target.value)} />
    </div>
  )
  const bar = (label: string, x: number, color: string, sub: string) => (
    <div className="stack" style={{ gap: 4 }}>
      <div className="row"><b>{label}</b><span className="spacer" /><span className="big" style={{ fontSize: 26 }}>{usd(x)}</span></div>
      <div style={{ height: 22, background: '#edf0f3', borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${(Math.max(0, x) / max) * 100}%`, height: '100%', background: color, transition: 'width .3s' }} />
      </div>
      <span className="small muted">{sub}</span>
    </div>
  )

  return (
    <div className="value">
      <section className="panel stack" aria-label="Assumptions">
        <h1 style={{ fontSize: 28 }}>What could it be worth?</h1>
        <p className="small muted">Move the sliders: these are assumptions about your plant, not measurements.</p>
        {slider('n', 'Motors run by drives', n, setN, 10, 500, 10, String(n))}
        {slider('f', 'Share with a bearing fault each year', fault, setFault, 0.01, 0.2, 0.01, `${Math.round(fault * 100)}%`)}
        {slider('b', 'Cost of one surprise breakdown', brk, setBrk, 1000, 200000, 1000, usd(brk))}
        {slider('c', 'Cost of one check visit', chk, setChk, 20, 1000, 10, usd(chk))}
        {slider('r', 'Screening rounds per year', rounds, setRounds, 1, 12, 1, String(rounds))}
      </section>
      <section className="stack">
        <div className="panel stack">
          <p className="small" style={{ color: '#9a6a00', fontWeight: 700 }}>Illustrative, not a measured saving.</p>
          {bar('Follow the detector', v.net, 'var(--signal)',
            `Catches ${v.caught.toFixed(1)} breakdowns a year; ${Math.round(v.wasted)} visits to healthy motors.`)}
          {bar('A person checks every motor every round', v.allNet, 'var(--ghost)',
            `Catches all ${v.allCaught.toFixed(1)} (assumes a manual check finds every fault); ${Math.round(v.allWasted)} visits to healthy motors.`)}
          <p>{v.net > v.allNet
            ? `Here the detector is worth ${usd(v.net - v.allNet)} more a year, because it skips most visits to healthy motors.`
            : `Here checking every motor is worth ${usd(v.allNet - v.net)} more a year: the detector's misses cost more than the visits it saves.`}</p>
        </div>
        <div className="panel stack">
          <h3>The measured part</h3>
          <p className="small">On lab bearings it never saw, per motor, the plant view caught <b>{Math.round(p.catch_rate * 100)}%</b> of
            {' '}{p.n_damaged} damaged motors, flagged <b>{Math.round(p.false_alarm_rate * 100)}%</b> of {p.n_healthy} healthy motors,
            and handed <b>{Math.round(p.handoff_healthy * 100)}%</b> of healthy motors to a person. Only {p.n_healthy} healthy
            motors exist in the data, so these rates are rough.</p>
          {data.proof.plant_round < 3 && <p className="small" style={{ color: '#9a6a00' }}>These rates held only at loads the
            detector learned. At a <Term k="newLoad">new load</Term> it fell to about chance (see Proof).</p>}
        </div>
      </section>
    </div>
  )
}
