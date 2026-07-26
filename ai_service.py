"""
OpenAI API interaction layer for IncidentIQ.

All OpenAI calls are isolated here so that app.py stays UI-only and
the functions are easy to unit-test with mocked clients.

Requirements: 2.1–2.7, 11.1–11.3
"""

import json
import os

import openai
from pydantic import ValidationError  # noqa: F401 — re-exported for callers

from models import AnalysisReport, ChallengeReport


def get_api_key() -> str | None:
    """Return the OpenAI API key, or ``None`` if unavailable.

    Precedence (Requirement 11.1):
    1. ``OPENAI_API_KEY`` environment variable.
    2. Streamlit secrets (``st.secrets["OPENAI_API_KEY"]``).
    """
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("OPENAI_API_KEY") or None
    except Exception:
        return None


def run_analysis(
    client: openai.OpenAI,
    system: str,
    user: str,
    model: str = "gpt-4o",
) -> AnalysisReport:
    """Call the OpenAI API and return a validated :class:`AnalysisReport`.

    Args:
        client: An ``openai.OpenAI`` instance (constructed with ``timeout=60``).
        system: The system prompt built by :func:`prompts.build_analysis_prompt`.
        user: The user prompt built by :func:`prompts.build_analysis_prompt`.
        model: The model name to use (default ``"gpt-4o"``; override via the
            ``MODEL`` constant in ``app.py``).

    Returns:
        A validated ``AnalysisReport`` Pydantic model.

    Raises:
        openai.APITimeoutError: If the request exceeds the client timeout.
        openai.AuthenticationError: If the API key is invalid.
        openai.APIError: For any other OpenAI API error.
        json.JSONDecodeError: If the response content is not valid JSON.
        pydantic.ValidationError: If the parsed JSON does not match the schema.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    data = json.loads(response.choices[0].message.content)
    return AnalysisReport.model_validate(data)


def run_challenge(
    client: openai.OpenAI,
    system: str,
    user: str,
    model: str = "gpt-4o",
) -> ChallengeReport:
    """Call the OpenAI API and return a validated :class:`ChallengeReport`.

    Args:
        client: An ``openai.OpenAI`` instance (constructed with ``timeout=60``).
        system: The system prompt built by :func:`prompts.build_challenge_prompt`.
        user: The user prompt built by :func:`prompts.build_challenge_prompt`.
        model: The model name to use (default ``"gpt-4o"``).

    Returns:
        A validated ``ChallengeReport`` Pydantic model.

    Raises:
        openai.APITimeoutError: If the request exceeds the client timeout.
        openai.AuthenticationError: If the API key is invalid.
        openai.APIError: For any other OpenAI API error.
        json.JSONDecodeError: If the response content is not valid JSON.
        pydantic.ValidationError: If the parsed JSON does not match the schema.
    """
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    data = json.loads(response.choices[0].message.content)
    return ChallengeReport.model_validate(data)
