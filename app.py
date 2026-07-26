"""
IncidentIQ — Streamlit UI entry point.

Wires together all supporting modules (ai_service, prompts, utils, models)
and manages session state.  All state lives in st.session_state; nothing is
written to disk.

Requirements: 1.1–1.6, 2.3, 7.1–7.2, 8.1–8.4, 9.1–9.4, 10.1, 10.4, 11.2–11.3
"""

import json

import openai
import streamlit as st
from pydantic import ValidationError

import ai_service
from prompts import build_analysis_prompt, build_challenge_prompt
from utils import assemble_markdown, format_postmortem_text, parse_file, validate_inputs

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "gpt-4o"

# ---------------------------------------------------------------------------
# Page config (must be the first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="IncidentIQ",
    page_icon="🔍",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Session state initialisation (Req 9.1–9.4)
# ---------------------------------------------------------------------------

_DEFAULTS: dict = {
    "analysis_report": None,
    "challenge_report": None,
    "api_error": None,
    "file_error": None,
    "api_key_valid": False,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ---------------------------------------------------------------------------
# API key check (Req 11.2–11.3)
# ---------------------------------------------------------------------------

_api_key = ai_service.get_api_key()
if _api_key:
    st.session_state.api_key_valid = True
    _client = openai.OpenAI(api_key=_api_key, timeout=60)
else:
    st.session_state.api_key_valid = False
    _client = None

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.title("🔍 IncidentIQ")
st.subheader("AI-Powered Incident Response and Root-Cause Analysis")

# Setup banner when API key is missing (Req 11.2)
if not st.session_state.api_key_valid:
    st.warning(
        "Set **OPENAI_API_KEY** to enable analysis. "
        "The interface is active for exploration."
    )

# ---------------------------------------------------------------------------
# Layout: two columns 40 / 60  (Req 8.1)
# ---------------------------------------------------------------------------

col_left, col_right = st.columns([0.4, 0.6])

# ===========================================================================
# LEFT COLUMN — inputs
# ===========================================================================

with col_left:
    st.markdown("### Incident Context")

    st.text_area(
        "Incident Description",
        placeholder="Describe what happened…",
        height=150,
        max_chars=10_000,
        key="inp_description",
    )

    st.text_area(
        "Application Logs",
        placeholder="Paste application logs here…",
        height=200,
        max_chars=50_000,
        key="inp_logs",
    )

    st.text_area(
        "Deployment Notes",
        placeholder="Recent deployment details…",
        height=120,
        max_chars=10_000,
        key="inp_deployment_notes",
    )

    st.text_area(
        "Monitoring Alerts",
        placeholder="Paste monitoring/alerting data…",
        height=120,
        max_chars=10_000,
        key="inp_alerts",
    )

    st.text_area(
        "User Complaints",
        placeholder="Relevant user-reported symptoms…",
        height=120,
        max_chars=10_000,
        key="inp_complaints",
    )

    uploaded_file = st.file_uploader(
        "Upload supplemental file (.txt / .json / .csv, max 5 MB)",
        type=["txt", "json", "csv"],
        key="uploaded_file",
    )

    # Inline file-error display
    if st.session_state.file_error:
        st.error(st.session_state.file_error)

    st.markdown("---")

    btn_col1, btn_col2 = st.columns(2)

    with btn_col1:
        analyze_clicked = st.button(
            "🔬 Analyze Incident",
            type="primary",
            disabled=not st.session_state.api_key_valid,
            use_container_width=True,
        )

    with btn_col2:
        reset_clicked = st.button(
            "🔄 Reset",
            use_container_width=True,
        )

# ===========================================================================
# RESET handler (Req 9.3)
# ===========================================================================

if reset_clicked:
    for key in ("analysis_report", "challenge_report", "api_error", "file_error"):
        st.session_state[key] = None
    # Clear all inp_* widget keys
    for key in list(st.session_state.keys()):
        if key.startswith("inp_"):
            del st.session_state[key]
    st.rerun()

# ===========================================================================
# ANALYZE handler (Req 2.1–2.7, 1.10–1.11)
# ===========================================================================

if analyze_clicked:
    # Clear previous errors
    st.session_state.api_error = None
    st.session_state.file_error = None

    # Collect field values
    fields = {
        "description": st.session_state.get("inp_description", ""),
        "logs": st.session_state.get("inp_logs", ""),
        "deployment_notes": st.session_state.get("inp_deployment_notes", ""),
        "alerts": st.session_state.get("inp_alerts", ""),
        "complaints": st.session_state.get("inp_complaints", ""),
    }

    # Parse uploaded file (Req 1.7–1.9, 1.11)
    file_content = ""
    if uploaded_file is not None:
        file_content, file_err = parse_file(uploaded_file)
        if file_err:
            st.session_state.file_error = file_err
            st.error(file_err)

    # Validate that at least one input is present (Req 1.10)
    if not validate_inputs(fields, file_content):
        st.warning(
            "At least one input is required. "
            "Please fill in a field or upload a file before analyzing."
        )
    else:
        # Build prompt and call the API (Req 2.1–2.7)
        system_msg, user_msg = build_analysis_prompt(fields, file_content)

        try:
            with st.spinner("Analyzing incident… this may take up to 60 s."):
                report = ai_service.run_analysis(_client, system_msg, user_msg, MODEL)
            st.session_state.analysis_report = report.model_dump()
            st.session_state.challenge_report = None  # reset stale challenge
            st.rerun()
        except openai.APITimeoutError:
            err = "Request timed out after 60 s."
            st.session_state.api_error = err
            st.error(err)
        except openai.AuthenticationError:
            err = "Invalid API key."
            st.session_state.api_error = err
            st.error(err)
        except openai.APIError as exc:
            err = f"OpenAI error: {exc.message}"
            st.session_state.api_error = err
            st.error(err)
        except json.JSONDecodeError:
            err = "Response was not valid JSON."
            st.session_state.api_error = err
            st.error(err)
        except ValidationError as exc:
            err = str(exc)
            st.session_state.api_error = err
            st.error(err)

# ===========================================================================
# RIGHT COLUMN — results (shown only when analysis_report is set, Req 8.1)
# ===========================================================================

with col_right:
    report = st.session_state.get("analysis_report")

    if report is None:
        st.markdown("### Results")
        st.info(
            "Results will appear here after you submit an incident for analysis.",
            icon="📋",
        )
    else:
        st.markdown("### Analysis Report")

        # ---- Incident Summary (Req 8.1, expanded) -----------------------
        with st.expander("📌 Incident Summary", expanded=True):
            summary = report["incident_summary"]
            st.markdown(f"**Description:** {summary['description']}")
            st.markdown(f"**Impact:** {summary['impact']}")
            st.markdown(f"**Affected System:** {summary['affected_system']}")

        # ---- Timeline (Req 3.2, expanded) --------------------------------
        with st.expander("🕐 Timeline", expanded=True):
            for event in report["timeline"]:
                ts_label = ""
                if event["timestamp_type"] == "inferred":
                    ts_label = " *(Inferred)*"
                elif event["timestamp_type"] == "unknown":
                    ts_label = " *(Unknown)*"
                st.markdown(
                    f"- **{event['timestamp']}**{ts_label} — {event['description']}"
                )

        # ---- Facts (Req 3.3, expanded) -----------------------------------
        with st.expander("📋 Facts", expanded=True):
            for fact in report["facts"]:
                st.markdown(
                    f"- {fact['statement']} *(source: {fact['source']})*"
                )

        # ---- Assumptions (Req 3.4, expanded) -----------------------------
        with st.expander("💭 Assumptions", expanded=True):
            for assumption in report["assumptions"]:
                st.markdown(f"- {assumption}")

        # ---- Hypotheses + Recommended Tests (Req 4.1–4.5, expanded) -----
        with st.expander("🔬 Hypotheses & Recommended Tests", expanded=True):
            for idx, hyp in enumerate(report["hypotheses"], start=1):
                st.markdown(f"#### Hypothesis {idx}: {hyp['title']}")
                # Confidence bar (Req 8.2)
                st.write(f"**Confidence:** {hyp['confidence']}%")
                st.progress(hyp["confidence"] / 100)

                st.markdown("**Supporting Evidence:**")
                for ev in hyp["supporting_evidence"]:
                    st.markdown(f"- {ev}")

                st.markdown("**Contradicting Evidence:**")
                for ev in hyp["contradicting_evidence"]:
                    st.markdown(f"- {ev}")

                st.markdown("**Recommended Tests:**")
                for t in hyp["recommended_tests"]:
                    st.markdown(f"- {t}")

                if idx < len(report["hypotheses"]):
                    st.divider()

        # ---- Reasoning Risks (Req 5.1, expanded) -------------------------
        with st.expander("⚠️ Reasoning Risks", expanded=True):
            for risk in report["reasoning_risks"]:
                st.markdown(f"- **{risk['bias_name']}**: {risk['explanation']}")

        # ---- Next Debugging Actions (Req 5.2, expanded) ------------------
        with st.expander("🛠️ Next Debugging Actions", expanded=True):
            for action in report["next_debugging_actions"]:
                st.markdown(
                    f"- **{action['action']}** — {action['motivation']} "
                    f"*(tool/component: {action['tool_or_component']})*"
                )

        # ---- Unanswered Questions (Req 5.3, expanded) --------------------
        with st.expander("❓ Unanswered Questions", expanded=True):
            for q in report["unanswered_questions"]:
                st.markdown(f"- {q}")

        # ---- Draft Postmortem (Req 6.1, collapsed by default, Req 8.4) ---
        with st.expander("📝 Draft Postmortem", expanded=False):
            pm = report["postmortem"]
            st.markdown("**Incident Summary**")
            st.markdown(pm["incident_summary"])
            st.markdown("**Timeline**")
            st.markdown(pm["timeline"])
            st.markdown("**Root Cause Status / Leading Hypothesis**")
            st.markdown(pm["root_cause_status_leading_hypothesis"])
            st.markdown("**Impact**")
            st.markdown(pm["impact"])
            st.markdown("**Resolution Steps**")
            st.markdown(pm["resolution_steps"])
            st.markdown("**Lessons Learned**")
            st.markdown(pm["lessons_learned"])

        # ---- Export as Markdown (Req 10.1, 10.4) -------------------------
        challenge_report = st.session_state.get("challenge_report")
        md_content = assemble_markdown(report, challenge_report)
        st.download_button(
            label="⬇️ Export as Markdown",
            data=md_content,
            file_name="incident_analysis.md",
            mime="text/markdown",
            use_container_width=True,
        )

        # ---- Copy Postmortem to clipboard (Req 6.2–6.3) ------------------
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

        # ---- Challenge Analysis button (Req 7.1–7.2) ---------------------
        challenge_clicked = st.button(
            "⚔️ Challenge Analysis",
            type="secondary",
            disabled=not st.session_state.api_key_valid,
            use_container_width=True,
        )

        # ---- Challenge handler ------------------------------------------
        if challenge_clicked:
            # Reconstruct the incident input text for the challenge prompt
            fields_snapshot = {
                "description": st.session_state.get("inp_description", ""),
                "logs": st.session_state.get("inp_logs", ""),
                "deployment_notes": st.session_state.get("inp_deployment_notes", ""),
                "alerts": st.session_state.get("inp_alerts", ""),
                "complaints": st.session_state.get("inp_complaints", ""),
            }
            incident_input_text = "\n\n".join(
                f"[{k.upper()}]\n{v}"
                for k, v in fields_snapshot.items()
                if v.strip()
            )

            system_c, user_c = build_challenge_prompt(incident_input_text, report)

            try:
                with st.spinner("Challenging analysis… this may take up to 60 s."):
                    ch_report = ai_service.run_challenge(
                        _client, system_c, user_c, MODEL
                    )
                st.session_state.challenge_report = ch_report.model_dump()
                st.rerun()
            except openai.APITimeoutError:
                st.error("Request timed out after 60 s.")
            except openai.AuthenticationError:
                st.error("Invalid API key.")
            except openai.APIError as exc:
                st.error(f"OpenAI error: {exc.message}")
            except json.JSONDecodeError:
                st.error("Challenge response was not valid JSON.")
            except ValidationError as exc:
                st.error(str(exc))

        # ---- Challenge Report display (Req 8.3, 7.3–7.5) ----------------
        if challenge_report:
            st.divider()
            st.markdown("### ⚔️ Challenge Report")

            st.markdown("**Unsupported Claims**")
            for claim in challenge_report["unsupported_claims"]:
                st.markdown(
                    f"- **{claim['claim']}**: {claim['explanation']}"
                )

            st.markdown("**Alternative Explanations**")
            for alt in challenge_report["alternative_explanations"]:
                st.markdown(f"- {alt}")

            st.markdown("**Reasoning Biases**")
            for bias in challenge_report["reasoning_biases"]:
                st.markdown(
                    f"- **{bias['bias_name']}**: {bias['cited_claim']}"
                )
