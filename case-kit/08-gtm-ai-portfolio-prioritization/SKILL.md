---
name: rubrik-case-08-portfolio-prioritization
description: Run the "GTM AI Portfolio Prioritisation" case — here is our GTM data; where would you invest AI first and why? Use when the problem is open-ended (no single agent named), mentions roadmap, prioritisation, needs assessment, ROI, "where's the biggest leak", pipeline velocity, close rates, funnel analysis, or "what would you build first". Produces a funnel diagnosis from rubrik_gtm_synthetic_v5.db, a ranked opportunity list with sized ROI, and one scoped first bet.
---

# Case 8 — GTM AI Portfolio Prioritisation  *(added — the "meta" case)*

Why this case is likely: the JD's own sentence — *"conduct needs assessments and use data-driven insights to prioritise features with the highest ROI"* — plus *"analyse pipeline velocity and close rates yourself"*. A Staff-level interviewer may hand you the whole dataset and ask *what* to build rather than *how*. If they do, cases 1–7 and 9–10 become your candidate list and this skill ranks them.

Read `_shared/DATA-MAP.md` first. Agent definition in `AGENT.md`; product spec (rules, metrics, rollout, edge cases) in `SPEC.md`. Output schema, guardrails and evaluation rubric are at the end of this file.

## How the prompt may land
- "Here's a snapshot of our GTM systems. You have one engineering pod for a quarter. What do you build first?"
- Variants: "where is the seller journey leaking?", "pipeline velocity is down — diagnose it", "build the AI roadmap for IT-GTM".

## Phase 0 · Q&A
| SCOPE | Question | Default |
|---|---|---|
| Outcome | Is the exec goal bookings, forecast accuracy, seller capacity, or GRR? Pick one to optimise, others as constraints. | Bookings via capacity (sellers' time) with forecast accuracy as a constraint |
| Constraints | Pod size / quarter? Read-only integrations only? | 1 pod, 1 quarter, read-only |
| Prior art | What do the five existing agents (`ai_agents`) already cover? | Deal desk, outbound drafting, co-sell routing, champion finding — so *don't* propose those |
| Stakeholder | Who's the buyer of the roadmap — CRO, CIO, or RevOps? | CIO (this role sits in IT) with CRO as the customer |
| Edge | If the data quality is the biggest finding, is "fix the data" an acceptable #1? | Yes, if sized — but pair it with a seller-visible win |

## Phase 1 · Solutioning
Scope line: **diagnose the funnel in five numbers, size five candidate bets on the same ROI formula, pick one, and name what I'm *not* doing.** ROI formula stated aloud: `value = affected_ARR × plausible_lift × confidence ÷ effort_weeks`. Confidence drops when the metric rests on a trap (T1–T20).

## Phase 2 · Build
```sql
-- 1. Funnel + hygiene in one view
SELECT stage, COUNT(*) n, ROUND(SUM(arr)/1e6,1) arr_m,
       SUM(close_date < '2026-09-15' AND stage NOT LIKE 'Closed%') past_close,
       ROUND(AVG(probability_pct)) avg_prob   -- T2: same in every stage
FROM opportunities GROUP BY stage;
```
```sql
-- 2. Win rate cuts: deal type, tier, partner-sourced, agent-assist mix
SELECT 'deal_type' cut, deal_type k, ROUND(1.0*SUM(stage='Closed Won')/SUM(stage LIKE 'Closed%'),3) win_rate, SUM(stage LIKE 'Closed%') closed
FROM opportunities GROUP BY 2
UNION ALL
SELECT 'tier', a.tier, ROUND(1.0*SUM(o.stage='Closed Won')/SUM(o.stage LIKE 'Closed%'),3), SUM(o.stage LIKE 'Closed%')
FROM opportunities o JOIN accounts a USING(account_id) GROUP BY 2
UNION ALL
SELECT 'sourcing', CASE WHEN deal_reg_id IS NULL THEN 'direct' ELSE 'partner-reg' END, ROUND(1.0*SUM(stage='Closed Won')/SUM(stage LIKE 'Closed%'),3), SUM(stage LIKE 'Closed%')
FROM opportunities GROUP BY 2;
```
```sql
-- 3. Velocity: days from first logged change to close, won vs lost (T6: sparse logs → label as lower bound)
SELECT o.stage, COUNT(*) n, ROUND(AVG(julianday(o.close_date) - julianday(substr(l.first_ts,1,10)))) avg_days
FROM opportunities o JOIN (SELECT opportunity_id, MIN(change_timestamp) first_ts FROM clari_forecast_history_logs GROUP BY 1) l USING(opportunity_id)
WHERE o.stage LIKE 'Closed%' GROUP BY 1;
```
```sql
-- 4. Top-of-funnel efficiency: sequence reply rates and 6QA accounts nobody is working
SELECT sequence_name, ROUND(1.0*SUM(response_status IN ('Replied','Meeting Booked'))/COUNT(*),3) reply_rate, COUNT(*) steps
FROM outreach_sequence_activities GROUP BY 1 ORDER BY 2 DESC;
```
```sql
SELECT COUNT(*) sixqa_decision_no_open_opp FROM sixsense_account_intent s
WHERE s.is_6qa=1 AND s.buying_stage='Decision'
  AND NOT EXISTS (SELECT 1 FROM opportunities o WHERE o.account_id=s.account_id AND o.stage NOT LIKE 'Closed%');
```
```sql
-- 5. Back half: renewal exposure and forecast disagreement (the two "silent" leaks)
SELECT
  (SELECT ROUND(SUM(c.total_contract_value)/1e6,1) FROM contracts c JOIN opportunities o USING(opportunity_id)
     WHERE o.stage='Closed Won' AND c.auto_renew=0 AND c.end_date BETWEEN '2026-09-15' AND '2027-03-15') renewal_tcv_m_no_autorenew,
  (SELECT ROUND(AVG(ABS(f.rep_forecast_amount - o.arr)/o.arr),2) FROM clari_opportunity_forecasts f JOIN opportunities o USING(opportunity_id)
     WHERE o.stage NOT LIKE 'Closed%') avg_rep_vs_arr_gap,
  (SELECT COUNT(*) FROM clari_opportunity_forecasts f JOIN opportunities o USING(opportunity_id)
     WHERE f.forecast_category='Commit' AND f.clari_health_score<40 AND o.stage NOT LIKE 'Closed%') commit_low_health;
```
```sql
-- 6. What the existing agents already touch (don't rebuild these)
SELECT ag.name, COUNT(DISTINCT ag.agent_id) versions, GROUP_CONCAT(DISTINCT x.action_type) actions, COUNT(*) assists
FROM ai_agents ag JOIN agent_opportunity_assists x USING(agent_id) GROUP BY 1 ORDER BY assists DESC;
```

Prompt to Claude (paste all six results):
```
You are the GTM AI Portfolio Prioritisation method in AGENT.md. 
1. Write the five-number diagnosis (one sentence each, with the number and the table it came from). Flag which numbers rest on a known data trap and lower their confidence.
2. Size these candidate bets on value = affected_ARR × lift × confidence ÷ effort_weeks, showing every input:
   pipeline hygiene (Case 2) · call-to-CRM (Case 4) · renewal risk (Case 7) · prospecting why-now (Case 3) · CPQ guardrail (Case 5) · data-quality fix (identity + close dates).
3. Pick ONE first bet and one "paired quick win". State what you are explicitly NOT doing this quarter and why.
4. List the three questions you'd need answered to change your #1.
Do not recommend rebuilding anything the existing agents already do.
```

## Phase 3 · Taste Validation
Rubric first (§Evaluation rubric below). Then ask Claude to produce the ranking *without* the confidence term and compare: hygiene and renewal risk usually swap places, because the hygiene case's headline (1,628 past-close opps) is partly a data artefact (T1) while renewal exposure rests on contract rows that are firmer. Defend which ranking you'd take to the CIO.

Traps to name: T1 (the "biggest problem" might be generated noise — confidence term), T2 (probability is useless → you can't compute expected value from it; say so), T4 (forecast disagreement is systemic → a data-pipeline bet, not a rep-behaviour bet), T6 (velocity is a lower bound), T14 (every opp has an agent assist → you cannot claim the existing agents work or don't — that's Case 9's problem and belongs on the roadmap as measurement), T18 (6QA and intent score are one signal).

Live iteration: the first answer will rank six bets with false precision ("$4.2M value"). Add *"express value as a range and state the single assumption that most moves it"* → regenerate → show the ranking is robust (or isn't) and say which.

## Known-gaps list
No cost data (seller comp, tool licences) · no time-on-task telemetry (the capacity lever is estimated) · no product usage/CS data for renewals · engineering capacity is assumed, not known · exec goal is assumed (bookings).

---

# Contract used by the agent

## Output schema
```json
{
  "quarter": "FY27-Q3", "goal_optimised": "bookings via seller capacity", "constraints": ["forecast accuracy", "read-only"],
  "diagnosis": [{"metric": "", "value": "", "source": "", "traps": ["T1"], "confidence": 0.6}],
  "bets": [{"name": "", "affected_arr": 0, "lift_low": 0.0, "lift_high": 0.0, "confidence": 0.0, "effort_weeks": 0,
            "value_low": 0, "value_high": 0, "key_assumption": "", "overlaps_existing_agent": false}],
  "recommendation": {"first_bet": "", "paired_quick_win": "", "why_now": "", "not_doing": [{"bet": "", "why": ""}]},
  "questions_that_flip_the_answer": ["", "", ""],
  "measurement_plan": {"leading": [], "lagging": [], "baseline_query": ""}
}
```

## Guardrails
- Every number in the memo traces to a query in SKILL.md; no numbers from memory.
- Ranges, never point estimates, for anything with confidence < 0.8.
- Never recommends a bet that duplicates an existing agent's action type without saying why the existing one is insufficient.
- Data-quality findings are reported even when they make the headline smaller.

## Evaluation rubric
| Axis | Good | Subtle failure |
|---|---|---|
| Diagnosis honesty | Trap-adjusted confidence per number | "1,628 stale opps" presented as pure rep behaviour |
| Formula transparency | Every input shown; ranges | "$4.2M value" with hidden assumptions |
| Prior-art awareness | Existing agents mapped; no duplicates | Proposing an outbound drafting bot |
| Decisiveness | One #1, a not-doing list | "All six are important" |
| Falsifiability | Three flip questions named | No path to being wrong |
