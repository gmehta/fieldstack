# SPEC — Account Planning Copilot

| | |
|---|---|
| **Job to be done** | Give an AE a trustworthy, cited, one-page picture of a strategic account in under a minute of reading, so the QBR is spent on decisions, not recall. |
| **Primary user** | Account Executive (secondary: their first-line manager reviewing the plan). |
| **Trigger** | On demand ("brief me on Quantum Systems") and scheduled 24h before any calendar event tagged QBR/EBC for an account with open ARR > $500k. |
| **Mode** | Read-only, advisory. No writes to Salesforce. |

> Product spec backing the agent in `AGENT.md`. Show this if asked "how would you productionise it?" — it is not needed to run the demo.

## Inputs (table.field, in priority order)
1. `opportunities` (stage, deal_type, arr, close_date) + `clari_opportunity_forecasts` (forecast_category, clari_health_score, deal_slip_count)
2. `contacts` × `buying_centers` × `buyer_personas` (persona title, seniority, budget owner, maturity)
3. `gong_call_transcripts.full_transcript_text` + `top_objection_raised`; `gong_account_insights` (sentiment, multithread ratio) — transcript wins on conflict
4. `contracts` × `entitlements` (utilisation), `technographics` where `category='Legacy Backup'` (incumbent + renewal_date)
5. `highspot_collateral_engagement` + `highspot_slide_views.buyer_comments`
6. `account_external_ids.match_confidence_score` — gate: any system < 0.8 gets a "low-confidence source" label on its section

## Reasoning steps
1. Resolve the account and its child accounts (`parent_account_id`); state whether children are included.
2. Build the money picture: open ARR by stage; flag opps with past close dates (T1) as *stale*, not *imminent*; ignore `probability_pct` (T2).
3. Build the stakeholder map; mark buying centers with no C-level/VP contact as **whitespace**; mark personas missing entirely (no Economic Buyer = red flag).
4. Extract from the last ≤5 transcripts: objections, commitments the *prospect* made, competitor named. Where transcript ≠ `competitor_tracker_hits`, report both and prefer the transcript.
5. Consumption: utilisation ratio; if active > purchased (T9) present as "possible expansion OR data error — verify before quoting".
6. Threats: incumbent renewal inside 180 days, negative sentiment trend, single-threaded (multithread ratio < 0.3), Commit category with health < 40 (T3).
7. Next best action: must name one opp id, one contact, and the date that makes it urgent. Reject generic actions.
8. Blind spots: list every section that had zero rows or a low-confidence identity match.

## Success metrics
Leading: AE prep time per QBR (self-reported, target −60%), % briefs edited before use (< 30% = trusted). Lagging: expansion opps created within 30 days of a brief; "surprised in QBR" incidents (manager-logged).

## Non-goals (this iteration)
Slide generation · multi-account territory rollups · write-back of the plan · real-time refresh during the meeting.

## Edge cases
Account with no open opps (brief becomes a renewal/expansion brief — hand to Case 7) · churned account with open pipeline (T16 — surface the status contradiction) · > 20 contacts (cap at senior + persona-complete set) · child accounts owned by a different AE.

## Rollout
Week 1–2: 10 AEs, briefs delivered as a doc, thumbs-up/down per section → Week 3–6: Slack delivery 24h pre-QBR, capture edits as labelled data → Quarter 2: feed the threats section into Clari health (still read-only).
