import pytest
from pydantic import ValidationError

from app.config import Settings


def _make(**overrides):
    base = dict(
        database_url="postgresql://catalyst:catalyst@localhost:5432/catalyst",
        secret_key="k" * 48,
        anthropic_api_key="sk-ant-test",
    )
    base.update(overrides)
    return Settings(**base)


def test_strong_secret_key_accepted():
    s = _make(secret_key="k" * 48)
    assert s.secret_key == "k" * 48


def test_empty_secret_key_rejected():
    with pytest.raises(ValidationError):
        _make(secret_key="")


def test_known_weak_secret_keys_rejected():
    with pytest.raises(ValidationError):
        _make(secret_key="dev-secret-key-change-in-production")
    with pytest.raises(ValidationError):
        _make(secret_key="change-this-to-a-long-random-string-in-production")


def test_short_secret_key_rejected():
    with pytest.raises(ValidationError):
        _make(secret_key="tooshort")
