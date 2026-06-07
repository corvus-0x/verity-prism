"""
Shared lazy Anthropic client.

All services call get_client() instead of instantiating Anthropic() directly.
Benefits:
- Missing API key fails at first call, not at module import
- Single instantiation point for future retry logic and spend tracking
- Single patch target in tests: patch("app.services.claude_client.get_client")
- LangSmith tracing auto-enabled when LANGSMITH_API_KEY is configured
"""
import os

from anthropic import Anthropic

from app.config import settings

# Model routing by task (Phase 2F A2).
# Field extraction on clean, structured documents does not need Sonnet —
# Haiku is ~4x cheaper and adequate. Chat reasons across many documents and
# stays on Sonnet. Type detection of ambiguous documents also stays on Sonnet
# (set in extraction_engine.detect_document_type, not here).
EXTRACTION_MODEL = "claude-haiku-4-5-20251001"
CHAT_MODEL = "claude-sonnet-4-6"

_client: "Anthropic | None" = None


def get_client() -> Anthropic:
    """Return the shared Anthropic client, constructing it on first call."""
    global _client
    if _client is None:
        client = Anthropic(api_key=settings.anthropic_api_key)
        if os.getenv("LANGSMITH_API_KEY"):
            try:
                from langsmith import wrappers
                client = wrappers.wrap_anthropic(client)
            except ImportError:
                pass
        _client = client
    return _client
