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
