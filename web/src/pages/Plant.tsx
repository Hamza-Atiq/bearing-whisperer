import { useState } from 'react'
import type { AppData, Motor, Status } from '../data'
import { num, sortMotors } from '../data'
import { HissChart } from '../components/HissChart'
import { Gauge } from '../components/Gauge'
import { Term } from '../components/Term'

export const CLS: Record<Status, string> = { 'check bearing': 'check', 'ask a person': 'ask', healthy: 'ok' }
export const COLOR: Record<Status, string> = { 'check bearing': 'var(--check)', 'ask a person': 'var(--ask)', healthy: 'var(--ok)' }

export function StatusPill({ s }: { s: Status }) {
  return <span className={`pill ${CLS[s]}`}>{s}</span>
}

type Filter = 'all' | Status

export function PlantPage({ data }: { data: AppData }) {
  const [filter, setFilter] = useState<Filter>('all')
  const ordered = sortMotors(data.motors)
  const first = ordered[0]
  const byNumber = [...data.motors].sort((a, b) => num(a) - num(b))
  const count = (s: Status) => data.motors.filter(m => m.plant_word === s).length
  const total = data.motors.length
  const percentOk = !!(data.proof.plant as { percent_ok?: boolean }).percent_ok
  const filters: [Filter, string][] = [['all', `All ${total}`], ['check bearing', `Check bearing ${count('check bearing')}`],
    ['ask a person', `Ask a person ${count('ask a person')}`], ['healthy', `Healthy ${count('healthy')}`]]

  return (
    <div className="plant">
      <section className="stack" aria-labelledby="floor-h">
        <div className="row">
          <h1 id="floor-h">Which motor needs you first?</h1>
        </div>
        <div className="mix" aria-hidden="true">
          {(['check bearing', 'ask a person', 'healthy'] as Status[]).map(s => (
            <span key={s} style={{ width: `${(count(s) / total) * 100}%`, background: COLOR[s] }} />
          ))}
        </div>
        <div className="row" role="group" aria-label="Show motors">
          {filters.map(([f, label]) => (
            <button key={f} className="chip" aria-pressed={filter === f} onClick={() => setFilter(f)}>{label}</button>
          ))}
        </div>
        <div className="floor">
          {byNumber.map(m => <Tile key={m.motor_name} m={m} data={data} dim={filter !== 'all' && m.plant_word !== filter}
            first={m === first && first.plant_word !== 'healthy'} />)}
        </div>
        <div className="legend muted">
          <span><i style={{ background: 'var(--check)' }} /><Term k="checkBearing">check bearing</Term></span>
          <span><i style={{ background: 'var(--ask)' }} /><Term k="askPerson">ask a person</Term></span>
          <span><i style={{ background: 'var(--ok)' }} />healthy</span>
          <span>line in a tile: its <Term k="hiss">hiss</Term> minus healthy; grey = healthy spread</span>
        </div>
      </section>

      {first.plant_word === 'healthy' ? (
        <section className="panel"><h2>No motor needs a check right now.</h2></section>
      ) : (
        <section className="panel stack first-card" aria-labelledby="first-h">
          <p className="small muted">Check first</p>
          <div className="row">
            <h2 id="first-h">{first.motor_name}</h2>
            <StatusPill s={first.plant_word} />
          </div>
          <div className="row" style={{ alignItems: 'flex-end' }}>
            {percentOk && <Gauge m={first} size={170} />}
            <div className="stack" style={{ gap: 4, flex: 1, minWidth: 140 }}>
              <span className="small muted"><Term k="howSure">How sure</Term></span>
              <span className="big">{first.how_sure}</span>
              {first.urgency && <span className="small">Act: <b>{first.urgency}</b></span>}
            </div>
          </div>
          <HissChart hiss={data.hiss} values={data.hiss.per_bearing[first.bearing]} compact diff height={90} width={420}
            color={COLOR[first.plant_word]} title={`${first.motor_name}: its hiss against healthy bearings`} />
          <p className="small">Why: {first.evidence[0] ?? 'no single clear sign'}.</p>
          <div className="row">
            <a className="btn" href={`#/motor/${num(first)}`}>Open {first.motor_name}</a>
            <a className="btn ghost" href="#/shift">Plan my shift</a>
          </div>
        </section>
      )}
    </div>
  )
}

function Tile({ m, data, dim, first }: { m: Motor; data: AppData; dim: boolean; first: boolean }) {
  const v = data.hiss.per_bearing[m.bearing]
  return (
    <a href={`#/motor/${num(m)}`} className={`tile ${CLS[m.plant_word]} ${dim ? 'dim' : ''} ${first ? 'first' : ''}`}
      style={{ textDecoration: 'none', color: 'inherit' }}
      aria-label={`${m.motor_name}: ${m.plant_word}, how sure ${m.how_sure}`}>
      <span className="row" style={{ justifyContent: 'space-between', gap: 2 }}>
        <span className="n">{String(num(m)).padStart(2, '0')}</span>
      </span>
      {v && <HissChart hiss={data.hiss} values={v} compact diff width={120} height={30} showNotes={false}
        color={COLOR[m.plant_word]} />}
      <span className="s">sure: {m.how_sure}</span>
    </a>
  )
}
