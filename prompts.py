"""
Prompt construction for IncidentIQ.

Pure functions — no side effects, no I/O.
Requirements: 2.1, 2.5, 11.1
"""

import json

# ---------------------------------------------------------------------------
# Analysis system message — embedded verbatim per design
# ---------------------------------------------------------------------------

_ANALYSIS_SYSTEM = """\
You are an expert site-reliability engineer and incident analyst.
Respond ONLY with a JSON object that exactly matches the schema below.
Do not include commentary outside the JSON.

Grounding rules:
- Only state claims that are directly supported by the supplied incident input.
- Do not invent facts, evidence, or details that are not present in the input.
- If the available evidence is insufficient to support a claim, explicitly state
  that uncertainty instead of guessing.

Schema:
{
  "incident_summary": {
    "description": "<string, ≤150 words>",
    "impact": "<string>",
    "affected_system": "<string>"
  },
  "timeline": [
    {
      "timestamp": "<string>",
      "timestamp_type": "exact|inferred|unknown",
      "description": "<string>"
    }
  ],
  "facts": [{ "statement": "<string>", "source": "<field or filename>" }],
  "assumptions": ["<string>"],
  "hypotheses": [
    {
      "title": "<string>",
      "confidence": <int 0-100>,
      "supporting_evidence": ["<string>"],
      "contradicting_evidence": ["<string>"],
      "recommended_tests": ["<string>"]
    }
  ],
  "reasoning_risks": [{ "bias_name": "<string>", "explanation": "<string>" }],
  "next_debugging_actions": [
    { "action": "<string>", "motivation": "<string>", "tool_or_component": "<string>" }
  ],
  "unanswered_questions": ["<string>"],
  "postmortem": {
    "incident_summary": "<string>",
    "timeline": "<string>",
    "root_cause_status_leading_hypothesis": "<string>",
    "impact": "<string>",
    "resolution_steps": "<string>",
    "lessons_learned": "<string>"
  }
}

Rules:
- hypotheses: minimum 3, different causal mechanisms
- reasoning_risks: 1–5 entries
- next_debugging_actions: 1–5 entries, ordered highest to lowest diagnostic value
- unanswered_questions: 1–5 entries
- recommended_tests: minimum 2 per hypothesis
- If no assumptions were made, assumptions = ["No assumptions."]
- If no contradicting evidence exists, contradicting_evidence = ["No contradicting evidence."]\
"""

# ---------------------------------------------------------------------------
# Challenge system message
# ---------------------------------------------------------------------------

_CHALLENGE_SYSTEM = """\
You are a rigorous critical reviewer. You will receive an incident analysis and the
original incident data. Identify weaknesses in the analysis.
Respond ONLY with a JSON object matching this schema:

{
  "unsupported_claims": [
    { "claim": "<string>", "explanation": "<string>" }
  ],
  "alternative_explanations": ["<string>"],
  "reasoning_biases": [
    { "bias_name": "<string>", "cited_claim": "<string>" }
  ]
}

Rules:
- unsupported_claims: statements in the analysis not traceable to the incident data
- alternative_explanations: at least 1, not already in the hypotheses
- reasoning_biases: name the bias, cite the specific claim it applies to\
"""


def build_analysis_prompt(
    fields: dict[str, str], file_content: str
) -> tuple[str, str]:
    """Build the system and user messages for the analysis API call.

    Sections whose source value is empty (after strip) are omitted from the
    user message to save tokens (Requirement 2.5 / Non-functional 5).

    Args:
        fields: Mapping of field names to their text values.  Expected keys:
            ``description``, ``logs``, ``deployment_notes``, ``alerts``,
            ``complaints``.
        file_content: Parsed content of an uploaded file, or ``""`` if none.

    Returns:
        ``(system_msg, user_msg)`` tuple.
    """
    section_map = [
        ("description",      "[INCIDENT DESCRIPTION]"),
        ("logs",             "[APPLICATION LOGS]"),
        ("deployment_notes", "[DEPLOYMENT NOTES]"),
        ("alerts",           "[MONITORING ALERTS]"),
        ("complaints",       "[USER COMPLAINTS]"),
    ]

    parts: list[str] = []
    for key, header in section_map:
        value = fields.get(key, "").strip()
        if value:
            parts.append(f"{header}\n{value}")

    if file_content.strip():
        parts.append(f"[ADDITIONAL FILE CONTENT]\n{file_content.strip()}")

    user_msg = "\n\n".join(parts)
    return _ANALYSIS_SYSTEM, user_msg


def build_challenge_prompt(
    incident_input: str, analysis_report: dict
) -> tuple[str, str]:
    """Build the system and user messages for the challenge API call.

    Args:
        incident_input: The raw incident input text shown to the user, used
            as context for the critical reviewer.
        analysis_report: The parsed analysis report dict (from
            ``AnalysisReport.model_dump()`` or equivalent).

    Returns:
        ``(system_msg, user_msg)`` tuple.
    """
    user_msg = (
        f"[ORIGINAL INCIDENT INPUT]\n{incident_input}\n\n"
        f"[ANALYSIS REPORT]\n{json.dumps(analysis_report, indent=2)}"
    )
    return _CHALLENGE_SYSTEM, user_msg
