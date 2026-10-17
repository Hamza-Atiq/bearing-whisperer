import { useEffect, useState } from 'react'
import type { AppData } from './data'
import { Term } from './components/Term'
import { PlantPage } from './pages/Plant'
import { MotorPage } from './pages/Motor'
import { ShiftPage } from './pages/Shift'
import { ProofPage } from './pages/Proof'
import { ValuePage } from './pages/Value'
import { AboutPage } from './pages/About'

const PAGES = [
  ['plant', 'Plant'], ['motor', 'Motor'], ['shift', 'Plan my shift'], ['proof', 'Proof'], ['value', 'Value'],
  ['about', 'How it works'],
] as const

function useRoute(): string[] {
  const read = () => (window.location.hash.replace(/^#\/?/, '') || 'plant').split('/')
  const [route, setRoute] = useState(read)
  useEffect(() => {
    const on = () => { setRoute(read()); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

export default function App() {
  const [data, setData] = useState<AppData | null>(null)
  const [error, setError] = useState('')
  const [online, setOnline] = useState<boolean | null>(null)
  const route = useRoute()

  useEffect(() => {
    fetch('/data/app.json', { cache: 'no-cache' }).then(r => r.json()).then(setData).catch(() => setError('Could not load the results file.'))
    fetch('/api/health', { method: 'POST' }).then(r => r.json()).then(d => setOnline(!!d.assistant)).catch(() => setOnline(false))
  }, [])

  const page = route[0]
  const titles: Record<string, string> = Object.fromEntries(PAGES)
  useEffect(() => { document.title = `${titles[page] ?? 'Plant'} | Bearing Whisperer` }, [page])

  return (
    <>
      <header className="top">
        <a className="brand" href="#/plant" aria-label="Bearing Whisperer, plant view">
          <img src="/bearing.svg" width={26} height={26} alt="" />
          <b>Bearing Whisperer</b>
        </a>
        <nav className="nav" aria-label="Pages">
          {PAGES.map(([id, label]) => (
            <a key={id} href={`#/${id}`} aria-current={page === id ? 'page' : undefined}>{label}</a>
          ))}
        </nav>
        <span className="amd-chip" title="The assistant runs on open models on AMD GPUs (AMD Token Factory)">
          <i className={`dot ${online ? 'on' : ''}`} />
          <span>{online == null ? 'AMD assistant…' : online ? 'AMD assistant online' : 'AMD assistant offline'}</span>
        </span>
      </header>
      <div className="labstrip">
        <Term k="lab">Recorded lab bearings</Term>, public Paderborn data, not a live plant. Each motor is one test bearing
        on the shaft line; <Term k="drive">drive-like quality</Term> is simulated.
      </div>
      <main>
        {error && <p role="alert">{error}</p>}
        {!data && !error && <p className="muted">Loading the plant…</p>}
        {data && page === 'plant' && <PlantPage data={data} />}
        {data && page === 'motor' && <MotorPage data={data} id={route[1]} online={!!online} />}
        {data && page === 'shift' && <ShiftPage data={data} online={!!online} />}
        {data && page === 'proof' && <ProofPage data={data} />}
        {data && page === 'value' && <ValuePage data={data} />}
        {data && page === 'about' && <AboutPage data={data} />}
      </main>
    </>
  )
}
