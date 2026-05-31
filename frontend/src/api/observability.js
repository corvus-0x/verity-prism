import client from './client'

export const getAutomationRate = () =>
  client.get('/observability/automation-rate')

export const getVolume = (days = 30) =>
  client.get('/observability/volume', { params: { days } })

export const getClassificationDetails = () =>
  client.get('/observability/classification-details')

export const getCurrentProcessing = () =>
  client.get('/observability/current-processing')
