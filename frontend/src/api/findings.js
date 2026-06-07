import client from './client'

export const getSignalTypes = () => client.get('/signal-types')
export const listFindings = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/findings`)
export const createFinding = (workspaceId, data) =>
  client.post(`/workspaces/${workspaceId}/findings`, data)
export const updateFinding = (workspaceId, id, data) =>
  client.patch(`/workspaces/${workspaceId}/findings/${id}`, data)
