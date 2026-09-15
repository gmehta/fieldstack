# SPEC — Call-to-CRM Notetaker & Deal-Risk Flag

| | |
|---|---|
| **Job to be done** | After a Gong call, get the facts from the call into Salesforce with one rep click, and tell the manager early when the call changed the deal's risk — without ever inventing a commitment. |
| **Primary user** | Rep (approves diffs); sales manager (risk digest). |
| **Trigger** | Gong call processed event (transcript available), for calls linked to an open opp. |
| **Mode** | Extract (autonomous) → Propose (autonomous) → Write (human-approved, one click). |

> Product spec backing the agent in `AGENT.md`. Show this if asked "how would you productionise it?" — it is not needed to run the demo.

## Inputs
- `gong_call_transcripts.full_transcript_text`, `speaker_diarization_json`, `call_date`, `call_title` (primary)
- `gong_account_insights` (competitor_tracker_hits, buyer_sentiment_score, multithread_contact_ratio) — corroboration only
- `opportunities` current state (stage, close_date, arr, deal_type) — the diff target
- `clari_opportunity_forecasts` (forecast_category, clari_health_score), latest `clari_forecast_history_logs.rep_notes_text`
- `technographics` (incumbent renewal_date) — for "timing the deal around renewal" risk
- `contacts` × `buyer_personas` — is an Economic Buyer on the call?

## Reasoning steps
1. Parse diarization; if speakers unlabelled or < 2 turns per side → `low_quality=true`, no proposals.
2. Extract with quotes: commitments (prospect vs rep), objections, competitor, next step, decision-process language (budget committee, security review, procurement).
3. Diff against CRM: NextStep (always proposable), CloseDate (only if a date/quarter is spoken), Stage (only forward one step, never to Closed), Competitor (if named).
4. Corroborate: if transcript competitor ≠ tracker, prefer transcript, log the conflict.
5. Risk: rule-assisted — economic buyer absent (+), incumbent renewal > 6 months out (+), "hold off"/"non-starter" language (++), security review requested (+), budget approved language (−). Output level + the single strongest reason + confidence.
6. Package: rep approval card (diffs), manager digest (risk changes only).

## Success metrics
Leading: NextStep filled within 24h of a call (baseline: calls almost never precede a CRM update within 7 days — see SKILL query), diff acceptance rate, minutes of post-call admin (rep-reported). Lagging: risk flags that preceded a slip by ≥ 14 days (true positives) vs flags on deals that closed on time (false positives).

## Non-goals
Rep coaching · call scoring · autonomous stage changes · replacing Gong's summary.

## Edge cases
One call spanning two opps (ask the rep to pick) · internal-only call (no prospect speaker → skip) · a prospect commitment that contradicts the last rep note (T5 — surface both) · transcript in a language other than English.

## Rollout
2 weeks shadow (extractions only, graded by 3 reps for invented commitments) → approval cards to one region → manager digest → propose Clari risk-signal feed after precision > 85% for a quarter.
