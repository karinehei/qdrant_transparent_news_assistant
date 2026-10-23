import type { ChatRequest, RunItem } from '../types/api'
import type { ApiAdapter, ChatResult, RunDetail } from '../api/types'
import { findScenario, getScenarioById, UNSUPPORTED_ANSWER, type ScenarioId } from './scenarios'
import {
  clearDemoState,
  loadDemoState,
  saveDemoState,
  type DemoHistoryEntry,
  type DemoPersistedState,
} from './storage'

const DEMO_MODEL = 'demo-prepared-scenarios'

type Listener = () => void

let sharedState: DemoPersistedState | null = null
const listeners = new Set<Listener>()

function getState(): DemoPersistedState {
  if (!sharedState) {
    sharedState = loadDemoState()
  }
  return sharedState
}

function setState(next: DemoPersistedState): void {
  sharedState = next
  saveDemoState(next)
  listeners.forEach((l) => l())
}

export function subscribeDemoState(listener: Listener): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}

export function getDemoSnapshot(): DemoPersistedState {
  return getState()
}

function toRunItem(entry: DemoHistoryEntry): RunItem {
  return {
    id: entry.id,
    created_at: entry.created_at,
    question: entry.question,
    model: entry.model,
  }
}

function toRunDetail(entry: DemoHistoryEntry): RunDetail {
  return {
    id: entry.id,
    created_at: entry.created_at,
    question: entry.question,
    answer: entry.answer,
    model: entry.model,
    sources: entry.sources,
    hits: entry.hits,
    warnings: entry.warnings,
  }
}

function appendRun(
  state: DemoPersistedState,
  question: string,
  result: ChatResult,
): DemoPersistedState {
  const runId = state.nextRunId
  const created_at = new Date().toISOString()
  const entry: DemoHistoryEntry = {
    id: runId,
    created_at,
    question,
    model: DEMO_MODEL,
    answer: result.response.answer,
    sources: result.response.sources,
    hits: result.response.hits,
    warnings: result.response.warnings,
    scenarioId: result.demo?.scenarioId,
    explanation: result.demo?.explanation,
  }

  const response = { ...result.response, run_id: runId }

  return {
    ...state,
    nextRunId: runId + 1,
    history: [entry, ...state.history],
    question,
    response,
    demoMeta: result.demo ?? null,
  }
}

function buildScenarioResult(scenarioId: ScenarioId): ChatResult {
  const scenario = getScenarioById(scenarioId)
  if (!scenario) {
    return {
      response: {
        answer: UNSUPPORTED_ANSWER,
        sources: [],
        hits: [],
        run_id: 0,
        warnings: [],
      },
      demo: { unsupported: true, explanation: 'Unknown scenario id.' },
    }
  }

  return {
    response: {
      ...scenario.response,
      run_id: 0,
    },
    demo: {
      scenarioId: scenario.id,
      explanation: scenario.explanation,
    },
  }
}

function buildFromQuestion(question: string): ChatResult {
  const scenario = findScenario(question)
  if (!scenario) {
    return {
      response: {
        answer: UNSUPPORTED_ANSWER,
        sources: [],
        hits: [],
        run_id: 0,
        warnings: [],
      },
      demo: {
        unsupported: true,
        explanation:
          'No prepared scenario matched this question. The demo never returns an unrelated canned answer.',
      },
    }
  }
  return buildScenarioResult(scenario.id)
}

/** Reset module singleton (tests). */
export function resetDemoAdapterForTests(): void {
  sharedState = null
  listeners.clear()
}

export function createDemoAdapter(): ApiAdapter {
  getState()

  const adapter: ApiAdapter = {
    async chat(request: ChatRequest): Promise<ChatResult> {
      const q = request.question.trim()
      if (!q) {
        throw new Error('Question is required')
      }
      const result = buildFromQuestion(q)
      const next = appendRun(getState(), q, result)
      setState(next)
      return {
        response: next.response!,
        demo: next.demoMeta ?? undefined,
      }
    },

    async listRuns(limit = 50): Promise<RunItem[]> {
      return getState().history.slice(0, limit).map(toRunItem)
    },

    async getRun(runId: number): Promise<RunDetail | null> {
      const entry = getState().history.find((h) => h.id === runId)
      return entry ? toRunDetail(entry) : null
    },

    reset(): void {
      sharedState = clearDemoState()
      listeners.forEach((l) => l())
    },
  }

  return adapter
}

/** Pure helpers exported for unit tests (no persistence side effects). */
export const demoMatching = {
  buildFromQuestion,
  buildScenarioResult,
  findScenario,
  UNSUPPORTED_ANSWER,
}
