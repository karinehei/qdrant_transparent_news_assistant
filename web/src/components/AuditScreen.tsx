import { useState, useEffect } from 'react'
import { RunItem } from '../types/api'
import './AuditScreen.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export default function AuditScreen() {
  const [runs, setRuns] = useState<RunItem[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedRun, setSelectedRun] = useState<number | null>(null)

  useEffect(() => {
    loadRuns()
  }, [])

  const loadRuns = async () => {
    try {
      const res = await fetch(`${API_BASE}/runs?limit=50`)
      if (res.ok) {
        const data: RunItem[] = await res.json()
        setRuns(data)
      }
    } catch (error) {
      console.error('Error loading runs:', error)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="audit-screen">Loading...</div>
  }

  return (
    <div className="audit-screen">
      <h2>Audit Trail</h2>
      <div className="runs-list">
        {runs.map((run) => (
          <div
            key={run.id}
            className={`run-item ${selectedRun === run.id ? 'selected' : ''}`}
            onClick={() => setSelectedRun(run.id)}
          >
            <div className="run-header">
              <span className="run-id">#{run.id}</span>
              <span className="run-date">{new Date(run.created_at).toLocaleString()}</span>
            </div>
            <div className="run-question">{run.question}</div>
            <div className="run-model">{run.model}</div>
          </div>
        ))}
      </div>
      {runs.length === 0 && <p>No runs yet.</p>}
    </div>
  )
}
