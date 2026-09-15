# SPEC — Renewal Risk & Expansion Agent

| | |
|---|---|
| **Job to be done** | 180 days before a contract ends, tell the renewal owner whether this is a SAVE, a GROW, or a STEADY — from four explainable signals with citations — and hand them the play, so churn is found before the renewal quote and expansion is quoted before the customer asks. |
| **Primary user** | Renewal owner / CSM. Secondary: AE (expansion), sales leadership (GRR/NRR exposure). |
| **Trigger** | Weekly; contract enters the 180-day window (Enterprise) / 90-day window (Mid-Market); on demand. |
| **Mode** | Read-only. Recommends plays; creates nothing. |

> Product spec backing the agent in `AGENT.md`. Show this if asked "how would you productionise it?" — it is not needed to run the demo.

## Inputs
- `contracts` (end_date, auto_renew, total_contract_value) restricted to opps with stage = Closed Won (T10)
- `entitlements` (used/allocated TB, active/purchased seats) — signal, not billing fact (T9)
- `gong_account_insights.buyer_sentiment_score` (last 90 days) — weakest signal
- `outreach_email_messages.reply_body_text` — hold-off / locked-in language
- `technographics` WHERE category='Legacy Backup' — competitor renewal proximity
- `opportunities` — is a Renewal opp already open? any open pipeline on a Churned account (T16)?
- `agent_opportunity_assists` WHERE action_type='Flagged Renewal Risk' — avoid duplicate flags

## Signals & default weights (state them; let the interviewer argue)
| Signal | Risk reading | Expansion reading | Weight |
|---|---|---|---|
| Contract ≤ 180d & auto_renew = 0 | + | — | 30 |
| Utilisation < 50% | + | — | 30 |
| Utilisation > 100% (≤ 120%) | — | + | 30 (GROW) |
| Utilisation > 120% | DATA-CHECK | DATA-CHECK | n/a |
| Negative reply text / sentiment < −0.3 | + | — | 20 |
| Incumbent renewal within ±90d of ours | + (being courted) | — | 20 |

## Reasoning steps
1. Build the book (Closed Won contracts in window). 2. Compute utilisation; classify > 1.2 as DATA-CHECK. 3. Pull text signals; prefer reply text over tags. 4. Score; assign lane (SAVE ≥ 50 risk, GROW ≥ 30 expansion and no risk signal, else STEADY). 5. Pick the play. 6. Check for an existing renewal opp and an existing agent flag — reference, don't duplicate. 7. Emit worklist ordered by TCV within lane.

## Play list
SAVE: exec sponsor call (Economic Buyer from `contacts`) · utilisation review with SE · competitive displacement defence (bridge to Case 10) · early-renewal incentive (route to Case 5 for the quote).
GROW: capacity true-up quote · add-on SKU (Anomaly Detection / Cyber Recovery) matched to `sixsense_account_intent.top_keywords` · multi-year renewal.

## Success metrics
Leading: % of renewals with a lane assigned ≥ 150 days out; SAVE precision (owner agreement); DATA-CHECK rows resolved per week. Lagging: GRR, NRR, churn found ≥ 90 days before end date (vs at quote time), expansion ARR quoted from GROW lane.

## Non-goals
Health-score modelling · renewal pricing · CS ticket ingestion (no data) · autonomous outreach.

## Edge cases
Multiple contracts per account (roll up, flag co-term) · contract with no entitlement row · auto_renew = 1 but usage < 20% (STEADY on paper, real downgrade risk at the next cycle — flag as WATCH) · Mid-Market with 90-day window still shown at 180 for planning.

## Rollout
Renewal owners for one region, 2 weeks, grade lanes → all regions → GROW lane feeds AE expansion pipeline → propose feeding SAVE lane into Clari as a risk signal after one quarter of > 80% precision.
