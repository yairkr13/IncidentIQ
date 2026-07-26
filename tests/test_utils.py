"""
Unit tests for utils.py.

Sub-task 2.1 — Requirements 1.7–1.11, 10.2–10.3
"""

import io
import json

import pytest

from utils import (
    assemble_markdown,
    format_postmortem_text,
    parse_file,
    validate_inputs,
)


# ---------------------------------------------------------------------------
# Minimal mock for Streamlit's UploadedFile
# ---------------------------------------------------------------------------

class MockUploadedFile:
    """Lightweight stand-in for streamlit.runtime.uploaded_file_manager.UploadedFile."""

    def __init__(self, data: bytes, name: str):
        self.name = name
        self.size = len(data)
        self._stream = io.BytesIO(data)

    def read(self) -> bytes:
        return self._stream.read()


# ---------------------------------------------------------------------------
# Helpers shared across tests
# ---------------------------------------------------------------------------

def _minimal_report() -> dict:
    """Return the smallest valid report dict that assemble_markdown can consume."""
    return {
        "incident_summary": {
            "description": "Checkout failed after deploy.",
            "impact": "Revenue loss",
            "affected_system": "Checkout service",
        },
        "timeline": [
            {"timestamp": "14:00", "timestamp_type": "exact", "description": "Deploy started"}
        ],
        "facts": [{"statement": "Error rate spiked.", "source": "logs"}],
        "assumptions": ["No assumptions."],
        "hypotheses": [
            {
                "title": "DB connection pool exhausted",
                "confidence": 80,
                "supporting_evidence": ["High DB CPU"],
                "contradicting_evidence": ["No contradicting evidence."],
                "recommended_tests": ["Check pool config", "Run load test"],
            }
        ],
        "reasoning_risks": [{"bias_name": "Confirmation bias", "explanation": "Only checked DB."}],
        "next_debugging_actions": [
            {
                "action": "Check DB pool",
                "motivation": "High connection count",
                "tool_or_component": "PostgreSQL",
            }
        ],
        "unanswered_questions": ["Was the deploy rolled back?"],
        "postmortem": {
            "incident_summary": "Checkout failed.",
            "timeline": "14:00 deploy, 14:05 errors.",
            "root_cause_status_leading_hypothesis": "DB pool exhausted.",
            "impact": "~$10k revenue loss.",
            "resolution_steps": "Rolled back deploy.",
            "lessons_learned": "Add connection pool monitoring.",
        },
    }


def _minimal_challenge() -> dict:
    return {
        "unsupported_claims": [
            {"claim": "DB was the root cause", "explanation": "No DB logs provided."}
        ],
        "alternative_explanations": ["Cache invalidation caused latency spike."],
        "reasoning_biases": [
            {"bias_name": "Anchoring", "cited_claim": "DB was the root cause"}
        ],
    }


# ---------------------------------------------------------------------------
# validate_inputs
# ---------------------------------------------------------------------------

class TestValidateInputs:
    def test_validate_inputs_all_empty(self):
        """All blank fields and no file content → False (Requirement 1.10)."""
        fields = {
            "description": "",
            "logs": "",
            "deployment_notes": "",
            "alerts": "",
            "complaints": "",
        }
        assert validate_inputs(fields, "") is False

    def test_validate_inputs_all_whitespace(self):
        """All-whitespace fields and no file content → False."""
        fields = {
            "description": "   ",
            "logs": "\t\n",
            "deployment_notes": "  ",
            "alerts": "",
            "complaints": "\n",
        }
        assert validate_inputs(fields, "") is False

    def test_validate_inputs_one_field(self):
        """One non-blank field → True."""
        fields = {
            "description": "checkout error",
            "logs": "",
            "deployment_notes": "",
            "alerts": "",
            "complaints": "",
        }
        assert validate_inputs(fields, "") is True

    def test_validate_inputs_only_file_content(self):
        """Empty fields but non-blank file_content → True."""
        fields = {k: "" for k in ["description", "logs", "deployment_notes", "alerts", "complaints"]}
        assert validate_inputs(fields, "some log content") is True

    def test_validate_inputs_whitespace_file_content(self):
        """Empty fields and whitespace-only file_content → False."""
        fields = {k: "" for k in ["description", "logs", "deployment_notes", "alerts", "complaints"]}
        assert validate_inputs(fields, "   \n\t  ") is False


# ---------------------------------------------------------------------------
# parse_file
# ---------------------------------------------------------------------------

class TestParseFileTxt:
    def test_parse_file_txt_basic(self):
        f = MockUploadedFile(b"hello world", "test.txt")
        content, err = parse_file(f)
        assert err is None
        assert content == "hello world"

    def test_parse_file_txt_empty(self):
        """Empty .txt file → error 'File is empty.' (Requirement 1.11)."""
        f = MockUploadedFile(b"", "empty.txt")
        content, err = parse_file(f)
        assert content == ""
        assert err == "File is empty."

    def test_parse_file_txt_whitespace_only(self):
        """Whitespace-only .txt file → error 'File is empty.'"""
        f = MockUploadedFile(b"   \n\t  ", "spaces.txt")
        content, err = parse_file(f)
        assert content == ""
        assert err == "File is empty."

    def test_parse_file_txt_unicode(self):
        """Unicode characters round-trip correctly."""
        text = "Błąd: połączenie zerwane 🔥"
        f = MockUploadedFile(text.encode("utf-8"), "unicode.txt")
        content, err = parse_file(f)
        assert err is None
        assert content == text

    def test_parse_file_txt_size_limit(self):
        """File exceeding 5 MB → size-limit error."""
        big = b"x" * (5 * 1024 * 1024 + 1)
        f = MockUploadedFile(big, "big.txt")
        content, err = parse_file(f)
        assert content == ""
        assert "5 MB" in err


class TestParseFileJson:
    def test_parse_file_json_flat(self):
        """Flat JSON dict → 'key: value' lines."""
        data = json.dumps({"env": "prod", "version": "1.2.3"}).encode()
        f = MockUploadedFile(data, "info.json")
        content, err = parse_file(f)
        assert err is None
        assert "env: prod" in content
        assert "version: 1.2.3" in content

    def test_parse_file_json_nested(self):
        """Nested JSON dict → falls back to json.dumps pretty-print."""
        data = json.dumps({"outer": {"inner": "value"}}).encode()
        f = MockUploadedFile(data, "nested.json")
        content, err = parse_file(f)
        assert err is None
        # Should contain pretty-printed JSON, not flat key: value
        assert '"outer"' in content
        assert '"inner"' in content

    def test_parse_file_json_empty(self):
        f = MockUploadedFile(b"", "empty.json")
        content, err = parse_file(f)
        assert content == ""
        assert err == "File is empty."

    def test_parse_file_json_invalid(self):
        f = MockUploadedFile(b"{not valid json}", "bad.json")
        content, err = parse_file(f)
        assert content == ""
        assert err is not None
        assert "bad.json" in err


class TestParseFileCsv:
    def test_parse_file_csv_single_row(self):
        """Single-row CSV → 'col: val' output (Requirement 1.9)."""
        csv_data = b"name,status\nweb-01,healthy"
        f = MockUploadedFile(csv_data, "hosts.csv")
        content, err = parse_file(f)
        assert err is None
        assert "name: web-01" in content
        assert "status: healthy" in content

    def test_parse_file_csv_multiple_rows(self):
        """Multiple rows are separated by blank lines."""
        csv_data = b"col1,col2\nval1a,val1b\nval2a,val2b"
        f = MockUploadedFile(csv_data, "data.csv")
        content, err = parse_file(f)
        assert err is None
        assert "col1: val1a" in content
        assert "col1: val2a" in content
        # blank-line separator between rows
        assert "\n\n" in content

    def test_parse_file_csv_empty(self):
        f = MockUploadedFile(b"", "empty.csv")
        content, err = parse_file(f)
        assert content == ""
        assert err == "File is empty."

    def test_parse_file_csv_header_only(self):
        """CSV with only a header row and no data rows → File is empty."""
        f = MockUploadedFile(b"col1,col2\n", "header_only.csv")
        content, err = parse_file(f)
        assert content == ""
        assert err == "File is empty."


# ---------------------------------------------------------------------------
# assemble_markdown
# ---------------------------------------------------------------------------

class TestAssembleMarkdown:
    def test_assemble_markdown_no_challenge(self):
        """No challenge → 'Challenge Report' heading absent (Requirement 10.2)."""
        md = assemble_markdown(_minimal_report())
        assert "## Challenge Report" not in md

    def test_assemble_markdown_with_challenge(self):
        """With challenge → 'Challenge Report' heading present (Requirement 10.3)."""
        md = assemble_markdown(_minimal_report(), challenge=_minimal_challenge())
        assert "## Challenge Report" in md

    def test_assemble_markdown_contains_top_level_heading(self):
        md = assemble_markdown(_minimal_report())
        assert "# IncidentIQ — Incident Analysis Report" in md

    def test_assemble_markdown_contains_draft_postmortem(self):
        md = assemble_markdown(_minimal_report())
        assert "## Draft Postmortem" in md

    def test_assemble_markdown_timeline_table(self):
        """Timeline is rendered as a Markdown table."""
        md = assemble_markdown(_minimal_report())
        assert "| Timestamp | Type | Description |" in md
        assert "14:00" in md

    def test_assemble_markdown_hypothesis_confidence(self):
        """Hypothesis confidence value appears in output."""
        md = assemble_markdown(_minimal_report())
        assert "Confidence: 80%" in md

    def test_assemble_markdown_challenge_sections(self):
        """Challenge report sections appear when challenge is provided."""
        md = assemble_markdown(_minimal_report(), challenge=_minimal_challenge())
        assert "### Unsupported Claims" in md
        assert "### Alternative Explanations" in md
        assert "### Reasoning Biases" in md

    def test_assemble_markdown_returns_string(self):
        result = assemble_markdown(_minimal_report())
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# format_postmortem_text
# ---------------------------------------------------------------------------

class TestFormatPostmortemText:
    def test_contains_all_six_sections(self):
        pm = _minimal_report()["postmortem"]
        text = format_postmortem_text(pm)
        assert "Incident Summary" in text
        assert "Timeline" in text
        assert "Root Cause Status / Leading Hypothesis" in text
        assert "Impact" in text
        assert "Resolution Steps" in text
        assert "Lessons Learned" in text

    def test_contains_actual_values(self):
        pm = _minimal_report()["postmortem"]
        text = format_postmortem_text(pm)
        assert "Checkout failed." in text
        assert "~$10k revenue loss." in text

    def test_returns_string(self):
        pm = _minimal_report()["postmortem"]
        assert isinstance(format_postmortem_text(pm), str)
