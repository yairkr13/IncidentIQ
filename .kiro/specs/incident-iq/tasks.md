# Implementation Plan: IncidentIQ

## Overview

Implement IncidentIQ as a single-process Streamlit application across five Python files
(`app.py`, `ai_service.py`, `prompts.py`, `models.py`, `utils.py`) and a `tests/`
directory. All state lives in `st.session_state`; no database or persistence layer.
Tasks are ordered by dependency: data models first, then pure helpers, then the AI
layer, and finally the UI wiring.

---

## Tasks

- [x] 1. Define Pydantic v2 data models (`models.py`)
  - Implement all models: `IncidentSummary`, `TimelineEvent`, `Fact`, `Hypothesis`,
    `ReasoningRisk`, `NextDebuggingAction`, `Postmortem`, `AnalysisReport`,
    `UnsupportedClaim`, `ReasoningBias`, `ChallengeReport`.
  - Apply field constraints: `Hypothesis.confidence` bounded to `[0, 100]`,
    list length constraints on `hypotheses` (≥3), `reasoning_risks` (1–5),
    `next_debugging_actions` (1–5), `unanswered_questions` (1–5),
    `ChallengeReport.alternative_explanations` (≥1),
    `Hypothesis.recommended_tests` (≥2).
  - `TimelineEvent.timestamp_type` must be `Literal["exact", "inferred", "unknown"]`.
  - _Requirements: 3.1–3.4, 4.1–4.5, 5.1–5.3, 6.1, 7.3–7.5_

  - [x]* 1.1 Write unit tests for model validation
    - `test_analysis_report_rejects_missing_field` → `ValidationError` raised.
    - `test_challenge_report_rejects_empty_alternatives` → `ValidationError` raised.
    - _Requirements: 4.2, 7.4_

  - [x]* 1.2 Write property test — Pydantic rejects out-of-range confidence scores
    - **Property 3: Pydantic rejects out-of-range confidence scores**
    - **Validates: Requirements 4.2**

- [x] 2. Implement pure helper functions (`utils.py`)
  - Implement `validate_inputs(fields, file_content) -> bool` (returns `True` if any
    non-blank value exists in fields or file_content).
  - Implement `parse_file(uploaded_file) -> tuple[str, str | None]` supporting `.txt`,
    `.json`, and `.csv`; enforce 5 MB size limit; return `(content, None)` on success
    and `("", error_message)` on failure including empty files.
  - Implement `assemble_markdown(report, challenge=None) -> str` producing the full
    export structure (Summary → Timeline → Facts → Assumptions → Hypotheses →
    Reasoning Risks → Next Debugging Actions → Unanswered Questions → Draft
    Postmortem, then optional Challenge Report).
  - Implement `format_postmortem_text(postmortem) -> str` for clipboard copy.
  - _Requirements: 1.7–1.11, 1.10, 6.2–6.3, 10.2–10.3_

  - [x]* 2.1 Write unit tests for `utils.py`
    - `test_validate_inputs_all_empty` → `False`.
    - `test_validate_inputs_one_field` → `True`.
    - `test_parse_file_txt_empty` → error "File is empty.".
    - `test_parse_file_json_nested` → falls back to `json.dumps`.
    - `test_parse_file_csv_single_row` → correct `col: val` output.
    - `test_assemble_markdown_no_challenge` → no "Challenge Report" heading.
    - `test_assemble_markdown_with_challenge` → "Challenge Report" heading present.
    - _Requirements: 1.7–1.11, 10.2–10.3_

  - [x]* 2.2 Write property test — TXT file parsing is a round-trip
    - **Property 1: TXT file parsing is a round-trip**
    - **Validates: Requirements 1.7**

  - [x]* 2.3 Write property test — input validation rejects all-whitespace input
    - **Property 2: Input validation rejects all-whitespace input**
    - **Validates: Requirements 1.10**

- [x] 3. Checkpoint — models and helpers verified
  - Ensure all tests in `tests/test_models.py` and `tests/test_utils.py` pass.
  - Ensure all three property tests in `tests/test_properties.py` pass.
  - Ask the user if any questions arise before proceeding.

- [x] 4. Implement prompts and AI service (`prompts.py`, `ai_service.py`)
  - In `prompts.py`, implement `build_analysis_prompt(fields, file_content)` and
    `build_challenge_prompt(incident_input, analysis_report)` returning
    `(system_msg, user_msg)` tuples. Embed the full JSON schemas as system messages
    per the design. Omit empty sections from the user message to save tokens.
  - In `ai_service.py`, implement `get_api_key() -> str | None` (env var first, then
    `st.secrets` fallback).
  - Implement `run_analysis(client, system, user) -> AnalysisReport` and
    `run_challenge(client, system, user) -> ChallengeReport`; each calls
    `client.chat.completions.create` with `response_format={"type":"json_object"}`,
    `temperature=0`, and validates the result with Pydantic.
  - OpenAI client is constructed with `timeout=60`; model constant `MODEL = "gpt-4o"`
    lives at the top of `app.py`.
  - _Requirements: 2.1–2.7, 11.1–11.3_

  - [x]* 4.1 Write unit tests for `ai_service.py` error paths
    - Mock `openai.OpenAI`; test `APITimeoutError` and `AuthenticationError` paths
      to confirm typed exceptions propagate without swallowing.
    - _Requirements: 2.4, 2.6_

- [ ] 5. Build the Streamlit UI and wire everything together (`app.py`)
  - Initialize `st.session_state` keys (`analysis_report`, `challenge_report`,
    `api_error`, `file_error`, `api_key_valid`) on first run.
  - Read the API key via `ai_service.get_api_key()` at startup; if absent, display the
    setup banner ("Set OPENAI_API_KEY to enable analysis…") and render the Analyze
    button as `disabled=True` — all input fields remain visible.
  - Render the two-column layout (40 / 60): left column has five `st.text_area` widgets
    (with `max_chars` per design) and `st.file_uploader` accepting `.txt/.json/.csv`
    up to 5 MB; right column shows results only when `analysis_report` is set.
  - Wire the **Analyze Incident** button: call `validate_inputs` → `parse_file` →
    `build_analysis_prompt` → `run_analysis` inside `st.spinner`; store result in
    `st.session_state.analysis_report` or display error via `st.error`.
  - Render results in `st.expander` widgets (all open by default except Draft
    Postmortem which is closed); display confidence bars with `st.progress`.
  - Render `st.download_button` for Markdown export (`assemble_markdown`) and the
    clipboard JS component for postmortem copy.
  - Wire the **Challenge Analysis** button (visible only when `analysis_report` is
    set): call `build_challenge_prompt` → `run_challenge` inside `st.spinner`; store
    in `st.session_state.challenge_report` or display error without touching
    `analysis_report`.
  - Wire the **Reset** button: clear `analysis_report`, `challenge_report`,
    `api_error`, `file_error`, and all `inp_*` widget keys from `st.session_state`.
  - _Requirements: 1.1–1.6, 2.3, 7.1–7.2, 8.1–8.4, 9.1–9.4, 10.1, 10.4, 11.2–11.3_

- [x] 6. Final checkpoint — full application verified
  - Run the full test suite (`pytest tests/`); all tests must pass.
  - Manually verify: app loads without API key showing the setup banner with input
    fields visible; submitting with empty fields shows the warning; file upload parses
    correctly; Reset clears all state.
  - Ask the user if any questions arise before marking complete.

---

## Notes

- Tasks marked with `*` are optional and can be skipped for a faster MVP.
- Property tests use the **Hypothesis** library (`tests/test_properties.py`).
- No Docker, authentication, database, LangChain, or Gemini integration.
- All data stays in `st.session_state`; nothing is written to disk.
- The `MODEL` constant in `app.py` makes the OpenAI model easily configurable.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.2", "2.3"] },
    { "id": 2, "tasks": ["4.1"] }
  ]
}
```
