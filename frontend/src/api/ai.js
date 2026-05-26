import client from './client'

export const listConversations = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/conversations`)
export const createConversation = (workspaceId) =>
  client.post(`/workspaces/${workspaceId}/conversations`)
export const listMessages = (workspaceId, conversationId) =>
  client.get(`/workspaces/${workspaceId}/conversations/${conversationId}/messages`)
export const sendMessage = (workspaceId, conversationId, content) =>
  client.post(`/workspaces/${workspaceId}/conversations/${conversationId}/messages`, { content })
