"""
Pure helper functions for IncidentIQ.

Covers: file parsing, input validation, markdown assembly, and clipboard text
formatting.  No Streamlit imports — all functions are side-effect-free and
independently testable.

Requirements: 1.7–1.11, 6.2–6.3, 10.2–10.3
"""

import csv
import io
import json

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

def validate_inputs(fields: dict[str, str], file_content: str) -> bool:
    """Return True if at least one field or file_content is non-empty after strip.

    Requirement 1.10: if all inputs are blank, the caller should NOT call the API.
    """
    return any(v.strip() for v in fields.values()) or bool(file_content.strip())


# ---------------------------------------------------------------------------
# File parsing
# ---------------------------------------------------------------------------

def parse_file(uploaded_file) -> tuple[str, str | None]:
    """Parse an uploaded file into plain text.

    Parameters
    ----------
    uploaded_file:
        A file-like object with attributes ``name`` (str), ``size`` (int),
        and a ``read()`` method that returns bytes.

    Returns
    -------
    (content_text, None)  on success
    ("", error_message)   on failure (file too large / empty / malformed)

    Requirements 1.7–1.9, 1.11
    """
    try:
        # Size check (Requirement 1.6 / 1.11)
        if uploaded_file.size > _MAX_FILE_BYTES:
            return "", f"File '{uploaded_file.name}' exceeds the 5 MB size limit."

        name: str = uploaded_file.name.lower()

        # ---- TXT --------------------------------------------------------
        if name.endswith(".txt"):
            raw = uploaded_file.read()
            if not raw:
                return "", "File is empty."
            content = raw.decode("utf-8")
            if not content.strip():
                return "", "File is empty."
            return content, None

        # ---- JSON -------------------------------------------------------
        elif name.endswith(".json"):
            raw = uploaded_file.read()
            if not raw:
                return "", "File is empty."
            obj = json.loads(raw.decode("utf-8"))
            if not obj:
                return "", "File is empty."
            # Flat dict → "key: value" lines; nested → pretty JSON
            if isinstance(obj, dict) and all(
                not isinstance(v, (dict, list)) for v in obj.values()
            ):
                content = "\n".join(f"{k}: {v}" for k, v in obj.items())
            else:
                content = json.dumps(obj, indent=2)
            return content, None

        # ---- CSV --------------------------------------------------------
        elif name.endswith(".csv"):
            raw = uploaded_file.read()
            if not raw:
                return "", "File is empty."
            text = raw.decode("utf-8")
            reader = csv.DictReader(io.StringIO(text))
            rows = []
            for row in reader:
                rows.append("\n".join(f"{col}: {val}" for col, val in row.items()))
            if not rows:
                return "", "File is empty."
            content = "\n\n".join(rows)
            return content, None

        else:
            return "", f"Unsupported file type: '{uploaded_file.name}'."

    except UnicodeDecodeError as exc:
        return "", f"Could not decode '{uploaded_file.name}': {exc}"
    except json.JSONDecodeError as exc:
        return "", f"Invalid JSON in '{uploaded_file.name}': {exc}"
    except csv.Error as exc:
        return "", f"CSV error in '{uploaded_file.name}': {exc}"
    except Exception as exc:  # noqa: BLE001
        return "", f"Error reading '{uploaded_file.name}': {exc}"


# ---------------------------------------------------------------------------
# Markdown export
# ---------------------------------------------------------------------------

def assemble_markdown(report: dict, challenge: dict | None = None) -> str:
    """Build the full export Markdown string.

    Parameters
    ----------
    report:
        Dict representation of an AnalysisReport (keys match Pydantic model).
    challenge:
        Optional dict representation of a ChallengeReport.

    Requirements 10.2–10.3
    """
    lines: list[str] = []

    lines.append("# IncidentIQ — Incident Analysis Report\n")

    # -- Incident Summary -------------------------------------------------
    lines.append("## Incident Summary\n")
    summary = report.get("incident_summary", {})
    lines.append(f"**Description:** {summary.get('description', '')}\n")
    lines.append(f"**Impact:** {summary.get('impact', '')}\n")
    lines.append(f"**Affected System:** {summary.get('affected_system', '')}\n")

    # -- Timeline ---------------------------------------------------------
    lines.append("## Timeline\n")
    lines.append("| Timestamp | Type | Description |")
    lines.append("|-----------|------|-------------|")
    for event in report.get("timeline", []):
        ts = event.get("timestamp", "")
        ts_type = event.get("timestamp_type", "")
        desc = event.get("description", "")
        lines.append(f"| {ts} | {ts_type} | {desc} |")
    lines.append("")

    # -- Facts ------------------------------------------------------------
    lines.append("## Facts\n")
    for fact in report.get("facts", []):
        lines.append(f"- {fact.get('statement', '')} *(source: {fact.get('source', '')})*")
    lines.append("")

    # -- Assumptions ------------------------------------------------------
    lines.append("## Assumptions\n")
    for assumption in report.get("assumptions", []):
        lines.append(f"- {assumption}")
    lines.append("")

    # -- Hypotheses -------------------------------------------------------
    lines.append("## Hypotheses\n")
    for idx, hyp in enumerate(report.get("hypotheses", []), start=1):
        lines.append(
            f"### Hypothesis {idx}: {hyp.get('title', '')}  — "
            f"Confidence: {hyp.get('confidence', 0)}%\n"
        )
        lines.append("**Supporting Evidence:**")
        for ev in hyp.get("supporting_evidence", []):
            lines.append(f"- {ev}")
        lines.append("\n**Contradicting Evidence:**")
        for ev in hyp.get("contradicting_evidence", []):
            lines.append(f"- {ev}")
        lines.append("\n**Recommended Tests:**")
        for t in hyp.get("recommended_tests", []):
            lines.append(f"- {t}")
        lines.append("")

    # -- Reasoning Risks --------------------------------------------------
    lines.append("## Reasoning Risks\n")
    for risk in report.get("reasoning_risks", []):
        lines.append(f"- **{risk.get('bias_name', '')}**: {risk.get('explanation', '')}")
    lines.append("")

    # -- Next Debugging Actions -------------------------------------------
    lines.append("## Next Debugging Actions\n")
    for action in report.get("next_debugging_actions", []):
        lines.append(
            f"- **{action.get('action', '')}** — "
            f"{action.get('motivation', '')} "
            f"*(tool/component: {action.get('tool_or_component', '')})*"
        )
    lines.append("")

    # -- Unanswered Questions ---------------------------------------------
    lines.append("## Unanswered Questions\n")
    for q in report.get("unanswered_questions", []):
        lines.append(f"- {q}")
    lines.append("")

    lines.append("---\n")

    # -- Draft Postmortem -------------------------------------------------
    lines.append("## Draft Postmortem\n")
    pm = report.get("postmortem", {})
    lines.append("### Incident Summary\n")
    lines.append(pm.get("incident_summary", ""))
    lines.append("")
    lines.append("### Timeline\n")
    lines.append(pm.get("timeline", ""))
    lines.append("")
    lines.append("### Root Cause Status / Leading Hypothesis\n")
    lines.append(pm.get("root_cause_status_leading_hypothesis", ""))
    lines.append("")
    lines.append("### Impact\n")
    lines.append(pm.get("impact", ""))
    lines.append("")
    lines.append("### Resolution Steps\n")
    lines.append(pm.get("resolution_steps", ""))
    lines.append("")
    lines.append("### Lessons Learned\n")
    lines.append(pm.get("lessons_learned", ""))
    lines.append("")

    # -- Challenge Report (optional) --------------------------------------
    if challenge is not None:
        lines.append("---\n")
        lines.append("## Challenge Report\n")

        lines.append("### Unsupported Claims\n")
        for claim in challenge.get("unsupported_claims", []):
            lines.append(
                f"- **{claim.get('claim', '')}**: {claim.get('explanation', '')}"
            )
        lines.append("")

        lines.append("### Alternative Explanations\n")
        for alt in challenge.get("alternative_explanations", []):
            lines.append(f"- {alt}")
        lines.append("")

        lines.append("### Reasoning Biases\n")
        for bias in challenge.get("reasoning_biases", []):
            lines.append(
                f"- **{bias.get('bias_name', '')}**: {bias.get('cited_claim', '')}"
            )
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Clipboard text formatting
# ---------------------------------------------------------------------------

def format_postmortem_text(postmortem: dict) -> str:
    """Return all six postmortem subsections as plain text for clipboard copy.

    Requirement 6.2
    """
    sections = [
        ("Incident Summary", postmortem.get("incident_summary", "")),
        ("Timeline", postmortem.get("timeline", "")),
        (
            "Root Cause Status / Leading Hypothesis",
            postmortem.get("root_cause_status_leading_hypothesis", ""),
        ),
        ("Impact", postmortem.get("impact", "")),
        ("Resolution Steps", postmortem.get("resolution_steps", "")),
        ("Lessons Learned", postmortem.get("lessons_learned", "")),
    ]
    parts = [f"=== {title} ===\n{body}" for title, body in sections]
    return "\n\n".join(parts)
