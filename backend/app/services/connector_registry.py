from app.services.connectors.base import ConnectorBase
from app.services.connectors.irs_teos import IrsTeosConnector

# Connectors live in code, registered by id. Tests monkeypatch _REGISTRY directly.
_REGISTRY: dict[str, ConnectorBase] = {IrsTeosConnector.id: IrsTeosConnector()}


def get_connectors_for_vertical(vertical: str) -> list[ConnectorBase]:
    """Connectors available to a workspace: those serving this vertical or 'general'."""
    return [
        c for c in _REGISTRY.values()
        if vertical in c.verticals or "general" in c.verticals
    ]


def get_connector(connector_id: str) -> ConnectorBase | None:
    return _REGISTRY.get(connector_id)
