---
name: rubrik-case-02-pipeline-hygiene
description: Run the "Pipeline Hygiene & Forecast-Risk Agent" case — forecast slips because reps don't update Salesforce. Use when the problem mentions pipeline hygiene, stale opportunities, forecast accuracy, Clari, commit risk, slipped deals, rep nudges, or "reps don't update the CRM". Produces a stale/at-risk classification over rubrik_gtm_synthetic_v5.db with drafted rep nudges and an eval rubric.
---

# Case 2 — Pipeline Hygiene & Forecast-Risk Agent

Read `_shared/DATA-MAP.md` first. Agent definition in `AGENT.md`; product spec (rules, metrics, rollout, edge cases) in `SPEC.md`. Output schema, guardrails and evaluation rubric are at the end of this file. This case is the one most exposed to the planted data traps (T1–T6), which is exactly what makes it a good Taste round.

## How the prompt may land
- "Our forecast keeps slipping because reps don't update Salesforce. Build something that fixes that."
- Variants: "Commit deals keep missing", "managers spend Mondays chasing reps", "Clari says one thing, reps say another".

## Phase 0 · Q&A — the three that change the build
| SCOPE | Question | Default |
|---|---|---|
| Outcome | Which of these is the target: fewer stale opps, tighter forecast accuracy, or less manager chasing? They lead to different agents. | Forecast accuracy, measured as Commit vs actual by quarter; stale-opp count is the leading indicator |
| Constraints | Read-only flags, or may the agent edit close dates / stages? | Read-only for the first 2 quarters; the nudge asks the *rep* to edit |
| Stakeholder | Who receives the nudge — the opp owner (often a BDR/SE, T13) or the AE? | Everyone staffed on the opp in `opportunity_employees`, AE first if present |
| Edge | If Clari and the rep disagree, who wins in the flag? | Neither — the flag says "disagreement", the human resolves |

## Phase 1 · Solutioning
Say the scope decision: **a narrow, explainable trigger set — not "AI reviews everything".** Four rules, each with a plain-English reason and a cited row:
1. STALE-DATE: open stage and `close_date` < today (T1 — 1,628 rows: this alone is the headline).
2. SILENT: no `clari_forecast_history_logs` entry in 60 days (T6 — 69% of open opps).
3. COMMIT-AT-RISK: `forecast_category='Commit'` and `clari_health_score < 40` (T3 — 243 rows).
4. AMOUNT-DISAGREE: |rep_forecast − arr| / arr > 25% (T4 — most rows; this is a data-quality finding, not a rep-behaviour finding — say so).

Out of scope: auto-editing records, predicting close probability (T2 makes `probability_pct` useless anyway), anything that touches Closed stages.

## Phase 2 · Build
```sql
-- Headline: how big is the hygiene problem, by rule
WITH open AS (SELECT * FROM opportunities WHERE stage NOT LIKE 'Closed%'),
last_log AS (SELECT opportunity_id, MAX(change_timestamp) last_ts FROM clari_forecast_history_logs GROUP BY 1)
SELECT
  COUNT(*) open_opps, ROUND(SUM(arr)/1e6,1) open_arr_m,
  SUM(close_date < '2026-09-15') stale_date,
  SUM(COALESCE(last_ts,'2000') < '2026-07-17') silent_60d,
  SUM(f.forecast_category='Commit' AND f.clari_health_score < 40) commit_at_risk,
  SUM(ABS(f.rep_forecast_amount - o.arr) / o.arr > 0.25) amount_disagree
FROM open o LEFT JOIN last_log USING(opportunity_id) LEFT JOIN clari_opportunity_forecasts f USING(opportunity_id);
```
```sql
-- The worklist: one row per flagged opp with reasons, who to nudge, and the last rep note (T5: note may contradict)
WITH open AS (SELECT * FROM opportunities WHERE stage NOT LIKE 'Closed%'),
last_log AS (SELECT opportunity_id, MAX(change_timestamp) last_ts FROM clari_forecast_history_logs GROUP BY 1),
last_note AS (SELECT l.opportunity_id, l.rep_notes_text, l.old_stage, l.new_stage FROM clari_forecast_history_logs l
              JOIN last_log ll ON ll.opportunity_id=l.opportunity_id AND ll.last_ts=l.change_timestamp)
SELECT o.opportunity_id, a.name account, o.stage, o.arr, o.close_date, f.forecast_category, f.clari_health_score,
       ROUND(f.rep_forecast_amount) rep_fcst, f.deal_slip_count,
       TRIM(
         CASE WHEN o.close_date < '2026-09-15' THEN 'STALE-DATE ' ELSE '' END ||
         CASE WHEN COALESCE(ll.last_ts,'2000') < '2026-07-17' THEN 'SILENT ' ELSE '' END ||
         CASE WHEN f.forecast_category='Commit' AND f.clari_health_score < 40 THEN 'COMMIT-AT-RISK ' ELSE '' END ||
         CASE WHEN ABS(f.rep_forecast_amount - o.arr)/o.arr > 0.25 THEN 'AMOUNT-DISAGREE' ELSE '' END) reasons,
       (SELECT GROUP_CONCAT(e.full_name || ' (' || oe.role || ')') FROM opportunity_employees oe JOIN employees e USING(employee_id)
         WHERE oe.opportunity_id=o.opportunity_id) nudge_to,
       ln.rep_notes_text last_note
FROM open o JOIN accounts a USING(account_id)
LEFT JOIN clari_opportunity_forecasts f USING(opportunity_id)
LEFT JOIN last_log ll USING(opportunity_id) LEFT JOIN last_note ln USING(opportunity_id)
WHERE o.close_date < '2026-09-15' OR COALESCE(ll.last_ts,'2000') < '2026-07-17'
   OR (f.forecast_category='Commit' AND f.clari_health_score < 40)
ORDER BY (f.forecast_category='Commit') DESC, o.arr DESC LIMIT 25;
```
```sql
-- Forecast-accuracy baseline so "did it work" has a number: Commit ARR by close quarter vs won ARR
SELECT substr(o.close_date,1,7) month,
       ROUND(SUM(CASE WHEN f.forecast_category='Commit' THEN o.arr END)/1e6,2) commit_m,
       ROUND(SUM(CASE WHEN o.stage='Closed Won' THEN o.arr END)/1e6,2) won_m
FROM opportunities o JOIN clari_opportunity_forecasts f USING(opportunity_id)
WHERE o.close_date BETWEEN '2026-01-01' AND '2026-09-15' GROUP BY 1 ORDER BY 1;
```

Prompt to Claude (paste the worklist JSON):
```
You are the Pipeline Hygiene agent in AGENT.md. For each of the top 10 rows: classify as STALE / AT-RISK / DATA-DEFECT / HEALTHY with one-sentence reasoning citing the fields,
then draft the nudge to the people in nudge_to. Nudge rules: ≤ 60 words, states the specific field and value that triggered it, asks one question, offers the one-click fix, never scolds.
If the last rep note contradicts the stage transition, say "note and stage disagree" instead of trusting either.
Do NOT propose changing any record yourself.
```

## Phase 3 · Taste Validation
Rubric first (§Evaluation rubric below). Then generate two nudge variants — (a) manager-cc'd, (b) rep-only — and argue which one reps will still open in week 3. The point to make: **tone is a product decision with a metric (nudge open/act rate), not a copy choice.**

Traps to name: T1 (headline number), T2 (never use probability), T3 (Clari category ≠ stage: some "Commit" deals are Closed Won — a sync defect, not rep laziness), T4 (amount disagreement is systemic — 81% avg gap — so it's a data pipeline problem, not 2,000 lazy reps), T5 (notes contradict transitions), T13 (owner isn't the AE).

Live iteration: the first nudge draft will read as accusatory ("this deal has not been updated"). Add *"lead with what you know, ask what you don't"* to the prompt, regenerate, show the delta.

## Known-gaps list
Time-zone / fiscal-calendar alignment · deals legitimately paused (no "snooze" state yet) · multi-quarter enterprise deals where 60-day silence is normal · Clari write-back API not scoped · nudge fatigue caps.

---

# Contract used by the agent

## Output schema
```json
{
  "run_date": "2026-09-15",
  "summary": {"open_opps": 0, "stale": 0, "at_risk": 0, "data_defect": 0, "commit_arr_at_risk": 0},
  "flags": [{
    "opportunity_id": 0, "account": "", "stage": "", "arr": 0, "class": "STALE|AT-RISK|DATA-DEFECT|REVIEW",
    "rules": ["STALE-DATE"], "evidence": {"close_date": "", "last_log": "", "health": 0, "category": ""},
    "nudge_to": ["name (role)"], "nudge_text": "", "one_click_fix": "update close_date | confirm stage | mark omitted",
    "confidence": "high|medium|low"
  }],
  "revops_escalations": [{"rule": "AMOUNT-DISAGREE", "count": 0, "note": "systemic, not rep-caused"}]
}
```

## Guardrails
- No writes. The one-click fix is a deep link into Salesforce/Clari the human confirms.
- Max 3 nudges per rep per day; never re-nudge the same opp inside 5 business days.
- DATA-DEFECT classes never generate a rep nudge.
- Nudge text never contains judgement words (ignored, failed, neglected).

## Evaluation rubric
| Axis | Good | Subtle failure |
|---|---|---|
| Precision of flags | Rep agrees ≥ 80% of STALE flags are real | Flagging paused enterprise deals as stale |
| Rep-vs-system separation | Sync bugs go to RevOps | Rep nudged about a Clari category mismatch they can't fix |
| Nudge quality | States field + value, asks one thing, offers fix | "Please update your pipeline" |
| Contradiction awareness | Note vs stage conflicts surfaced as REVIEW | Trusting the 5 canned notes as evidence |
| Measurability | Ties to Commit-vs-Won by month | "Hygiene improved" with no baseline |
