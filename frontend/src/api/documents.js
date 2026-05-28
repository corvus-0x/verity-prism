import client from './client'

export const listDocuments = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/documents`)

export const uploadDocument = (workspaceId, file) => {
  const form = new FormData()
  form.append('file', file)
  return client.post(`/workspaces/${workspaceId}/documents`, form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

export const getDocument = (workspaceId, documentId) =>
  client.get(`/workspaces/${workspaceId}/documents/${documentId}`)

export const getExtractions = (workspaceId, documentId) =>
  client.get(`/workspaces/${workspaceId}/documents/${documentId}/extractions`)

export const getDocumentFile = (workspaceId, documentId) =>
  client.get(`/workspaces/${workspaceId}/documents/${documentId}/file`, {
    responseType: 'blob',
  })
