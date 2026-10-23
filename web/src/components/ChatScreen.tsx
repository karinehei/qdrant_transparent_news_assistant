import { useState, useEffect, useRef, useCallback, lazy, Suspense, type ComponentType } from 'react'
import type { ChatResponse } from '../types/api'
import type { DemoMeta } from '../api/types'
import { useApi } from '../api/ApiContext'
import { isDemoMode } from '../api/mode'
import { formatScore } from '../utils/formatScore'
import { renderAnswerWithCitations } from '../utils/renderAnswer'
import './ChatScreen.css'

/** Only reference the demo intro module when VITE_DEMO_MODE is true (tree-shaken otherwise). */
const DemoIntro: ComponentType<{
  loading: boolean
  disabled: boolean
  onRunScenario: (id: string) => void
  onFillQuestion: (question: string) => void
}> | null =
  import.meta.env.VITE_DEMO_MODE === 'true'
    ? lazy(() => import('../demo/DemoIntro'))
    : null

const STORAGE_KEY_QUESTION = 'news_assistant_question'
const STORAGE_KEY_RESPONSE = 'news_assistant_response'

export default function ChatScreen() {
  const { api, ready, isDemo, demoRevision, demoState, resetDemo, notifyDemoChanged } = useApi()

  const [question, setQuestion] = useState('')
  const [response, setResponse] = useState<ChatResponse | null>(null)
  const [demoMeta, setDemoMeta] = useState<DemoMeta | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showTransparency, setShowTransparency] = useState(false)
  const [focusedSource, setFocusedSource] = useState<string | null>(null)

  const requestGen = useRef(0)
  const sourceRefs = useRef<Record<string, HTMLDivElement | null>>({})
  const hydratedNormal = useRef(false)

  useEffect(() => {
    if (isDemo || hydratedNormal.current) return
    hydratedNormal.current = true
    const savedQ = localStorage.getItem(STORAGE_KEY_QUESTION)
    const savedR = localStorage.getItem(STORAGE_KEY_RESPONSE)
    if (savedQ) setQuestion(savedQ)
    if (savedR) {
      try {
        setResponse(JSON.parse(savedR) as ChatResponse)
      } catch {
        localStorage.removeItem(STORAGE_KEY_RESPONSE)
      }
    }
  }, [isDemo])

  useEffect(() => {
    if (!isDemo || !demoState) return
    setQuestion(demoState.question)
    setResponse(demoState.response)
    setDemoMeta(demoState.demoMeta)
    setError(null)
  }, [isDemo, demoState, demoRevision])

  useEffect(() => {
    if (isDemo) return
    if (question) {
      localStorage.setItem(STORAGE_KEY_QUESTION, question)
    }
  }, [question, isDemo])

  useEffect(() => {
    if (isDemo) return
    if (response) {
      localStorage.setItem(STORAGE_KEY_RESPONSE, JSON.stringify(response))
    } else {
      localStorage.removeItem(STORAGE_KEY_RESPONSE)
    }
  }, [response, isDemo])

  const focusSource = useCallback((label: string) => {
    setFocusedSource(label)
    setShowTransparency(true)
    requestAnimationFrame(() => {
      const el = sourceRefs.current[label]
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
        el.focus()
      }
    })
  }, [])

  const runChat = async (q: string) => {
    if (!api || !q.trim()) return

    const gen = ++requestGen.current
    setLoading(true)
    setError(null)
    setFocusedSource(null)

    try {
      const result = await api.chat({ question: q.trim() })
      if (gen !== requestGen.current) return

      setResponse(result.response)
      setDemoMeta(result.demo ?? null)
      setQuestion(q.trim())
      if (isDemo) {
        notifyDemoChanged()
      }
    } catch (err) {
      if (gen !== requestGen.current) return
      setError(err instanceof Error ? err.message : 'Unknown error')
    } finally {
      if (gen === requestGen.current) {
        setLoading(false)
      }
    }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await runChat(question)
  }

  const handleScenario = async (id: string) => {
    if (!isDemoMode) return
    const { getScenarioById } = await import('../demo/scenarios')
    const scenario = getScenarioById(id as import('../demo/scenarios').ScenarioId)
    if (!scenario) return
    // Invalidate in-flight work, then run (runChat assigns a fresh generation)
    requestGen.current += 1
    setLoading(false)
    setError(null)
    await runChat(scenario.question)
  }

  const handleReset = () => {
    requestGen.current += 1
    setLoading(false)
    setError(null)
    setFocusedSource(null)
    setShowTransparency(false)
    if (isDemo) {
      resetDemo()
    } else {
      setQuestion('')
      setResponse(null)
      setDemoMeta(null)
      localStorage.removeItem(STORAGE_KEY_QUESTION)
      localStorage.removeItem(STORAGE_KEY_RESPONSE)
    }
  }

  if (!ready) {
    return <div className="chat-screen">Loading…</div>
  }

  return (
    <div className="chat-screen">
      <div className="chat-main">
        {isDemo && DemoIntro && (
          <Suspense fallback={<p>Loading scenarios…</p>}>
            <DemoIntro
              loading={loading}
              disabled={!api}
              onRunScenario={handleScenario}
              onFillQuestion={setQuestion}
            />
          </Suspense>
        )}

        <div className="chat-input-section">
          <form onSubmit={handleSubmit}>
            <label htmlFor="question-input" className="visually-hidden">
              Question
            </label>
            <input
              id="question-input"
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder={
                isDemo
                  ? 'Try a scenario button or an example question…'
                  : 'Ask a question about recent news...'
              }
              disabled={loading || !api}
              className="question-input"
              autoComplete="off"
            />
            <button type="submit" disabled={loading || !api || !question.trim()}>
              {loading ? 'Asking…' : 'Ask'}
            </button>
            {question && (
              <button
                type="button"
                onClick={() => {
                  setQuestion('')
                  if (!isDemo) localStorage.removeItem(STORAGE_KEY_QUESTION)
                }}
                className="clear-button"
                disabled={loading}
                title="Clear question"
                aria-label="Clear question"
              >
                ✕
              </button>
            )}
            <button
              type="button"
              onClick={handleReset}
              className="reset-demo-button"
              disabled={loading}
              aria-label={isDemo ? 'Reset demo' : 'Clear chat'}
            >
              {isDemo ? 'Reset demo' : 'Clear'}
            </button>
          </form>
        </div>

        {error && (
          <div className="inline-error" role="alert">
            {error}
          </div>
        )}

        {response && (
          <div className="answer-section">
            {demoMeta?.explanation && (
              <aside className="demo-explanation" aria-label="Scenario explanation">
                <strong>What this shows:</strong> {demoMeta.explanation}
              </aside>
            )}

            {demoMeta?.unsupported && (
              <div className="unsupported-notice" role="status">
                Unmatched input — no unrelated canned answer was used.
              </div>
            )}

            <div className="answer-text">
              {renderAnswerWithCitations(response.answer, focusSource)}
            </div>

            {response.warnings && response.warnings.length > 0 && (
              <div
                className={`warnings ${
                  response.warnings.some((w) => /insufficient/i.test(w))
                    ? 'warnings-insufficient'
                    : ''
                }`}
                role="status"
              >
                <strong>Warnings:</strong>
                <ul>
                  {response.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            {response.sources.length > 0 && (
              <div className="sources-section">
                <h3>Sources</h3>
                <div className="sources-list">
                  {response.sources.map((source) => (
                    <div
                      key={source.label}
                      className={`source-item ${
                        focusedSource === source.label ? 'source-focused' : ''
                      }`}
                      ref={(el) => {
                        sourceRefs.current[source.label] = el
                      }}
                      tabIndex={-1}
                      id={`source-${source.label}`}
                    >
                      <span className="source-label">{source.label}</span>
                      <div>
                        <strong>{source.title}</strong>
                        {source.publisher && (
                          <span className="source-publisher">{source.publisher}</span>
                        )}
                        {source.url && (
                          <a href={source.url} target="_blank" rel="noopener noreferrer">
                            {source.url}
                          </a>
                        )}
                        {source.published_at && (
                          <span className="source-date">{source.published_at}</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {response.hits.length > 0 && (
              <>
                <button
                  type="button"
                  onClick={() => setShowTransparency(!showTransparency)}
                  className="transparency-toggle"
                  aria-expanded={showTransparency}
                >
                  {showTransparency ? 'Hide' : 'Show'} Retrieval Details
                </button>

                {showTransparency && (
                  <div className="transparency-drawer">
                    <h4>Retrieval Hits</h4>
                    <p className="score-legend">
                      Retrieval and rerank scores indicate relative relevance ranking for this
                      demo — not factual correctness or answer confidence.
                    </p>
                    <div className="hits-list">
                      {response.hits.map((hit, idx) => (
                        <div
                          key={hit.uid ?? `${hit.source_label}-${idx}`}
                          className={`hit-item ${
                            focusedSource === hit.source_label ? 'hit-focused' : ''
                          }`}
                        >
                          <div className="hit-header">
                            <button
                              type="button"
                              className="hit-label citation-ref"
                              onClick={() => focusSource(hit.source_label)}
                              aria-label={`Focus source ${hit.source_label}`}
                            >
                              {hit.source_label}
                            </button>
                            <span className="hit-score">
                              Retrieval: {formatScore(hit.score)}
                              {' · '}
                              Rerank: {formatScore(hit.rerank_score)}
                            </span>
                          </div>
                          <div className="hit-title">{hit.title}</div>
                          {hit.text && <div className="hit-snippet">{hit.text}</div>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
