"""
Property-based tests for IncidentIQ — uses the Hypothesis library.

Sub-task 1.2: Property 3 — Pydantic rejects out-of-range confidence scores.
Validates: Requirements 4.2
"""

import pytest
from hypothesis import given, settings
import hypothesis.strategies as st
from pydantic import ValidationError

from models import Hypothesis


# ---------------------------------------------------------------------------
# Property 3: Pydantic rejects out-of-range confidence scores
# Feature: incident-iq
# Validates: Requirements 4.2
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(st.integers().filter(lambda x: not (0 <= x <= 100)))
def test_hypothesis_confidence_out_of_range(bad_confidence):
    """
    For any integer outside the range [0, 100] used as a Hypothesis.confidence
    value, Pydantic SHALL raise a ValidationError when constructing the model.

    Validates: Requirements 4.2
    """
    with pytest.raises(ValidationError):
        Hypothesis(
            title="T",
            confidence=bad_confidence,
            supporting_evidence=["e"],
            contradicting_evidence=[],
            recommended_tests=["t1", "t2"],
        )


# ---------------------------------------------------------------------------
# MockUploadedFile for property tests
# ---------------------------------------------------------------------------

import io as _io


class MockUploadedFile:
    """Lightweight stand-in for streamlit.runtime.uploaded_file_manager.UploadedFile."""

    def __init__(self, data: bytes, name: str):
        self.name = name
        self.size = len(data)
        self._stream = _io.BytesIO(data)

    def read(self) -> bytes:
        return self._stream.read()


# ---------------------------------------------------------------------------
# Property 1: TXT file parsing is a round-trip
# Feature: incident-iq
# Validates: Requirements 1.7
# ---------------------------------------------------------------------------

from utils import parse_file, validate_inputs


@settings(max_examples=200)
@given(st.text(min_size=1))
def test_txt_round_trip(content: str):
    """
    For any non-empty UTF-8 string, encoding it as bytes and passing it through
    parse_file as a .txt upload SHALL return the original string with no error.

    Validates: Requirements 1.7
    """
    # Only test strings that are non-whitespace (whitespace-only files return "File is empty.")
    # and that are encodable as UTF-8 (Hypothesis text() always produces valid Unicode).
    fake = MockUploadedFile(content.encode("utf-8"), name="f.txt")
    result, err = parse_file(fake)

    if content.strip():
        # Non-whitespace content must round-trip exactly
        assert err is None, f"Unexpected error: {err!r}"
        assert result == content, f"Round-trip failed: {result!r} != {content!r}"
    else:
        # Whitespace-only strings are treated as empty files
        assert result == ""
        assert err == "File is empty."


# ---------------------------------------------------------------------------
# Property 2: Input validation rejects all-whitespace input
# Feature: incident-iq
# Validates: Requirements 1.10
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(st.lists(st.text(alphabet=" \t\n"), min_size=5, max_size=5))
def test_validate_inputs_whitespace_only(fields: list[str]):
    """
    For any combination of the five incident input fields where every value is
    composed solely of whitespace characters and no file content is provided,
    validate_inputs SHALL return False.

    Validates: Requirements 1.10
    """
    keys = ["description", "logs", "deployment_notes", "alerts", "complaints"]
    assert validate_inputs(dict(zip(keys, fields)), "") is False
