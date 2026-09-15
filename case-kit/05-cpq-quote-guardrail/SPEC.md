# SPEC — CPQ Quote Guardrail

| | |
|---|---|
| **Job to be done** | Catch off-policy, inconsistent, or arithmetically wrong quotes *before* they reach deal desk, explain each problem in one sentence with the numbers, and route the rest straight through. |
| **Primary user** | Rep at quote-build time. Secondary: deal desk (sees exceptions only), finance (audit trail). |
| **Trigger** | Quote saved / submitted for approval in CPQ; on demand "check this quote". |
| **Mode** | Advisory. Never edits a quote line. BLOCK = cannot submit until reconciled; WARN = submit with note. |

> Product spec backing the agent in `AGENT.md`. Show this if asked "how would you productionise it?" — it is not needed to run the demo.

## Inputs
- `opportunity_skus` (sku_id, quantity, negotiated_price) × `skus` (name, pricing_metric, list_price) — the quote
- `opportunities` (arr, tcv, deal_type, close_date, deal_reg_id) — reconciliation target
- `contracts` × `entitlements` for the account — renewal-term and coverage checks
- `deal_registrations` → `partners` → `partner_programs.discount_margin_pct` — partner band
- Policy doc (discount matrix) if provided; else bands inferred from Closed Won history and labelled **inferred**

## Rules
| Rule | Check | Severity |
|---|---|---|
| PRICE-ABOVE-LIST | negotiated > list on any line | WARN (BLOCK if > 2× list — data integrity) |
| DISCOUNT-BEYOND-BAND | discount > 30% direct / > partner margin + 10 pts | WARN → deal desk |
| DISCOUNT-IMPLAUSIBLE | discount > 60% or < 0% | BLOCK (integrity, not pricing) |
| SKU-AMBIGUITY | SKU name has > 1 sku_id with different list prices | WARN — must confirm id |
| ARR-MISMATCH | abs(Σ qty×negotiated − opp.arr)/arr > 10% | BLOCK — state both numbers |
| RENEWAL-NO-BASE | deal_type = Renewal but no Closed Won contract on account | BLOCK |
| RENEWAL-GAP | new close_date > contract.end_date + 60d | WARN — coverage gap |
| METRIC-MIX | per-TB and per-Node SKUs of the same product family on one quote | WARN |

## Reasoning steps
1. Load lines; compute per-line list total, negotiated total, discount — full precision.
2. Reconcile quote total to opp ARR/TCV; if mismatched, BLOCK and show both (never choose).
3. Apply discount bands; pick the partner band only if the deal-reg partner is also on `opportunity_partners` (T11) — otherwise WARN "partner attribution unclear".
4. Renewal checks against the account's Closed Won contracts only (T10).
5. Emit violations with arithmetic shown; route: BLOCK → rep must fix; WARN → deal desk with note; clean → auto-approve recommendation.

## Success metrics
Leading: % quotes auto-approve-recommended (target 60%+), quote-to-approval hours (baseline from deal desk), BLOCK precision (deal desk agrees ≥ 90%). Lagging: post-signature contract corrections per quarter; deal desk headcount hours.

## Non-goals
Quote generation · bundling/compatibility logic · approval-matrix ownership · multi-currency · co-term math.

## Edge cases
Uplift SKUs legitimately above list (needs a flag on `skus` — propose) · a quote with zero lines · same SKU twice on one quote · a renewal on a churned account (T16) · partner-sourced deal with expired protection (T11 — margin may not apply).

## Rollout
Shadow on all Proposal-stage opps for 2 weeks; deal desk grades BLOCKs → rep-facing warnings in CPQ sidebar → auto-approve recommendation to deal desk (they still click) → revisit autonomy after a quarter of > 90% precision.
