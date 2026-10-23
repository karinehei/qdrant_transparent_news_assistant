import { isDemoMode } from './mode'
import { httpAdapter } from './httpAdapter'
import type { ApiAdapter } from './types'

export { isDemoMode } from './mode'
export type { ApiAdapter, ChatResult, DemoMeta, RunDetail } from './types'
export { httpAdapter } from './httpAdapter'

/**
 * Resolve the API adapter. Demo adapter is loaded only when VITE_DEMO_MODE === 'true'
 * so scenario data stays out of the normal production bundle where practical.
 */
export async function getApiAdapter(): Promise<ApiAdapter> {
  if (isDemoMode) {
    const { createDemoAdapter } = await import('../demo/adapter.ts')
    return createDemoAdapter()
  }
  return httpAdapter
}

/** Sync factory for tests; does not load demo data unless demoMode is true. */
export async function createApiAdapter(demoMode: boolean): Promise<ApiAdapter> {
  if (demoMode) {
    const { createDemoAdapter } = await import('../demo/adapter.ts')
    return createDemoAdapter()
  }
  return httpAdapter
}
