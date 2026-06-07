import { Outlet } from 'react-router-dom'
import AppShell from '../../components/layout/AppShell'
import WorkspaceSidebar from '../../components/layout/WorkspaceSidebar'
import { WorkspaceProvider } from '../../context/WorkspaceContext'
import { ToastProvider } from '../../hooks/useToast'
import ResizeHandle from '../../components/shared/ResizeHandle'
import { useResizable } from '../../hooks/useResizable'

export default function WorkspaceLayout() {
  const [sidebarWidth, startSidebarResize] = useResizable(192, { min: 140, max: 320 })

  return (
    <WorkspaceProvider>
      <ToastProvider>
        <AppShell>
          <div style={{ width: sidebarWidth }} className="shrink-0 h-full">
            <WorkspaceSidebar />
          </div>
          <ResizeHandle onMouseDown={startSidebarResize} />
          <div className="flex-1 overflow-auto p-6 min-w-0">
            <Outlet />
          </div>
        </AppShell>
      </ToastProvider>
    </WorkspaceProvider>
  )
}
