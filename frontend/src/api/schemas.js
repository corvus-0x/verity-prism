import client from './client'

export const listSchemas = () => client.get('/schemas/')
