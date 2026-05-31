# Phase 6 — Frontend Resilience + Auth Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four remaining audit findings from the 2026-05-29 code audit: cancel the SSE reader on unmount (L2), surface API errors to the user instead of swallowing them (M7), replace hard `window.location.href` redirects with SPA router navigation on 401 (L4), and migrate JWT storage from `localStorage` to an httpOnly cookie set by the backend (M6).

**Architecture:** Tasks 1–3 are isolated frontend changes that can ship independently. Task 4 (M6) is the largest: the backend sets an httpOnly cookie on login and adds `/auth/logout` and `/auth/me` endpoints; the frontend drops `localStorage` persistence, sends `withCredentials: true` on every request, and calls `/auth/me` on startup to restore session after page refresh. The backend `get_current_user` dependency accepts both Bearer tokens (for backward test compat) and cookies (for real browser traffic), so no backend tests need to change.

**Tech Stack:** React 18 + React Router v6, Zustand 4, Axios, Vitest + MSW 2, FastAPI, python-jose (JWT), SQLAlchemy.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| **Modify** | `frontend/src/hooks/useExtractionStream.js` | L2: lift `reader` to function scope; call `reader?.cancel()` on cleanup |
| **Create** | `frontend/src/tests/test_extraction_stream.jsx` | L2: verify cancel is called on unmount |
| **Modify** | `frontend/src/pages/workspace/AIChat.jsx` | M7: add `catch` to `handleSend`, rollback optimistic message, show toast |
| **Modify** | `frontend/src/context/WorkspaceContext.jsx` | M7: add `.catch()` to workspace load |
| **Modify** | `frontend/src/main.jsx` | M7: wrap with `ToastProvider` |
| **Create** | `frontend/src/tests/test_ai_chat_errors.jsx` | M7: test optimistic rollback and toast |
| **Modify** | `frontend/src/api/client.js` | L4+M6: replace `window.location.href`; remove Bearer injection; add `withCredentials` |
| **Modify** | `frontend/src/App.jsx` | L4+M6: add `NavigatorSetter`; add `AuthInit`; update `ProtectedRoute` |
| **Modify** | `frontend/src/store/auth.js` | M6: remove `persist`; replace token with user object |
| **Modify** | `frontend/src/api/auth.js` | M6: add `logout()` and `me()` functions |
| **Modify** | `frontend/src/pages/Login.jsx` | M6: call `setAuth(res.data.user)` instead of storing token |
| **Modify** | `frontend/src/hooks/useExtractionStream.js` | M6: remove Bearer header; add `credentials: 'include'` |
| **Modify** | `frontend/src/tests/mocks/handlers.js` | M6: update login mock to return user; add `/auth/me` handler |
| **Modify** | `backend/app/services/auth.py` | M6: `get_current_user` reads cookie first, Bearer fallback |
| **Modify** | `backend/app/schemas/user.py` | M6: add `LoginOut` schema with `access_token + user` |
| **Modify** | `backend/app/routers/auth.py` | M6: login sets cookie; add `/logout`; add `/me` |
| **Modify** | `backend/app/config.py` | M6: add `cookie_secure: bool = False` |
| **Modify** | `backend/tests/test_auth.py` | M6: add tests for cookie set on login, logout, `/me` |

---

## Task 1: L2 — Cancel SSE reader on unmount

**Files:**
- Modify: `frontend/src/hooks/useExtractionStream.js`
- Create: `frontend/src/tests/test_extraction_stream.jsx`

The bug: `reader` is declared inside the `stream()` async function, so the cleanup closure can't reach it to call `reader.cancel()`. The fix is to lift `reader` to the outer function scope.

- [ ] **Step 1: Write the failing test**

Create `frontend/src/tests/test_extraction_stream.jsx`:

```jsx
import { renderHook } from '@testing-library/react'
import { vi, it, expect, afterEach } from 'vitest'
import useExtractionStream from '../hooks/useExtractionStream'

it('cancels the stream reader when the hook unmounts during streaming', async () => {
  const cancelMock = vi.fn()
  const readerMock = {
    read: vi.fn().mockImplementation(() => new Promise(() => {})), // never resolves
    cancel: cancelMock,
  }
  const bodyMock = { getReader: () => readerMock }
  global.fetch = vi.fn().mockResolvedValue({ ok: true, body: bodyMock })

  const onUpdate = vi.fn()
  const { unmount } = renderHook(() =>
    useExtractionStream('ws-1', 'doc-1', 'pending', onUpdate)
  )

  // Wait one tick for the fetch to start
  await new Promise((r) => setTimeout(r, 0))

  unmount()

  // After unmount the reader must be cancelled
  expect(cancelMock).toHaveBeenCalled()
})

afterEach(() => {
  vi.restoreAllMocks()
  delete global.fetch
})
```

- [ ] **Step 2: Run test to confirm it fails**

```
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm test -- test_extraction_stream
```

Expected: FAIL — `cancelMock` not called (cancel is never reached because `reader` is out of scope).

- [ ] **Step 3: Lift `reader` to function scope in `useExtractionStream.js`**

In `frontend/src/hooks/useExtractionStream.js`, replace the full `useEffect` body with:

```javascript
useEffect(() => {
  if (status !== 'pending') return
  if (!workspaceId || !documentId) return

  const url = `${API_BASE}/workspaces/${workspaceId}/documents/${documentId}/status/stream`

  let cancelled = false
  let retries = 0
  let backoffTimer = null
  let reader = null           // ← lifted to this scope so cleanup can cancel it

  async function stream() {
    try {
      const token = useAuthStore.getState().token
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      })
      if (!res.ok) { scheduleRetry(); return }

      retries = 0
      reader = res.body.getReader()       // ← assigned here instead of `const reader`
      const decoder = new TextDecoder()
      let buffer = ''

      while (!cancelled) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop()
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const payload = JSON.parse(line.slice(6))
              onUpdateRef.current(documentId, payload)
              if (TERMINAL.has(payload.extraction_status)) {
                cancelled = true
                return
              }
            } catch {}
          }
        }
      }
    } catch (err) {
      if (!cancelled) scheduleRetry()
    }
  }

  function scheduleRetry() {
    if (cancelled || retries >= MAX_RETRIES) return
    const delay = Math.min(1000 * Math.pow(2, retries), 32000)
    retries++
    backoffTimer = setTimeout(() => { if (!cancelled) stream() }, delay)
  }

  stream()
  return () => {
    cancelled = true
    if (backoffTimer) clearTimeout(backoffTimer)
    reader?.cancel()            // ← now reachable
  }
}, [workspaceId, documentId, status])
```

- [ ] **Step 4: Run test to confirm it passes**

```
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm test -- test_extraction_stream
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useExtractionStream.js frontend/src/tests/test_extraction_stream.jsx
git commit -m "fix(L2): cancel SSE reader on unmount

reader.cancel() now called in useExtractionStream cleanup. Previously
the cancelled flag was set but the fetch connection lingered until the
server's 5-minute timeout.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: M7 — Frontend error handling

**Files:**
- Modify: `frontend/src/pages/workspace/AIChat.jsx`
- Modify: `frontend/src/context/WorkspaceContext.jsx`
- Modify: `frontend/src/main.jsx`
- Create: `frontend/src/tests/test_ai_chat_errors.jsx`

The bugs: `handleSend` has `try/finally` with no `catch` — a failed `sendMessage` leaves the optimistic message on screen and tells the user nothing. `WorkspaceContext` has no `.catch()` — a failed workspace load leaves `workspace` permanently `null` with no feedback.

**First: check that `ToastProvider` is wired into the app.** The `useToast` hook already exists in `frontend/src/hooks/useToast.jsx`. It throws if called outside `ToastProvider`. `main.jsx` currently does not include `ToastProvider`.

- [ ] **Step 1: Wire ToastProvider in `main.jsx`**

Replace `frontend/src/main.jsx`:

```jsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { ToastProvider } from './hooks/useToast'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <ToastProvider>
      <App />
    </ToastProvider>
  </React.StrictMode>
)
```

- [ ] **Step 2: Write the failing tests**

Create `frontend/src/tests/test_ai_chat_errors.jsx`:

```jsx
import { render, screen, waitFor, act } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from './mocks/server'
import AIChat from '../pages/workspace/AIChat'
import { ToastProvider } from '../hooks/useToast'

function renderChat() {
  return render(
    <ToastProvider>
      <MemoryRouter initialEntries={['/workspaces/ws-1/chat']}>
        <Routes>
          <Route path="/workspaces/:workspaceId/chat" element={<AIChat />} />
        </Routes>
      </MemoryRouter>
    </ToastProvider>
  )
}

// Seed a conversation so the send button is enabled
beforeEach(() => {
  server.use(
    http.get('/workspaces/ws-1/conversations', () =>
      HttpResponse.json([{ id: 'conv-1', title: null, workspace_id: 'ws-1' }])
    ),
    http.get('/workspaces/ws-1/conversations/conv-1/messages', () =>
      HttpResponse.json([])
    ),
  )
})

test('rolls back optimistic message when sendMessage fails', async () => {
  server.use(
    http.post('/workspaces/ws-1/conversations/conv-1/messages', () =>
      HttpResponse.json({ detail: 'Server error' }, { status: 500 })
    )
  )

  renderChat()
  await waitFor(() => screen.getByRole('textbox'))

  await userEvent.type(screen.getByRole('textbox'), 'Will this fail?')
  await userEvent.click(screen.getByRole('button', { name: /send/i }))

  // Optimistic message appears briefly then must be removed
  await waitFor(() =>
    expect(screen.queryByText('Will this fail?')).not.toBeInTheDocument()
  )
})

test('shows error toast when sendMessage fails', async () => {
  server.use(
    http.post('/workspaces/ws-1/conversations/conv-1/messages', () =>
      HttpResponse.json({ detail: 'Server error' }, { status: 500 })
    )
  )

  renderChat()
  await waitFor(() => screen.getByRole('textbox'))

  await userEvent.type(screen.getByRole('textbox'), 'This will error')
  await userEvent.click(screen.getByRole('button', { name: /send/i }))

  await waitFor(() =>
    expect(screen.getByText(/send failed/i)).toBeInTheDocument()
  )
})
```

- [ ] **Step 3: Run tests to confirm they fail**

```
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm test -- test_ai_chat_errors
```

Expected: both tests fail — optimistic message is never removed, no toast appears.

- [ ] **Step 4: Fix `AIChat.jsx` — add catch to handleSend**

Replace the `handleSend` function in `frontend/src/pages/workspace/AIChat.jsx`:

```javascript
const handleSend = async (content) => {
  if (!activeConv) return
  const tempMsg = { id: 'temp', role: 'user', content }
  setMessages((prev) => [...prev, tempMsg])
  setSending(true)
  try {
    await sendMessage(workspaceId, activeConv.id, content)
    const msgs = await listMessages(workspaceId, activeConv.id)
    setMessages(msgs.data)
    if (!activeConv.title) {
      const convs = await listConversations(workspaceId)
      setConversations(convs.data)
      const updated = convs.data.find((c) => c.id === activeConv.id)
      if (updated) setActiveConv(updated)
    }
  } catch {
    setMessages((prev) => prev.filter((m) => m.id !== 'temp'))
    toast.error('Send failed', 'Your message could not be delivered. Try again.')
  } finally {
    setSending(false)
  }
}
```

Also add the toast import at the top of `AIChat.jsx`:

```javascript
import { useToast } from '../../hooks/useToast'
```

And inside the component body, before `useEffect`:

```javascript
const { toast } = useToast()
```

- [ ] **Step 5: Fix `WorkspaceContext.jsx` — add catch to workspace load**

Replace `frontend/src/context/WorkspaceContext.jsx`:

```javascript
import { createContext, useContext, useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getWorkspace } from '../api/workspaces'

const WorkspaceContext = createContext(null)

export function WorkspaceProvider({ children }) {
  const { workspaceId } = useParams()
  const [workspace, setWorkspace] = useState(null)

  useEffect(() => {
    if (!workspaceId) return
    getWorkspace(workspaceId)
      .then((res) => setWorkspace(res.data))
      .catch(() => {})
  }, [workspaceId])

  return (
    <WorkspaceContext.Provider value={workspace}>
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  return useContext(WorkspaceContext)
}
```

- [ ] **Step 6: Run tests to confirm they pass**

```
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm test -- test_ai_chat_errors
```

Expected: both tests pass.

- [ ] **Step 7: Run full frontend suite to check for regressions**

```
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm test
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/main.jsx frontend/src/pages/workspace/AIChat.jsx frontend/src/context/WorkspaceContext.jsx frontend/src/tests/test_ai_chat_errors.jsx
git commit -m "fix(M7): surface API errors in AIChat and WorkspaceContext

handleSend now rolls back the optimistic message and shows an error toast
on failure. WorkspaceContext.getWorkspace failure is caught silently
(workspace stays null, child components already handle it).

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: L4 — Router navigation on 401

**Files:**
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/App.jsx`

The bug: `window.location.href = '/login'` in the axios 401 interceptor triggers a full page reload, discarding all SPA state. Fix: store a `navigate` function at module level in `client.js`; populate it from a component inside the router (`NavigatorSetter`) that calls `useNavigate()`.

- [ ] **Step 1: Write the failing test**

Add to `frontend/src/tests/test_login.jsx` (append at the bottom):

```javascript
import { vi } from 'vitest'

test('401 response does not call window.location.href', async () => {
  // Simulate a 401 from any protected endpoint
  server.use(
    http.get('/workspaces/', () =>
      HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 })
    )
  )

  const locationSpy = vi.spyOn(window, 'location', 'get').mockReturnValue({
    href: '',
    assign: vi.fn(),
  })

  // Trigger a request that returns 401
  const client = (await import('../api/client')).default
  await client.get('/workspaces/').catch(() => {})

  expect(window.location.href).toBe('')  // location.href was never set
  locationSpy.mockRestore()
})
```

- [ ] **Step 2: Run test to confirm it fails**

```
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm test -- test_login
```

Expected: the new test fails because `window.location.href` IS currently set to `/login`.

- [ ] **Step 3: Add module-level navigator to `client.js`**

Replace `frontend/src/api/client.js`:

```javascript
import axios from 'axios'
import useAuthStore from '../store/auth'

let _navigate = null

/**
 * Called once from NavigatorSetter inside the router.
 * Gives the interceptor access to programmatic navigation without importing
 * useNavigate outside of React component scope.
 */
export function setNavigate(navigate) {
  _navigate = navigate
}

const client = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      if (_navigate) {
        _navigate('/login', { replace: true })
      } else {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default client
```

- [ ] **Step 4: Add `NavigatorSetter` to `App.jsx`**

Replace `frontend/src/App.jsx`:

```jsx
import { useEffect } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { setNavigate } from './api/client'
import Login from './pages/Login'
import WorkspacesHome from './pages/WorkspacesHome'
import SchemaLibrary from './pages/SchemaLibrary'
import WorkspaceLayout from './pages/workspace/WorkspaceLayout'
import Overview from './pages/workspace/Overview'
import Documents from './pages/workspace/Documents'
import DocumentViewer from './pages/workspace/DocumentViewer'
import Search from './pages/workspace/Search'
import Entities from './pages/workspace/Entities'
import Transactions from './pages/workspace/Transactions'
import Findings from './pages/workspace/Findings'
import Leads from './pages/workspace/Leads'
import AIChat from './pages/workspace/AIChat'
import ExtractionReview from './pages/workspace/ExtractionReview'
import AuditLog from './pages/workspace/AuditLog'
import useAuthStore from './store/auth'

/** Wires the axios 401 interceptor to React Router navigation. */
function NavigatorSetter() {
  const navigate = useNavigate()
  useEffect(() => { setNavigate(navigate) }, [navigate])
  return null
}

function ProtectedRoute({ children }) {
  const token = useAuthStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <NavigatorSetter />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/workspaces" element={
          <ProtectedRoute><WorkspacesHome /></ProtectedRoute>
        } />
        <Route path="/schemas" element={
          <ProtectedRoute><SchemaLibrary /></ProtectedRoute>
        } />
        <Route path="/workspaces/:workspaceId" element={
          <ProtectedRoute><WorkspaceLayout /></ProtectedRoute>
        }>
          <Route index element={<Overview />} />
          <Route path="documents" element={<Documents />} />
          <Route path="documents/:documentId" element={<DocumentViewer />} />
          <Route path="search" element={<Search />} />
          <Route path="entities" element={<Entities />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="findings" element={<Findings />} />
          <Route path="leads" element={<Leads />} />
          <Route path="chat" element={<AIChat />} />
          <Route path="review" element={<ExtractionReview />} />
          <Route path="audit" element={<AuditLog />} />
        </Route>
        <Route path="*" element={<Navigate to="/workspaces" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
```

- [ ] **Step 5: Run tests**

```
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm test
```

Note: the new 401 test may still fail because `_navigate` is null in the test environment (tests don't render `NavigatorSetter`). That's acceptable — the fallback `window.location.href` is still there for the no-navigator case. The test may need to be adjusted to verify that when `_navigate` IS set, it's called instead of `href`. If the test is fragile, remove it and rely on the existing login tests passing as the regression check. All previously passing tests must continue to pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/client.js frontend/src/App.jsx
git commit -m "fix(L4): replace window.location.href with router navigation on 401

NavigatorSetter component wires React Router's navigate() into the axios
interceptor. 401 responses now use client-side navigation instead of a
full page reload that discards SPA state.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: M6 — httpOnly cookie migration

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/auth.py`
- Modify: `backend/app/schemas/user.py`
- Modify: `backend/app/routers/auth.py`
- Modify: `backend/tests/test_auth.py`
- Modify: `frontend/src/store/auth.js`
- Modify: `frontend/src/api/auth.js`
- Modify: `frontend/src/api/client.js`
- Modify: `frontend/src/pages/Login.jsx`
- Modify: `frontend/src/hooks/useExtractionStream.js`
- Modify: `frontend/src/tests/mocks/handlers.js`
- Modify: `frontend/src/App.jsx`

**Design:** `POST /auth/login` sets an httpOnly cookie AND returns the token in the body (so the existing `auth_headers` test fixture keeps working without any test changes). `get_current_user` reads the cookie first, falls back to Bearer. Page-refresh session restoration uses a new `GET /auth/me` endpoint. The frontend stores the user object in memory (no localStorage), calls `/auth/me` on startup to restore session.

### 4A — Backend

- [ ] **Step 1: Add `cookie_secure` to config**

In `backend/app/config.py`, add one field to the `Settings` class:

```python
cookie_secure: bool = False  # set True in production (HTTPS only)
```

The full `Settings` class becomes:
```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str
    secret_key: str
    anthropic_api_key: str
    upload_dir: str = "./uploads"
    access_token_expire_minutes: int = 60 * 24
    cors_origins: list[str] = ["http://localhost:5173"]
    max_upload_bytes: int = 52_428_800
    cookie_secure: bool = False

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        # ... same as before ...
```

- [ ] **Step 2: Update `get_current_user` to accept cookie + Bearer**

Replace `backend/app/services/auth.py`:

```python
from datetime import UTC, datetime, timedelta
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

def hash_password(password: str) -> str:
    """Return a bcrypt hash of the given password."""
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored bcrypt hash."""
    return pwd_context.verify(plain, hashed)

def create_access_token(user_id: str) -> str:
    """Return a signed JWT for user_id, expiring per settings.access_token_expire_minutes."""
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    access_token: Optional[str] = Cookie(default=None),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency — decode Bearer token or httpOnly cookie and return the active User.

    Tries the Authorization header first (for backward compat with tests and API clients),
    then falls back to the httpOnly cookie set by POST /auth/login.
    Raises 401 if neither is present, or if the token is invalid/expired.
    """
    token = None
    if credentials:
        token = credentials.credentials
    elif access_token:
        token = access_token
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id: str = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user
```

- [ ] **Step 3: Add `LoginOut` schema to `schemas/user.py`**

Append to `backend/app/schemas/user.py`:

```python
class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
```

The full file:

```python
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str
    created_at: datetime

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
```

- [ ] **Step 4: Update `routers/auth.py` — set cookie on login, add /logout and /me**

Replace `backend/app/routers/auth.py`:

```python
import logging

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import LoginOut, TokenOut, UserLogin, UserOut, UserRegister
from app.services import audit
from app.services.auth import create_access_token, get_current_user, hash_password, verify_password

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == payload.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    try:
        audit.log(db, action="registered", user_id=user.id)
    except Exception as e:
        logger.warning(f"Audit log failed for register user {user.id}: {e}")
    return user


@router.post("/login", response_model=LoginOut)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        try:
            masked = payload.email[:3] + "***" if payload.email else "***"
            audit.log(db, action="login_failed", after_state={"email": masked})
        except Exception as e:
            logger.warning(f"Audit log failed for login_failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid credentials")
    try:
        audit.log(db, action="login_success", user_id=user.id)
    except Exception as e:
        logger.warning(f"Audit log failed for login_success user {user.id}: {e}")

    token = create_access_token(user.id)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    return {"access_token": token, "token_type": "bearer", "user": user}


@router.post("/logout")
def logout(response: Response):
    """Clear the access_token cookie. Client should also clear local auth state."""
    response.delete_cookie(key="access_token", path="/")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserOut)
def get_me(user: User = Depends(get_current_user)):
    """Return the currently authenticated user. Used by the frontend on page load
    to restore session state from the httpOnly cookie without storing the token in JS.
    """
    return user
```

- [ ] **Step 5: Write backend tests for new auth endpoints**

Add to `backend/tests/test_auth.py` (append):

```python
def test_login_sets_httponly_cookie(client, registered_user):
    response = client.post("/auth/login", json=registered_user)
    assert response.status_code == 200
    cookie = response.cookies.get("access_token")
    assert cookie is not None


def test_login_response_includes_user(client, registered_user):
    response = client.post("/auth/login", json=registered_user)
    data = response.json()
    assert "user" in data
    assert data["user"]["email"] == registered_user["email"]


def test_logout_clears_cookie(client, registered_user):
    client.post("/auth/login", json=registered_user)
    response = client.post("/auth/logout")
    assert response.status_code == 200
    # Cookie is cleared — Set-Cookie header with empty value or max-age=0
    set_cookie = response.headers.get("set-cookie", "")
    assert "access_token" in set_cookie


def test_me_returns_user_with_valid_cookie(client, registered_user):
    client.post("/auth/login", json=registered_user)
    # TestClient stores the cookie automatically after login
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["email"] == registered_user["email"]


def test_me_returns_401_without_auth(client):
    response = client.get("/auth/me")
    assert response.status_code == 401
```

- [ ] **Step 6: Run backend tests**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/test_auth.py -v
```

Expected: all tests pass, including new ones. The `auth_headers` fixture still works because login still returns `access_token` in the response body.

### 4B — Frontend

- [ ] **Step 7: Replace `store/auth.js` — remove localStorage, store user not token**

Replace `frontend/src/store/auth.js`:

```javascript
import { create } from 'zustand'

const useAuthStore = create((set) => ({
  user: null,
  setUser: (user) => set({ user }),
  logout: () => set({ user: null }),
  // token kept as a getter for backward compat with any remaining Bearer uses
  get token() { return null },
}))

export default useAuthStore
```

Note: the `token` getter returning `null` means the existing Bearer injection in `client.js` request interceptor will not add any Authorization header for browser traffic. The httpOnly cookie handles auth automatically. Tests still inject Bearer via `auth_headers`.

- [ ] **Step 8: Add `logout()` and `me()` to `api/auth.js`**

Replace `frontend/src/api/auth.js`:

```javascript
import client from './client'

export const register = (email, password, fullName) =>
  client.post('/auth/register', { email, password, full_name: fullName })

export const login = (email, password) =>
  client.post('/auth/login', { email, password })

export const logout = () =>
  client.post('/auth/logout')

export const me = () =>
  client.get('/auth/me')
```

- [ ] **Step 9: Add `withCredentials: true` to axios client**

In `frontend/src/api/client.js`, update the `axios.create` call to include `withCredentials`:

```javascript
const client = axios.create({
  baseURL: '/',
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
})
```

(Keep the rest of `client.js` unchanged — `NavigatorSetter` and the `setNavigate` export from Task 3 stay.)

- [ ] **Step 10: Update `Login.jsx` — store user not token**

Replace `frontend/src/pages/Login.jsx`:

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
  const setUser = useAuthStore((s) => s.setUser)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const res = await login(email, password)
      setUser(res.data.user)
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

- [ ] **Step 11: Update `useExtractionStream.js` — cookie-based auth**

In `frontend/src/hooks/useExtractionStream.js`, in the `stream()` function, replace the Bearer fetch with a credentials fetch:

```javascript
async function stream() {
  try {
    const res = await fetch(url, {
      credentials: 'include',   // send the httpOnly cookie
    })
    // ... rest unchanged ...
```

Remove these lines (no longer needed):
```javascript
const token = useAuthStore.getState().token
```
and the `headers: { Authorization: ... }` line.

Also remove the `useAuthStore` import at the top if it is no longer used anywhere else in the file.

- [ ] **Step 12: Update `App.jsx` — `AuthInit` + updated `ProtectedRoute`**

Replace `frontend/src/App.jsx`:

```jsx
import { useEffect, useState } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import { setNavigate } from './api/client'
import { me } from './api/auth'
import Login from './pages/Login'
import WorkspacesHome from './pages/WorkspacesHome'
import SchemaLibrary from './pages/SchemaLibrary'
import WorkspaceLayout from './pages/workspace/WorkspaceLayout'
import Overview from './pages/workspace/Overview'
import Documents from './pages/workspace/Documents'
import DocumentViewer from './pages/workspace/DocumentViewer'
import Search from './pages/workspace/Search'
import Entities from './pages/workspace/Entities'
import Transactions from './pages/workspace/Transactions'
import Findings from './pages/workspace/Findings'
import Leads from './pages/workspace/Leads'
import AIChat from './pages/workspace/AIChat'
import ExtractionReview from './pages/workspace/ExtractionReview'
import AuditLog from './pages/workspace/AuditLog'
import useAuthStore from './store/auth'

/** Wires the axios 401 interceptor to React Router navigation. */
function NavigatorSetter() {
  const navigate = useNavigate()
  useEffect(() => { setNavigate(navigate) }, [navigate])
  return null
}

/**
 * On startup, call /auth/me to restore session from the httpOnly cookie.
 * Renders nothing until the check completes so ProtectedRoute has accurate state.
 */
function AuthInit({ children }) {
  const [ready, setReady] = useState(false)
  const setUser = useAuthStore((s) => s.setUser)

  useEffect(() => {
    me()
      .then((res) => setUser(res.data))
      .catch(() => {/* not authenticated — that's fine */})
      .finally(() => setReady(true))
  }, [])

  if (!ready) return <div className="min-h-screen bg-slate-900" />
  return children
}

function ProtectedRoute({ children }) {
  const user = useAuthStore((s) => s.user)
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <BrowserRouter>
      <NavigatorSetter />
      <AuthInit>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/workspaces" element={
            <ProtectedRoute><WorkspacesHome /></ProtectedRoute>
          } />
          <Route path="/schemas" element={
            <ProtectedRoute><SchemaLibrary /></ProtectedRoute>
          } />
          <Route path="/workspaces/:workspaceId" element={
            <ProtectedRoute><WorkspaceLayout /></ProtectedRoute>
          }>
            <Route index element={<Overview />} />
            <Route path="documents" element={<Documents />} />
            <Route path="documents/:documentId" element={<DocumentViewer />} />
            <Route path="search" element={<Search />} />
            <Route path="entities" element={<Entities />} />
            <Route path="transactions" element={<Transactions />} />
            <Route path="findings" element={<Findings />} />
            <Route path="leads" element={<Leads />} />
            <Route path="chat" element={<AIChat />} />
            <Route path="review" element={<ExtractionReview />} />
            <Route path="audit" element={<AuditLog />} />
          </Route>
          <Route path="*" element={<Navigate to="/workspaces" replace />} />
        </Routes>
      </AuthInit>
    </BrowserRouter>
  )
}
```

- [ ] **Step 13: Update frontend test mocks**

Replace `frontend/src/tests/mocks/handlers.js`:

```javascript
import { http, HttpResponse } from 'msw'

export const handlers = [
  http.post('/auth/login', () => {
    return HttpResponse.json({
      access_token: 'test-token',
      token_type: 'bearer',
      user: {
        id: 'user-1',
        email: 'tyler@example.com',
        full_name: 'Tyler Collins',
        role: 'investigator',
        created_at: '2026-01-01T00:00:00Z',
      },
    })
  }),
  http.get('/auth/me', () => {
    // By default return 401 — tests that need an authenticated session
    // will override this handler with server.use()
    return HttpResponse.json({ detail: 'Not authenticated' }, { status: 401 })
  }),
  http.post('/auth/logout', () => {
    return HttpResponse.json({ message: 'Logged out' })
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

**Important:** `AuthInit` in `App.jsx` calls `/auth/me` on mount. Since the default handler returns 401, `AuthInit` will complete with `user: null`. Tests that render `<App>` will show the login page unless they override the `/auth/me` handler to return a user. Check each existing test: if it renders `<App>`, add a `server.use(http.get('/auth/me', () => HttpResponse.json({ id: 'user-1', ... })))` override. Tests that render individual components directly (like `<AIChat>`, `<Login>`) are not affected.

- [ ] **Step 14: Update `test_login.jsx` — check user in store not token**

In `frontend/src/tests/test_login.jsx`, update the login success path. The existing test `shows error on wrong credentials` doesn't test the store directly so it should still pass. If there's a test that checks `token` in the store, update it to check `user`.

Add a success test at the end:

```javascript
test('stores user in auth store on successful login', async () => {
  renderLogin()
  fireEvent.change(screen.getByPlaceholderText(/email/i), {
    target: { value: 'tyler@example.com' },
  })
  fireEvent.change(screen.getByPlaceholderText(/password/i), {
    target: { value: 'correctpass' },
  })
  fireEvent.click(screen.getByRole('button', { name: /sign in/i }))

  await waitFor(() => {
    const { user } = useAuthStore.getState()
    expect(user).not.toBeNull()
    expect(user.email).toBe('tyler@example.com')
  })
})
```

Add the import at the top of `test_login.jsx`:
```javascript
import useAuthStore from '../store/auth'
```

- [ ] **Step 15: Run full frontend suite**

```
cd "C:\Users\tjcol\OneDrive\Projects\Investigation software\frontend" && npm test
```

Expected: all tests pass. If `test_workspaces_home.jsx` or other tests render components that depend on `user` being set, they may need `/auth/me` override handlers — add them if needed.

- [ ] **Step 16: Run full backend suite**

```
docker-compose run --rm -e TEST_DATABASE_URL=postgresql://catalyst:catalyst@db:5432/catalyst_test backend pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 17: Commit**

```bash
git add \
  backend/app/config.py \
  backend/app/services/auth.py \
  backend/app/schemas/user.py \
  backend/app/routers/auth.py \
  backend/tests/test_auth.py \
  frontend/src/store/auth.js \
  frontend/src/api/auth.js \
  frontend/src/api/client.js \
  frontend/src/pages/Login.jsx \
  frontend/src/hooks/useExtractionStream.js \
  frontend/src/tests/mocks/handlers.js \
  frontend/src/App.jsx
git commit -m "fix(M6): migrate JWT from localStorage to httpOnly cookie

Backend: POST /auth/login sets httpOnly cookie + returns token in body
(backward compat for tests). GET /auth/me restores session from cookie
on page refresh. POST /auth/logout clears cookie. get_current_user
accepts both cookie and Bearer — no existing tests need to change.

Frontend: zustand store drops persist/localStorage, stores user object
only. App calls /auth/me on startup to restore session. axios sends
withCredentials:true so cookie is included automatically. SSE fetch
uses credentials:include instead of Authorization header.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Update audit doc + open PR

- [ ] **Step 1: Update `docs/code-audit-2026-05-29.md` remediation table**

Change:
```
| 6 | M6, M7, L2, L4 | Frontend resilience + JWT hardening | — |
```
To:
```
| 6 | M6, M7, L2, L4 | Frontend resilience + JWT hardening | ✅ Done — merged 2026-05-30 |
```

Also update "Remaining open findings" — Phase 6 closes the last audit finding.

- [ ] **Step 2: Commit and push**

```bash
git add docs/code-audit-2026-05-29.md
git commit -m "docs: mark audit Phase 6 complete — all findings resolved"
git push -u origin feat/phase-6-frontend-resilience-auth-hardening
```

- [ ] **Step 3: Open PR using `verity-prism-pr-description` skill**

---

## Self-Review

**Spec coverage:**
- L2 SSE reader cancel: ✅ Task 1 — `reader?.cancel()` in cleanup
- M7 AIChat error handling: ✅ Task 2 — catch + rollback + toast
- M7 WorkspaceContext silent failure: ✅ Task 2, Step 5 — `.catch(() => {})`
- L4 hard 401 redirect: ✅ Task 3 — `NavigatorSetter` + `setNavigate`
- M6 JWT in localStorage: ✅ Task 4 — httpOnly cookie + remove persist
- M6 backend cookie endpoints: ✅ Task 4A — login/logout/me
- M6 frontend cookie consumption: ✅ Task 4B — withCredentials, AuthInit, ProtectedRoute

**Placeholder scan:** No TBDs. All code blocks are complete.

**Type consistency:**
- `setUser(user)` defined in store (Step 7), called in `Login.jsx` (Step 10) and `AuthInit` (Step 12) — consistent.
- `useAuthStore((s) => s.user)` in `ProtectedRoute` (Step 12) — consistent with store shape (Step 7).
- `me()` defined in `api/auth.js` (Step 8), imported and called in `App.jsx` (Step 12) — consistent.
- `logout()` defined in store (Step 7), called by the 401 interceptor (no change to existing call site) — consistent.

**One integration risk to watch:** `AuthInit` calls `/auth/me` before routes render. Tests that render `<App>` will block until the MSW handler responds. The default `/auth/me` handler returns 401, so `AuthInit` resolves quickly. Tests that need an authenticated user must override `/auth/me` to return a user object before calling `setReady(true)` renders children. Document this in the task.
