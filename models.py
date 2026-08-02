"""
Pydantic v2 data models for IncidentIQ.

These models mirror the JSON schema returned by OpenAI and enforce all
field-level constraints defined in Requirements 3.1–3.4, 4.1–4.5, 5.1–5.3,
6.1, 7.3–7.5.
"""

from typing import Literal

from pydantic import BaseModel, Field


class IncidentSummary(BaseModel):
    """Summary of the incident (Requirement 3.1)."""

    description: str  # ≤150 words — enforced via AI prompt; no char limit on model
    impact: str
    affected_system: str


class TimelineEvent(BaseModel):
    """A single event in the incident timeline (Requirement 3.2)."""

    timestamp: str
    timestamp_type: Literal["exact", "inferred", "unknown"]
    description: str


class Fact(BaseModel):
    """A verifiable fact derived from the incident input (Requirement 3.3)."""

    statement: str
    source: str


class Hypothesis(BaseModel):
    """A root-cause hypothesis with evidence and recommended tests (Requirements 4.1–4.5)."""

    title: str
    confidence: int = Field(ge=0, le=100)  # Requirement 4.2: integer in [0, 100]
    supporting_evidence: list[str] = Field(min_length=1)  # Requirement 4.3: ≥1 supporting evidence item
    contradicting_evidence: list[str]
    recommended_tests: list[str] = Field(min_length=2)  # Requirement 4.5: ≥2 tests


class ReasoningRisk(BaseModel):
    """A cognitive bias or logical fallacy identified in the analysis (Requirement 5.1)."""

    bias_name: str
    explanation: str


class NextDebuggingAction(BaseModel):
    """A concrete next debugging step (Requirement 5.2)."""

    action: str
    motivation: str
    tool_or_component: str


class Postmortem(BaseModel):
    """Draft post-mortem document (Requirement 6.1)."""

    incident_summary: str
    timeline: str
    root_cause_status_leading_hypothesis: str
    impact: str
    resolution_steps: str
    lessons_learned: str


class AnalysisReport(BaseModel):
    """Full analysis report produced by the Analysis Engine (Requirements 3–6)."""

    incident_summary: IncidentSummary
    timeline: list[TimelineEvent] = Field(min_length=1)  # Requirement 3.2: ≥1 timeline event
    facts: list[Fact]
    assumptions: list[str]
    hypotheses: list[Hypothesis] = Field(min_length=3)           # Requirement 4.1: ≥3
    reasoning_risks: list[ReasoningRisk] = Field(min_length=1, max_length=5)       # Requirement 5.1
    next_debugging_actions: list[NextDebuggingAction] = Field(min_length=1, max_length=5)  # Requirement 5.2
    unanswered_questions: list[str] = Field(min_length=1, max_length=5)            # Requirement 5.3
    postmortem: Postmortem


class UnsupportedClaim(BaseModel):
    """A claim in the analysis that has no traceable source (Requirement 7.3)."""

    claim: str
    explanation: str


class ReasoningBias(BaseModel):
    """A reasoning bias found in the analysis (Requirement 7.5)."""

    bias_name: str
    cited_claim: str


class ChallengeReport(BaseModel):
    """Critique of an existing AnalysisReport (Requirements 7.3–7.5)."""

    unsupported_claims: list[UnsupportedClaim]
    alternative_explanations: list[str] = Field(min_length=1)   # Requirement 7.4: ≥1
    reasoning_biases: list[ReasoningBias]
