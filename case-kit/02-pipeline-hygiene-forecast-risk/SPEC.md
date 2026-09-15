# SPEC — Pipeline Hygiene & Forecast-Risk Agent

| | |
|---|---|
| **Job to be done** | Make the Commit forecast believable by finding the opportunities whose CRM state is stale, silent, or self-contradictory, and getting the right human to fix them — without the agent touching the record. |
| **Primary user** | Opp owner / staffed AE (receives nudges); RevOps + sales manager (receive the rollup). |
| **Trigger** | Daily 06:00 local per territory; on-demand "audit my pipeline". |
| **Mode** | Read-only. Flags + drafted nudges. Write-back only via the rep clicking a pre-filled link. |

> Product spec backing the agent in `AGENT.md`. Show this if asked "how would you productionise it?" — it is not needed to run the demo.

## Inputs
- `opportunities` (stage, arr, close_date, employee_id) — open stages only
- `clari_opportunity_forecasts` (forecast_category, clari_health_score, rep_forecast_amount, ai_forecast_amount, deal_slip_count)
- `clari_forecast_history_logs` (change_timestamp, old/new_stage, rep_notes_text) — recency + contradiction check
- `opportunity_employees` × `employees` — who to nudge (T13: owner is a BDR/SE/CAM 81% of the time)
- `gong_account_insights.buyer_sentiment_score` (last 30 days) — optional corroboration for AT-RISK

## Rules (deterministic, explainable — the LLM writes the nudge, not the rule)
| Rule | Condition | Class |
|---|---|---|
| STALE-DATE | open AND close_date < today | STALE |
| SILENT | no history log in 60d | STALE (low severity) |
| COMMIT-AT-RISK | Commit AND health < 40 | AT-RISK |
| SLIPPER | deal_slip_count ≥ 3 | AT-RISK |
| AMOUNT-DISAGREE | abs(rep_fcst − arr)/arr > 0.25 | DATA-DEFECT (systemic — escalate to RevOps, not the rep) |
| CATEGORY-MISMATCH | Closed stage with non-Omitted Clari category | DATA-DEFECT (sync) |
| NOTE-CONTRADICTS | last note sentiment opposes last stage move | REVIEW |

## Reasoning steps
1. Fix "today" explicitly. 2. Apply rules; a row may carry several. 3. Separate **rep-behaviour** classes (STALE, AT-RISK) from **system** classes (DATA-DEFECT) — sending a rep a nudge about a sync bug destroys trust. 4. Rank by Commit first, then ARR. 5. Draft one nudge per opp, one digest per manager. 6. Log every flag with rule id + evidence so accuracy can be measured later.

## Success metrics
Leading: stale-date count (1,628 → < 200 in 60 days), nudge act-rate (> 40% in week 1, > 25% sustained). Lagging: Commit forecast accuracy (|Commit − Won| / Won per month), manager hours spent chasing (survey).

## Non-goals
Predicting win probability · editing records · replacing Clari's health score · coaching.

## Edge cases
Opp with no staffed employee (route to territory manager) · owner left the company · deal legitimately > 60 days silent (add a rep-set "paused until" field — proposal, not built) · same account flagged on 4 opps (bundle into one nudge).

## Rollout
Shadow mode 2 weeks (flags logged, no nudges; measure precision with 3 managers) → nudges to 2 territories → all territories → propose Clari write-back after 2 quarters of > 80% precision.
