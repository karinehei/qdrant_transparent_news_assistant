import { useState, useEffect, useRef } from 'react'
import type { RunItem } from '../types/api'
import type { RunDetail } from '../api/types'
import { useApi } from '../api/ApiContext'
import { formatScore } from '../utils/formatScore'
import { renderAnswerWithCitations } from '../utils/renderAnswer'
import './AuditScreen.css'

export default function AuditScreen() {
  const { api, ready, isDemo, demoRevision } = useApi()
  const [runs, setRuns] = useState<RunItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null)
  const [detail, setDetail] = useState<RunDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const loadGen = useRef(0)

  useEffect(() => {
    if (!ready || !api) return

    const gen = ++loadGen.current
    setLoading(true)
    setError(null)

    api
      .listRuns(50)
      .then((data) => {
        if (gen !== loadGen.current) return
        setRuns(data)
      })
      .catch((err) => {
        if (gen !== loadGen.current) return
        setError(err instanceof Error ? err.message : 'Failed to load runs')
        setRuns([])
      })
      .finally(() => {
        if (gen === loadGen.current) setLoading(false)
      })
  }, [api, ready, demoRevision])

  useEffect(() => {
    if (!api || selectedRunId === null) {
      setDetail(null)
      return
    }

    let cancelled = false
    setDetailLoading(true)
    api
      .getRun(selectedRunId)
      .then((d) => {
        if (!cancelled) setDetail(d)
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load run')
          setDetail(null)
        }
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [api, selectedRunId, demoRevision])

  // After reset, clear selection if run no longer exists
  useEffect(() => {
    if (selectedRunId !== null && !runs.some((r) => r.id === selectedRunId)) {
      setSelectedRunId(null)
      setDetail(null)
    }
  }, [runs, selectedRunId])

  if (!ready || loading) {
    return <div className="audit-screen">Loading…</div>
  }

  return (
    <div className="audit-screen">
      <h2>Audit Trail</h2>
      {isDemo && (
        <p className="audit-demo-note">
          Local demo history only — populated by completed scenario runs in this browser session.
        </p>
      )}

      {error && (
        <div className="inline-error" role="alert">
          {error}
        </div>
      )}

      <div className="audit-layout">
        <div className="runs-list" role="list" aria-label="Chat runs">
          {runs.map((run) => (
            <button
              key={run.id}
              type="button"
              role="listitem"
              className={`run-item ${selectedRunId === run.id ? 'selected' : ''}`}
              onClick={() => setSelectedRunId(run.id)}
              aria-pressed={selectedRunId === run.id}
              aria-label={`Open run ${run.id}: ${run.question}`}
            >
              <div className="run-header">
                <span className="run-id">#{run.id}</span>
                <span className="run-date">{new Date(run.created_at).toLocaleString()}</span>
              </div>
              <div className="run-question">{run.question}</div>
              <div className="run-model">{run.model}</div>
            </button>
          ))}
          {runs.length === 0 && <p>No runs yet.</p>}
        </div>

        <div className="run-detail-panel" aria-live="polite">
          {selectedRunId === null && (
            <p className="run-detail-placeholder">Select a run to view question, answer, sources, and warnings.</p>
          )}
          {detailLoading && <p>Loading run…</p>}
          {!detailLoading && detail && (
            <article className="run-detail">
              <header>
                <h3>Run #{detail.id}</h3>
                <time dateTime={detail.created_at}>
                  {new Date(detail.created_at).toLocaleString()}
                </time>
              </header>
              <section>
                <h4>Question</h4>
                <p>{detail.question}</p>
              </section>
              <section>
                <h4>Answer</h4>
                <div className="answer-text">
                  {renderAnswerWithCitations(detail.answer, () => {
                    /* focus handled in chat; audit shows sources below */
                  })}
                </div>
              </section>
              {detail.warnings.length > 0 && (
                <section className="warnings" role="status">
                  <h4>Warnings</h4>
                  <ul>
                    {detail.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </section>
              )}
              {detail.sources.length > 0 && (
                <section>
                  <h4>Sources</h4>
                  <ul className="detail-sources">
                    {detail.sources.map((s) => (
                      <li key={s.label}>
                        <strong>{s.label}</strong> {s.title}
                        {s.publisher ? ` — ${s.publisher}` : ''}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              {detail.hits.length > 0 && (
                <section>
                  <h4>Retrieval hits</h4>
                  <p className="score-legend">
                    Scores are retrieval relevance ranks, not factual correctness or confidence.
                  </p>
                  <ul className="detail-hits">
                    {detail.hits.map((h, i) => (
                      <li key={h.uid ?? i}>
                        <strong>{h.source_label}</strong>
                        {' — '}
                        Retrieval: {formatScore(h.score)} · Rerank: {formatScore(h.rerank_score)}
                        {h.text && <p className="hit-snippet">{h.text}</p>}
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </article>
          )}
        </div>
      </div>
    </div>
  )
}
