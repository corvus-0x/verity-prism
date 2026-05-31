import client from './client'

export const listSchemas = () => client.get('/schemas/')

export const getSchema = (schemaId) =>
  client.get(`/schemas/${schemaId}`)
