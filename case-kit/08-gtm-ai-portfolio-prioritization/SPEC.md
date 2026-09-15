# SPEC — GTM AI Portfolio Prioritisation (a repeatable method, not a bot)

| | |
|---|---|
| **Job to be done** | Every quarter, turn the GTM warehouse into a ranked, sized, defensible list of AI bets for IT-GTM — with confidence discounted for data quality — so the pod builds the thing with the highest real ROI, not the loudest ask. |
| **Primary user** | Staff PM (owner), CIO / IT leadership (approver), CRO org (customer). |
| **Trigger** | Quarterly planning; any time a new "we should build X" request lands. |
| **Mode** | Analysis + recommendation. Produces a one-page memo and a scored table. |

> Product spec backing the agent in `AGENT.md`. Show this if asked "how would you productionise it?" — it is not needed to run the demo.

## Inputs
- Funnel: `opportunities` (stage, arr, close_date, deal_type), `accounts.tier`
- Velocity: `clari_forecast_history_logs` first/last change per opp (lower bound — T6)
- Forecast integrity: `clari_opportunity_forecasts` (category vs stage, rep vs arr — T3, T4)
- Top of funnel: `outreach_sequence_activities` reply rates; `sixsense_account_intent` 6QA-no-opp count
- Back half: `contracts` (auto_renew, end_date) on Closed Won; `entitlements` utilisation (T9)
- Existing coverage: `ai_agents` × `agent_opportunity_assists` (action mix per agent)
- Data quality: `account_external_ids.match_confidence_score` (T15); past-close share (T1)

## Scoring formula (say it out loud, then let them attack it)
`value_range = affected_ARR × lift_range × confidence ÷ effort_weeks`
- `affected_ARR`: from the query, cited
- `lift_range`: low/high, from analogues (state them: e.g. hygiene nudges 10–25% stale reduction; renewal early-warning 2–5 pts GRR)
- `confidence` (0.3–0.9): starts 0.8, −0.2 per trap the metric depends on, −0.1 if no baseline exists
- `effort_weeks`: read-only integration = 4–6; write-back = 10+; data fix = 6–8

## Reasoning steps
1. Five-number diagnosis: pipeline size & staleness, win rate spread, velocity, TOFU efficiency + untouched 6QA, renewal exposure + forecast disagreement.
2. Attach a trap list to each number → confidence.
3. Enumerate candidate bets (cases 1–7, 9–10 + "data fix"); drop anything an existing agent already does.
4. Score with ranges; rank by low-end value (conservative) and by high-end (upside); note where the two rankings disagree.
5. Choose #1 + one paired quick win; write the not-doing list.
6. Name the three questions that would flip #1; write them as the next week's discovery plan.

## Success metrics
Leading: % roadmap items with a baseline query before build; time from ask → sized answer (< 1 week). Lagging: realised value vs sized range per shipped bet (calibration), CRO-org adoption of shipped bets.

## Non-goals
Building anything · cost modelling beyond effort weeks · org design · vendor selection.

## Edge cases
Exec goal changes mid-quarter (re-run with new goal; keep the old memo) · two bets tie (prefer the one with a firmer baseline) · biggest finding is data quality (pair it with a seller-visible win so IT isn't "just fixing plumbing").

## Rollout
Run once for the interview → make it the quarterly planning artefact → add realised-value tracking so the confidence term gets calibrated from history.
