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

export const getReviewQueue = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/review-queue`)

export const correctExtraction = (workspaceId, documentId, extractionId, fieldValue, evidence = null) =>
  client.patch(
    `/workspaces/${workspaceId}/documents/${documentId}/extractions/${extractionId}/correct`,
    { field_value: fieldValue, evidence }
  )

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  setTimeout(() => URL.revokeObjectURL(url), 100)
}

export const getExtractionsCSV = async (workspaceId, documentId, docFilename) => {
  const res = await client.get(
    `/workspaces/${workspaceId}/documents/${documentId}/extractions.csv`,
    { responseType: 'blob' }
  )
  triggerDownload(res.data, `${docFilename}_extractions.csv`)
}

export const getExtractionsJSON = async (workspaceId, documentId, docFilename) => {
  const res = await client.get(
    `/workspaces/${workspaceId}/documents/${documentId}/extractions.json`,
    { responseType: 'blob' }
  )
  triggerDownload(res.data, `${docFilename}_extractions.json`)
}

export const getWorkspaceExtractionsCSV = async (workspaceId) => {
  const res = await client.get(
    `/workspaces/${workspaceId}/extractions.csv`,
    { responseType: 'blob' }
  )
  triggerDownload(res.data, `workspace_extractions.csv`)
}

export const getWorkspaceExtractionsJSON = async (workspaceId) => {
  const res = await client.get(
    `/workspaces/${workspaceId}/extractions.json`,
    { responseType: 'blob' }
  )
  triggerDownload(res.data, `workspace_extractions.json`)
}

export const flagDocument = (workspaceId, documentId, flagReason, flagNote = null) =>
  client.patch(`/workspaces/${workspaceId}/documents/${documentId}/flag`, {
    flag_reason: flagReason,
    flag_note: flagNote,
  })

export const createExtraction = (workspaceId, documentId, fieldName, fieldValue, fieldType, schemaId, evidence = null) =>
  client.post(`/workspaces/${workspaceId}/documents/${documentId}/extractions`, {
    field_name: fieldName,
    field_value: fieldValue,
    field_type: fieldType,
    schema_id: schemaId,
    evidence,
  })
