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
