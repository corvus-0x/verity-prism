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

function NavigatorSetter() {
  const navigate = useNavigate()
  useEffect(() => { setNavigate(navigate) }, [navigate])
  return null
}

function AuthInit({ children }) {
  const [ready, setReady] = useState(false)
  const setUser = useAuthStore((s) => s.setUser)

  useEffect(() => {
    me()
      .then((res) => setUser(res.data))
      .catch(() => {})
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
