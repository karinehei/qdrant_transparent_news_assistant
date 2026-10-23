import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { getApiAdapter, isDemoMode, type ApiAdapter } from './index'
import type { DemoPersistedState } from '../demo/storage'

const EMPTY_DEMO_STATE: DemoPersistedState = {
  version: 1,
  nextRunId: 1,
  history: [],
  question: '',
  response: null,
  demoMeta: null,
}

interface ApiContextValue {
  api: ApiAdapter | null
  ready: boolean
  error: string | null
  isDemo: boolean
  /** Demo revision bump so Chat/Audit refresh after runs or reset. */
  demoRevision: number
  demoState: DemoPersistedState | null
  resetDemo: () => void
  notifyDemoChanged: () => void
}

const ApiContext = createContext<ApiContextValue | null>(null)

export function ApiProvider({ children }: { children: ReactNode }) {
  const [api, setApi] = useState<ApiAdapter | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [demoRevision, setDemoRevision] = useState(0)
  const [demoState, setDemoState] = useState<DemoPersistedState | null>(
    isDemoMode ? EMPTY_DEMO_STATE : null,
  )

  const bumpFromSnapshot = useCallback((snapshot: DemoPersistedState) => {
    setDemoState({
      ...snapshot,
      history: [...snapshot.history],
    })
    setDemoRevision((n) => n + 1)
  }, [])

  useEffect(() => {
    let cancelled = false
    getApiAdapter()
      .then(async (adapter) => {
        if (cancelled) return
        setApi(adapter)
        if (isDemoMode) {
          const { getDemoSnapshot } = await import('../demo/adapter')
          if (!cancelled) bumpFromSnapshot(getDemoSnapshot())
        }
        setReady(true)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof Error ? err.message : 'Failed to initialize API')
        setReady(true)
      })
    return () => {
      cancelled = true
    }
  }, [bumpFromSnapshot])

  useEffect(() => {
    if (!isDemoMode || !api) return

    let active = true
    let unsubscribe: (() => void) | undefined

    void import('../demo/adapter').then(({ subscribeDemoState, getDemoSnapshot }) => {
      if (!active) return
      unsubscribe = subscribeDemoState(() => {
        if (!active) return
        bumpFromSnapshot(getDemoSnapshot())
      })
    })

    return () => {
      active = false
      unsubscribe?.()
    }
  }, [api, bumpFromSnapshot])

  const resetDemo = useCallback(() => {
    api?.reset?.()
    // Synchronous UI clear — do not wait on dynamic import
    bumpFromSnapshot(EMPTY_DEMO_STATE)
  }, [api, bumpFromSnapshot])

  const notifyDemoChanged = useCallback(() => {
    if (!isDemoMode) return
    void import('../demo/adapter').then(({ getDemoSnapshot }) => {
      bumpFromSnapshot(getDemoSnapshot())
    })
  }, [bumpFromSnapshot])

  const value = useMemo(
    () => ({
      api,
      ready,
      error,
      isDemo: isDemoMode,
      demoRevision,
      demoState,
      resetDemo,
      notifyDemoChanged,
    }),
    [api, ready, error, demoRevision, demoState, resetDemo, notifyDemoChanged],
  )

  return <ApiContext.Provider value={value}>{children}</ApiContext.Provider>
}

export function useApi(): ApiContextValue {
  const ctx = useContext(ApiContext)
  if (!ctx) {
    throw new Error('useApi must be used within ApiProvider')
  }
  return ctx
}
