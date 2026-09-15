---
name: rubrik-case-05-cpq-guardrail
description: Run the "Quote-to-Cash / CPQ Guardrail" case — reps get quoting wrong (bad bundles, wrong renewal terms, off-policy discounts) and it slows deals. Use when the problem mentions CPQ, quotes, pricing, discount approval, deal desk, bundles, renewal terms, SKUs, or billing errors. Produces a rules-based quote validation over rubrik_gtm_synthetic_v5.db with plain-language violation explanations and an eval rubric. Billing-adjacent: exactness is the bar.
---

# Case 5 — Quote-to-Cash / CPQ Guardrail Agent

Read `_shared/DATA-MAP.md` first, especially **T8** — this DB's pricing data is chaotic on purpose, and the whole case is about not being fooled by it. Agent definition in `AGENT.md`; product spec (rules, metrics, rollout, edge cases) in `SPEC.md`. Output schema, guardrails and evaluation rubric are at the end of this file. `Deal Desk Assistant` already exists in `ai_agents`; yours is the *pre-submission guardrail* that keeps bad quotes out of its queue.

## How the prompt may land
- "Reps get quoting wrong — bad bundles, wrong renewal terms — and it slows every deal down. What would you build?"
- Variants: "deal desk is a bottleneck", "discount approvals take 4 days", "renewal quotes don't match the contract".

## Phase 0 · Q&A
| SCOPE | Question | Default |
|---|---|---|
| Constraints | Where does quoting break today — bundling rules, discount approval routing, or renewal terms? Each is a different agent. | Discount + renewal-term checks; bundling needs a rules doc I don't have |
| Constraints | Is there a written discount policy? If not, may I infer thresholds from history and label them "inferred"? | Infer from history, label clearly, e.g. partner margin from `partner_programs.discount_margin_pct` |
| Stakeholder | Rep at quote time, or deal desk at approval time? | Rep, pre-submission (shift-left); deal desk sees only exceptions |
| Outcome | Cycle time from quote to approval, or error rate in signed contracts? | Quote-to-approval hours; contract error rate lagging |
| Edge | Multi-currency? Co-termed renewals? | Out; say so |

## Phase 1 · Solutioning
Scope line: **advisory guardrail, not generator — validate a quote against 5 explicit rules, explain each violation in one sentence with the numbers, and route.** Lower blast radius than generating quotes, and a billing-adjacent surface is where a Staff PM should start at the safe end.

Rules (each must be stated with its data source):
1. PRICE-ABOVE-LIST: negotiated_price > list_price (T8 — happens; is it a data error or a genuine uplift SKU? flag, don't fix).
2. DISCOUNT-BEYOND-BAND: discount > 30% direct, or > program `discount_margin_pct` + 10 pts for partner-sourced deals — thresholds labelled *inferred*.
3. SKU-AMBIGUITY: SKU name maps to multiple `sku_id`s with different list prices (T8) — quote must name the id.
4. ARR-MISMATCH: Σ(qty × negotiated) vs `opportunities.arr` differ > 10% — one of them is wrong; block until reconciled.
5. RENEWAL-TERM: deal_type='Renewal' but no prior Closed Won contract on the account, or new `close_date` is > 60 days after the existing `contracts.end_date` (coverage gap).

## Phase 2 · Build
```sql
-- Scale of the problem across all open quotes (open opps with SKUs)
WITH q AS (
  SELECT o.opportunity_id, o.arr, o.deal_type, o.deal_reg_id,
         SUM(os.quantity*os.negotiated_price) quote_total,
         SUM(os.negotiated_price > s.list_price) lines_above_list,
         MAX(1 - os.negotiated_price/s.list_price) max_discount
  FROM opportunities o JOIN opportunity_skus os USING(opportunity_id) JOIN skus s USING(sku_id)
  WHERE o.stage IN ('Proposal','Validation') GROUP BY 1)
SELECT COUNT(*) open_quotes,
       SUM(lines_above_list > 0) price_above_list,
       SUM(max_discount > 0.30) discount_beyond_30,
       SUM(ABS(quote_total - arr)/arr > 0.10) arr_mismatch,
       SUM(deal_type='Renewal') renewals
FROM q;
```
```sql
-- One quote, line by line, with everything the rules need (pick an opp from the Proposal stage)
SELECT o.opportunity_id, o.deal_type, o.arr opp_arr, o.close_date, a.name account,
       s.sku_id, s.name sku, s.pricing_metric, s.list_price, os.quantity, os.negotiated_price,
       ROUND(1 - os.negotiated_price/s.list_price, 3) discount,
       (SELECT COUNT(*) FROM skus s2 WHERE s2.name = s.name) same_name_sku_ids,
       pp.discount_margin_pct partner_margin_pct, p.name partner
FROM opportunities o JOIN accounts a USING(account_id)
JOIN opportunity_skus os USING(opportunity_id) JOIN skus s USING(sku_id)
LEFT JOIN deal_registrations d ON d.deal_reg_id = o.deal_reg_id
LEFT JOIN partners p ON p.partner_id = d.partner_id LEFT JOIN partner_programs pp ON pp.program_id = p.program_id
WHERE o.opportunity_id = (SELECT opportunity_id FROM opportunities WHERE stage='Proposal' AND deal_type='Renewal' ORDER BY arr DESC LIMIT 1);
```
```sql
-- Renewal-term check for that same account: existing contract coverage
-- (0 rows is not an error — it means RENEWAL-NO-BASE fires: a "Renewal" with no prior signed contract. Say that.)
SELECT c.contract_id, c.msa_number, c.start_date, c.end_date, c.auto_renew, c.total_contract_value, o2.stage prior_opp_stage
FROM contracts c JOIN opportunities o2 USING(opportunity_id)
WHERE o2.account_id = (SELECT account_id FROM opportunities WHERE stage='Proposal' AND deal_type='Renewal' ORDER BY arr DESC LIMIT 1)
ORDER BY c.end_date DESC;
```
```sql
-- Inferred discount bands from history (label as inferred): p50/p90 discount on Closed Won by deal type
SELECT o.deal_type, COUNT(*) lines,
       ROUND(AVG(1 - os.negotiated_price/s.list_price),3) avg_discount,
       ROUND(AVG(CASE WHEN os.negotiated_price <= s.list_price THEN 1 - os.negotiated_price/s.list_price END),3) avg_discount_excl_uplift
FROM opportunities o JOIN opportunity_skus os USING(opportunity_id) JOIN skus s USING(sku_id)
WHERE o.stage='Closed Won' GROUP BY 1;
```

Prompt to Claude (paste the line-item result + contract result):
```
You are the CPQ Guardrail agent in AGENT.md. Validate this quote against the five rules. For each violation output {rule, line (sku_id), the two numbers being compared, one-sentence plain-language explanation, severity BLOCK|WARN, route}.
Show arithmetic explicitly (list × qty, negotiated × qty, discount %). Do not round until the final display.
Where a threshold is inferred from history rather than policy, say "inferred" in the explanation.
If the quote total and the opportunity ARR disagree, do NOT pick one — mark BLOCK and state both.
```

## Phase 3 · Taste Validation
Rubric first (§Evaluation rubric below). This is the case where "close enough" is disqualifying: have Claude recompute one line's discount by hand and check it. Then generate a variant explanation written for the rep vs. for the deal desk — the rep version must say what to *change*, the desk version must say what to *approve*.

Traps to name: T8 (all four faces of it: duplicate SKU names, uplift above list, ARR ≠ quote total, absurd discount range), T10 (contracts exist for un-won deals — a "renewal" may have no real prior contract), T11 (partner on the deal-reg ≠ partner on the opp — which margin applies?), T12 (which partner program row is canonical?).

Live iteration: first output will describe a 98% discount as "a deep discount". Add *"any discount > 60% or < 0% is a data-integrity BLOCK, not a pricing WARN"* → regenerate → show the reclassification and why that matters on a billing surface.

## Known-gaps list
Bundling/compatibility rules (no rules doc) · multi-currency · co-termination math · approval routing matrix by amount · tax/billing frequency · ramp deals.

---

# Contract used by the agent

## Output schema
```json
{
  "opportunity_id": 0, "account": "", "deal_type": "", "quote_total": 0.0, "opp_arr": 0.0, "reconciled": false,
  "lines": [{"sku_id": 0, "sku": "", "qty": 0, "list": 0.0, "negotiated": 0.0, "discount_pct": 0.0, "list_total": 0.0, "net_total": 0.0}],
  "violations": [{"rule": "", "sku_id": 0, "compared": {"a": 0.0, "b": 0.0}, "explanation": "", "severity": "BLOCK|WARN", "threshold_source": "policy|inferred", "route": "rep|deal_desk|revops"}],
  "decision": "AUTO_APPROVE_RECOMMENDED|NEEDS_DEAL_DESK|BLOCKED",
  "arithmetic_check": "recomputed one line by hand: …"
}
```

## Guardrails
- Never modifies a quote, price, or discount. Never approves — recommends.
- Never rounds intermediate values; displays two decimals only at the end.
- Inferred thresholds are always labelled; never presented as policy.
- Financial numbers are echoed from source rows, never re-typed from memory.

## Evaluation rubric
| Axis | Good | Subtle failure |
|---|---|---|
| Arithmetic exactness | Recomputation matches to the cent | Off-by-rounding on a $1.3M line |
| Integrity vs pricing | 98% discount = BLOCK integrity | "deep discount, needs VP approval" |
| Explainability | Rep knows what to change from one sentence | "Violates policy R-7" |
| Ambiguity handling | SKU-id ambiguity and partner attribution flagged | Silently picks the cheaper sku_id |
| Provenance | Every threshold labelled policy/inferred | Inferred band stated as rule |
