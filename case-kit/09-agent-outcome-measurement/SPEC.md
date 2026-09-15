# SPEC — Agent Outcome Measurement (method + observability spec)

| | |
|---|---|
| **Job to be done** | Answer "are our GTM agents working?" honestly from the data that exists, and specify the minimum instrumentation and experiment design so the question is answerable with confidence next quarter. |
| **Primary user** | IT/GTM leadership (verdict); agent engineering + RevOps (design); Staff PM (owner). |
| **Trigger** | Quarterly review; before any agent version rollout; on demand. |
| **Mode** | Analysis + recommendation. Produces a verdict memo, a per-agent scorecard, and an eval/holdout design. |

> Product spec backing the agent in `AGENT.md`. Show this if asked "how would you productionise it?" — it is not needed to run the demo.

## Inputs
- `ai_agents` (agent_id, name, system_version, total_actions_executed) — name is *not* unique across versions (T14)
- `agent_opportunity_assists` (agent_id, opportunity_id, action_type, last_action_timestamp)
- `opportunities` (stage, close_date, arr, deal_type) — outcomes
- `clari_forecast_history_logs` — cycle-time lower bound (T6)
- Not available (must be built): assist input/output payloads, human grades, seller time, rollout dates, holdout membership

## What the observational data can and cannot support
| Claim | Supportable? | Method |
|---|---|---|
| Agent X vs no agent lifts win rate | **No** — every opp has ≥ 1 assist | Needs holdout |
| Version a vs version b of the same family | Partly — same population, different periods unknown | Compare with CIs; caveat rollout timing |
| Action type correlates with wins | Yes (correlation only) | Action-mix table with n |
| More assists → better outcome | No — selection effect (hard deals get more help) | Dose table shows it; say so |
| Assists logged after close | Yes — measure logging noise | Timing split |

## Reasoning steps
1. Coverage check → declare the control-group gap first.
2. Per-family, per-version scorecard with win rate, closed n, 95% interval (Wilson); refuse to rank overlapping intervals.
3. Action-mix and dose tables → label as correlational; call out selection.
4. Timing split → quantify after-close logging noise; exclude from any influence claim.
5. Precision proxy for `Flagged Renewal Risk` (flagged renewals → lost vs won) — the one agent whose *decision* can be graded from outcomes.
6. Design: holdout (10–20% of opps by territory hash), primary metric per agent, MDE at current closed volume (~1,568 closed/yr → ~5-pt win-rate MDE at 80% power), offline eval set of 200 graded outputs per agent, payload logging schema.

## Success metrics
Leading: % agents with a primary metric + holdout live; offline eval coverage; payload logging in place. Lagging: next quarter's verdict can state a causal lift with an interval; rollback decisions made on evidence.

## Non-goals
Building the dashboard · re-training models · redefining agents' scope · seller-hours studies (no data).

## Edge cases
Agent family with one version (no within-family comparison) · opp touched by all four families (attribution split — don't; treat as a bundle) · assists logged after close (exclude) · new version launched mid-quarter (partial period).

## Rollout
Verdict memo now → holdout + logging schema in 6 weeks → first causal read next quarter → quarterly scorecard thereafter.
