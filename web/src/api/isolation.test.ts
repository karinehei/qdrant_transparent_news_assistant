import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createApiAdapter, httpAdapter } from './index'
import { resetDemoAdapterForTests } from '../demo/adapter'
import { resetDemoStorageForTests } from '../demo/storage'

describe('demo-mode isolation', () => {
  beforeEach(() => {
    resetDemoAdapterForTests()
    resetDemoStorageForTests()
    vi.unstubAllGlobals()
  })

  it('selects the HTTP adapter when demo mode is false', async () => {
    const api = await createApiAdapter(false)
    expect(api).toBe(httpAdapter)
    expect(api.reset).toBeUndefined()
  })

  it('selects the demo adapter when demo mode is true', async () => {
    const api = await createApiAdapter(true)
    expect(api).not.toBe(httpAdapter)
    expect(typeof api.reset).toBe('function')
  })

  it('HTTP adapter never silently returns demo scenario answers', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        answer: 'live backend answer',
        sources: [],
        hits: [],
        run_id: 99,
        warnings: [],
      }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const result = await httpAdapter.chat({
      question: 'What did the fictional city council decide about the riverside park renovation?',
    })

    expect(fetchMock).toHaveBeenCalled()
    const calledUrl = String(fetchMock.mock.calls[0][0])
    expect(calledUrl).toMatch(/\/chat$/)
    expect(result.response.answer).toBe('live backend answer')
    expect(result.demo).toBeUndefined()
  })

  it('demo adapter does not call fetch', async () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    const api = await createApiAdapter(true)
    await api.chat({
      question: 'What did the fictional city council decide about the riverside park renovation?',
    })

    expect(fetchMock).not.toHaveBeenCalled()
  })
})
