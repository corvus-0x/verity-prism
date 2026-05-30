"""
Shared lazy Anthropic client.

All services call get_client() instead of instantiating Anthropic() directly.
Benefits:
- Missing API key fails at first call, not at module import
- Single instantiation point for future retry logic and spend tracking
- Single patch target in tests: patch("app.services.claude_client.get_client")
"""
from anthropic import Anthropic

from app.config import settings

_client: "Anthropic | None" = None


def get_client() -> Anthropic:
    """Return the shared Anthropic client, constructing it on first call."""
    global _client
    if _client is None:
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client
