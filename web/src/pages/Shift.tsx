import { Fragment, useState } from 'react'
import type { AppData, Status } from '../data'
import { num } from '../data'
import { StatusPill } from './Plant'
import { Term } from '../components/Term'
import { isAmd, post, type PlanReply } from '../api'

const TOOL_WORDS: Record<string, string> = {
  get_fleet: 'Looked at the fleet list', get_motor: 'Read the facts for', get_motors: 'Read the facts for', get_track_record: 'Checked how good the detector is',
}

export function ShiftPage({ data, online }: { data: AppData; online: boolean }) {
  const [minutes, setMinutes] = useState(120)
  const [perCheck, setPerCheck] = useState(20)
  const [request, setRequest] = useState('')
  const [skip, setSkip] = useState<string[]>([])
  const [plan, setPlan] = useState<PlanReply | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState<string | null>(null)
  const candidates = data.motors.filter(m => m.plant_word !== 'healthy').sort((a, b) => num(a) - num(b))
  const fits = Math.floor(minutes / perCheck)

  const run = async () => {
    setBusy(true); setError(''); setPlan(null)
    try {
      setPlan(await post<PlanReply>('plan', { minutes, per_check: perCheck, request, skip }))
    } catch (e) { setError((e as Error).message) } finally { setBusy(false) }
  }

  return (
    <div className="shift">
      <section className="panel stack" aria-labelledby="shift-h" style={{ position: 'sticky', top: 72 }}>
        <h1 id="shift-h" style={{ fontSize: 28 }}>Plan my shift</h1>
        <div className="field">
          <label htmlFor="mins">Time I have</label>
          <span className="big">{minutes >= 60 ? `${Math.floor(minutes / 60)} h ${minutes % 60 ? `${minutes % 60} min` : ''}` : `${minutes} min`}</span>
          <input id="mins" type="range" min={20} max={480} step={10} value={minutes} onChange={e => setMinutes(+e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="per">One check takes about</label>
          <span className="big">{perCheck} min</span>
          <input id="per" type="range" min={10} max={60} step={5} value={perCheck} onChange={e => setPerCheck(+e.target.value)} />
          <span className="tiny">Room for {fits} visit{fits === 1 ? '' : 's'}.</span>
        </div>
        <button className="btn amd" onClick={run} disabled={busy}>{busy ? 'Planning…' : 'Plan with the AMD assistant'}</button>
        {!online && <p className="tiny">The assistant is offline, so the fixed rule will plan instead.</p>}
        <details>
          <summary className="small"><b>More options</b> (skip motors, add a request)</summary>
          <div className="stack" style={{ marginTop: 10 }}>
        <div className="field">
          <label>Skip these motors (tap to skip)</label>
          <div className="row" style={{ gap: 5 }}>
            {candidates.map(m => {
              const on = skip.includes(m.motor_name)
              return <button key={m.motor_name} className="chip" aria-pressed={on} style={{ padding: '3px 9px', fontSize: 13 }}
                onClick={() => setSkip(s => (on ? s.filter(x => x !== m.motor_name) : [...s, m.motor_name]))}>{num(m)}</button>
            })}
          </div>
        </div>
        <div className="field">
          <label htmlFor="req">Anything else? (optional)</label>
          <textarea id="req" value={request} maxLength={300} onChange={e => setRequest(e.target.value)}
            placeholder="For example: I am new, keep reasons simple." />
        </div>
          </div>
        </details>
      </section>

      <section className="stack" aria-live="polite">
        {!plan && !busy && !error && (
          <div className="panel stack">
            <h2>How it plans</h2>
            <p className="muted">The <Term k="amd">AMD assistant</Term> is not handed the answer. It asks the plant for
              what it needs (the fleet list, each motor's facts, the track record), decides the order, and writes a reason
              for each stop. Then our checker makes sure every motor, status and number came from those answers. If not,
              the plan is thrown away and a fixed rule plans instead, and the page says so.</p>
            <ol className="small" style={{ margin: 0, paddingLeft: 20 }}>
              <li>Check-bearing motors first, most sure first.</li>
              <li>Then ask-a-person motors.</li>
              <li>Healthy motors are never planned unless you ask.</li>
            </ol>
          </div>
        )}
        {busy && (
          <div className="panel stack">
            <span className="row small muted" style={{ gap: 8 }}><span className="thinking"><i /><i /><i /></span>
              Gemma on AMD Token Factory is calling the plant's tools. This takes about 10 to 30 seconds.</span>
          </div>
        )}
        {error && <p className="panel" role="alert">Could not plan: {error}</p>}
        {plan && (
          <>
            <div className="panel stack">
              <div className="row">
                <h2>{plan.visits.length} visit{plan.visits.length === 1 ? '' : 's'}</h2>
                <span className="spacer" />
                {isAmd(plan.source)
                  ? <span className="source"><i className="dot on" /> Planned by <b>{plan.source}</b> on AMD GPUs, fact-checked</span>
                  : <span className="source"><i className="dot" /> Planned by the fixed rule (assistant offline or its plan failed the check)</span>}
              </div>
              <p>{plan.summary}</p>
              {plan.steps.length > 0 && (
                <details open>
                  <summary className="small"><b>What the assistant did ({plan.steps.length} tool calls)</b></summary>
                  <ol className="trace" style={{ marginTop: 8 }}>
                    {plan.steps.map((s, i) => (
                      <li key={i} style={{ animationDelay: `${i * 0.08}s` }}>
                        <span>{TOOL_WORDS[s.tool] ?? s.tool} {s.tool === 'get_motor' ? <b>{String(s.args.motor)}</b> : s.tool === 'get_motors' ? <b>{(s.args.motors as string[] ?? []).join(', ')}</b> : ''}
                          {' '}<code className="tiny">{s.tool}</code></span>
                      </li>
                    ))}
                  </ol>
                </details>
              )}
              {plan.problems.length > 0 && (
                <details>
                  <summary className="small">Why the assistant's plan was not used</summary>
                  <ul className="small">{plan.problems.map((p, i) => <li key={i}>{p}</li>)}</ul>
                </details>
              )}
            </div>
            <div className="panel">
              {plan.visits.map((v, i) => (
                <div key={v.motor}>
                  <div className="visit">
                    <span className="k">{i + 1}</span>
                    <div className="stack" style={{ gap: 3 }}>
                      <div className="row" style={{ gap: 8 }}>
                        <a href={`#/motor/${num({ motor_name: v.motor } as never)}`}><b>{v.motor}</b></a>
                        <StatusPill s={v.status as Status} />
                        <span className="tiny">how sure: {v.how_sure}</span>
                      </div>
                      <span className="small muted">{v.reason}</span>
                    </div>
                    <button className="chip" aria-expanded={open === v.motor} onClick={() => setOpen(o => (o === v.motor ? null : v.motor))}>
                      Work order
                    </button>
                  </div>
                  {open === v.motor && (
                    <dl className="wo" style={{ margin: '0 0 12px 52px' }}>
                      {Object.entries(v.work_order).map(([k, val]) => <Fragment key={k}><dt>{k.replace('_', ' ')}</dt><dd>{val}</dd></Fragment>)}
                    </dl>
                  )}
                </div>
              ))}
              {plan.visits.length === 0 && <p className="muted">Nothing to visit in this time.</p>}
            </div>
          </>
        )}
      </section>
    </div>
  )
}
