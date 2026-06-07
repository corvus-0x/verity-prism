import client from './client'

export const listLeads = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/leads`)
export const createLead = (workspaceId, data) =>
  client.post(`/workspaces/${workspaceId}/leads`, data)
export const updateLead = (workspaceId, id, data) =>
  client.patch(`/workspaces/${workspaceId}/leads/${id}`, data)
