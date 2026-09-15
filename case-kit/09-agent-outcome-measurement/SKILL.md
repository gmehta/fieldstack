---
name: rubrik-case-09-agent-measurement
description: Run the "Agent Outcome Measurement" case — Rubrik already runs GTM agents (Deal Desk Assistant, Champion Finder, Outbound Prospecting Bot, Co-Sell Router); prove whether they work. Use when the problem mentions measuring AI impact, agent ROI, evals, observability, attribution, "are our agents working", A/B or holdout, or accountability for outcomes. Produces an attribution analysis from rubrik_gtm_synthetic_v5.db, an honest verdict on what can and cannot be claimed, and a measurement design.
---

# Case 9 — Agent Outcome Measurement  *(added)*

Why this case is likely: the JD says *"own GTM AI end-to-end with accountability for outcomes"* and *"shipping production agents"*. The DB shows five agent families across 20 versions with 7,055 logged assists. The question "so, did they work?" is the most Staff-level question in the room — and the honest answer from this data is "you can't tell yet, here's why, and here's how you'd make it tellable."

Read `_shared/DATA-MAP.md` first (T14 is the whole case). Agent definition in `AGENT.md`; product spec (rules, metrics, rollout, edge cases) in `SPEC.md`. Output schema, guardrails and evaluation rubric are at the end of this file.

## How the prompt may land
- "We shipped four agents last year. Leadership wants to know the ROI. What do you tell them and what do you build so we can answer next time?"
- Variants: "which agent version should we roll back?", "design the evals for our GTM agents", "attribution for AI-assisted deals".

## Phase 0 · Q&A
| SCOPE | Question | Default |
|---|---|---|
| Outcome | ROI in what unit — win rate, cycle time, seller hours, or ARR influenced? | Win rate + cycle time (outcomes) with seller hours as the efficiency claim |
| Constraints | Was there ever a holdout / control? (DB: no — every opp has an assist, T14) | No → observational only; design the holdout going forward |
| Stakeholder | Is the audience leadership (a verdict) or engineering (a dashboard)? | Leadership verdict first, with the dashboard as the "never again" |
| Prior art | Is there any agent-level eval today (offline accuracy, human grading)? | Assume none |
| Edge | If an agent version looks worse, is rollback in scope? | Recommend, don't execute |

## Phase 1 · Solutioning
Scope line: **three things — (1) what the observational data *can* say (version-vs-version, action-mix-vs-outcome, timing), (2) what it *cannot* say (agent vs no agent — no control group), (3) the minimum measurement design that makes next quarter answerable.** Refusing to over-claim *is* the Staff signal.

## Phase 2 · Build
```sql
-- 1. Coverage: every opp has ≥1 assist → no control group (T14). Say this number first.
SELECT COUNT(*) opps,
       SUM(EXISTS (SELECT 1 FROM agent_opportunity_assists x WHERE x.opportunity_id=o.opportunity_id)) opps_with_assist
FROM opportunities o;
```
```sql
-- 2. Version-vs-version within an agent family: win rate and closed count (the only fair comparison available)
SELECT ag.name family, ag.system_version version, ag.total_actions_executed lifetime_actions,
       COUNT(DISTINCT x.opportunity_id) opps_touched,
       ROUND(1.0*SUM(o.stage='Closed Won')/NULLIF(SUM(o.stage LIKE 'Closed%'),0),3) win_rate,
       SUM(o.stage LIKE 'Closed%') closed_n
FROM ai_agents ag JOIN agent_opportunity_assists x USING(agent_id) JOIN opportunities o USING(opportunity_id)
GROUP BY 1,2 ORDER BY 1, 2;
```
```sql
-- 3. Action-mix vs outcome: which action types co-occur with wins (correlation, not cause — say so)
SELECT x.action_type, COUNT(DISTINCT x.opportunity_id) opps,
       ROUND(1.0*SUM(o.stage='Closed Won')/NULLIF(SUM(o.stage LIKE 'Closed%'),0),3) win_rate
FROM agent_opportunity_assists x JOIN opportunities o USING(opportunity_id)
GROUP BY 1 ORDER BY win_rate DESC;
```
```sql
-- 4. Dose: assists per opp vs win rate (selection effect: harder deals get more help?)
SELECT n_assists, COUNT(*) opps, ROUND(1.0*SUM(won)/NULLIF(SUM(closed),0),3) win_rate FROM (
  SELECT o.opportunity_id, COUNT(x.agent_id) n_assists, o.stage='Closed Won' won, o.stage LIKE 'Closed%' closed
  FROM opportunities o LEFT JOIN agent_opportunity_assists x USING(opportunity_id) GROUP BY 1)
GROUP BY 1 ORDER BY 1;
```
```sql
-- 5. Timing: did the assist precede the close (plausible influence) or follow it (logging noise)?
SELECT CASE WHEN substr(x.last_action_timestamp,1,10) <= o.close_date THEN 'before_close' ELSE 'after_close' END timing,
       COUNT(*) assists
FROM agent_opportunity_assists x JOIN opportunities o USING(opportunity_id)
WHERE o.stage LIKE 'Closed%' GROUP BY 1;
```
```sql
-- 6. Does 'Flagged Renewal Risk' flag the right deals? Precision proxy: flagged renewals that were then Closed Lost vs Won
SELECT o.stage, COUNT(DISTINCT o.opportunity_id) flagged_renewals
FROM agent_opportunity_assists x JOIN opportunities o USING(opportunity_id)
WHERE x.action_type='Flagged Renewal Risk' AND o.deal_type='Renewal' AND o.stage LIKE 'Closed%' GROUP BY 1;
```

Prompt to Claude (paste all six results):
```
You are the Agent Outcome Measurement method in AGENT.md. Write the leadership verdict in three parts:
CAN SAY (with numbers and the comparison that justifies each), CANNOT SAY (name the missing control and the selection effects visible in the dose table),
and NEXT QUARTER'S DESIGN (holdout %, unit of randomisation, primary metric, minimum detectable effect at current closed volume, per-agent offline eval).
Every win-rate difference must come with its sample size; do not call anything significant without it.
Never claim the agents caused wins.
```

## Phase 3 · Taste Validation
Rubric first (§Evaluation rubric below). Then ask Claude for a version that "tells leadership the ROI number they asked for" — and dismantle it: point at T14 (no control), the dose/selection effect, and after-close assists (logging noise). The taste call: **a Staff PM who says "we can't claim it yet, and here's the 6-week plan to be able to" beats one who produces a confident ROI slide.**

Traps to name: T14 (universal coverage; duplicate agent names across versions — `ai_agents.name` is not unique, compare by `agent_id`), T2 (don't use probability as an outcome), T6 (cycle time is a lower bound), T3 (Clari category can't be an outcome either).

Live iteration: first output will rank agent versions by win rate with n = 30 vs n = 300. Add *"show a 95% interval or refuse to rank"* → regenerate → show the ranking collapse into "indistinguishable".

## Known-gaps list
No seller-hours telemetry (efficiency claim unmeasurable) · no offline eval sets per agent · no human-grading labels · agent logs lack input/output payloads (observability gap — propose the schema) · version rollout dates unknown (can't do before/after).

---

# Contract used by the agent

## Output schema
```json
{
  "verdict": {"can_say": [{"claim": "", "evidence": "", "n": 0, "interval": ""}],
              "cannot_say": [{"claim": "", "why": "no control group / selection effect / timing noise"}]},
  "scorecard": [{"agent_id": 0, "family": "", "version": "", "opps": 0, "closed_n": 0, "win_rate": 0.0, "ci95": "", "rank": "indistinguishable|higher|lower"}],
  "noise": {"assists_after_close_pct": 0.0, "duplicate_family_names": true},
  "design": {"holdout_pct": 15, "unit": "opportunity (hash of territory+id)", "primary_metric": {"Deal Desk Assistant": "quote-to-approval hours", "Champion Finder": "multithread ratio at Proposal", "Outbound Prospecting Bot": "reply rate", "Co-Sell Router": "partner-attached win rate", "Renewal Risk flag": "precision vs Closed Lost"},
             "mde": "", "offline_eval": {"per_agent_labels": 200, "graders": "2 reps + 1 RevOps", "rubric_axes": []},
             "logging_schema": ["assist_id", "agent_id", "version", "opp_id", "input_hash", "output_text", "human_action (accepted|edited|ignored)", "ts"]},
  "recommendation": {"rollback_candidates": [], "keep": [], "next_review": ""}
}
```

## Guardrails
- Never states causation from observational data. Never reports a win-rate difference without n and an interval.
- Never ranks versions whose intervals overlap.
- Does not execute rollbacks; recommends with evidence.
- Treats `total_actions_executed` as vanity — usage ≠ outcome.

## Evaluation rubric
| Axis | Good | Subtle failure |
|---|---|---|
| Epistemic honesty | Control gap named first | ROI slide with a single % |
| Statistical hygiene | n + interval on every difference | Ranking v5.4 over v1.0 on n=30 |
| Selection awareness | Dose effect explained | "More assists → more wins, scale it" |
| Design quality | Holdout, MDE, per-agent metric | "Add a dashboard" |
| Actionability | Rollback/keep list with reasons | Analysis with no decision |
