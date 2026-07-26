# Requirements Document

## Introduction

IncidentIQ is an AI-powered incident response and root-cause analysis web application built with Python, Streamlit, and the OpenAI API. The application helps engineers analyze production incidents by processing contextual inputs (descriptions, logs, deployment notes, monitoring alerts, and user complaints) and generating a structured, multi-faceted analysis. It also provides a "Challenge Analysis" mode that critiques the AI's own conclusions to surface unsupported claims, alternative explanations, and reasoning biases.

The primary scenario is an e-commerce checkout failing after a deployment.

---

## Glossary

- **Application**: The IncidentIQ Streamlit web application.
- **User**: An engineer or student interacting with the Application.
- **Incident_Input**: The complete set of inputs provided by the User for a single analysis session, including description, logs, deployment notes, alerts, complaints, and any uploaded file content.
- **Analysis_Engine**: The Application component responsible for sending the Incident_Input to the OpenAI_API and receiving a structured response.
- **Analysis_Report**: The structured output produced by the Analysis_Engine for a given Incident_Input.
- **Challenge_Report**: The output produced by the Analysis_Engine when it critiques an existing Analysis_Report.
- **OpenAI_API**: The external OpenAI service used for all AI inference.
- **Session**: A single browser session in Streamlit, holding all in-memory state for one User.
- **Postmortem**: A draft incident post-mortem document generated as part of the Analysis_Report.

---

## Requirements

### Requirement 1: Incident Context Input

**User Story:** As an engineer, I want to enter all relevant incident information in a single interface, so that I can provide complete context to the AI for analysis.

#### Acceptance Criteria

1. THE Application SHALL provide a free-text input field, accepting up to 10,000 characters, for the User to enter an incident description.
2. THE Application SHALL provide a free-text input field, accepting up to 50,000 characters, for the User to paste application logs.
3. THE Application SHALL provide a free-text input field, accepting up to 10,000 characters, for the User to paste deployment notes.
4. THE Application SHALL provide a free-text input field, accepting up to 10,000 characters, for the User to paste monitoring alerts.
5. THE Application SHALL provide a free-text input field, accepting up to 10,000 characters, for the User to paste user complaints.
6. THE Application SHALL provide a file upload control that accepts files with `.txt`, `.json`, and `.csv` extensions up to 5 MB each.
7. WHEN the User uploads a `.txt` file, THE Application SHALL read its content and append it to the Incident_Input as additional text.
8. WHEN the User uploads a `.json` file, THE Application SHALL parse its content and append a key-value text representation of the JSON fields to the Incident_Input.
9. WHEN the User uploads a `.csv` file, THE Application SHALL parse its rows and append a plain-text representation where each row is rendered as `column: value` pairs to the Incident_Input.
10. IF the User submits the analysis form with all input fields empty and no file uploaded, THEN THE Application SHALL display a validation error message stating that at least one input is required and SHALL NOT call the OpenAI_API.
11. IF an uploaded file is malformed, unreadable, or empty, THEN THE Application SHALL display an error message identifying the file and the reason it could not be processed, and SHALL NOT include that file's content in the Incident_Input.

---

### Requirement 2: AI-Powered Incident Analysis

**User Story:** As an engineer, I want the AI to generate a comprehensive structured analysis of the incident, so that I can quickly understand what happened and why.

#### Acceptance Criteria

1. WHEN the User submits a non-empty Incident_Input, THE Analysis_Engine SHALL send the Incident_Input to the OpenAI_API with a structured prompt requesting all required output sections.
2. WHEN the OpenAI_API returns a response, THE Analysis_Engine SHALL parse it into an Analysis_Report containing all required sections defined in Requirements 3–6.
3. WHILE the Analysis_Engine is waiting for the OpenAI_API response, THE Application SHALL display a loading indicator visible to the User.
4. IF the OpenAI_API call fails or returns an error status, THEN THE Application SHALL display an error message indicating the nature of the failure and SHALL NOT display a partial Analysis_Report.
5. THE Analysis_Engine SHALL request the OpenAI_API response in JSON format so that each section of the Analysis_Report is an individually extractable field.
6. IF the OpenAI_API does not return a response within 60 seconds, THEN THE Application SHALL cancel the request and display an error message indicating the request timed out.
7. IF the OpenAI_API returns a response that cannot be fully parsed into all required Analysis_Report sections, THEN THE Application SHALL display an error message indicating which sections are absent and SHALL NOT display a partial Analysis_Report.

---

### Requirement 3: Analysis Report — Summary and Timeline

**User Story:** As an engineer, I want a concise summary and a chronological timeline of the incident, so that I can quickly grasp what happened and when.

#### Acceptance Criteria

1. THE Analysis_Report SHALL include an Incident Summary section containing a description of the incident in 150 words or fewer, its observed impact, and the affected system.
2. THE Analysis_Report SHALL include a Timeline section listing at least one event in chronological order, where each event carries a timestamp classification of "exact" (reproduced verbatim from the Incident_Input), "inferred" (estimated by the AI from context), or "unknown" (no time information available); WHEN a Timeline event has an inferred timestamp, THE Application SHALL display the label "Inferred" adjacent to that event's timestamp.
3. THE Analysis_Report SHALL include a Facts section listing only statements where each fact cites the specific field or file in the Incident_Input from which it was derived.
4. THE Analysis_Report SHALL include an Assumptions section listing statements that have no traceable source in the Incident_Input; IF no assumptions were made, THEN the section SHALL be present and SHALL state "No assumptions."

---

### Requirement 4: Analysis Report — Root-Cause Hypotheses

**User Story:** As an engineer, I want multiple ranked root-cause hypotheses with supporting and contradicting evidence, so that I can evaluate the most likely cause of the incident.

#### Acceptance Criteria

1. THE Analysis_Report SHALL include a Hypotheses section containing at least three root-cause hypotheses that differ in their proposed causal mechanism.
2. THE Analysis_Report SHALL assign each hypothesis an independent confidence score expressed as an integer percentage between 0 and 100; confidence scores are independent of one another and do not need to sum to 100.
3. THE Analysis_Report SHALL include, for each hypothesis, a list of at least one supporting evidence item that quotes or references a specific portion of the Incident_Input.
4. THE Analysis_Report SHALL include, for each hypothesis, a list of contradicting evidence items that quote or reference a specific portion of the Incident_Input; IF no contradicting evidence exists, THEN the list SHALL state "No contradicting evidence."
5. THE Analysis_Report SHALL include a Recommended Tests section listing at least two diagnostic actions per hypothesis that would confirm or refute that specific hypothesis.

---

### Requirement 5: Analysis Report — Risks and Next Steps

**User Story:** As an engineer, I want the AI to flag reasoning risks and suggest next actions, so that I can avoid analytical blind spots and know what to do next.

#### Acceptance Criteria

1. THE Analysis_Report SHALL include a Reasoning Risks section identifying between 1 and 5 cognitive biases or logical fallacies that are directly applicable to the conclusions drawn in the Analysis_Report, where each entry names the bias and provides a one-sentence explanation of how it applies.
2. THE Analysis_Report SHALL include a Next Debugging Actions section listing between 1 and 5 concrete steps ordered from highest to lowest potential to confirm or change the current diagnosis, where each step is linked to the specific evidence or reasoning that motivated it and names a specific tool, system component, or log category relevant to that step.
3. THE Analysis_Report SHALL include an Unanswered Questions section listing between 1 and 5 information gaps where each entry names a specific absent data point whose presence would confirm or contradict the current diagnosis.

---

### Requirement 6: Analysis Report — Draft Postmortem

**User Story:** As an engineer, I want a draft postmortem report generated automatically, so that I have a starting point for the official incident record.

#### Acceptance Criteria

1. THE Analysis_Report SHALL include a Draft Postmortem section containing the following labeled subsections in order: Incident Summary, Timeline, Root Cause Status / Leading Hypothesis, Impact, Resolution Steps, and Lessons Learned, where each subsection is populated with content derived from the corresponding Analysis_Report sections.
2. THE Application SHALL provide a copy-to-clipboard action that, when activated, copies the complete text of all six Draft Postmortem subsections to the system clipboard and displays a confirmation message to the User.
3. IF the clipboard write operation fails, THEN THE Application SHALL display an error message instructing the User to manually select and copy the text.

---

### Requirement 7: Challenge Analysis

**User Story:** As an engineer, I want the AI to critique its own analysis, so that I can identify unsupported claims and consider alternative explanations before acting.

#### Acceptance Criteria

1. WHEN an Analysis_Report has been generated in the current Session, THE Application SHALL display a "Challenge Analysis" button that the User can invoke.
2. WHEN the User invokes Challenge Analysis, THE Analysis_Engine SHALL send both the existing Analysis_Report and the Incident_Input to the OpenAI_API with a prompt instructing it to act as a critical reviewer, and WHILE the response is pending THE Application SHALL display a loading indicator.
3. THE Challenge_Report SHALL include a list of unsupported claims, where each entry identifies a specific statement in the Analysis_Report that has no traceable source in the Incident_Input.
4. THE Challenge_Report SHALL include a list of at least one alternative explanation that was not present in the Hypotheses section of the Analysis_Report.
5. THE Challenge_Report SHALL include a list of reasoning biases or fallacies present in the Analysis_Report, where each entry names the bias and cites the specific claim in the Analysis_Report it applies to.
6. IF the Challenge Analysis API call fails or the response cannot be parsed, THEN THE Application SHALL display a user-readable error message indicating the nature of the failure and SHALL NOT display a partial Challenge_Report or modify the existing Analysis_Report.

---

### Requirement 8: Analysis Output Display

**User Story:** As an engineer, I want the analysis results presented in a clear, navigable layout, so that I can read each section without being overwhelmed.

#### Acceptance Criteria

1. THE Application SHALL display each of the following Analysis_Report sections in a distinct, labeled UI element: Incident Summary, Timeline, Facts, Assumptions, Hypotheses, Recommended Tests, Reasoning Risks, Next Debugging Actions, Unanswered Questions, and Draft Postmortem.
2. THE Application SHALL display the confidence score for each hypothesis as an integer (0–100) accompanied by a proportional visual bar whose filled length corresponds to the score value.
3. THE Application SHALL display the Challenge_Report in a labeled area positioned below the Analysis_Report, visually separated by a horizontal divider.
4. THE Application SHALL render all sections of the Analysis_Report in an expanded state by default, except the Draft Postmortem section which SHALL be collapsed by default; the User SHALL be able to toggle each section between expanded and collapsed.

---

### Requirement 9: Session and State Management

**User Story:** As an engineer, I want the application to maintain my inputs and results within a session, so that I can review and re-use information without re-entering it.

#### Acceptance Criteria

1. WHEN the User submits the analysis form, THE Application SHALL retain all Incident_Input field values in the UI so they remain visible and editable without re-entry.
2. WHEN an Analysis_Report has been generated, THE Application SHALL retain it so the User can invoke Challenge Analysis without resubmitting the Incident_Input.
3. WHEN the User activates the "Reset" action, THE Application SHALL clear all Incident_Input fields, remove the Analysis_Report from display, and remove the Challenge_Report from display, returning the UI to its initial state.
4. THE Application SHALL NOT write Incident_Input, Analysis_Report, or Challenge_Report data to disk, external storage, browser localStorage, sessionStorage, or cookies at any point during the Session.

---

### Requirement 10: Markdown Export

**User Story:** As an engineer, I want to export the full analysis as a Markdown file, so that I can save and share the complete incident record outside the application.

#### Acceptance Criteria

1. WHEN an Analysis_Report has been generated in the current Session, THE Application SHALL display an "Export as Markdown" action that the User can invoke.
2. WHEN the User invokes "Export as Markdown", THE Application SHALL produce a single Markdown (.md) file containing all sections of the Analysis_Report followed by the Draft Postmortem.
3. WHEN the User invokes "Export as Markdown" and a Challenge_Report exists in the current Session, THE Application SHALL append the Challenge_Report as an additional section at the end of the exported file.
4. WHEN the export file is ready, THE Application SHALL offer it as a download to the User's browser.

---

### Requirement 11: Configuration and API Key Management

**User Story:** As a developer, I want the application to load the OpenAI API key from the environment, so that credentials are never hard-coded in source files.

#### Acceptance Criteria

1. THE Application SHALL read the OpenAI API key from the `OPENAI_API_KEY` environment variable, falling back to the Streamlit secrets file if the environment variable is absent; IF both are present, THEN the environment variable value SHALL take precedence.
2. IF both the `OPENAI_API_KEY` environment variable and the Streamlit secrets file are absent or contain an empty value at startup, THEN THE Application SHALL display an error message that references `OPENAI_API_KEY` by name and SHALL render the analysis submission button as visible but not clickable.
3. THE Application SHALL never render the OpenAI API key value in the UI or write it to any log output.

---

## Non-Functional Requirements

The following constraints apply to the entire implementation and take precedence over any design or technical choice that would conflict with them.

1. THE Application SHALL be implemented as a single-process Streamlit application; no microservices, container orchestration, or multi-process architectures are permitted.
2. THE Application SHALL use the OpenAI API exclusively for all AI inference; integration with any other AI provider (including Gemini) is not permitted.
3. THE Application SHALL NOT require Docker, a relational database, a vector database, or any authentication system.
4. THE Application SHALL NOT depend on LangChain or any agent-orchestration framework; direct OpenAI API calls are required.
5. THE Application SHALL minimise token consumption by keeping prompts focused and avoiding redundant or decorative content in API requests.
6. THE Application's codebase SHALL be kept minimal: avoid unnecessary abstraction layers, helper classes, and files that do not directly contribute to the acceptance criteria above.
