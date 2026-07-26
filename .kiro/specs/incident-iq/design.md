# Design Document — IncidentIQ

## Overview

IncidentIQ is a single-page Streamlit application that accepts incident context as text
and files, calls the OpenAI Chat Completions API twice (once for analysis, once for
challenge), and renders a structured report with export and clipboard actions. All
application state lives in `st.session_state`. No server-side persistence, no external
services beyond OpenAI, no framework layers.

---

## Architecture

```
┌──────────────────────────────────────────────┐
│                  Browser                     │
│  ┌──────────────────────────────────────────┐│
│  │           Streamlit UI  (app.py)          ││
│  │                                           ││
│  │  Input Panel          Results Panel       ││
│  │  ─────────────        ────────────        ││
│  │  Text areas           Section expanders   ││
│  │  File uploader        Confidence bars     ││
│  │  Analyze button       Challenge Report    ││
│  │  Reset button         Export / Copy btns  ││
│  └──────────┬────────────────────────────────┘│
└─────────────┼────────────────────────────────-┘
              │
    ┌─────────▼──────────┐   ┌──────────────────┐
    │  prompts.py        │   │  utils.py        │
    │  build_analysis_   │   │  parse_file()    │
    │    prompt()        │   │  assemble_md()   │
    │  build_challenge_  │   │  validate_       │
    │    prompt()        │   │    inputs()      │
    └─────────┬──────────┘   └──────────────────┘
              │
    ┌─────────▼──────────┐
    │  OpenAI API        │
    │  (two calls,       │
    │   JSON mode,       │
    │   60 s timeout)    │
    └────────────────────┘
```

**File structure (minimal):**

```
app.py          — Streamlit UI, session state, button handlers
ai_service.py   — OpenAI client construction, API calls
prompts.py      — Prompt construction (system + user messages)
models.py       — Pydantic models for AnalysisReport and ChallengeReport
utils.py        — File parsing, markdown assembly, input validation
```

No further files are introduced. Third-party dependencies: `streamlit`, `openai`, `pydantic`.
File parsing uses the standard library (`io`, `csv`, `json`).

---

## Session State Schema

All runtime state is stored in `st.session_state`. Keys and types:

| Key                   | Type               | Description                                         |
|-----------------------|--------------------|-----------------------------------------------------|
| `analysis_report`     | `dict \| None`     | Parsed Analysis_Report JSON object                  |
| `challenge_report`    | `dict \| None`     | Parsed Challenge_Report JSON object                 |
| `api_error`           | `str \| None`      | Last API error message to display                   |
| `file_error`          | `str \| None`      | Last file-parse error message to display            |
| `api_key_valid`       | `bool`             | Whether a non-empty API key was found at startup    |

Input field values are managed directly by Streamlit widget `key=` parameters (Streamlit
persists them automatically across reruns while the session is live).  
`session_state` keys for the five text inputs:

| Widget key              | Type   | Max chars |
|-------------------------|--------|-----------|
| `inp_description`       | `str`  | 10 000    |
| `inp_logs`              | `str`  | 50 000    |
| `inp_deployment_notes`  | `str`  | 10 000    |
| `inp_alerts`            | `str`  | 10 000    |
| `inp_complaints`        | `str`  | 10 000    |

**Initialization** (called once at module level):

```python
defaults = {
    "analysis_report": None,
    "challenge_report": None,
    "api_error": None,
    "file_error": None,
    "api_key_valid": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v
```

---

## OpenAI Prompt Strategy

### Shared settings

- Model: `gpt-4o` (configurable via `MODEL` constant at top of `app.py`)
- `response_format={"type": "json_object"}` on both calls
- `timeout=60` via `openai.OpenAI(timeout=60)` client construction
- Temperature: `0` for determinism

### Analysis call (`prompts.py: build_analysis_prompt`)

**System message** — concise role + JSON schema contract:

```
You are an expert site-reliability engineer and incident analyst.
Respond ONLY with a JSON object that exactly matches the schema below.
Do not include commentary outside the JSON.

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
- If no contradicting evidence exists, contradicting_evidence = ["No contradicting evidence."]
```

**User message** — assembled from all non-empty inputs:

```
[INCIDENT DESCRIPTION]
{description}

[APPLICATION LOGS]
{logs}

[DEPLOYMENT NOTES]
{deployment_notes}

[MONITORING ALERTS]
{alerts}

[USER COMPLAINTS]
{complaints}

[ADDITIONAL FILE CONTENT]
{file_content}
```

Sections whose source field is empty are omitted entirely to save tokens.

### Challenge call (`prompts.py: build_challenge_prompt`)

**System message:**

```
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
- reasoning_biases: name the bias, cite the specific claim it applies to
```

**User message:**

```
[ORIGINAL INCIDENT INPUT]
{incident_input_text}

[ANALYSIS REPORT]
{json.dumps(analysis_report, indent=2)}
```

### API call wrapper (in `app.py`)

```python
def call_openai(client: openai.OpenAI, system: str, user: str) -> dict:
    """Make a single chat completion call. Returns parsed dict or raises."""
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(response.choices[0].message.content)
```

Errors (`openai.APITimeoutError`, `openai.APIError`, `json.JSONDecodeError`,
`KeyError`) are caught in the calling button handler and stored in
`st.session_state.api_error`.

---

## File Parsing (`utils.py`)

```python
def parse_file(uploaded_file) -> tuple[str, str | None]:
    """
    Returns (content_text, error_message).
    content_text is "" and error_message is set on failure.
    """
```

| Extension | Logic |
|-----------|-------|
| `.txt`    | `uploaded_file.read().decode("utf-8")` |
| `.json`   | `json.load(uploaded_file)` → flatten with `"\n".join(f"{k}: {v}" for k, v in obj.items())` for flat dicts; for nested, use `json.dumps(obj, indent=2)` |
| `.csv`    | `csv.DictReader(io.StringIO(text))` → each row rendered as `"\n".join(f"{col}: {val}" for col, val in row.items())`, rows separated by blank lines |

All exceptions (`UnicodeDecodeError`, `json.JSONDecodeError`, `csv.Error`,
`ValueError`) are caught and returned as the error string. Empty file → error
`"File is empty."`.

Size limit (5 MB) is enforced by passing `accept` and checking
`uploaded_file.size` before parsing.

---

## Input Validation (`utils.py`)

```python
def validate_inputs(fields: dict[str, str], file_content: str) -> bool:
    """Returns True if at least one field or file_content is non-empty after strip."""
    return any(v.strip() for v in fields.values()) or bool(file_content.strip())
```

Called before every API request; if `False`, an `st.warning` is shown and the
API call is skipped.

---

## UI Layout

```
st.set_page_config(layout="wide")

─ Page title + subheader
─ API key error banner (if api_key_valid is False: "Set OPENAI_API_KEY to enable analysis. The interface is active for exploration.")

Left column (40%)            Right column (60%)
─────────────────            ──────────────────
st.text_area × 5             [shown only when analysis_report is set]
st.file_uploader             st.expander("Incident Summary")   [open]
                             st.expander("Timeline")           [open]
[Analyze Incident] btn       st.expander("Facts")              [open]
[Reset] btn                  st.expander("Assumptions")        [open]
                             st.expander("Hypotheses +         [open]
                               Recommended Tests")
                             st.expander("Reasoning Risks")    [open]
                             st.expander("Next Debugging       [open]
                               Actions")
                             st.expander("Unanswered           [open]
                               Questions")
                             st.expander("Draft Postmortem")   [closed]
                             ── st.download_button (Export MD) ──
                             ── Copy Postmortem button ──
                             ── [Challenge Analysis] button ──
                             st.divider()
                             [Challenge Report section, if present]
```

**Confidence bar rendering** (Hypotheses expander):

```python
st.write(f"**Confidence:** {h['confidence']}%")
st.progress(h["confidence"] / 100)
```

**Copy-to-clipboard** (Draft Postmortem):

```python
postmortem_text = format_postmortem_text(report["postmortem"])
copy_js = f"""
<script>
function copyText() {{
    navigator.clipboard.writeText({json.dumps(postmortem_text)})
        .then(() => {{ document.getElementById('msg').innerText = '✅ Copied!'; }})
        .catch(() => {{ document.getElementById('msg').innerText =
            '❌ Copy failed — please select and copy manually.'; }});
}}
</script>
<button onclick="copyText()">📋 Copy Postmortem</button>
<span id="msg"></span>
"""
st.components.v1.html(copy_js, height=50)
```

---

## Data Flow

```
User fills inputs / uploads file
         │
         ▼
validate_inputs() ──✗──► st.warning, stop
         │ ✓
         ▼
parse_file() → appends file_content to prompt
         │
         ▼
build_analysis_prompt(fields, file_content)
         │
         ▼
st.spinner("Analyzing...") + ai_service.run_analysis(client, system, user)
         │   ← Pydantic validates response internally
    ┌────┴────┐
    │success  │ APIError / ValidationError
    ▼         ▼
st.session_state   st.error(...), stop
.analysis_report   (AnalysisReport instance)
         │
         ▼
Render Results Panel
         │
  [Challenge button clicked]
         │
         ▼
build_challenge_prompt(incident_input, analysis_report)
         │
         ▼
st.spinner("Challenging...") + ai_service.run_challenge(client, system, user)
         │
    ┌────┴────┐
    │success  │ error
    ▼         ▼
st.session_state   st.error(...)
.challenge_report  (analysis_report unchanged)
```

---

## Schema Validation (`models.py`)

Pydantic v2 is used for all response validation. `ai_service.py` calls
`AnalysisReport.model_validate(json.loads(response_content))` and
`ChallengeReport.model_validate(...)`. A `pydantic.ValidationError` is raised if any
required field is missing or fails a constraint; `app.py` catches it and calls
`st.error(str(e))`. No manual key-checking code is needed.

---

## Markdown Export Assembly (`utils.py`)

```python
def assemble_markdown(report: dict, challenge: dict | None = None) -> str:
    """Build the full export .md string from report (and optional challenge)."""
```

Structure of the output:

```markdown
# IncidentIQ — Incident Analysis Report

## Incident Summary
...

## Timeline
| Timestamp | Type | Description |
|...

## Facts
...

## Assumptions
...

## Hypotheses
### Hypothesis 1: {title}  — Confidence: {n}%
...

## Reasoning Risks
...

## Next Debugging Actions
...

## Unanswered Questions
...

---

## Draft Postmortem
### Incident Summary
...
### Timeline
...
### Root Cause Status / Leading Hypothesis
...
### Impact
...
### Resolution Steps
...
### Lessons Learned
...

---

## Challenge Report          ← appended only if challenge is not None
### Unsupported Claims
...
### Alternative Explanations
...
### Reasoning Biases
...
```

The assembled string is passed directly to `st.download_button(data=md_string,
file_name="incident_analysis.md", mime="text/markdown")`. No file is written to disk.

---

## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid
executions of a system — essentially, a formal statement about what the system should
do. Properties serve as the bridge between human-readable specifications and
machine-verifiable correctness guarantees.

PBT is applicable here for the pure-function layer: file parsers, schema validators,
markdown assembler, and input validator. These functions have clear inputs/outputs,
and varied inputs meaningfully exercise edge cases. The PBT library used is
**Hypothesis** (Python).

Three high-value property tests are included; all others are covered by example-based
unit tests, which are sufficient given the straightforward logic.

### Property 1: TXT file parsing is a round-trip

*For any* non-empty UTF-8 string, encoding it as bytes and passing it through
`parse_file` as a `.txt` upload SHALL return the original string with no error.

**Validates: Requirements 1.7**

---

### Property 2: Input validation rejects all-whitespace input

*For any* combination of the five incident input fields where every value is composed
solely of whitespace characters and no file content is provided, `validate_inputs`
SHALL return `False`.

**Validates: Requirements 1.10**

---

### Property 3: Pydantic rejects out-of-range confidence scores

*For any* integer outside the range [0, 100] used as a `Hypothesis.confidence` value,
Pydantic SHALL raise a `ValidationError` when constructing the model.

**Validates: Requirements 4.2**

## Components and Interfaces

### `app.py`

The top-level Streamlit script. Responsibilities:
- Renders all UI widgets and layout (input panel, results panel, buttons).
- Initialises `st.session_state` keys.
- Reads the API key and calls `ai_service.get_api_key()` at startup.
- If no API key is found, displays a clear setup message and disables the Analyze button; the interface and sample inputs remain visible.
- Calls `validate_inputs`, `parse_file`, `build_analysis_prompt`, `build_challenge_prompt`, `run_analysis`, `run_challenge`, and `assemble_markdown` from the supporting modules.
- Renders `st.download_button` and the clipboard JS component.

### `ai_service.py`

Owns all OpenAI interaction. Responsibilities:
- `get_api_key() -> str | None`: reads `OPENAI_API_KEY` env var, falls back to `st.secrets`; returns `None` if absent.
- `run_analysis(client, system, user) -> AnalysisReport`: calls the API, parses and validates the response with Pydantic, returns a typed model.
- `run_challenge(client, system, user) -> ChallengeReport`: same pattern for the challenge call.
- Raises typed exceptions (`openai.APITimeoutError`, `openai.APIError`, `pydantic.ValidationError`) that `app.py` catches and converts to `st.error` messages.

### `prompts.py`

Pure functions with no side effects:

| Function | Signature | Returns |
|----------|-----------|---------|
| `build_analysis_prompt` | `(fields: dict[str,str], file_content: str) -> tuple[str, str]` | `(system_msg, user_msg)` |
| `build_challenge_prompt` | `(incident_input: str, analysis_report: dict) -> tuple[str, str]` | `(system_msg, user_msg)` |

### `models.py`

Pydantic v2 models that mirror the JSON schema returned by OpenAI. Used by `ai_service.py` to parse and validate responses. Replaces all manual `validate_analysis_report` / `validate_challenge_report` dict checks.

Key models: `IncidentSummary`, `TimelineEvent`, `Fact`, `Hypothesis`, `ReasoningRisk`, `NextDebuggingAction`, `Postmortem`, `AnalysisReport`, `UnsupportedClaim`, `ReasoningBias`, `ChallengeReport`.

Validation rules encoded in the models:
- `TimelineEvent.timestamp_type`: `Literal["exact", "inferred", "unknown"]`
- `Hypothesis.confidence`: `int` constrained to `[0, 100]`
- `AnalysisReport.hypotheses`: `list` with `min_length=3`
- `AnalysisReport.reasoning_risks`: `list` with `min_length=1, max_length=5`
- `AnalysisReport.next_debugging_actions`: `list` with `min_length=1, max_length=5`
- `AnalysisReport.unanswered_questions`: `list` with `min_length=1, max_length=5`
- `ChallengeReport.alternative_explanations`: `list` with `min_length=1`

### `utils.py`

Pure / near-pure helper functions:

| Function | Signature | Returns |
|----------|-----------|---------|
| `validate_inputs` | `(fields: dict[str,str], file_content: str) -> bool` | `True` if any non-blank input |
| `parse_file` | `(uploaded_file) -> tuple[str, str \| None]` | `(content, error_or_None)` |
| `assemble_markdown` | `(report: AnalysisReport, challenge: ChallengeReport \| None) -> str` | Full export string |
| `format_postmortem_text` | `(postmortem: Postmortem) -> str` | Plain text for clipboard |

---

## Data Models

All data models are Pydantic v2 models defined in `models.py`. They are used by
`ai_service.py` to parse and validate OpenAI JSON responses, and by `utils.py` for
typed inputs to `assemble_markdown` and `format_postmortem_text`. Using Pydantic
replaces all manual dict key checks and keeps validation logic in one place.

### Analysis_Report

Pydantic model (`AnalysisReport` in `models.py`):

```python
class IncidentSummary(BaseModel):
    description: str       # ≤150 words
    impact: str
    affected_system: str

class TimelineEvent(BaseModel):
    timestamp: str
    timestamp_type: Literal["exact", "inferred", "unknown"]
    description: str

class Fact(BaseModel):
    statement: str
    source: str

class Hypothesis(BaseModel):
    title: str
    confidence: int        # 0–100 (Field(ge=0, le=100))
    supporting_evidence: list[str]
    contradicting_evidence: list[str]
    recommended_tests: list[str]   # min_length=2

class ReasoningRisk(BaseModel):
    bias_name: str
    explanation: str

class NextDebuggingAction(BaseModel):
    action: str
    motivation: str
    tool_or_component: str

class Postmortem(BaseModel):
    incident_summary: str
    timeline: str
    root_cause_status_leading_hypothesis: str
    impact: str
    resolution_steps: str
    lessons_learned: str

class AnalysisReport(BaseModel):
    incident_summary: IncidentSummary
    timeline: list[TimelineEvent]
    facts: list[Fact]
    assumptions: list[str]
    hypotheses: list[Hypothesis]           # min_length=3
    reasoning_risks: list[ReasoningRisk]   # min_length=1, max_length=5
    next_debugging_actions: list[NextDebuggingAction]  # min_length=1, max_length=5
    unanswered_questions: list[str]        # min_length=1, max_length=5
    postmortem: Postmortem
```

### Challenge_Report

```python
class UnsupportedClaim(BaseModel):
    claim: str
    explanation: str

class ReasoningBias(BaseModel):
    bias_name: str
    cited_claim: str

class ChallengeReport(BaseModel):
    unsupported_claims: list[UnsupportedClaim]
    alternative_explanations: list[str]    # min_length=1
    reasoning_biases: list[ReasoningBias]
```

---

## Error Handling

| Scenario | Handling |
|----------|----------|
| All inputs empty | `st.warning` before API call; API not called |
| File unreadable / malformed / empty | `st.error` with filename + reason; file excluded from prompt |
| `openai.APITimeoutError` | `st.error("Request timed out after 60 s.")` |
| `openai.AuthenticationError` | `st.error("Invalid API key.")` |
| `openai.APIError` (other) | `st.error(f"OpenAI error: {e.message}")` |
| `json.JSONDecodeError` on response | `st.error("Response was not valid JSON.")` |
| Missing sections in parsed JSON | `st.error(f"Missing sections: {missing}")` |
| Challenge API failure | `st.error(...)`, `challenge_report` stays `None`, `analysis_report` unchanged |
| Clipboard JS failure | Inline error text in the HTML component |
| Missing API key at startup | `st.error(...)` banner; Analyze button `disabled=True` |

All error conditions are stored or displayed immediately; no partial reports are
rendered.

---

## Testing Strategy

**Unit tests** (pytest, `tests/test_utils.py` and `tests/test_models.py`):
- `test_validate_inputs_all_empty` → returns `False`
- `test_validate_inputs_one_field` → returns `True`
- `test_parse_file_txt_empty` → error "File is empty."
- `test_parse_file_json_nested` → falls back to `json.dumps`
- `test_parse_file_csv_single_row` → correct `col: val` output
- `test_analysis_report_rejects_missing_field` → `ValidationError` raised
- `test_challenge_report_rejects_empty_alternatives` → `ValidationError` raised
- `test_assemble_markdown_no_challenge` → no "Challenge Report" heading
- `test_assemble_markdown_with_challenge` → "Challenge Report" heading present

**Property-based tests** (Hypothesis, `tests/test_properties.py`, 2–3 high-value cases):

```python
# Feature: incident-iq, Property 1: TXT file parsing is a round-trip
@given(st.text(min_size=1))
def test_txt_round_trip(content):
    fake = MockUploadedFile(content.encode("utf-8"), name="f.txt")
    result, err = parse_file(fake)
    assert err is None and result == content

# Feature: incident-iq, Property 2: validate_inputs rejects all-whitespace inputs
@given(st.lists(st.text(alphabet=" \t\n"), min_size=5, max_size=5))
def test_validate_inputs_whitespace_only(fields):
    keys = ["description", "logs", "deployment_notes", "alerts", "complaints"]
    assert validate_inputs(dict(zip(keys, fields)), "") is False

# Feature: incident-iq, Property 3: Pydantic rejects out-of-range confidence
@given(st.integers().filter(lambda x: not (0 <= x <= 100)))
def test_hypothesis_confidence_out_of_range(bad_confidence):
    with pytest.raises(ValidationError):
        Hypothesis(title="T", confidence=bad_confidence,
                   supporting_evidence=["e"], contradicting_evidence=[],
                   recommended_tests=["t1", "t2"])
```

**No integration tests against the live OpenAI API.** `ai_service.run_analysis` and
`ai_service.run_challenge` are tested via mocked `openai.OpenAI` client in
`tests/test_ai_service.py` for timeout and auth-error paths only.
