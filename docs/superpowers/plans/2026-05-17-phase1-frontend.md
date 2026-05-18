# Phase 1 Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the React frontend for the Verity Prism IDP platform — auth, workspaces home, and all 8 sections of the workspace — consuming the Phase 1 backend API.

**Prerequisite:** The backend API (Tasks 1–11 in `2026-05-17-phase1-backend-api.md` + `...-part2.md`) must be running before you test any frontend feature.

**Architecture:** React + Vite SPA. Pages are route-level components. Shared UI is in `components/`. All API calls go through functions in `api/` — never call fetch/axios directly from a component. Auth state (the JWT token) lives in a Zustand store. Tailwind CSS for styling.

**Tech Stack:** React 18, Vite, React Router v6, Axios, Zustand, Tailwind CSS, Vitest, React Testing Library

**Written for:** A junior developer coming from the IBM full stack cert. React is familiar territory — this plan focuses on the patterns specific to this codebase.

---

## How Testing Works in React

We use **Vitest** (fast test runner, works with Vite) and **React Testing Library** (renders components and tests what the user sees, not implementation details).

The rule: test what a user would do, not how the code works internally.
- Good: `expect(screen.getByText('Do Good In His Name Inc')).toBeInTheDocument()`
- Bad: `expect(component.state.workspaceName).toBe('...')`

For API calls, we use **MSW (Mock Service Worker)** — it intercepts HTTP requests in tests so you don't need the real backend running.

---

## File Map

```
frontend/
├── src/
│   ├── main.jsx                       # React entry point — renders App into the DOM
│   ├── App.jsx                        # Router setup — all routes defined here
│   ├── api/
│   │   ├── client.js                  # Axios instance with base URL and auth header
│   │   ├── auth.js                    # register(), login()
│   │   ├── workspaces.js              # list(), create(), get(), update()
│   │   ├── entities.js                # list(), create(), update(), delete(), relationships
│   │   ├── documents.js               # upload(), list(), get(), getExtractions()
│   │   ├── search.js                  # search()
│   │   ├── transactions.js            # list(), create()
│   │   ├── findings.js                # list(), create(), update(), signalTypes()
│   │   ├── leads.js                   # list(), create(), update()
│   │   ├── notes.js                   # list(), create()
│   │   └── ai.js                      # listConversations(), createConversation(), sendMessage(), listMessages()
│   ├── store/
│   │   └── auth.js                    # Zustand store: token, user, login(), logout()
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppShell.jsx           # Top nav with NLP search bar — wraps authenticated pages
│   │   │   └── WorkspaceSidebar.jsx   # Left sidebar with 8 section links
│   │   ├── shared/
│   │   │   ├── Badge.jsx              # Severity/status colored badge (critical, high, open, etc.)
│   │   │   ├── EmptyState.jsx         # "Nothing here yet" placeholder with an action button
│   │   │   ├── LoadingSpinner.jsx     # Centered spinner for loading states
│   │   │   └── ConfirmModal.jsx       # "Are you sure?" dialog for destructive actions
│   │   ├── documents/
│   │   │   ├── DropZone.jsx           # Drag-and-drop file upload area
│   │   │   └── ExtractionTable.jsx    # Shows extracted fields with confidence scores
│   │   └── ai/
│   │       ├── ChatMessage.jsx        # Single message bubble (user or assistant)
│   │       └── ChatInput.jsx          # Text input + send button for chat
│   └── pages/
│       ├── Login.jsx                  # Login form — redirects to /workspaces on success
│       ├── WorkspacesHome.jsx         # List of all workspaces as cards
│       └── workspace/
│           ├── WorkspaceLayout.jsx    # Workspace shell: sidebar + main content area
│           ├── Overview.jsx           # Stats, AI suggestion banner, recent activity
│           ├── Documents.jsx          # Upload + browse + view extracted fields
│           ├── Search.jsx             # NLP search interface
│           ├── Entities.jsx           # People, orgs, properties — tabbed
│           ├── Transactions.jsx       # Financial flows table
│           ├── Findings.jsx           # Signal board (fraud vertical)
│           ├── Leads.jsx              # Investigation workflow (fraud vertical)
│           └── AIChat.jsx             # Conversation threads with Claude
├── src/tests/
│   ├── setup.js                       # Vitest setup — configures Testing Library
│   ├── mocks/
│   │   ├── handlers.js                # MSW API mock handlers
│   │   └── server.js                  # MSW server setup for tests
│   ├── test_login.jsx
│   ├── test_workspaces_home.jsx
│   ├── test_documents.jsx
│   ├── test_search.jsx
│   └── test_ai_chat.jsx
├── index.html
├── vite.config.js
├── tailwind.config.js
├── package.json
└── Dockerfile
```

---

## Task 1: Project Setup

**What you're building:** The empty React project configured with Vite, Tailwind, React Router, and the test toolchain. One working page proves the setup is right.

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.jsx`
- Create: `frontend/src/App.jsx`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "prism-frontend",
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "axios": "^1.7.3",
    "zustand": "^4.5.4"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.3.1",
    "vite": "^5.3.5",
    "tailwindcss": "^3.4.7",
    "autoprefixer": "^10.4.19",
    "postcss": "^8.4.40",
    "vitest": "^2.0.5",
    "@vitest/ui": "^2.0.5",
    "jsdom": "^24.1.1",
    "@testing-library/react": "^16.0.0",
    "@testing-library/jest-dom": "^6.4.6",
    "@testing-library/user-event": "^14.5.2",
    "msw": "^2.3.4"
  }
}
```

- [ ] **Step 2: Install dependencies**

```bash
cd frontend
npm install
```

- [ ] **Step 3: Create `frontend/vite.config.js`**

```js
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: './src/tests/setup.js',
  },
  server: {
    port: 5173,
    // Proxy API calls to the backend so you don't get CORS errors in dev
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
```

- [ ] **Step 4: Create `frontend/tailwind.config.js`**

```js
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Dark theme palette used throughout the platform
        surface: {
          900: '#0f1117',
          800: '#0f172a',
          700: '#1e293b',
          600: '#334155',
        },
      },
    },
  },
  plugins: [],
}
```

- [ ] **Step 5: Create `frontend/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Verity Prism — IDP Platform</title>
  </head>
  <body class="bg-slate-900 text-slate-100 min-h-screen">
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 6: Create `frontend/src/main.jsx`**

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

- [ ] **Step 7: Create `frontend/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] **Step 8: Create `frontend/src/App.jsx`**

```jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Login from './pages/Login'
import WorkspacesHome from './pages/WorkspacesHome'
import WorkspaceLayout from './pages/workspace/WorkspaceLayout'
import Overview from './pages/workspace/Overview'
import Documents from './pages/workspace/Documents'
import Search from './pages/workspace/Search'
import Entities from './pages/workspace/Entities'
import Transactions from './pages/workspace/Transactions'
import Findings from './pages/workspace/Findings'
import Leads from './pages/workspace/Leads'
import AIChat from './pages/workspace/AIChat'
import useAuthStore from './store/auth'

// ProtectedRoute checks if the user is logged in.
// If not, it sends them to /login.
function ProtectedRoute({ children }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/workspaces" element={
          <ProtectedRoute><WorkspacesHome /></ProtectedRoute>
        } />
        <Route path="/workspaces/:workspaceId" element={
          <ProtectedRoute><WorkspaceLayout /></ProtectedRoute>
        }>
          <Route index element={<Overview />} />
          <Route path="documents" element={<Documents />} />
          <Route path="search" element={<Search />} />
          <Route path="entities" element={<Entities />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="findings" element={<Findings />} />
          <Route path="leads" element={<Leads />} />
          <Route path="chat" element={<AIChat />} />
        </Route>
        <Route path="*" element={<Navigate to="/workspaces" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 9: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-slim
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]
```

- [ ] **Step 10: Create the test setup files**

`frontend/src/tests/setup.js`:
```js
import '@testing-library/jest-dom'
```

`frontend/src/tests/mocks/handlers.js`:
```js
import { http, HttpResponse } from 'msw'

// These mock the backend API responses during tests.
// Add handlers here as you build each feature.
export const handlers = [
  http.post('/auth/login', () => {
    return HttpResponse.json({ access_token: 'test-token', token_type: 'bearer' })
  }),
  http.get('/workspaces/', () => {
    return HttpResponse.json([
      {
        id: 'ws-1',
        name: 'Do Good In His Name Inc',
        subject_name: 'Karen Homan',
        vertical: 'fraud',
        status: 'active',
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      }
    ])
  }),
]
```

`frontend/src/tests/mocks/server.js`:
```js
import { setupServer } from 'msw/node'
import { handlers } from './handlers'

export const server = setupServer(...handlers)
```

- [ ] **Step 11: Update `frontend/src/tests/setup.js` to start MSW**

```js
import '@testing-library/jest-dom'
import { server } from './mocks/server'

// Start the mock server before all tests
beforeAll(() => server.listen())
// Reset handlers between tests so one test doesn't affect another
afterEach(() => server.resetHandlers())
// Clean up after all tests
afterAll(() => server.close())
```

- [ ] **Step 12: Add frontend to `docker-compose.yml`**

Add this service to your existing `docker-compose.yml`:

```yaml
  frontend:
    build: ./frontend
    ports:
      - "5173:5173"
    environment:
      VITE_API_URL: http://localhost:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - backend
```

- [ ] **Step 13: Run the dev server and verify**

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173` — you should see a blank dark page. No errors in the console. That means Vite, Tailwind, and React are all wired up correctly.

- [ ] **Step 14: Commit**

```bash
git add frontend/
git commit -m "feat: React frontend scaffold with Vite, Tailwind, React Router, and Vitest"
```

---

## Task 2: API Client + Auth Store

**What you're building:** The two foundational pieces everything else depends on. The API client adds the auth token to every request automatically. The auth store holds the logged-in user's state.

**Files:**
- Create: `frontend/src/api/client.js`
- Create: `frontend/src/api/auth.js`
- Create: `frontend/src/store/auth.js`

- [ ] **Step 1: Create `frontend/src/api/client.js`**

```js
import axios from 'axios'
import useAuthStore from '../store/auth'

// Create one Axios instance that all API functions use.
// The base URL points to the backend — in dev it's proxied through Vite.
const client = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
})

// This interceptor runs before every request.
// It reads the JWT token from the auth store and adds it to the Authorization header.
// This means you never have to manually add auth headers in your API functions.
client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// This interceptor runs when the server returns an error.
// A 401 means the token expired — log the user out automatically.
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default client
```

- [ ] **Step 2: Create `frontend/src/store/auth.js`**

```js
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

// Zustand is a simple state management library.
// 'persist' saves the state to localStorage so the user stays logged in
// after they refresh the page.
const useAuthStore = create(
  persist(
    (set) => ({
      token: null,
      user: null,
      login: (token, user) => set({ token, user }),
      logout: () => set({ token: null, user: null }),
    }),
    { name: 'catalyst-auth' }  // localStorage key
  )
)

export default useAuthStore
```

- [ ] **Step 3: Create `frontend/src/api/auth.js`**

```js
import client from './client'

export const register = (email, password, fullName) =>
  client.post('/auth/register', { email, password, full_name: fullName })

export const login = (email, password) =>
  client.post('/auth/login', { email, password })
```

- [ ] **Step 4: Create the remaining API files**

`frontend/src/api/workspaces.js`:
```js
import client from './client'

export const listWorkspaces = () => client.get('/workspaces/')
export const createWorkspace = (data) => client.post('/workspaces/', data)
export const getWorkspace = (id) => client.get(`/workspaces/${id}`)
export const updateWorkspace = (id, data) => client.patch(`/workspaces/${id}`, data)
```

`frontend/src/api/documents.js`:
```js
import client from './client'

export const listDocuments = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/documents`)

export const uploadDocument = (workspaceId, file) => {
  const form = new FormData()
  form.append('file', file)
  return client.post(`/workspaces/${workspaceId}/documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const getDocument = (workspaceId, documentId) =>
  client.get(`/workspaces/${workspaceId}/documents/${documentId}`)

export const getExtractions = (workspaceId, documentId) =>
  client.get(`/workspaces/${workspaceId}/documents/${documentId}/extractions`)
```

`frontend/src/api/search.js`:
```js
import client from './client'

export const search = (workspaceId, query) =>
  client.post(`/workspaces/${workspaceId}/search`, { query })
```

`frontend/src/api/entities.js`:
```js
import client from './client'

export const listEntities = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/entities`)
export const createEntity = (workspaceId, data) =>
  client.post(`/workspaces/${workspaceId}/entities`, data)
export const updateEntity = (workspaceId, id, data) =>
  client.patch(`/workspaces/${workspaceId}/entities/${id}`, data)
export const deleteEntity = (workspaceId, id) =>
  client.delete(`/workspaces/${workspaceId}/entities/${id}`)
export const listRelationships = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/relationships`)
export const createRelationship = (workspaceId, data) =>
  client.post(`/workspaces/${workspaceId}/relationships`, data)
```

`frontend/src/api/transactions.js`:
```js
import client from './client'

export const listTransactions = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/transactions`)
export const createTransaction = (workspaceId, data) =>
  client.post(`/workspaces/${workspaceId}/transactions`, data)
```

`frontend/src/api/findings.js`:
```js
import client from './client'

export const getSignalTypes = () => client.get('/signal-types')
export const listFindings = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/findings`)
export const createFinding = (workspaceId, data) =>
  client.post(`/workspaces/${workspaceId}/findings`, data)
export const updateFinding = (workspaceId, id, data) =>
  client.patch(`/workspaces/${workspaceId}/findings/${id}`, data)
```

`frontend/src/api/leads.js`:
```js
import client from './client'

export const listLeads = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/leads`)
export const createLead = (workspaceId, data) =>
  client.post(`/workspaces/${workspaceId}/leads`, data)
export const updateLead = (workspaceId, id, data) =>
  client.patch(`/workspaces/${workspaceId}/leads/${id}`, data)
```

`frontend/src/api/notes.js`:
```js
import client from './client'

export const listNotes = (workspaceId, entityType, entityId) =>
  client.get(`/workspaces/${workspaceId}/notes`, {
    params: { entity_type: entityType, entity_id: entityId }
  })
export const createNote = (workspaceId, data) =>
  client.post(`/workspaces/${workspaceId}/notes`, data)
```

`frontend/src/api/ai.js`:
```js
import client from './client'

export const listConversations = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/conversations`)
export const createConversation = (workspaceId) =>
  client.post(`/workspaces/${workspaceId}/conversations`)
export const listMessages = (workspaceId, conversationId) =>
  client.get(`/workspaces/${workspaceId}/conversations/${conversationId}/messages`)
export const sendMessage = (workspaceId, conversationId, content) =>
  client.post(`/workspaces/${workspaceId}/conversations/${conversationId}/messages`, { content })
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/ frontend/src/store/
git commit -m "feat: API client with auto-auth headers and Zustand auth store"
```

---

## Task 3: Login Page

**Files:**
- Create: `frontend/src/pages/Login.jsx`
- Create: `frontend/src/tests/test_login.jsx`

- [ ] **Step 1: Write failing test — `frontend/src/tests/test_login.jsx`**

```jsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import Login from '../pages/Login'

const renderLogin = () =>
  render(<MemoryRouter><Login /></MemoryRouter>)

test('renders email and password fields', () => {
  renderLogin()
  expect(screen.getByPlaceholderText(/email/i)).toBeInTheDocument()
  expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument()
})

test('shows error on wrong credentials', async () => {
  server.use(
    http.post('/auth/login', () =>
      HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 })
    )
  )
  renderLogin()
  fireEvent.change(screen.getByPlaceholderText(/email/i), {
    target: { value: 'wrong@example.com' }
  })
  fireEvent.change(screen.getByPlaceholderText(/password/i), {
    target: { value: 'wrongpass' }
  })
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }))
  await waitFor(() =>
    expect(screen.getByText(/invalid credentials/i)).toBeInTheDocument()
  )
})
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd frontend && npm test
```

- [ ] **Step 3: Create `frontend/src/pages/Login.jsx`**

```jsx
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/auth'
import useAuthStore from '../store/auth'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const setAuth = useAuthStore((s) => s.login)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await login(email, password)
      setAuth(res.data.access_token, null)
      navigate('/workspaces')
    } catch (err) {
      setError(err.response?.data?.detail || 'Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex items-center justify-center">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-white">Verity Prism</h1>
          <p className="text-slate-400 text-sm mt-1">Intelligent Document Processing</p>
        </div>
        <form onSubmit={handleSubmit} className="bg-slate-800 rounded-xl p-8 space-y-4">
          <div>
            <label className="block text-sm text-slate-400 mb-1">Email</label>
            <input
              type="email"
              placeholder="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2
                         text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              required
            />
          </div>
          <div>
            <label className="block text-sm text-slate-400 mb-1">Password</label>
            <input
              type="password"
              placeholder="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2
                         text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
              required
            />
          </div>
          {error && <p className="text-red-400 text-sm">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-50
                       text-white font-medium py-2 rounded-lg transition-colors"
          >
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run tests**

```bash
npm test
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Login.jsx frontend/src/tests/test_login.jsx
git commit -m "feat: login page with error handling"
```

---

## Task 4: Shared Components + Layout Shell

**Files:**
- Create: `frontend/src/components/shared/Badge.jsx`
- Create: `frontend/src/components/shared/EmptyState.jsx`
- Create: `frontend/src/components/shared/LoadingSpinner.jsx`
- Create: `frontend/src/components/layout/AppShell.jsx`
- Create: `frontend/src/components/layout/WorkspaceSidebar.jsx`

- [ ] **Step 1: Create `frontend/src/components/shared/Badge.jsx`**

```jsx
// Severity and status badges used throughout the platform.
// severity prop: 'critical' | 'high' | 'medium' | 'low'
// status prop: 'active' | 'open' | 'confirmed' | 'pending' | 'complete' | 'closed'
const colors = {
  critical: 'bg-red-900 text-red-300',
  high: 'bg-orange-900 text-orange-300',
  medium: 'bg-yellow-900 text-yellow-300',
  low: 'bg-slate-700 text-slate-300',
  active: 'bg-green-900 text-green-300',
  open: 'bg-blue-900 text-blue-300',
  confirmed: 'bg-red-900 text-red-300',
  pending: 'bg-slate-700 text-slate-300',
  complete: 'bg-green-900 text-green-300',
  closed: 'bg-slate-700 text-slate-400',
}

export default function Badge({ label }) {
  const key = label?.toLowerCase()
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[key] || 'bg-slate-700 text-slate-300'}`}>
      {label}
    </span>
  )
}
```

- [ ] **Step 2: Create `frontend/src/components/shared/EmptyState.jsx`**

```jsx
export default function EmptyState({ message, action, onAction }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 text-center">
      <p className="text-slate-400 mb-4">{message}</p>
      {action && (
        <button
          onClick={onAction}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm"
        >
          {action}
        </button>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/components/shared/LoadingSpinner.jsx`**

```jsx
export default function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center py-20">
      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
}
```

- [ ] **Step 4: Create `frontend/src/components/layout/AppShell.jsx`**

```jsx
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { search } from '../../api/search'
import useAuthStore from '../../store/auth'

export default function AppShell({ children }) {
  const [query, setQuery] = useState('')
  const [searching, setSearching] = useState(false)
  const logout = useAuthStore((s) => s.logout)
  const navigate = useNavigate()
  const { workspaceId } = useParams()

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!query.trim() || !workspaceId) return
    setSearching(true)
    try {
      navigate(`/workspaces/${workspaceId}/search?q=${encodeURIComponent(query)}`)
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="min-h-screen bg-slate-900 flex flex-col">
      {/* Top navigation bar */}
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-3 flex items-center gap-4">
        <span className="text-white font-bold text-lg shrink-0">Verity Prism</span>
        {/* NLP Search bar — the most important UI element */}
        <form onSubmit={handleSearch} className="flex-1 max-w-2xl">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search in plain English — e.g. 'find all deeds where consideration was zero'"
            className="w-full bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-sm
                       text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
          />
        </form>
        <button
          onClick={() => { logout(); navigate('/login') }}
          className="text-slate-400 hover:text-white text-sm ml-auto shrink-0"
        >
          Sign out
        </button>
      </header>
      <main className="flex-1 flex">
        {children}
      </main>
    </div>
  )
}
```

- [ ] **Step 5: Create `frontend/src/components/layout/WorkspaceSidebar.jsx`**

```jsx
import { NavLink, useParams } from 'react-router-dom'

const sections = [
  { path: '', label: 'Overview', icon: '📊', end: true },
  { path: 'documents', label: 'Documents', icon: '📄' },
  { path: 'search', label: 'Search', icon: '🔍' },
  { path: 'entities', label: 'Entities', icon: '🏛' },
  { path: 'transactions', label: 'Transactions', icon: '💰' },
  { path: 'findings', label: 'Findings', icon: '🚨' },
  { path: 'leads', label: 'Leads', icon: '🔬' },
  { path: 'chat', label: 'AI Chat', icon: '🤖' },
]

export default function WorkspaceSidebar() {
  const { workspaceId } = useParams()

  return (
    <nav className="w-48 bg-slate-900 border-r border-slate-800 p-3 flex flex-col gap-1 shrink-0">
      {sections.map(({ path, label, icon, end }) => (
        <NavLink
          key={label}
          to={`/workspaces/${workspaceId}${path ? `/${path}` : ''}`}
          end={end}
          className={({ isActive }) =>
            `flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-colors
             ${isActive
               ? 'bg-slate-700 text-white'
               : 'text-slate-400 hover:text-white hover:bg-slate-800'
             }`
          }
        >
          <span>{icon}</span>
          <span>{label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/
git commit -m "feat: shared Badge, EmptyState, LoadingSpinner components and AppShell + sidebar layout"
```

---

## Task 5: Workspaces Home + Workspace Layout

**Files:**
- Create: `frontend/src/pages/WorkspacesHome.jsx`
- Create: `frontend/src/pages/workspace/WorkspaceLayout.jsx`
- Create: `frontend/src/tests/test_workspaces_home.jsx`

- [ ] **Step 1: Write failing test — `frontend/src/tests/test_workspaces_home.jsx`**

```jsx
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import WorkspacesHome from '../pages/WorkspacesHome'

test('displays list of workspaces', async () => {
  render(<MemoryRouter><WorkspacesHome /></MemoryRouter>)
  await waitFor(() =>
    expect(screen.getByText('Do Good In His Name Inc')).toBeInTheDocument()
  )
})

test('shows Karen Homan as subject', async () => {
  render(<MemoryRouter><WorkspacesHome /></MemoryRouter>)
  await waitFor(() =>
    expect(screen.getByText(/karen homan/i)).toBeInTheDocument()
  )
})
```

- [ ] **Step 2: Create `frontend/src/pages/WorkspacesHome.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { listWorkspaces, createWorkspace } from '../api/workspaces'
import AppShell from '../components/layout/AppShell'
import Badge from '../components/shared/Badge'
import LoadingSpinner from '../components/shared/LoadingSpinner'

export default function WorkspacesHome() {
  const [workspaces, setWorkspaces] = useState([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const navigate = useNavigate()

  useEffect(() => {
    listWorkspaces()
      .then((res) => setWorkspaces(res.data))
      .finally(() => setLoading(false))
  }, [])

  const handleCreate = async () => {
    const name = prompt('Workspace name:')
    if (!name) return
    setCreating(true)
    try {
      const res = await createWorkspace({ name, vertical: 'fraud' })
      navigate(`/workspaces/${res.data.id}`)
    } finally {
      setCreating(false)
    }
  }

  return (
    <AppShell>
      <div className="flex-1 p-8 max-w-4xl mx-auto w-full">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-xl font-bold text-white">Workspaces</h1>
          <button
            onClick={handleCreate}
            disabled={creating}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm"
          >
            + New Workspace
          </button>
        </div>
        {loading ? <LoadingSpinner /> : (
          <div className="space-y-3">
            {workspaces.map((ws) => (
              <Link
                key={ws.id}
                to={`/workspaces/${ws.id}`}
                className="block bg-slate-800 border border-slate-700 hover:border-slate-500
                           rounded-xl p-5 transition-colors"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-white font-semibold">{ws.name}</h2>
                    {ws.subject_name && (
                      <p className="text-slate-400 text-sm mt-1">Subject: {ws.subject_name}</p>
                    )}
                    {ws.jurisdiction && (
                      <p className="text-slate-500 text-xs mt-0.5">{ws.jurisdiction}</p>
                    )}
                  </div>
                  <Badge label={ws.status} />
                </div>
              </Link>
            ))}
            {workspaces.length === 0 && (
              <p className="text-slate-400 text-center py-12">
                No workspaces yet. Create one to get started.
              </p>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
```

- [ ] **Step 3: Create `frontend/src/pages/workspace/WorkspaceLayout.jsx`**

```jsx
import { Outlet } from 'react-router-dom'
import AppShell from '../../components/layout/AppShell'
import WorkspaceSidebar from '../../components/layout/WorkspaceSidebar'

// WorkspaceLayout wraps all 8 workspace sections.
// The <Outlet /> is where React Router renders the active section.
export default function WorkspaceLayout() {
  return (
    <AppShell>
      <WorkspaceSidebar />
      <div className="flex-1 overflow-auto p-6">
        <Outlet />
      </div>
    </AppShell>
  )
}
```

- [ ] **Step 4: Run tests**

```bash
npm test
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/
git commit -m "feat: workspaces home with create button and workspace layout shell"
```

---

## Task 6: Overview, Documents, and Search Sections

These three are the most important sections — Overview is the first thing you see, Documents is the core IDP action, and Search is the primary feature.

**Files:**
- Create: `frontend/src/pages/workspace/Overview.jsx`
- Create: `frontend/src/pages/workspace/Documents.jsx`
- Create: `frontend/src/components/documents/DropZone.jsx`
- Create: `frontend/src/components/documents/ExtractionTable.jsx`
- Create: `frontend/src/pages/workspace/Search.jsx`
- Create: `frontend/src/tests/test_documents.jsx`
- Create: `frontend/src/tests/test_search.jsx`

- [ ] **Step 1: Write failing test — `frontend/src/tests/test_documents.jsx`**

```jsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import Documents from '../pages/workspace/Documents'

const renderDocuments = () =>
  render(
    <MemoryRouter initialEntries={['/workspaces/ws-1/documents']}>
      <Routes>
        <Route path="/workspaces/:workspaceId/documents" element={<Documents />} />
      </Routes>
    </MemoryRouter>
  )

test('shows upload area', () => {
  renderDocuments()
  expect(screen.getByText(/drag and drop/i)).toBeInTheDocument()
})

test('displays document list after upload', async () => {
  server.use(
    http.get('/workspaces/ws-1/documents', () =>
      HttpResponse.json([{
        id: 'doc-1',
        filename: '2022-09-15_DEED_DoGoodRealEstate_47-Patterson.pdf',
        original_filename: 'scan0047.pdf',
        detected_doc_type: 'DEED',
        extraction_status: 'complete',
        uploaded_at: '2026-01-01T00:00:00Z',
      }])
    )
  )
  renderDocuments()
  await waitFor(() =>
    expect(screen.getByText(/2022-09-15_DEED/)).toBeInTheDocument()
  )
})
```

- [ ] **Step 2: Write failing test — `frontend/src/tests/test_search.jsx`**

```jsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import Search from '../pages/workspace/Search'

const renderSearch = () =>
  render(
    <MemoryRouter initialEntries={['/workspaces/ws-1/search']}>
      <Routes>
        <Route path="/workspaces/:workspaceId/search" element={<Search />} />
      </Routes>
    </MemoryRouter>
  )

test('shows search input', () => {
  renderSearch()
  expect(screen.getByPlaceholderText(/plain english/i)).toBeInTheDocument()
})

test('displays results after search', async () => {
  server.use(
    http.post('/workspaces/ws-1/search', () =>
      HttpResponse.json({
        query: 'deeds with zero consideration',
        result_count: 1,
        results: [{
          document_id: 'doc-1',
          filename: '2023-09-22_DEED_Mescher_13-Trinity-Zero.pdf',
          detected_doc_type: 'DEED',
          matched_fields: { consideration_amount: '0', grantee_name: 'Mescher Family' },
        }]
      })
    )
  )
  renderSearch()
  const input = screen.getByPlaceholderText(/plain english/i)
  await userEvent.type(input, 'deeds with zero consideration')
  await userEvent.keyboard('{Enter}')
  await waitFor(() =>
    expect(screen.getByText(/Mescher/)).toBeInTheDocument()
  )
})
```

- [ ] **Step 3: Create `frontend/src/components/documents/DropZone.jsx`**

```jsx
import { useCallback, useState } from 'react'

export default function DropZone({ onFile, uploading }) {
  const [dragging, setDragging] = useState(false)

  const handleDrop = useCallback((e) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) onFile(file)
  }, [onFile])

  const handleChange = (e) => {
    const file = e.target.files[0]
    if (file) onFile(file)
  }

  return (
    <label
      onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`block border-2 border-dashed rounded-xl p-10 text-center cursor-pointer
                  transition-colors ${dragging
                    ? 'border-blue-400 bg-blue-950'
                    : 'border-slate-600 hover:border-slate-400'
                  }`}
    >
      <input type="file" className="hidden" onChange={handleChange} accept=".pdf,.png,.jpg,.jpeg,.csv,.txt,.xml" />
      <p className="text-slate-400 text-sm">
        {uploading ? 'Uploading and extracting...' : 'Drag and drop a file here, or click to browse'}
      </p>
      <p className="text-slate-600 text-xs mt-2">PDF, images, spreadsheets, XML</p>
    </label>
  )
}
```

- [ ] **Step 4: Create `frontend/src/components/documents/ExtractionTable.jsx`**

```jsx
// Shows all extracted fields for a document with confidence scores.
// Low confidence fields (< 0.7) are highlighted for review.
export default function ExtractionTable({ extractions }) {
  if (!extractions?.length) return <p className="text-slate-500 text-sm">No extractions yet.</p>

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-slate-500 border-b border-slate-700">
          <th className="pb-2 font-medium">Field</th>
          <th className="pb-2 font-medium">Value</th>
          <th className="pb-2 font-medium text-right">Confidence</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-800">
        {extractions.map((e) => (
          <tr key={e.id} className={e.confidence < 0.7 ? 'bg-yellow-950' : ''}>
            <td className="py-2 text-slate-400 pr-4">{e.field_name}</td>
            <td className="py-2 text-white">{e.field_value || '—'}</td>
            <td className="py-2 text-right">
              <span className={`text-xs ${e.confidence >= 0.9 ? 'text-green-400' : e.confidence >= 0.7 ? 'text-yellow-400' : 'text-red-400'}`}>
                {Math.round(e.confidence * 100)}%
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

- [ ] **Step 5: Create `frontend/src/pages/workspace/Documents.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listDocuments, uploadDocument, getExtractions } from '../../api/documents'
import DropZone from '../../components/documents/DropZone'
import ExtractionTable from '../../components/documents/ExtractionTable'
import Badge from '../../components/shared/Badge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

export default function Documents() {
  const { workspaceId } = useParams()
  const [documents, setDocuments] = useState([])
  const [selected, setSelected] = useState(null)
  const [extractions, setExtractions] = useState([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)

  useEffect(() => {
    listDocuments(workspaceId).then((r) => setDocuments(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  const handleFile = async (file) => {
    setUploading(true)
    try {
      const res = await uploadDocument(workspaceId, file)
      setDocuments((prev) => [res.data, ...prev])
      handleSelect(res.data)
    } finally {
      setUploading(false)
    }
  }

  const handleSelect = async (doc) => {
    setSelected(doc)
    const res = await getExtractions(workspaceId, doc.id)
    setExtractions(res.data)
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="flex gap-6 h-full">
      {/* Left: upload + document list */}
      <div className="w-80 shrink-0 space-y-4">
        <DropZone onFile={handleFile} uploading={uploading} />
        <div className="space-y-2">
          {documents.map((doc) => (
            <button
              key={doc.id}
              onClick={() => handleSelect(doc)}
              className={`w-full text-left p-3 rounded-lg border transition-colors ${
                selected?.id === doc.id
                  ? 'border-blue-500 bg-slate-800'
                  : 'border-slate-700 bg-slate-800 hover:border-slate-500'
              }`}
            >
              <p className="text-white text-xs font-mono truncate">{doc.filename}</p>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-slate-500 text-xs">{doc.detected_doc_type || 'Unknown'}</span>
                <Badge label={doc.extraction_status} />
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Right: extracted fields for selected document */}
      <div className="flex-1">
        {selected ? (
          <div>
            <h2 className="text-white font-semibold mb-1">{selected.filename}</h2>
            <p className="text-slate-500 text-xs mb-4">Original: {selected.original_filename}</p>
            <ExtractionTable extractions={extractions} />
          </div>
        ) : (
          <p className="text-slate-500 text-sm">Select a document to view its extracted fields.</p>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Create `frontend/src/pages/workspace/Search.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { search } from '../../api/search'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

export default function Search() {
  const { workspaceId } = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const [query, setQuery] = useState(searchParams.get('q') || '')
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(false)

  // If the search bar in AppShell set a ?q= param, run the search automatically
  useEffect(() => {
    const q = searchParams.get('q')
    if (q) { setQuery(q); runSearch(q) }
  }, [])

  const runSearch = async (q) => {
    if (!q.trim()) return
    setLoading(true)
    try {
      const res = await search(workspaceId, q)
      setResults(res.data)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    setSearchParams({ q: query })
    runSearch(query)
  }

  return (
    <div className="max-w-3xl">
      <form onSubmit={handleSubmit} className="flex gap-3 mb-6">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search in plain English — e.g. 'find all deeds where consideration was zero'"
          className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-3
                     text-white placeholder-slate-400 focus:outline-none focus:border-blue-500"
        />
        <button type="submit" className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-3 rounded-lg">
          Search
        </button>
      </form>

      {loading && <LoadingSpinner />}

      {results && !loading && (
        <div>
          <p className="text-slate-400 text-sm mb-4">
            {results.result_count} result{results.result_count !== 1 ? 's' : ''} for "{results.query}"
          </p>
          <div className="space-y-3">
            {results.results.map((r) => (
              <div key={r.document_id} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
                <div className="flex items-center gap-3 mb-3">
                  <span className="text-slate-500 text-xs bg-slate-700 px-2 py-0.5 rounded">
                    {r.detected_doc_type || 'Unknown'}
                  </span>
                  <p className="text-white text-sm font-mono">{r.filename}</p>
                </div>
                {/* Show matched fields as key-value pairs */}
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(r.matched_fields || {}).map(([field, value]) => (
                    <div key={field} className="bg-slate-700 rounded p-2">
                      <p className="text-slate-400 text-xs">{field.replace(/_/g, ' ')}</p>
                      <p className="text-white text-sm mt-0.5">{value}</p>
                    </div>
                  ))}
                </div>
              </div>
            ))}
            {results.result_count === 0 && (
              <p className="text-slate-500 text-center py-8">No documents matched that search.</p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 7: Create `frontend/src/pages/workspace/Overview.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getWorkspace } from '../../api/workspaces'
import { listDocuments } from '../../api/documents'
import { listEntities } from '../../api/entities'
import { listFindings } from '../../api/findings'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import Badge from '../../components/shared/Badge'

export default function Overview() {
  const { workspaceId } = useParams()
  const [workspace, setWorkspace] = useState(null)
  const [stats, setStats] = useState({ documents: 0, entities: 0, findings: 0 })
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      getWorkspace(workspaceId),
      listDocuments(workspaceId),
      listEntities(workspaceId),
      listFindings(workspaceId),
    ]).then(([ws, docs, ents, findings]) => {
      setWorkspace(ws.data)
      setStats({
        documents: docs.data.length,
        entities: ents.data.length,
        findings: findings.data.length,
      })
    }).finally(() => setLoading(false))
  }, [workspaceId])

  if (loading) return <LoadingSpinner />

  return (
    <div className="max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-bold text-white">{workspace?.name}</h1>
        {workspace?.subject_name && (
          <p className="text-slate-400 text-sm mt-1">Subject: {workspace.subject_name}</p>
        )}
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'Documents', value: stats.documents, color: 'text-blue-400' },
          { label: 'Entities', value: stats.entities, color: 'text-purple-400' },
          { label: 'Findings', value: stats.findings, color: 'text-red-400' },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-slate-800 rounded-xl p-5 text-center">
            <p className={`text-3xl font-bold ${color}`}>{value}</p>
            <p className="text-slate-400 text-sm mt-1">{label}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 8: Run tests**

```bash
npm test
```

Expected: All tests PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/workspace/ frontend/src/components/documents/ \
        frontend/src/tests/
git commit -m "feat: overview, document upload with extraction viewer, and NLP search"
```

---

## Task 7: Remaining Sections — Entities, Transactions, Findings, Leads

These four follow the same list + create pattern. Build them all in one commit.

**Files:**
- Create: `frontend/src/pages/workspace/Entities.jsx`
- Create: `frontend/src/pages/workspace/Transactions.jsx`
- Create: `frontend/src/pages/workspace/Findings.jsx`
- Create: `frontend/src/pages/workspace/Leads.jsx`

- [ ] **Step 1: Create `frontend/src/pages/workspace/Entities.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listEntities } from '../../api/entities'
import Badge from '../../components/shared/Badge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

const TYPES = ['person', 'organization', 'property', 'financial_account']

export default function Entities() {
  const { workspaceId } = useParams()
  const [entities, setEntities] = useState([])
  const [activeTab, setActiveTab] = useState('person')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listEntities(workspaceId).then((r) => setEntities(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  const filtered = entities.filter((e) => e.type === activeTab)

  if (loading) return <LoadingSpinner />

  return (
    <div>
      <div className="flex gap-2 mb-6">
        {TYPES.map((t) => (
          <button
            key={t}
            onClick={() => setActiveTab(t)}
            className={`px-4 py-2 rounded-lg text-sm capitalize transition-colors ${
              activeTab === t ? 'bg-blue-600 text-white' : 'bg-slate-800 text-slate-400 hover:text-white'
            }`}
          >
            {t}s ({entities.filter((e) => e.type === t).length})
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState message={`No ${activeTab}s added yet.`} />
      ) : (
        <div className="space-y-3">
          {filtered.map((e) => (
            <div key={e.id} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
              <div className="flex items-center justify-between">
                <h3 className="text-white font-medium">{e.name}</h3>
                <Badge label={e.status} />
              </div>
              {Object.keys(e.data || {}).length > 0 && (
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {Object.entries(e.data).map(([k, v]) => (
                    <div key={k}>
                      <span className="text-slate-500 text-xs">{k.replace(/_/g, ' ')}: </span>
                      <span className="text-slate-300 text-xs">{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Create `frontend/src/pages/workspace/Transactions.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listTransactions } from '../../api/transactions'
import Badge from '../../components/shared/Badge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

function overpaymentPct(paid, appraised) {
  if (!paid || !appraised || appraised === 0) return null
  return Math.round(((paid - appraised) / appraised) * 100)
}

export default function Transactions() {
  const { workspaceId } = useParams()
  const [transactions, setTransactions] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listTransactions(workspaceId).then((r) => setTransactions(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  if (loading) return <LoadingSpinner />
  if (!transactions.length) return <EmptyState message="No transactions recorded yet." />

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-slate-500 border-b border-slate-700">
            <th className="pb-3 pr-4">Type</th>
            <th className="pb-3 pr-4">Amount Paid</th>
            <th className="pb-3 pr-4">Appraised</th>
            <th className="pb-3 pr-4">Consideration</th>
            <th className="pb-3 pr-4">Date</th>
            <th className="pb-3">Instrument</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800">
          {transactions.map((t) => {
            const pct = overpaymentPct(t.amount_paid, t.appraised_value)
            return (
              <tr key={t.id} className={t.consideration === 'above_market' ? 'bg-red-950' : t.consideration === 'zero' ? 'bg-orange-950' : ''}>
                <td className="py-3 pr-4 capitalize text-white">{t.transaction_type}</td>
                <td className="py-3 pr-4 text-white">
                  {t.amount_paid != null ? `$${Number(t.amount_paid).toLocaleString()}` : '—'}
                </td>
                <td className="py-3 pr-4 text-slate-300">
                  {t.appraised_value != null ? `$${Number(t.appraised_value).toLocaleString()}` : '—'}
                </td>
                <td className="py-3 pr-4">
                  {t.consideration && <Badge label={t.consideration} />}
                  {pct !== null && (
                    <span className={`ml-2 text-xs ${pct > 100 ? 'text-red-400' : pct > 0 ? 'text-yellow-400' : 'text-green-400'}`}>
                      {pct > 0 ? '+' : ''}{pct}%
                    </span>
                  )}
                </td>
                <td className="py-3 pr-4 text-slate-400">{t.transaction_date || '—'}</td>
                <td className="py-3 text-slate-500 text-xs font-mono">{t.instrument_number || '—'}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/pages/workspace/Findings.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listFindings, updateFinding } from '../../api/findings'
import Badge from '../../components/shared/Badge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

export default function Findings() {
  const { workspaceId } = useParams()
  const [findings, setFindings] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listFindings(workspaceId).then((r) => setFindings(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  const handleStatus = async (id, status) => {
    const res = await updateFinding(workspaceId, id, { status })
    setFindings((prev) => prev.map((f) => f.id === id ? res.data : f))
  }

  if (loading) return <LoadingSpinner />
  if (!findings.length) return <EmptyState message="No findings recorded yet." />

  return (
    <div className="space-y-3">
      {findings.map((f) => (
        <div key={f.id} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Badge label={f.severity} />
                <Badge label={f.status} />
              </div>
              <h3 className="text-white font-medium">{f.title}</h3>
              {f.description && <p className="text-slate-400 text-sm mt-1">{f.description}</p>}
            </div>
            <div className="flex gap-2 shrink-0">
              {f.status === 'open' && (
                <>
                  <button onClick={() => handleStatus(f.id, 'confirmed')}
                    className="text-xs bg-green-800 hover:bg-green-700 text-green-200 px-3 py-1 rounded">
                    Confirm
                  </button>
                  <button onClick={() => handleStatus(f.id, 'dismissed')}
                    className="text-xs bg-slate-700 hover:bg-slate-600 text-slate-300 px-3 py-1 rounded">
                    Dismiss
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 4: Create `frontend/src/pages/workspace/Leads.jsx`**

```jsx
import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { listLeads, updateLead } from '../../api/leads'
import Badge from '../../components/shared/Badge'
import LoadingSpinner from '../../components/shared/LoadingSpinner'
import EmptyState from '../../components/shared/EmptyState'

export default function Leads() {
  const { workspaceId } = useParams()
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    listLeads(workspaceId).then((r) => setLeads(r.data)).finally(() => setLoading(false))
  }, [workspaceId])

  const handleStatus = async (id, status) => {
    const res = await updateLead(workspaceId, id, { status })
    setLeads((prev) => prev.map((l) => l.id === id ? res.data : l))
  }

  if (loading) return <LoadingSpinner />
  if (!leads.length) return <EmptyState message="No investigation leads yet." />

  const byStatus = (s) => leads.filter((l) => l.status === s)

  return (
    <div className="space-y-6">
      {[
        { status: 'in_progress', label: 'In Progress' },
        { status: 'pending', label: 'Pending' },
        { status: 'complete', label: 'Complete' },
        { status: 'dead_end', label: 'Dead End' },
      ].map(({ status, label }) => (
        byStatus(status).length > 0 && (
          <div key={status}>
            <h3 className="text-slate-400 text-xs font-medium uppercase tracking-wider mb-3">
              {label} ({byStatus(status).length})
            </h3>
            <div className="space-y-2">
              {byStatus(status).map((l) => (
                <div key={l.id} className="bg-slate-800 border border-slate-700 rounded-lg p-4">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <p className="text-white text-sm">{l.question}</p>
                      {l.source && <p className="text-slate-500 text-xs mt-1">Source: {l.source}</p>}
                      {l.result_summary && <p className="text-slate-300 text-xs mt-2 italic">{l.result_summary}</p>}
                    </div>
                    {status === 'pending' && (
                      <button onClick={() => handleStatus(l.id, 'in_progress')}
                        className="text-xs bg-blue-800 hover:bg-blue-700 text-blue-200 px-3 py-1 rounded shrink-0">
                        Start
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )
      ))}
    </div>
  )
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/workspace/Entities.jsx \
        frontend/src/pages/workspace/Transactions.jsx \
        frontend/src/pages/workspace/Findings.jsx \
        frontend/src/pages/workspace/Leads.jsx
git commit -m "feat: entities, transactions, findings, and leads workspace sections"
```

---

## Task 8: AI Chat Section

**Files:**
- Create: `frontend/src/components/ai/ChatMessage.jsx`
- Create: `frontend/src/components/ai/ChatInput.jsx`
- Create: `frontend/src/pages/workspace/AIChat.jsx`
- Create: `frontend/src/tests/test_ai_chat.jsx`

- [ ] **Step 1: Write failing test — `frontend/src/tests/test_ai_chat.jsx`**

```jsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import AIChat from '../pages/workspace/AIChat'

server.use(
  http.get('/workspaces/ws-1/conversations', () => HttpResponse.json([])),
)

test('shows new conversation button', () => {
  render(
    <MemoryRouter initialEntries={['/workspaces/ws-1/chat']}>
      <Routes>
        <Route path="/workspaces/:workspaceId/chat" element={<AIChat />} />
      </Routes>
    </MemoryRouter>
  )
  expect(screen.getByText(/new conversation/i)).toBeInTheDocument()
})
```

- [ ] **Step 2: Create `frontend/src/components/ai/ChatMessage.jsx`**

```jsx
// A single message bubble in the chat.
// User messages align right, assistant messages align left.
export default function ChatMessage({ role, content }) {
  const isUser = role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div className={`max-w-[75%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
        isUser
          ? 'bg-blue-600 text-white'
          : 'bg-slate-700 text-slate-100'
      }`}>
        {/* Preserve newlines in Claude's response */}
        {content.split('\n').map((line, i) => (
          <p key={i} className={i > 0 ? 'mt-2' : ''}>{line}</p>
        ))}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Create `frontend/src/components/ai/ChatInput.jsx`**

```jsx
import { useState } from 'react'

export default function ChatInput({ onSend, disabled }) {
  const [value, setValue] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!value.trim() || disabled) return
    onSend(value)
    setValue('')
  }

  // Allow Shift+Enter for newlines, Enter to send
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-3 p-4 border-t border-slate-700">
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Ask a question about this workspace... (Enter to send, Shift+Enter for new line)"
        rows={2}
        disabled={disabled}
        className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-4 py-2 text-white
                   placeholder-slate-400 focus:outline-none focus:border-blue-500 resize-none text-sm"
      />
      <button
        type="submit"
        disabled={disabled || !value.trim()}
        className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white px-4
                   rounded-lg self-end py-2 text-sm"
      >
        Send
      </button>
    </form>
  )
}
```

- [ ] **Step 4: Create `frontend/src/pages/workspace/AIChat.jsx`**

```jsx
import { useState, useEffect, useRef } from 'react'
import { useParams } from 'react-router-dom'
import {
  listConversations, createConversation,
  listMessages, sendMessage
} from '../../api/ai'
import ChatMessage from '../../components/ai/ChatMessage'
import ChatInput from '../../components/ai/ChatInput'
import LoadingSpinner from '../../components/shared/LoadingSpinner'

export default function AIChat() {
  const { workspaceId } = useParams()
  const [conversations, setConversations] = useState([])
  const [activeConv, setActiveConv] = useState(null)
  const [messages, setMessages] = useState([])
  const [sending, setSending] = useState(false)
  const [loading, setLoading] = useState(true)
  const bottomRef = useRef(null)

  useEffect(() => {
    listConversations(workspaceId).then((r) => {
      setConversations(r.data)
      if (r.data.length > 0) loadConversation(r.data[0])
    }).finally(() => setLoading(false))
  }, [workspaceId])

  // Scroll to bottom whenever messages change
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const loadConversation = async (conv) => {
    setActiveConv(conv)
    const res = await listMessages(workspaceId, conv.id)
    setMessages(res.data)
  }

  const handleNew = async () => {
    const res = await createConversation(workspaceId)
    setConversations((prev) => [res.data, ...prev])
    setActiveConv(res.data)
    setMessages([])
  }

  const handleSend = async (content) => {
    if (!activeConv) return
    // Show user message immediately for fast feel
    setMessages((prev) => [...prev, { id: 'temp', role: 'user', content }])
    setSending(true)
    try {
      const res = await sendMessage(workspaceId, activeConv.id, content)
      // Replace temp message + add assistant response
      const msgs = await listMessages(workspaceId, activeConv.id)
      setMessages(msgs.data)
      // Update conversation title in sidebar if it was just set
      if (!activeConv.title) {
        const convs = await listConversations(workspaceId)
        setConversations(convs.data)
        const updated = convs.data.find((c) => c.id === activeConv.id)
        if (updated) setActiveConv(updated)
      }
    } finally {
      setSending(false)
    }
  }

  if (loading) return <LoadingSpinner />

  return (
    <div className="flex h-[calc(100vh-8rem)] gap-4">
      {/* Conversation list sidebar */}
      <div className="w-56 shrink-0 space-y-2">
        <button
          onClick={handleNew}
          className="w-full bg-blue-600 hover:bg-blue-700 text-white text-sm py-2 rounded-lg"
        >
          + New Conversation
        </button>
        {conversations.map((c) => (
          <button
            key={c.id}
            onClick={() => loadConversation(c)}
            className={`w-full text-left px-3 py-2 rounded-lg text-sm truncate transition-colors ${
              activeConv?.id === c.id
                ? 'bg-slate-700 text-white'
                : 'text-slate-400 hover:text-white hover:bg-slate-800'
            }`}
          >
            {c.title || 'New conversation'}
          </button>
        ))}
      </div>

      {/* Message area */}
      <div className="flex-1 flex flex-col bg-slate-800 rounded-xl overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4">
          {messages.length === 0 && (
            <p className="text-slate-500 text-sm text-center mt-8">
              Ask a question about this workspace. Claude has access to all entities,
              transactions, documents, and findings.
            </p>
          )}
          {messages.map((m) => (
            <ChatMessage key={m.id} role={m.role} content={m.content} />
          ))}
          {sending && (
            <div className="flex justify-start mb-4">
              <div className="bg-slate-700 rounded-xl px-4 py-3 text-slate-400 text-sm">
                Thinking...
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <ChatInput onSend={handleSend} disabled={sending || !activeConv} />
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Run all tests**

```bash
npm test
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ai/ frontend/src/pages/workspace/AIChat.jsx \
        frontend/src/tests/test_ai_chat.jsx
git commit -m "feat: AI chat with conversation threads, message history, and streaming feel"
```

---

## Task 9: End-to-End Verification

- [ ] **Step 1: Start the full stack**

```bash
docker-compose up --build
```

- [ ] **Step 2: Run the full test suite**

```bash
cd frontend && npm test
cd backend && pytest tests/ -v
```

Expected: All tests pass in both.

- [ ] **Step 3: Manual end-to-end test**

Walk through this path in the browser at `http://localhost:5173`:

1. Register a new account → `/login`
2. Log in → redirected to `/workspaces`
3. Create a workspace: "Do Good In His Name Inc", vertical: fraud
4. Open the workspace → Overview shows 0 documents, 0 entities, 0 findings
5. Go to Documents → upload a PDF → verify it shows a standardized filename and extracted fields
6. Go to Search → type "show me all documents" → verify results appear
7. Go to AI Chat → create a new conversation → ask "what is in this workspace?" → verify Claude responds
8. Sign out → redirected to login

- [ ] **Step 4: Final commit**

```bash
git add .
git commit -m "feat: Phase 1 frontend complete — all sections built and end-to-end verified"
```
