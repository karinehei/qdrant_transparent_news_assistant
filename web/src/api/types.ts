import type { ChatRequest, ChatResponse, RunItem } from '../types/api'

/** Full run payload for audit detail views (HTTP or demo). */
export interface RunDetail {
  id: number
  created_at: string
  question: string
  answer: string
  model: string
  sources: ChatResponse['sources']
  hits: ChatResponse['hits']
  warnings: string[]
}

/** Optional demo-only metadata; never mixed into backend ChatResponse fields. */
export interface DemoMeta {
  scenarioId?: string
  explanation?: string
  /** True when free-text did not match a prepared scenario. */
  unsupported?: boolean
}

export interface ChatResult {
  response: ChatResponse
  demo?: DemoMeta
}

export interface ApiAdapter {
  chat(request: ChatRequest): Promise<ChatResult>
  listRuns(limit?: number): Promise<RunItem[]>
  getRun(runId: number): Promise<RunDetail | null>
  /** Demo-only: clear history and current result. No-op in HTTP mode. */
  reset?(): void
}
