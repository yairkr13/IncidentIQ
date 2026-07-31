# Testing IncidentIQ with the Sample Incident

The files in [`input/`](input/) all describe the same fictional incident: a
checkout failure on an e-commerce site following the deployment of release
`2.4.1`. Use them to exercise every feature of the app end to end.

## 1. Fill in the text fields

Copy the contents of each file into the matching field in the **Incident
Context** panel (left column):

| File | Paste into |
|---|---|
| `input/incident_description.txt` | **Incident Description** |
| `input/application_logs.txt` | **Application Logs** |
| `input/deployment_notes.txt` | **Deployment Notes** |
| `input/monitoring_alerts.txt` | **Monitoring Alerts** |
| `input/user_complaints.txt` | **User Complaints** |

## 2. Upload a supplemental file (optional)

The app accepts **one** supplemental upload (`.txt`, `.json`, or `.csv`, max
5 MB). Pick either:

- `input/supplemental_incident_data.json`, or
- `input/supplemental_logs.csv`

to see structured-file parsing in action. You can re-run the analysis later
with the other one if you want to compare.

## 3. Run the analysis

Click **🔬 Analyze Incident**. This requires `OPENAI_API_KEY` to be set — see
the main [README](../README.md#openai-api-key-configuration-windows-powershell)
for setup instructions. The report (summary, timeline, facts, assumptions,
hypotheses, reasoning risks, next debugging actions, unanswered questions, and
a draft postmortem) will appear in the right-hand column.

## 4. Run Challenge Analysis

Once a report is showing, click **⚔️ Challenge Analysis** to have a second AI
pass critique the first report — flagging unsupported claims, alternative
explanations, and reasoning biases.

## 5. Export the Markdown result

Click **⬇️ Export as Markdown** to download the combined report (and challenge
report, if generated). A real report generated this way is already checked in
at [`output/incident_analysis_example.md`](output/incident_analysis_example.md)
— if you re-run the analysis and want to refresh it, save the newly downloaded
file over that same path:

```
examples/output/incident_analysis_example.md
```
