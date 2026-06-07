import client from './client'

export const listNotes = (workspaceId, entityType, entityId) =>
  client.get(`/workspaces/${workspaceId}/notes`, {
    params: { entity_type: entityType, entity_id: entityId }
  })
export const createNote = (workspaceId, data) =>
  client.post(`/workspaces/${workspaceId}/notes`, data)
