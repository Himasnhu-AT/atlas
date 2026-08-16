// First, so its handlers exist before any other module is evaluated.
import './boot'

import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { HashRouter } from 'react-router-dom'
import App from './App'
import { ErrorBoundary } from './components/ErrorBoundary'
import './index.css'

const container = document.getElementById('root')

if (!container) {
  throw new Error('Root container #root is missing from index.html')
}

// HashRouter rather than BrowserRouter: in a packaged build the frontend is
// served from the `tauri://` asset protocol, which has no server to rewrite
// deep paths, so a reload on `/practice/...` would 404. Hash routes always
// resolve against index.html.
createRoot(container).render(
  <StrictMode>
    <ErrorBoundary>
      <HashRouter>
        <App />
      </HashRouter>
    </ErrorBoundary>
  </StrictMode>,
)
