import { beforeEach, describe, expect, it } from 'vitest'
import {
  clearDemoState,
  DEMO_STORAGE_KEY,
  loadDemoState,
  resetDemoStorageForTests,
  saveDemoState,
  type DemoPersistedState,
} from './storage'
import { createDemoAdapter, resetDemoAdapterForTests } from './adapter'

describe('demo storage and reset', () => {
  beforeEach(() => {
    resetDemoAdapterForTests()
    resetDemoStorageForTests()
  })

  it('persists and reloads valid state via storage layer', () => {
    const state: DemoPersistedState = {
      version: 1,
      nextRunId: 3,
      history: [
        {
          id: 2,
          created_at: '2024-01-01T00:00:00.000Z',
          question: 'q',
          model: 'demo',
          answer: 'a',
          sources: [],
          hits: [],
          warnings: [],
        },
      ],
      question: 'q',
      response: {
        answer: 'a',
        sources: [],
        hits: [],
        run_id: 2,
        warnings: [],
      },
      demoMeta: { scenarioId: 'supported' },
    }
    saveDemoState(state)
    const loaded = loadDemoState()
    expect(loaded.nextRunId).toBe(3)
    expect(loaded.history).toHaveLength(1)
    expect(loaded.response?.run_id).toBe(2)
  })

  it('rejects corrupted storage and falls back to empty state', () => {
    // Force write invalid JSON through save then overwrite raw if possible
    try {
      sessionStorage.setItem(DEMO_STORAGE_KEY, '{not-json')
    } catch {
      // node env without sessionStorage — exercise memory path via invalid load
    }
    // Also save then manually corrupt via load path: write invalid through saveDemoState bypass
    const empty = loadDemoState()
    // If sessionStorage worked and held corrupt data:
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.setItem(DEMO_STORAGE_KEY, '{"version":999}')
      const recovered = loadDemoState()
      expect(recovered.history).toEqual([])
      expect(recovered.nextRunId).toBe(1)
    } else {
      expect(empty.history).toEqual([])
    }
  })

  it('reset clears history and current result', async () => {
    const api = createDemoAdapter()
    await api.chat({
      question: 'What did the fictional city council decide about the riverside park renovation?',
    })
    let runs = await api.listRuns()
    expect(runs.length).toBe(1)

    api.reset?.()
    runs = await api.listRuns()
    expect(runs).toHaveLength(0)

    const cleared = clearDemoState()
    expect(cleared.response).toBeNull()
    expect(cleared.question).toBe('')
  })

  it('avoids duplicate history entries only when chat is invoked once per submit', async () => {
    const api = createDemoAdapter()
    const q = 'What did the fictional city council decide about the riverside park renovation?'
    await api.chat({ question: q })
    await api.chat({ question: q })
    const runs = await api.listRuns()
    expect(runs).toHaveLength(2)
    expect(runs[0].id).not.toBe(runs[1].id)
  })
})
