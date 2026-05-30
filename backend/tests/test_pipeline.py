"""
Pipeline and extraction engine tests.

All Claude calls are mocked via `patch("app.services.extraction_engine.client")`.
_run_pipeline is called directly (not through the HTTP router) so we can
inspect DB state after each step without fighting background-task timing.
"""
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models.document import Document
from app.models.document_extraction import DocumentExtraction
from app.models.document_schema import DocumentSchema
from app.models.user import User
from app.models.workspace import Workspace
from app.services.extraction_evaluator import EvaluationResult, evaluate


# ── Evaluator unit tests ─────────────────────────────────────────────────────

def test_evaluate_returns_no_review_when_all_confident():
    extractions = [
        {"field_name": "grantor_name", "confidence": 0.95},
        {"field_name": "sale_price", "confidence": 0.90},
    ]
    result = evaluate(extractions, threshold=0.75)
    assert isinstance(result, EvaluationResult)
    assert result.needs_review is False
    assert result.low_confidence_fields == []
    assert result.total_fields == 2


def test_evaluate_flags_fields_below_threshold():
    extractions = [
        {"field_name": "grantor_name", "confidence": 0.95},
        {"field_name": "sale_price", "confidence": 0.40},
        {"field_name": "parcel_id", "confidence": 0.30},
    ]
    result = evaluate(extractions, threshold=0.75)
    assert result.needs_review is True
    assert "sale_price" in result.low_confidence_fields
    assert "parcel_id" in result.low_confidence_fields
    assert "grantor_name" not in result.low_confidence_fields
    assert result.total_fields == 3


def test_evaluate_empty_input_is_not_needs_review():
    # evaluate() is pure — empty list = no low-confidence fields = no review.
    # The pipeline (not the evaluator) is responsible for detecting API failure.
    result = evaluate([], threshold=0.75)
    assert result.needs_review is False
    assert result.total_fields == 0
