import { useEffect, useRef, useState } from 'react'
import type { AppData } from '../data'
import { num, sortMotors } from '../data'
import { HissChart, svgToPng } from '../components/HissChart'
import { Gauge } from '../components/Gauge'
import { VerdictBar } from '../components/VerdictBar'
import { Term } from '../components/Term'
import { StatusPill } from './Plant'
import { isAmd, post, type AnswerReply, type ExplainReply, type NoteReply } from '../api'

const QUESTIONS = ['Why do you think so?', 'What should I check?', "What does 'how sure' mean?",
  'How many days until it fails?']

const ORIGIN: Record<string, string> = { healthy: 'a healthy bearing', artificial: 'a bearing with lab-made damage',
  real: 'a bearing with real wear damage' }

// The pitch slices named in the detector's evidence ("more electrical buzz between 4,515 and 5,765 Hz ...").
function signsOf(evidence: string[], edges: number[]) {
  const out: { i: number; more: boolean }[] = []
  for (const e of evidence) {
    const r = /between ([\d,]+) and ([\d,]+) Hz/.exec(e)
    if (!r) continue
    const lo = Number(r[1].replace(/,/g, ''))
    const i = edges.findIndex((x, k) => k < edges.length - 1 && Math.round(x) === lo)
    if (i >= 0) out.push({ i, more: e.startsWith('more') })
  }
  return out
}

function Thinking({ label }: { label: string }) {
  return <span className="row small muted" style={{ gap: 8 }}><span className="thinking"><i /><i /><i /></span>{label}</span>
}

function Source({ source }: { source: string }) {
  return isAmd(source)
    ? <span className="source"><i className="dot on" /> Written by <b>{source}</b> on AMD GPUs (AMD Token Factory), fact-checked</span>
    : <span className="source"><i className="dot" /> Fixed template: the AMD assistant was offline or its answer failed the fact check</span>
}

export function MotorPage({ data, id, online }: { data: AppData; id?: string; online: boolean }) {
  const ordered = sortMotors(data.motors)
  const m = data.motors.find(x => num(x) === Number(id)) ?? ordered[0]
  const idx = ordered.indexOf(m)
  const prev = ordered[(idx - 1 + ordered.length) % ordered.length]
  const next = ordered[(idx + 1) % ordered.length]
  const [show, setShow] = useState({ healthy: true, notes: true, listen: true, diff: true, signs: true })
  const [note, setNote] = useState<NoteReply | null>(null)
  const [tab, setTab] = useState<'amd' | 'template'>('amd')
  const [explain, setExplain] = useState<ExplainReply | null>(null)
  const [explaining, setExplaining] = useState(false)
  const [q, setQ] = useState('')
  const [answers, setAnswers] = useState<{ q: string; a?: AnswerReply; err?: string }[]>([])
  const [approved, setApproved] = useState(false)
  const chart = useRef<SVGSVGElement>(null)
  const percentOk = !!(data.proof.plant as { percent_ok?: boolean }).percent_ok

  useEffect(() => {
    setNote(null); setExplain(null); setAnswers([]); setApproved(false); setTab('amd')
    let live = true
    post<NoteReply>('note', { motor: m.motor_name }).then(r => live && setNote(r))
      .catch(() => live && setNote({ text: '', source: 'template', template: '', problems: ['offline'] }))
    return () => { live = false }
  }, [m.motor_name])

  const ask = async (question: string) => {
    if (!question.trim()) return
    setQ('')
    setAnswers(a => [...a, { q: question }])
    try {
      const a = await post<AnswerReply>('ask', { motor: m.motor_name, question })
      setAnswers(list => list.map(x => (x.q === question && !x.a ? { ...x, a } : x)))
    } catch (e) {
      setAnswers(list => list.map(x => (x.q === question && !x.a ? { ...x, err: String((e as Error).message) } : x)))
    }
  }

  const runExplain = async () => {
    if (!chart.current) return
    setExplaining(true)
    try {
      const image = await svgToPng(chart.current, 0.7)   // about 600 px wide: larger pictures ran AMD's vision model out of memory
      setExplain(await post<ExplainReply>('explain', { motor: m.motor_name, image, diff: show.diff }))
    } catch (e) {
      setExplain({ text: `Could not reach the assistant: ${(e as Error).message}`, source: 'template', problems: [] })
    } finally { setExplaining(false) }
  }

  const values = data.hiss.per_bearing[m.bearing]
  const outside = values ? values.filter((v, i) => v > data.hiss.healthy_high[i] + 1 || v < data.hiss.healthy_low[i] - 1).length : 0
  const signs = signsOf(m.evidence, data.hiss.edges)
  const toggle = (k: keyof typeof show) => setShow(s => ({ ...s, [k]: !s[k] }))

  return (
    <div className="stack" style={{ gap: 18 }}>
      <div className="motor-head">
        <a className="btn ghost" href={`#/motor/${num(prev)}`} aria-label={`Previous: ${prev.motor_name}`}>‹</a>
        <h1>{m.motor_name}</h1>
        <StatusPill s={m.plant_word} />
        <span className="small"><Term k="howSure">How sure</Term>: <b>{m.how_sure}</b></span>
        {m.urgency && <span className="small">Act: <b>{m.urgency}</b></span>}
        {m.ring && <span className="small">Which ring: <b>{m.ring}</b></span>}
        <span className="spacer" />
        <span className="tiny">{idx + 1} of {ordered.length} in check order</span>
        <a className="btn ghost" href={`#/motor/${num(next)}`} aria-label={`Next: ${next.motor_name}`}>›</a>
      </div>

      <section className="panel stack" aria-labelledby="verdict-h">
        <h2 id="verdict-h">What the detector decided</h2>
        <VerdictBar m={m} />
        <p className="small muted">
          How it decides: the detector learned from other bearings, never this one. It listens to 26 pitches of the
          current at once and adds up many tiny differences into one hidden score. Red zone: check bearing. Amber
          middle: too close to call, so a person decides. Green: healthy. We show the zone, not the score: on bearings
          it had never seen, the score was not reliable enough to read as a percentage.
        </p>
      </section>

      <section className="panel stack" aria-labelledby="hiss-h">
        <div className="row">
          <h2 id="hiss-h">What its current sounds like</h2>
          <span className="spacer" />
          <div className="toggles" role="group" aria-label="Layers">
            <button className="chip" aria-pressed={show.diff} onClick={() => toggle('diff')}>Zoom on the difference</button>
            <button className="chip" aria-pressed={show.healthy} onClick={() => toggle('healthy')}>Healthy range</button>
            <button className="chip" aria-pressed={show.notes} onClick={() => toggle('notes')}>Bearing notes</button>
            <button className="chip" aria-pressed={show.listen} onClick={() => toggle('listen')}>Where it listens</button>
            {signs.length > 0 && <button className="chip" aria-pressed={show.signs} onClick={() => toggle('signs')}>Top signs</button>}
          </div>
        </div>
        <p className="small muted">
          Blue: this motor's <Term k="hiss">hiss</Term> at each <Term k="pitch">pitch</Term>{show.diff ? ', minus the middle of the healthy bearings' : ''}.
          Grey: where the six healthy lab bearings sit. Red dashes: the <Term k="bearingNotes">bearing notes</Term>. Yellow: <Term k="listens">where
          the detector listens</Term> on average. Purple dots 1 and 2: this motor's top signs. Point at the chart for numbers.
        </p>
        {values && <HissChart ref={chart} hiss={data.hiss} values={values}
          showHealthy={show.healthy} showNotes={show.notes} showListen={show.listen} diff={show.diff} signs={show.signs ? signs : []} />}
        {values && <p className="small"><b>{outside === 0
          ? "At every pitch this motor stays inside the healthy bearings' spread."
          : `At ${outside} of ${values.length} pitch slices this motor leaves the healthy bearings' spread.`}</b>{' '}
          The detector does not rely on one pitch: it adds up many small shifts of 1 to 2 dB, which is why the
          verdict can differ even when the lines look alike.</p>}
        {signs.length > 0 && show.signs && (
          <p className="small" style={{ borderLeft: '3px solid var(--sign)', paddingLeft: 10 }}>
            <b style={{ color: 'var(--sign)' }}>Purple: the {signs.length === 1 ? 'pitch' : `${signs.length} pitches`} that
            pushed this verdict most</b>{' '}
            ({m.evidence.map((e, k) => `sign ${k + 1}: ${e.replace(' than the average motor in training', '')}`).join('; ')}).
            Each sign compares this motor with the average motor in training, not with the grey band, so a sign can sit
            inside the grey band. A sign counts more when the detector cares about that pitch and this motor is unusual there.
          </p>
        )}
        <div className="row">
          <button className="btn amd" onClick={runExplain} disabled={explaining}>
            {explaining ? 'Reading the chart…' : 'Explain this chart'}
          </button>
          <span className="tiny">An AMD vision model looks at this exact picture plus the detector's facts.</span>
        </div>
        {explaining && <Thinking label="Gemma on AMD is reading the picture" />}
        {explain && <div className="answer stack" style={{ gap: 6 }}><p>{explain.text}</p><Source source={explain.source} /></div>}
      </section>

      <div className="grid2">
        <section className="panel stack" aria-labelledby="note-h">
          <h2 id="note-h">Note for the technician</h2>
          {percentOk ? (
            <div className="row" style={{ alignItems: 'center' }}>
              <Gauge m={m} size={150} />
              <p className="small muted" style={{ flex: 1, minWidth: 160 }}>
                The needle is the detector's damage estimate. Amber is its <Term k="askPerson">ask a person</Term> zone,
                set on training bearings only.
              </p>
            </div>
          ) : (
            <p className="small muted">The detector's percentages were not accurate enough on unseen bearings to show
              as numbers, so it says <Term k="howSure">how sure</Term> in words only: high, medium or low.</p>
          )}
          <div className="tabs" role="tablist">
            <button role="tab" aria-selected={tab === 'amd'} onClick={() => setTab('amd')}>AMD assistant</button>
            <button role="tab" aria-selected={tab === 'template'} onClick={() => setTab('template')}>Plain template</button>
          </div>
          {!note && <Thinking label="Writing the note on AMD Token Factory" />}
          {note && tab === 'amd' && <><p className="note">{note.text}</p><Source source={note.source} /></>}
          {note && tab === 'template' && <><p className="note">{note.template || note.text}</p>
            <span className="source">Filled in by fixed code from the same facts, for comparison.</span></>}
        </section>

        <section className="panel stack" aria-labelledby="ask-h">
          <h2 id="ask-h">Ask about {m.motor_name}</h2>
          <div className="row" style={{ gap: 6 }}>
            {QUESTIONS.map(x => <button key={x} className="chip" onClick={() => ask(x)} disabled={!online}>{x}</button>)}
          </div>
          <form className="ask-box" onSubmit={e => { e.preventDefault(); ask(q) }}>
            <input value={q} onChange={e => setQ(e.target.value)} placeholder="Type a question in plain words"
              aria-label="Your question" maxLength={300} disabled={!online} />
            <button className="btn" disabled={!online || !q.trim()}>Ask</button>
          </form>
          {!online && <p className="small muted">The AMD assistant is offline right now; verdicts and notes still work.</p>}
          {answers.map((x, i) => (
            <div key={i} className="stack" style={{ gap: 6 }}>
              <b className="small">{x.q}</b>
              {!x.a && !x.err && <Thinking label="Thinking on AMD" />}
              {x.a && <div className="answer stack" style={{ gap: 6 }}><p>{x.a.text}</p><Source source={x.a.source} /></div>}
              {x.err && <p className="small" role="alert">{x.err}</p>}
            </div>
          ))}
          <p className="tiny">It may only use this motor's facts and the honest results. If the answer is not there, it
            says "I don't know that from this data".</p>
        </section>
      </div>

      {m.plant_word !== 'healthy' && (
        <section className="panel stack" aria-labelledby="wo-h">
          <div className="row"><h2 id="wo-h">Draft work order</h2><span className="spacer" />
            <button className={`btn ${approved ? 'ghost' : ''}`} onClick={() => setApproved(a => !a)} aria-pressed={approved}>
              {approved ? 'Approved (undo)' : 'Approve draft'}
            </button>
          </div>
          <dl className="wo">
            <dt>Motor</dt><dd>{m.motor_name}</dd>
            <dt>Problem</dt><dd>Detector says: {m.plant_word}</dd>
            <dt>Urgency</dt><dd>{m.urgency ?? 'none'}</dd>
            <dt>Check</dt><dd>Vibration or ultrasound check of the bearing on the shaft line, before replacing anything</dd>
            <dt>How sure</dt><dd>{m.how_sure}</dd>
            <dt>Status</dt><dd>{approved ? 'Approved by a person (demo: not sent anywhere)' : "Draft, needs a person's approval"}</dd>
          </dl>
        </section>
      )}

      <details className="panel">
        <summary><b>For judges: which lab bearing is this?</b></summary>
        <p className="small" style={{ marginTop: 8 }}>
          {m.motor_name} is Paderborn bearing <b>{m.bearing}</b>, {ORIGIN[m.origin]}. Its verdict comes from test group
          {' '}{m.fold}, in which the detector never learned from this bearing ({m.detector}, {m.setting},
          {' '}{m.n_recordings} recordings of 4 seconds combined by their median).
        </p>
      </details>
    </div>
  )
}
