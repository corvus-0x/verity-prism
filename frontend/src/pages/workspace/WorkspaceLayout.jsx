import { Outlet } from 'react-router-dom'
import AppShell from '../../components/layout/AppShell'
import WorkspaceSidebar from '../../components/layout/WorkspaceSidebar'

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
