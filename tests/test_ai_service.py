"""
Unit tests for ai_service.py error paths.

Verifies that APITimeoutError and AuthenticationError propagate from
run_analysis and run_challenge without being swallowed.

Requirements: 2.4, 2.6
"""

from unittest.mock import MagicMock

import httpx
import openai
import pytest

from ai_service import run_analysis, run_challenge


# ---------------------------------------------------------------------------
# Helpers to build minimal httpx objects required by openai exception ctors
# ---------------------------------------------------------------------------


def _make_request() -> httpx.Request:
    """Return a minimal httpx.Request for APITimeoutError."""
    return httpx.Request("POST", "https://api.openai.com/v1/chat/completions")


def _make_response(status_code: int = 401) -> httpx.Response:
    """Return a minimal httpx.Response for AuthenticationError."""
    return httpx.Response(
        status_code=status_code,
        request=_make_request(),
    )


# ---------------------------------------------------------------------------
# run_analysis — timeout
# ---------------------------------------------------------------------------


def test_run_analysis_raises_timeout_error():
    """APITimeoutError from the client propagates unchanged (Requirement 2.6)."""
    client = MagicMock(spec=openai.OpenAI)
    client.chat.completions.create.side_effect = openai.APITimeoutError(
        request=_make_request()
    )

    with pytest.raises(openai.APITimeoutError):
        run_analysis(client, "system", "user")


# ---------------------------------------------------------------------------
# run_analysis — auth error
# ---------------------------------------------------------------------------


def test_run_analysis_raises_auth_error():
    """AuthenticationError from the client propagates unchanged (Requirement 2.4)."""
    client = MagicMock(spec=openai.OpenAI)
    client.chat.completions.create.side_effect = openai.AuthenticationError(
        message="Invalid API key.",
        response=_make_response(401),
        body=None,
    )

    with pytest.raises(openai.AuthenticationError):
        run_analysis(client, "system", "user")


# ---------------------------------------------------------------------------
# run_challenge — timeout
# ---------------------------------------------------------------------------


def test_run_challenge_raises_timeout_error():
    """APITimeoutError from the client propagates unchanged (Requirement 2.6)."""
    client = MagicMock(spec=openai.OpenAI)
    client.chat.completions.create.side_effect = openai.APITimeoutError(
        request=_make_request()
    )

    with pytest.raises(openai.APITimeoutError):
        run_challenge(client, "system", "user")


# ---------------------------------------------------------------------------
# run_challenge — auth error
# ---------------------------------------------------------------------------


def test_run_challenge_raises_auth_error():
    """AuthenticationError from the client propagates unchanged (Requirement 2.4)."""
    client = MagicMock(spec=openai.OpenAI)
    client.chat.completions.create.side_effect = openai.AuthenticationError(
        message="Invalid API key.",
        response=_make_response(401),
        body=None,
    )

    with pytest.raises(openai.AuthenticationError):
        run_challenge(client, "system", "user")
