"""
Signal registry — extension seam for vertical cap signal detectors.

The engine ships the universal saliences (saliences.py). A vertical cap
registers additional domain detectors here over time (e.g. a fraud
"below-appraisal transfer" rule), keyed by vertical. The synthesis engine
and its eval harness never change when a cap adds a detector — open for
extension, closed for modification.

A detector is a callable: (evidence, documents) -> list[Salience].
No detectors are registered by the engine; this is the seam only.
"""

from collections import defaultdict

_registry: dict[str, list] = defaultdict(list)


def register(vertical: str, detector) -> None:
    """Register a cap signal detector under a vertical."""
    _registry[vertical].append(detector)


def get_detectors(vertical: str | None) -> list:
    """Return registered detectors for a vertical (empty list if none/unknown)."""
    if not vertical:
        return []
    return list(_registry.get(vertical, []))
