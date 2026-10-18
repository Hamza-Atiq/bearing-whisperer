import type { AppData } from '../data'
import { sortMotors } from '../data'
import { Term } from '../components/Term'

function Box({ x, y, w, h, title, sub, dark, amd }: { x: number; y: number; w: number; h: number; title: string; sub: string;
  dark?: boolean; amd?: boolean }) {
  return (
    <g>
      <rect x={x} y={y} width={w} height={h} rx={8} fill={dark ? 'var(--ink)' : '#fff'}
        stroke={amd ? 'var(--signal)' : 'var(--rule)'} strokeWidth={amd ? 2.5 : 1} />
      <text x={x + 14} y={y + 26} style={{ fontWeight: 700, fontSize: 15, fill: dark ? '#fff' : 'var(--ink)' }}>{title}</text>
      <text x={x + 14} y={y + 46} style={{ fontSize: 12.5, fill: dark ? '#c4ced8' : 'var(--ink-2)' }}>{sub}</text>
    </g>
  )
}

const Arrow = ({ x1, y1, x2, y2 }: { x1: number; y1: number; x2: number; y2: number }) => (
  <line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--ink-2)" strokeWidth={2} markerEnd="url(#arr)" />
)

export function AboutPage({ data }: { data: AppData }) {
  const rounds = data.proof.rounds
  const first = sortMotors(data.motors)[0]
  return (
    <div className="stack" style={{ gap: 18 }}>
      <h1>How it works</h1>
      <section className="panel stack" aria-labelledby="flow-h">
        <h2 id="flow-h">From a wire to a work order</h2>
        <svg className="flow" viewBox="0 0 980 330" width="100%" role="img"
          aria-label="Motor current goes to a small detector, then to the fact sheet. The AMD assistant reads the facts and writes notes, answers, shift plans and chart explanations. A fact checker passes them to the technician.">
          <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--ink-2)" /></marker></defs>
          <Box x={10} y={30} w={180} h={62} title="Motor current" sub="what a drive already measures" />
          <Box x={230} y={30} w={190} h={62} title="Small detector" sub={data.proof.plant_round >= 3 ? 'hiss vs fleet, runs anywhere' : 'hiss shape, runs anywhere'} />
          <Box x={460} y={30} w={170} h={62} title="Fact sheet" sub="status, how sure, signs" />
          <rect x={430} y={128} width={300} height={186} rx={12} fill="var(--signal-soft)" stroke="var(--signal)" strokeWidth={2} />
          <text x={446} y={152} style={{ fontWeight: 800, fontSize: 15, fill: 'var(--signal)' }}>AMD Token Factory: open models on AMD GPUs</text>
          <Box x={446} y={164} w={130} h={62} title="Note" sub="plain words" amd />
          <Box x={586} y={164} w={130} h={62} title="Answers" sub="follow-up questions" amd />
          <Box x={446} y={238} w={130} h={62} title="Shift plan" sub="calls plant tools" amd />
          <Box x={586} y={238} w={130} h={62} title="Chart explainer" sub="reads the picture" amd />
          <Box x={770} y={150} w={190} h={62} title="Fact checker" sub="no invented facts" dark />
          <Box x={770} y={250} w={190} h={62} title="Technician" sub="approves every order" />
          <Arrow x1={190} y1={61} x2={228} y2={61} />
          <Arrow x1={420} y1={61} x2={458} y2={61} />
          <Arrow x1={545} y1={92} x2={545} y2={126} />
          <Arrow x1={730} y1={200} x2={768} y2={185} />
          <Arrow x1={865} y1={212} x2={865} y2={248} />
          <text x={10} y={130} style={{ fontSize: 13, fill: 'var(--ink-2)' }}>If the AMD assistant is down or fails the check,</text>
          <text x={10} y={148} style={{ fontSize: 13, fill: 'var(--ink-2)' }}>a fixed template answers and the page says so.</text>
        </svg>
      </section>

      <div className="grid2">
        <section className="panel stack">
          <h2>What runs on AMD, and why it matters</h2>
          <p>The detector is small; it does not need a GPU. Everything a person reads or asks goes through open models
            (Gemma 4, with Qwen as backup) on <Term k="amd">AMD Token Factory</Term>:</p>
          <ul className="caveats">
            <li>the note for each motor, in plain words;</li>
            <li>answers to follow-up questions, refusing what the data cannot say;</li>
            <li>the shift plan, where the model calls the plant's tools itself;</li>
            <li>the chart explainer, where a vision model reads the same picture you see.</li>
          </ul>
          <p className="small muted">Without this layer a technician gets a spectrum and a probability. With it they get
            "go to {first.motor_name}{first.urgency ? ` ${first.urgency}` : ''}, confirm with a vibration check first".</p>
        </section>
        <section className="panel stack">
          <h2>How it was tested</h2>
          <ul className="caveats small">
            <li>32 lab bearings: 6 healthy, 12 with lab-made damage, 14 with real wear (Paderborn University, Lessmeier et al. 2016).</li>
            <li>Scored only on bearings the detector never learned from, in six fixed groups.</li>
            {rounds.map(r => <li key={r.round}>{r.name}: rules locked first (fingerprint {r.sealed}).</li>)}
            <li>Never claimed: days until failure, bearings inside a motor, any drive brand's sensor.</li>
          </ul>
          <p className="small">Code: <a href="https://github.com/Hamza-Atiq/bearing-whisperer">github.com/Hamza-Atiq/bearing-whisperer</a></p>
          <p className="tiny">{data.licence} Our code is MIT.</p>
        </section>
      </div>
    </div>
  )
}
