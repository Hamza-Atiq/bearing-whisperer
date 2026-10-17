// Calls to the app's own server functions. The AMD key never reaches the browser (FR-013).

export async function post<T>(route: string, body: unknown): Promise<T> {
  const r = await fetch(`/api/${route}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  })
  const data = await r.json().catch(() => ({ error: `HTTP ${r.status}` }))
  if (!r.ok) throw new Error(data.error ?? `HTTP ${r.status}`)
  return data as T
}

export interface NoteReply { text: string; source: string; template: string; problems: string[] }
export interface AnswerReply { text: string; source: string }
export interface Visit { motor: string; status: string; how_sure: string; reason: string;
  work_order: Record<string, string> }
export interface PlanReply { visits: Visit[]; summary: string; source: string;
  steps: { tool: string; args: Record<string, unknown> }[]; problems: string[] }
export interface ExplainReply { text: string; source: string; problems: string[] }

export const isAmd = (source: string) => source !== 'template' && source !== 'rule'
