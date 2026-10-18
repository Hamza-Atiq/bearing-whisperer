// The one data file the app reads. Every number in it is copied from the project's saved results (bearing/export_web.py).

export type Status = 'check bearing' | 'ask a person' | 'healthy'
export type Sure = 'high' | 'medium' | 'low'

export interface Motor {
  motor_name: string
  bearing: string
  origin: 'healthy' | 'artificial' | 'real'
  label: number
  fold: string
  plant_word: Status
  how_sure: Sure
  line: number | null
  band: number | null
  medium: number | null
  p_median: number | null
  n_recordings: number
  evidence: string[]
  urgency: string | null
  ring?: string | null
  detector: string
  setting: string
}

export interface Run {
  ba: number | null
  ci: [number | null, number | null]
  false_alarm?: number | null
  miss?: number | null
  decided_share?: number | null
  decided_ba?: number | string | null
}

export interface Round {
  round: number
  name: string
  sealed: string
  same_load: Run
  seen_ba: number | null
  new_load: Record<string, Run>
  new_load_control?: Record<string, Run>
  new_load_plant?: Record<string, Run>
  quality: Record<string, Run>
  new_load_note?: string
  candidates?: Record<string, Record<string, { same_load: number; ci: number[]; new_load?: Record<string, number> }>>
}

export interface Sub { ba: number | null; ci: (number | null)[]; n_damaged_bearings: number }

export interface Proof {
  rounds: Round[]
  plant_round: number
  plant: { catch_rate: number; false_alarm_rate: number; handoff_healthy: number; handoff_damaged: number;
    n_healthy: number; n_damaged: number }
  baselines: Record<string, Run>
  per_bearing: { bearing: string; origin: string; share_flagged: number; n: number }[]
  per_condition: Record<string, number>
  by_level: Record<string, Record<string, { share_flagged: number; n_bearings: number }>>
  damage_levels: Record<string, number>
  ring: Record<string, { ba: number; ci: [number, number]; n_bearings: number; n_recordings: number }>
  ring_shown: boolean
  authors_split: Record<string, Record<string, { accuracy: number; balanced_3class: number;
    recall_per_class: Record<string, number> }>>
  authors_reported: { mcs_low: number; mcs_high: number; mcs_ensemble: number; guess: number }
  checks: Record<string, unknown>
  hearing: null | { round: number; tones: [number, number[]]; low: [number, number[]]; mid: [number, number[]];
    high: [number, number[]]; real: [number, number[]]; setting_only?: [number, number[]];
    null_summary: { n: number; mean: number; max: number; share_at_or_above_real: number };
    runin_flagged: Record<string, number>; runin_hours: Record<string, string> }
  cekic_akan: number
  plant_lab?: Run | null
  loco?: Record<string, { per_condition: Record<string, Run>; mean_ba: number | null; pooled: Run;
    subsets: Record<string, Sub> }>
  loco_candidates?: Record<string, Record<string, { loco_mean: number | null; loco: Record<string, number | null>;
    subsets: Record<string, Sub> }>>
  published?: {
    cekic_akan: { cite: string; protocol: string; target_a: { ba: number; what: string };
      target_d: { ba: number; specificity: number; what: string }; target_d_note: string }
    lessmeier: { cite: string; mcs_low: number; mcs_high: number; mcs_ensemble: number; guess: number }
  }
  questions: { n: number; auto_ok: number; must_decline: number; declined: number; claude_ok: number;
    human_ok: (boolean | null)[] }
}

export interface Hiss {
  edges: number[]
  per_bearing: Record<string, number[]>
  healthy_median: number[]
  healthy_low: number[]
  healthy_high: number[]
  listening: number[]
  main_tone_hz: number
  bearing_pitches: Record<string, number>
  bearing_traces: number[]
  shaft_hz: number
  unit: string
  setting: string
  condition: string
}

export interface AppData {
  motors: Motor[]
  hiss: Hiss
  proof: Proof
  fingerprints: Record<string, string | null>
  licence: string
}

export const STATUS_ORDER: Record<Status, number> = { 'check bearing': 0, 'ask a person': 1, healthy: 2 }
const SURE_ORDER: Record<Sure, number> = { high: 0, medium: 1, low: 2 }

export function sortMotors(ms: Motor[]): Motor[] {
  return [...ms].sort((a, b) => STATUS_ORDER[a.plant_word] - STATUS_ORDER[b.plant_word]
    || SURE_ORDER[a.how_sure] - SURE_ORDER[b.how_sure] || (b.p_median ?? 0) - (a.p_median ?? 0))
}

export const num = (m: Motor) => Number(m.motor_name.split(' ')[1])

export function pct(x: number | null | undefined): string {
  if (x == null) return 'n/a'
  if (x >= 0.995) return 'over 99%'
  if (x < 0.005) return 'under 1%'
  return `${Math.round(x * 100)}%`
}

export const f2 = (x: number | null | undefined) => (x == null ? 'n/a' : x.toFixed(2))

export const QUALITY_LABEL: Record<string, string> = {
  lab: 'Lab quality (64 kHz)', '32k_12b': '32 kHz, 12-bit', '16k_12b': '16 kHz, 12-bit',
  '8k_12b': '8 kHz, 12-bit', '16k_10b': '16 kHz, 10-bit',
}

export const CONDITION_LABEL: Record<string, string> = {
  N15_M07_F10: 'normal (1,500 rpm, 0.7 Nm)', N09_M07_F10: 'slower (900 rpm)', N15_M01_F10: 'light load (0.1 Nm)',
  N15_M07_F04: 'less side force (400 N)',
}

export const LOAD_LABEL: Record<string, string> = {
  'N15_M07_F10->N15_M01_F10': 'Learned at normal load, tested at light load',
  'N15_M01_F10->N15_M07_F10': 'Learned at light load, tested at normal load',
}
