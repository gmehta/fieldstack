---
name: rubrik-case-07-renewal-risk
description: Run the "Renewal Risk & Expansion" case — customers churn or under-consume and the renewal team finds out too late; or usage says expand and nobody quotes it. Use when the problem mentions renewals, churn, retention, NRR/GRR, entitlements, consumption/utilisation, expansion, upsell, customer health, or "relationship management". Produces a renewal-risk + expansion worklist from rubrik_gtm_synthetic_v5.db with cited reasons and an eval rubric.
---

# Case 7 — Renewal Risk & Expansion Agent  *(added — not in the original six)*

Why this case is likely: the JD says "relationship management"; Rubrik's own Salesforce postings say "Sales Cloud · CPQ · Renewals"; the DB already carries a `Flagged Renewal Risk` action type, contracts, entitlements with utilisation, and 817 Churned accounts. A subscription company will test whether you can think about the *back half* of the seller journey.

Read `_shared/DATA-MAP.md` first (T9, T10, T16 are central). Agent definition in `AGENT.md`; product spec (rules, metrics, rollout, edge cases) in `SPEC.md`. Output schema, guardrails and evaluation rubric are at the end of this file.

## How the prompt may land
- "We find out a customer is churning when the renewal quote bounces. Build something that gets ahead of it."
- Variants: "usage data says customers are over-consuming and we never upsell", "GRR is slipping, what would you build first", "renewal reps have 200 accounts each".

## Phase 0 · Q&A
| SCOPE | Question | Default |
|---|---|---|
| Outcome | Is the target GRR (save the base) or NRR (expand it)? Different worklists. | GRR first — a save is worth more than an upsell on a churning account |
| Stakeholder | Renewal rep, CSM, or the AE who owns the account? | Renewal owner; AE cc'd on expansion signals |
| Constraints | How far ahead is useful — 90, 120, 180 days? | 180 days for Enterprise, 90 for Mid-Market |
| Constraints | Can I trust `entitlements` usage? (T9: 47% show more active seats than purchased) | Trust it as a *signal*, never as a billing fact; both readings shown |
| Edge | What about accounts marked Churned but with open opps (756)? | Surface as a data contradiction; don't exclude silently |

## Phase 1 · Solutioning
Scope line: **one worklist, two lanes — SAVE (risk) and GROW (expansion) — each row with a score built from four cited signals and a recommended play.** Not a health-score model; four explainable signals.

Signals: (1) contract ending ≤ 180d and `auto_renew = 0`; (2) utilisation < 50% (risk) or > 100% (expansion — or data error); (3) last-30-day Gong sentiment < 0 or negative Outreach reply text ("hold off", "locked into"); (4) competitor incumbent renewal near ours (they're being courted) — from `technographics`.

Out: pricing the renewal (Case 5), autonomous outreach, CS ticket data (none in DB).

## Phase 2 · Build
```sql
-- The renewal book: contracts on WON deals ending in 180d (T10 filter), with utilisation and auto-renew
SELECT c.contract_id, c.msa_number, a.account_id, a.name account, a.tier, a.status acct_status,
       c.end_date, c.auto_renew, ROUND(c.total_contract_value) tcv,
       ROUND(e.used_capacity_tb / NULLIF(e.allocated_capacity_tb,0), 2) tb_util,
       ROUND(1.0 * e.seat_count_active / NULLIF(e.seat_count_purchased,0), 2) seat_util,
       (SELECT ROUND(AVG(g.buyer_sentiment_score),2) FROM gong_account_insights g WHERE g.account_id=a.account_id) sentiment,
       (SELECT MIN(t.vendor_name || ' ' || t.renewal_date) FROM technographics t WHERE t.account_id=a.account_id AND t.category='Legacy Backup' AND t.renewal_date >= '2026-09-15') incumbent_renewal,
       EXISTS (SELECT 1 FROM opportunities o2 WHERE o2.account_id=a.account_id AND o2.deal_type='Renewal' AND o2.stage NOT LIKE 'Closed%') renewal_opp_open
FROM contracts c JOIN opportunities o USING(opportunity_id) JOIN accounts a USING(account_id)
LEFT JOIN entitlements e USING(contract_id)
WHERE o.stage = 'Closed Won' AND c.end_date BETWEEN '2026-09-15' AND '2027-03-15'
ORDER BY c.end_date;
```
```sql
-- Lane sizing: how many SAVE vs GROW candidates, and how much TCV
WITH book AS (
  SELECT c.contract_id, c.total_contract_value tcv, c.auto_renew,
         1.0*e.seat_count_active/NULLIF(e.seat_count_purchased,0) seat_util,
         e.used_capacity_tb/NULLIF(e.allocated_capacity_tb,0) tb_util
  FROM contracts c JOIN opportunities o USING(opportunity_id) LEFT JOIN entitlements e USING(contract_id)
  WHERE o.stage='Closed Won' AND c.end_date BETWEEN '2026-09-15' AND '2027-03-15')
SELECT COUNT(*) contracts, ROUND(SUM(tcv)/1e6,1) tcv_m,
       SUM(auto_renew=0 AND (seat_util<0.5 OR tb_util<0.5)) save_lane,
       SUM(seat_util>1.0 OR tb_util>1.0) grow_lane_or_data_error,
       SUM(auto_renew=1) auto_renew
FROM book;
```
```sql
-- Negative-signal text for one account: hold-off / locked-in replies (T19: read the text, not the tag)
SELECT m.contact_id, c.job_title, m.subject_line, m.reply_body_text
FROM outreach_email_messages m JOIN contacts c USING(contact_id)
WHERE c.account_id = :acct AND (m.reply_body_text LIKE '%hold off%' OR m.reply_body_text LIKE '%non-starter%')
ORDER BY m.message_id DESC LIMIT 5;
```
```sql
-- The contradiction to show: churned accounts with open pipeline (T16)
SELECT a.status, COUNT(DISTINCT o.opportunity_id) open_opps, ROUND(SUM(o.arr)/1e6,1) arr_m
FROM opportunities o JOIN accounts a USING(account_id) WHERE o.stage NOT LIKE 'Closed%' GROUP BY 1;
```
```sql
-- What did the existing agent already flag? (reuse, don't duplicate)
SELECT ag.name, ag.system_version, COUNT(*) flags
FROM agent_opportunity_assists x JOIN ai_agents ag USING(agent_id)
WHERE x.action_type='Flagged Renewal Risk' AND x.last_action_timestamp >= '2026-06-15' GROUP BY 1,2 ORDER BY flags DESC;
```

Prompt to Claude (paste the renewal book):
```
You are the Renewal Risk & Expansion agent in AGENT.md. For each contract: assign lane SAVE / GROW / STEADY / DATA-CHECK, a 0–100 score built only from the four signals (state the weights you used), the single strongest cited reason, and a recommended play from the play list.
seat_util > 1.0 must be labelled "over-consumption OR data error — verify before quoting"; never treat it as a pure expansion fact.
If acct_status = 'Churned' but the contract is live, put it in DATA-CHECK with the contradiction spelled out.
Output the top 10 by TCV in each lane.
```

## Phase 3 · Taste Validation
Rubric first (§Evaluation rubric below). Then generate two versions of the play recommendation for the top SAVE account: (a) rep-facing "call this person about this", (b) exec-facing "here's the GRR exposure". Argue which of the four signals you'd drop if you could only keep two — and why sentiment is the weakest (T7/T19).

Traps to name: T9 (over-consumption vs data error — 945/2,000 rows), T10 (contracts on un-won deals — filter first), T16 (churned accounts with live contracts and open opps), T19 (sentiment_tag is derived — use reply text), T15 (identity confidence for Gong/Outreach joins).

Live iteration: the first output will score `seat_util = 1.6` as a strong GROW. Add *"any utilisation > 1.2 is DATA-CHECK until entitlements are reconciled with billing"* → regenerate → watch the GROW lane shrink and explain why that's the honest number.

## Known-gaps list
No support-ticket or product-telemetry data in the DB (real health needs it) · co-term / multi-contract accounts · price uplift policy at renewal · CSM ownership model · what "auto_renew" legally means for the quote.

---

# Contract used by the agent

## Output schema
```json
{
  "run_date": "2026-09-15", "window_days": 180,
  "exposure": {"contracts": 0, "tcv": 0, "save_tcv": 0, "grow_tcv": 0, "data_check_tcv": 0},
  "rows": [{
    "contract_id": 0, "account": "", "tier": "", "end_date": "", "tcv": 0, "auto_renew": false,
    "lane": "SAVE|GROW|STEADY|DATA-CHECK", "score": 0, "weights_used": {},
    "signals": [{"name": "", "value": "", "citation": ""}],
    "strongest_reason": "", "play": "", "owner": "", "existing_flag": "",
    "caveats": ["seat_util 1.6 — over-consumption or data error"]
  }]
}
```

## Guardrails
- Utilisation > 1.2 is never presented as expansion until reconciled with billing.
- Never contacts the customer; never creates the renewal opp or quote.
- Churned-status accounts with live contracts are surfaced as contradictions, never auto-resolved.
- Sentiment alone never puts an account in SAVE.

## Evaluation rubric
| Axis | Good | Subtle failure |
|---|---|---|
| Signal honesty | Over-consumption flagged as ambiguous | "Strong expansion signal: 160% seat utilisation" |
| Explainability | Weights stated; strongest reason cited | Opaque "health score 42" |
| Lane precision | Renewal owner agrees with ≥ 80% of SAVE lane | Half the SAVE lane is auto_renew=1 with fine usage |
| Play specificity | Names contact + SKU + date | "Engage the customer proactively" |
| Contradiction surfacing | Churned-with-live-contract rows in DATA-CHECK | Silently dropped |
