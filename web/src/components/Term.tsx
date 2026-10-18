import { useEffect, useRef, useState, type ReactNode } from 'react'

// Every technical word a trainee might trip on, explained in one or two plain sentences (G7, FR-023).
export const GLOSSARY: Record<string, { title: string; text: string }> = {
  hiss: { title: 'Hiss', text: "A motor's current is mostly one steady hum. Around it there is a very quiet hiss spread over many pitches. A damaged bearing can change that hiss a little." },
  pitch: { title: 'Pitch (Hz)', text: 'How fast something wobbles, in waves per second (hertz, Hz). Low pitch is on the left of the chart, high pitch on the right, like the keys of a piano.' },
  howSure: { title: 'How sure', text: "How far the detector's estimate is from its 'ask a person' zone. High means far from it. It says how confident the detector is, not how bad the damage is." },
  askPerson: { title: 'Ask a person', text: 'The detector is not sure, so it hands the motor to a person instead of guessing.' },
  checkBearing: { title: 'Check bearing', text: 'The detector says the bearing is damaged. A person confirms with a vibration or ultrasound check before anything is replaced.' },
  bearingNotes: { title: 'Bearing notes', text: 'A damaged spot on a bearing ring is hit by the balls at a fixed rhythm. At 1,500 rpm that is about 76 times a second (outer ring) or 124 (inner ring).' },
  listens: { title: 'Where it listens', text: 'The pitches the detector leans on most when it decides. Ours leans on high-pitch hiss, not on the bearing notes. We say so openly.' },
  honest: { title: 'Honest score', text: 'The score on bearings the detector never saw while learning. This is what to expect on a new bearing of this lab rig.' },
  inflated: { title: 'Inflated score', text: 'The score when the same bearings appear in learning and testing. The detector can recognise each bearing instead of damage, so this number looks better than it is.' },
  balanced: { title: 'Score (balanced accuracy)', text: 'The average of two hit rates: healthy bearings called healthy, and damaged bearings called damaged. Always saying "damaged" scores 0.50. Perfect is 1.00.' },
  range95: { title: '95% range', text: 'If we had a different set of bearings, the score would likely land inside this range. A wide range means: few bearings, be careful.' },
  newLoad: { title: 'New load', text: 'Trained while the motor worked at one load, tested while it worked at another. Real motors change load, so this is the harder, more honest test.' },
  fleet: { title: 'Compared with the fleet', text: "Each motor's hiss is compared with how the other motors sound at the same speed and load (never the side force: a drive cannot know it). No one tells the detector which of them are damaged." },
  unseen: { title: 'Unseen bearing', text: 'A bearing the detector never learned from. Testing only on these is the fair way.' },
  lab: { title: 'Lab data', text: 'Recorded from 32 test bearings at Paderborn University (public data). Each "motor" here is one of those bearings. It is not a live factory.' },
  drive: { title: 'Drive-like quality', text: 'A motor drive measures current less finely than a lab. We simulate that by keeping fewer samples per second and fewer bits.' },
  amd: { title: 'AMD Token Factory', text: 'Open AI models (Gemma, Qwen) running on AMD GPUs. They write the notes, answer questions, plan the shift and explain charts. Every answer is fact-checked first.' },
  level: { title: 'Damage size level', text: 'How long the damaged spot is, from the dataset paper: level 1 is up to 2 mm, level 2 over 2 mm, level 3 over 4.5 mm.' },
}

export function Term({ k, children }: { k: keyof typeof GLOSSARY; children?: ReactNode }) {
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState({ left: 0, top: 0 })
  const ref = useRef<HTMLButtonElement>(null)
  const g = GLOSSARY[k]
  useEffect(() => {
    if (!open) return
    const close = (e: Event) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    const esc = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    document.addEventListener('pointerdown', close)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', esc) }
  }, [open])
  const toggle = () => {
    const r = ref.current!.getBoundingClientRect()
    setPos({ left: Math.min(Math.max(8, r.left + window.scrollX - 20), window.innerWidth - 290), top: r.bottom + window.scrollY + 8 })
    setOpen(o => !o)
  }
  return (
    <>
      <button ref={ref} type="button" className="term" aria-expanded={open} onClick={toggle}>{children ?? g.title}</button>
      {open && (
        <span role="tooltip" className="term-pop" style={{ left: pos.left, top: pos.top }}>
          <b>{g.title}</b>{g.text}
        </span>
      )}
    </>
  )
}
