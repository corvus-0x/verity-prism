import client from './client'

export const search = (workspaceId, query) =>
  client.post(`/workspaces/${workspaceId}/search`, { query })
