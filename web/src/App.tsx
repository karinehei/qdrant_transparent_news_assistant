import { useState } from 'react'
import ChatScreen from './components/ChatScreen'
import AuditScreen from './components/AuditScreen'
import { ApiProvider, useApi } from './api/ApiContext'
import './App.css'

function AppShell() {
  const [currentView, setCurrentView] = useState<'chat' | 'audit'>('chat')
  const { isDemo, resetDemo } = useApi()

  return (
    <div className="app">
      {isDemo && (
        <div className="demo-banner" role="status">
          <p>
            Interactive demo · Prepared examples · No live AI or news retrieval
          </p>
          <p className="demo-banner-sub">
            Safety examples illustrate behavior and do not execute the backend&apos;s safety
            checks.
          </p>
        </div>
      )}
      <header className="app-header">
        <h1>Transparent News Assistant{isDemo ? ' (Demo)' : ''}</h1>
        <nav aria-label="Primary">
          <button
            type="button"
            onClick={() => setCurrentView('chat')}
            className={currentView === 'chat' ? 'active' : ''}
            aria-current={currentView === 'chat' ? 'page' : undefined}
          >
            Chat
          </button>
          <button
            type="button"
            onClick={() => setCurrentView('audit')}
            className={currentView === 'audit' ? 'active' : ''}
            aria-current={currentView === 'audit' ? 'page' : undefined}
          >
            Audit
          </button>
          {isDemo && (
            <button type="button" className="header-reset" onClick={resetDemo}>
              Reset demo
            </button>
          )}
        </nav>
      </header>
      <main>
        <div style={{ display: currentView === 'chat' ? 'block' : 'none' }}>
          <ChatScreen />
        </div>
        <div style={{ display: currentView === 'audit' ? 'block' : 'none' }}>
          <AuditScreen />
        </div>
      </main>
    </div>
  )
}

function App() {
  return (
    <ApiProvider>
      <AppShell />
    </ApiProvider>
  )
}

export default App
