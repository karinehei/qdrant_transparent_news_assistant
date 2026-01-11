import { useState } from 'react'
import ChatScreen from './components/ChatScreen'
import AuditScreen from './components/AuditScreen'
import './App.css'

function App() {
  const [currentView, setCurrentView] = useState<'chat' | 'audit'>('chat')

  return (
    <div className="app">
      <header className="app-header">
        <h1>Transparent News Assistant</h1>
        <nav>
          <button
            onClick={() => setCurrentView('chat')}
            className={currentView === 'chat' ? 'active' : ''}
          >
            Chat
          </button>
          <button
            onClick={() => setCurrentView('audit')}
            className={currentView === 'audit' ? 'active' : ''}
          >
            Audit
          </button>
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

export default App
