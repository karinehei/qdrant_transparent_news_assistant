import type { ChatResponse } from '../types/api'
import type { DemoMeta } from '../api/types'

/** Versioned, repository-specific session key — separate from normal-mode localStorage keys. */
export const DEMO_STORAGE_KEY = 'qdrant_transparent_news_assistant_demo_v1'
export const DEMO_STATE_VERSION = 1 as const

export interface DemoHistoryEntry {
  id: number
  created_at: string
  question: string
  model: string
  answer: string
  sources: ChatResponse['sources']
  hits: ChatResponse['hits']
  warnings: string[]
  scenarioId?: string
  explanation?: string
}

export interface DemoPersistedState {
  version: typeof DEMO_STATE_VERSION
  nextRunId: number
  history: DemoHistoryEntry[]
  question: string
  response: ChatResponse | null
  demoMeta: DemoMeta | null
}

const EMPTY_STATE: DemoPersistedState = {
  version: DEMO_STATE_VERSION,
  nextRunId: 1,
  history: [],
  question: '',
  response: null,
  demoMeta: null,
}

type MemoryStore = { value: string | null }

/** In-memory fallback when sessionStorage is unavailable or corrupted. */
let memoryFallback: MemoryStore = { value: null }
let useMemoryOnly = false

function canUseSessionStorage(): boolean {
  try {
    const k = '__qdrant_demo_probe__'
    sessionStorage.setItem(k, '1')
    sessionStorage.removeItem(k)
    return true
  } catch {
    return false
  }
}

function readRaw(): string | null {
  if (useMemoryOnly) return memoryFallback.value
  if (!canUseSessionStorage()) {
    useMemoryOnly = true
    return memoryFallback.value
  }
  try {
    return sessionStorage.getItem(DEMO_STORAGE_KEY)
  } catch {
    useMemoryOnly = true
    return memoryFallback.value
  }
}

function writeRaw(value: string | null): void {
  if (useMemoryOnly) {
    memoryFallback.value = value
    return
  }
  try {
    if (value === null) {
      sessionStorage.removeItem(DEMO_STORAGE_KEY)
    } else {
      sessionStorage.setItem(DEMO_STORAGE_KEY, value)
    }
  } catch {
    useMemoryOnly = true
    memoryFallback.value = value
  }
}

function isSourceItem(x: unknown): boolean {
  if (!x || typeof x !== 'object') return false
  const o = x as Record<string, unknown>
  return typeof o.label === 'string' && typeof o.title === 'string'
}

function isHitItem(x: unknown): boolean {
  if (!x || typeof x !== 'object') return false
  const o = x as Record<string, unknown>
  return typeof o.source_label === 'string'
}

function isChatResponse(x: unknown): x is ChatResponse {
  if (!x || typeof x !== 'object') return false
  const o = x as Record<string, unknown>
  return (
    typeof o.answer === 'string' &&
    Array.isArray(o.sources) &&
    o.sources.every(isSourceItem) &&
    Array.isArray(o.hits) &&
    o.hits.every(isHitItem) &&
    typeof o.run_id === 'number' &&
    Array.isArray(o.warnings)
  )
}

function isHistoryEntry(x: unknown): x is DemoHistoryEntry {
  if (!x || typeof x !== 'object') return false
  const o = x as Record<string, unknown>
  return (
    typeof o.id === 'number' &&
    typeof o.created_at === 'string' &&
    typeof o.question === 'string' &&
    typeof o.model === 'string' &&
    typeof o.answer === 'string' &&
    Array.isArray(o.sources) &&
    Array.isArray(o.hits) &&
    Array.isArray(o.warnings)
  )
}

function isValidState(x: unknown): x is DemoPersistedState {
  if (!x || typeof x !== 'object') return false
  const o = x as Record<string, unknown>
  if (o.version !== DEMO_STATE_VERSION) return false
  if (typeof o.nextRunId !== 'number' || o.nextRunId < 1) return false
  if (!Array.isArray(o.history) || !o.history.every(isHistoryEntry)) return false
  if (typeof o.question !== 'string') return false
  if (o.response !== null && !isChatResponse(o.response)) return false
  if (o.demoMeta !== null && (typeof o.demoMeta !== 'object' || Array.isArray(o.demoMeta))) {
    return false
  }
  return true
}

/** Reset memory fallback (for tests). */
export function resetDemoStorageForTests(): void {
  memoryFallback = { value: null }
  useMemoryOnly = false
  try {
    sessionStorage.removeItem(DEMO_STORAGE_KEY)
  } catch {
    /* ignore */
  }
}

export function loadDemoState(): DemoPersistedState {
  const raw = readRaw()
  if (!raw) return { ...EMPTY_STATE, history: [] }

  try {
    const parsed: unknown = JSON.parse(raw)
    if (!isValidState(parsed)) {
      writeRaw(null)
      return { ...EMPTY_STATE, history: [] }
    }
    return {
      ...parsed,
      history: [...parsed.history],
    }
  } catch {
    writeRaw(null)
    return { ...EMPTY_STATE, history: [] }
  }
}

export function saveDemoState(state: DemoPersistedState): void {
  writeRaw(JSON.stringify(state))
}

export function clearDemoState(): DemoPersistedState {
  const empty = { ...EMPTY_STATE, history: [] as DemoHistoryEntry[] }
  writeRaw(null)
  return empty
}

export function isUsingMemoryFallback(): boolean {
  return useMemoryOnly
}
