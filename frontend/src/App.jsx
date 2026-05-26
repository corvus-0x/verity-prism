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
