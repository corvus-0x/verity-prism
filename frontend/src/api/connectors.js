import client from "./client";

export const listConnectors = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/connectors`).then((r) => r.data);

export const searchConnector = (workspaceId, connectorId, params) =>
  client.post(`/workspaces/${workspaceId}/connectors/${connectorId}/search`, { params })
    .then((r) => r.data);

export const listConnectorItems = (workspaceId, connectorId, candidateRef) =>
  client.post(`/workspaces/${workspaceId}/connectors/${connectorId}/list`,
    { candidate_ref: candidateRef }).then((r) => r.data);

export const fetchConnector = (workspaceId, connectorId, body) =>
  client.post(`/workspaces/${workspaceId}/connectors/${connectorId}/fetch`, body)
    .then((r) => r.data);

export const listRuns = (workspaceId) =>
  client.get(`/workspaces/${workspaceId}/connector-runs`).then((r) => r.data);

export const getRun = (workspaceId, runId) =>
  client.get(`/workspaces/${workspaceId}/connector-runs/${runId}`).then((r) => r.data);
