import type { ChatRequest, ChatResponse, RunItem, SourceItem, HitItem } from '../types/api'
import type { ApiAdapter, ChatResult, RunDetail } from './types'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function mapHitsFromBackend(raw: unknown): HitItem[] {
  if (!Array.isArray(raw)) return []
  return raw.map((h: Record<string, unknown>) => ({
    uid: typeof h.uid === 'string' ? h.uid : undefined,
    source_label: String(h.source_label ?? ''),
    title: typeof h.title === 'string' ? h.title : undefined,
    url: typeof h.url === 'string' ? h.url : undefined,
    published_at: typeof h.published_at === 'string' ? h.published_at : undefined,
    score: typeof h.score === 'number' ? h.score : undefined,
    rerank_score: typeof h.rerank_score === 'number' ? h.rerank_score : undefined,
    text:
      typeof h.text === 'string'
        ? h.text
        : typeof h.text_snippet === 'string'
          ? h.text_snippet
          : undefined,
  }))
}

function sourcesFromHits(hits: HitItem[]): SourceItem[] {
  const seen = new Set<string>()
  const sources: SourceItem[] = []
  for (const hit of hits) {
    const label = hit.source_label
    if (!label || seen.has(label)) continue
    seen.add(label)
    sources.push({
      label,
      title: hit.title || label,
      url: hit.url,
      published_at: hit.published_at,
    })
  }
  return sources
}

export const httpAdapter: ApiAdapter = {
  async chat(request: ChatRequest): Promise<ChatResult> {
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 240000)

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
        signal: controller.signal,
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const data: ChatResponse = await res.json()
      return { response: data }
    } finally {
      clearTimeout(timeoutId)
    }
  },

  async listRuns(limit = 50): Promise<RunItem[]> {
    const res = await fetch(`${API_BASE}/runs?limit=${limit}`)
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`)
    }
    return res.json()
  },

  async getRun(runId: number): Promise<RunDetail | null> {
    const res = await fetch(`${API_BASE}/runs/${runId}`)
    if (res.status === 404) return null
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`)
    }
    const raw = await res.json()
    const hits = mapHitsFromBackend(raw.hits)
    return {
      id: raw.id,
      created_at:
        typeof raw.created_at === 'string'
          ? raw.created_at
          : new Date(raw.created_at).toISOString(),
      question: raw.question ?? '',
      answer: raw.answer ?? '',
      model: raw.model ?? '',
      sources: sourcesFromHits(hits),
      hits,
      warnings: Array.isArray(raw.warnings) ? raw.warnings : [],
    }
  },
}
