from app.services import connector_registry
from app.services.connectors.base import ConnectorBase, FetchResult


class _FakeGeneral(ConnectorBase):
    id = "fake-general"
    name = "Fake General"
    verticals = ["general"]
    def search(self, params): return []
    def list_items(self, candidate_ref): return []
    def fetch(self, item_refs, workspace_id, user_id, db): return FetchResult()


class _FakeFraud(ConnectorBase):
    id = "fake-fraud"
    name = "Fake Fraud"
    verticals = ["fraud"]
    def search(self, params): return []
    def list_items(self, candidate_ref): return []
    def fetch(self, item_refs, workspace_id, user_id, db): return FetchResult()


def test_general_connector_visible_to_all_verticals(monkeypatch):
    monkeypatch.setattr(connector_registry, "_REGISTRY",
                        {"fake-general": _FakeGeneral(), "fake-fraud": _FakeFraud()})
    fraud = {c.id for c in connector_registry.get_connectors_for_vertical("fraud")}
    general = {c.id for c in connector_registry.get_connectors_for_vertical("general")}
    assert "fake-general" in fraud and "fake-fraud" in fraud
    assert "fake-general" in general and "fake-fraud" not in general


def test_get_connector_by_id(monkeypatch):
    monkeypatch.setattr(connector_registry, "_REGISTRY", {"fake-general": _FakeGeneral()})
    assert connector_registry.get_connector("fake-general").id == "fake-general"
    assert connector_registry.get_connector("nope") is None
