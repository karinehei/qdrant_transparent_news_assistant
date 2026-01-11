import { useState, useEffect } from 'react'
import { ChatResponse, ChatRequest } from '../types/api'
import './ChatScreen.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Persist question and response to localStorage
const STORAGE_KEY_QUESTION = 'news_assistant_question'
const STORAGE_KEY_RESPONSE = 'news_assistant_response'

export default function ChatScreen() {
  // Load from localStorage on mount
  const [question, setQuestion] = useState(() => {
    const saved = localStorage.getItem(STORAGE_KEY_QUESTION)
    return saved || ''
  })
  const [response, setResponse] = useState<ChatResponse | null>(() => {
    const saved = localStorage.getItem(STORAGE_KEY_RESPONSE)
    return saved ? JSON.parse(saved) : null
  })
  const [loading, setLoading] = useState(false)
  const [showTransparency, setShowTransparency] = useState(false)

  // Persist question to localStorage
  useEffect(() => {
    if (question) {
      localStorage.setItem(STORAGE_KEY_QUESTION, question)
    }
  }, [question])

  // Persist response to localStorage
  useEffect(() => {
    if (response) {
      localStorage.setItem(STORAGE_KEY_RESPONSE, JSON.stringify(response))
    } else {
      localStorage.removeItem(STORAGE_KEY_RESPONSE)
    }
  }, [response])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim() || loading) return

    setLoading(true)
    // Don't clear response immediately - keep previous response visible while loading
    // setResponse(null)

    try {
      const req: ChatRequest = { question: question.trim() }
      
      // Create AbortController for timeout
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 240000) // 4 minutes timeout
      
      const res = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(req),
        signal: controller.signal,
      })
      
      clearTimeout(timeoutId)

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }

      const data: ChatResponse = await res.json()
      setResponse(data)
      // Keep the question in the input field so user can see what they asked
      // Don't clear it - user might want to ask a follow-up
    } catch (error) {
      console.error('Chat error:', error)
      alert('Error: ' + (error instanceof Error ? error.message : 'Unknown error'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-screen">
      <div className="chat-main">
        <div className="chat-input-section">
          <form onSubmit={handleSubmit}>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="Ask a question about recent news..."
              disabled={loading}
              className="question-input"
            />
            <button type="submit" disabled={loading || !question.trim()}>
              {loading ? 'Asking...' : 'Ask'}
            </button>
            {question && (
              <button
                type="button"
                onClick={() => {
                  setQuestion('')
                  localStorage.removeItem(STORAGE_KEY_QUESTION)
                }}
                className="clear-button"
                disabled={loading}
                title="Clear question"
              >
                ✕
              </button>
            )}
          </form>
        </div>

        {response && (
          <div className="answer-section">
            <div className="answer-text">
              {response.answer.split('\n').map((line, i) => (
                <p key={i}>{line}</p>
              ))}
            </div>

            {response.warnings && response.warnings.length > 0 && (
              <div className="warnings">
                <strong>Warnings:</strong>
                <ul>
                  {response.warnings.map((w, i) => (
                    <li key={i}>{w}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="sources-section">
              <h3>Sources</h3>
              <div className="sources-list">
                {response.sources.map((source) => (
                  <div key={source.label} className="source-item">
                    <span className="source-label">{source.label}</span>
                    <div>
                      <strong>{source.title}</strong>
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

            <button
              onClick={() => setShowTransparency(!showTransparency)}
              className="transparency-toggle"
            >
              {showTransparency ? 'Hide' : 'Show'} Retrieval Details
            </button>

            {showTransparency && (
              <div className="transparency-drawer">
                <h4>Retrieval Hits</h4>
                <div className="hits-list">
                  {response.hits.map((hit, idx) => (
                    <div key={idx} className="hit-item">
                      <div className="hit-header">
                        <span className="hit-label">{hit.source_label}</span>
                        <span className="hit-score">
                          Score: {hit.score?.toFixed(3)}
                          {hit.rerank_score && ` (rerank: ${hit.rerank_score.toFixed(3)})`}
                        </span>
                      </div>
                      <div className="hit-title">{hit.title}</div>
                      {hit.text && (
                        <div className="hit-snippet">{hit.text.substring(0, 200)}...</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
