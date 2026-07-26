"""
Unit tests for models.py — sub-task 1.1.

Validates: Requirements 4.2, 7.4
"""

import pytest
from pydantic import ValidationError

from models import (
    AnalysisReport,
    ChallengeReport,
    Fact,
    Hypothesis,
    IncidentSummary,
    NextDebuggingAction,
    Postmortem,
    ReasoningBias,
    ReasoningRisk,
    TimelineEvent,
    UnsupportedClaim,
)


# ---------------------------------------------------------------------------
# Helpers — minimal valid payloads
# ---------------------------------------------------------------------------

def _valid_hypothesis(confidence: int = 50) -> dict:
    return {
        "title": "Database connection pool exhausted",
        "confidence": confidence,
        "supporting_evidence": ["Error log shows pool timeout"],
        "contradicting_evidence": ["No contradicting evidence."],
        "recommended_tests": ["Check pool metrics", "Restart connection pool"],
    }


def _valid_analysis_report_payload() -> dict:
    return {
        "incident_summary": {
            "description": "Checkout service failed.",
            "impact": "100% of checkout transactions failed.",
            "affected_system": "checkout-service",
        },
        "timeline": [
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "timestamp_type": "exact",
                "description": "Deployment started.",
            }
        ],
        "facts": [
            {"statement": "Error rate spiked to 100%.", "source": "alerts"}
        ],
        "assumptions": ["No assumptions."],
        "hypotheses": [
            _valid_hypothesis(70),
            _valid_hypothesis(50),
            _valid_hypothesis(30),
        ],
        "reasoning_risks": [
            {"bias_name": "Confirmation bias", "explanation": "Applies here."}
        ],
        "next_debugging_actions": [
            {
                "action": "Check DB pool",
                "motivation": "Pool timeouts observed.",
                "tool_or_component": "postgresql",
            }
        ],
        "unanswered_questions": ["Was the deployment rolled back?"],
        "postmortem": {
            "incident_summary": "Checkout failed.",
            "timeline": "10:00 deployment.",
            "root_cause_status_leading_hypothesis": "DB pool exhaustion.",
            "impact": "All checkouts failed.",
            "resolution_steps": "Rolled back deployment.",
            "lessons_learned": "Test DB pool limits before deploying.",
        },
    }


# ---------------------------------------------------------------------------
# AnalysisReport validation
# ---------------------------------------------------------------------------

class TestAnalysisReport:
    def test_valid_analysis_report_parses_successfully(self):
        report = AnalysisReport.model_validate(_valid_analysis_report_payload())
        assert report.incident_summary.affected_system == "checkout-service"
        assert len(report.hypotheses) == 3

    def test_analysis_report_rejects_missing_field(self):
        """Requirement 4.2 — missing required field must raise ValidationError."""
        payload = _valid_analysis_report_payload()
        del payload["incident_summary"]  # required field removed
        with pytest.raises(ValidationError):
            AnalysisReport.model_validate(payload)

    def test_analysis_report_rejects_too_few_hypotheses(self):
        """Requirement 4.1 — fewer than 3 hypotheses must raise ValidationError."""
        payload = _valid_analysis_report_payload()
        payload["hypotheses"] = [_valid_hypothesis()]  # only 1
        with pytest.raises(ValidationError):
            AnalysisReport.model_validate(payload)

    def test_analysis_report_rejects_too_many_reasoning_risks(self):
        """Requirement 5.1 — more than 5 reasoning risks must raise ValidationError."""
        payload = _valid_analysis_report_payload()
        payload["reasoning_risks"] = [
            {"bias_name": f"Bias {i}", "explanation": "x"} for i in range(6)
        ]
        with pytest.raises(ValidationError):
            AnalysisReport.model_validate(payload)

    def test_analysis_report_rejects_empty_reasoning_risks(self):
        """Requirement 5.1 — zero reasoning risks must raise ValidationError."""
        payload = _valid_analysis_report_payload()
        payload["reasoning_risks"] = []
        with pytest.raises(ValidationError):
            AnalysisReport.model_validate(payload)

    def test_analysis_report_rejects_empty_unanswered_questions(self):
        """Requirement 5.3 — zero unanswered questions must raise ValidationError."""
        payload = _valid_analysis_report_payload()
        payload["unanswered_questions"] = []
        with pytest.raises(ValidationError):
            AnalysisReport.model_validate(payload)

    def test_analysis_report_rejects_too_many_unanswered_questions(self):
        """Requirement 5.3 — more than 5 unanswered questions must raise ValidationError."""
        payload = _valid_analysis_report_payload()
        payload["unanswered_questions"] = [f"Q{i}" for i in range(6)]
        with pytest.raises(ValidationError):
            AnalysisReport.model_validate(payload)


# ---------------------------------------------------------------------------
# Hypothesis validation
# ---------------------------------------------------------------------------

class TestHypothesis:
    def test_valid_hypothesis(self):
        h = Hypothesis(**_valid_hypothesis(100))
        assert h.confidence == 100

    def test_hypothesis_rejects_confidence_above_100(self):
        """Requirement 4.2 — confidence > 100 must raise ValidationError."""
        with pytest.raises(ValidationError):
            Hypothesis(**_valid_hypothesis(101))

    def test_hypothesis_rejects_negative_confidence(self):
        """Requirement 4.2 — confidence < 0 must raise ValidationError."""
        with pytest.raises(ValidationError):
            Hypothesis(**_valid_hypothesis(-1))

    def test_hypothesis_accepts_boundary_values(self):
        """Confidence values 0 and 100 are both valid."""
        Hypothesis(**_valid_hypothesis(0))
        Hypothesis(**_valid_hypothesis(100))

    def test_hypothesis_rejects_too_few_recommended_tests(self):
        """Requirement 4.5 — fewer than 2 recommended tests must raise ValidationError."""
        data = _valid_hypothesis()
        data["recommended_tests"] = ["only one test"]
        with pytest.raises(ValidationError):
            Hypothesis(**data)


# ---------------------------------------------------------------------------
# TimelineEvent validation
# ---------------------------------------------------------------------------

class TestTimelineEvent:
    def test_valid_exact_timestamp_type(self):
        e = TimelineEvent(timestamp="10:00", timestamp_type="exact", description="Started.")
        assert e.timestamp_type == "exact"

    def test_valid_inferred_timestamp_type(self):
        e = TimelineEvent(timestamp="~10:05", timestamp_type="inferred", description="Probably.")
        assert e.timestamp_type == "inferred"

    def test_valid_unknown_timestamp_type(self):
        e = TimelineEvent(timestamp="unknown", timestamp_type="unknown", description="No time.")
        assert e.timestamp_type == "unknown"

    def test_invalid_timestamp_type_raises(self):
        with pytest.raises(ValidationError):
            TimelineEvent(timestamp="10:00", timestamp_type="approximate", description="Bad.")


# ---------------------------------------------------------------------------
# ChallengeReport validation
# ---------------------------------------------------------------------------

class TestChallengeReport:
    def _valid_challenge_payload(self) -> dict:
        return {
            "unsupported_claims": [
                {"claim": "DB was overloaded.", "explanation": "Not in logs."}
            ],
            "alternative_explanations": ["Network partition caused failures."],
            "reasoning_biases": [
                {"bias_name": "Anchoring", "cited_claim": "First hypothesis."}
            ],
        }

    def test_valid_challenge_report(self):
        cr = ChallengeReport.model_validate(self._valid_challenge_payload())
        assert len(cr.alternative_explanations) == 1

    def test_challenge_report_rejects_empty_alternatives(self):
        """Requirement 7.4 — empty alternative_explanations must raise ValidationError."""
        payload = self._valid_challenge_payload()
        payload["alternative_explanations"] = []
        with pytest.raises(ValidationError):
            ChallengeReport.model_validate(payload)

    def test_challenge_report_rejects_missing_field(self):
        """Missing required field must raise ValidationError."""
        payload = self._valid_challenge_payload()
        del payload["unsupported_claims"]
        with pytest.raises(ValidationError):
            ChallengeReport.model_validate(payload)
