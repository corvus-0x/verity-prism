import client from './client'

export const listTransactions = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/transactions`)
export const createTransaction = (workspaceId, data) =>
  client.post(`/workspaces/${workspaceId}/transactions`, data)
