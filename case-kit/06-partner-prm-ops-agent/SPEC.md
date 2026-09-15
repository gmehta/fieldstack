# SPEC — Partner / PRM Operations Agent

| | |
|---|---|
| **Job to be done** | Tell a Channel Account Manager, every morning, which partner deals, payouts, and certifications are actually stuck and why — and draft the record-grounded reply to the partner so CAMs answer in minutes, not days. |
| **Primary user** | CAM (internal). Partner-facing answers only after CAM approval; portal delivery is a later phase. |
| **Trigger** | Daily worklist; on demand for a partner question ("why is deal reg 1234 stuck?"). |
| **Mode** | Read-only. Recommends approve/reject/escalate; CAM acts in PRM. |

> Product spec backing the agent in `AGENT.md`. Show this if asked "how would you productionise it?" — it is not needed to run the demo.

## Inputs
- `deal_registrations` (status, source_type, submission_date, protection_expiration_date, partner_id, account_id)
- `opportunity_partners` (partner_role, influence_weight), `opportunities` (stage, arr, deal_reg_id)
- `incentive_payouts` (payout_type, amount, payment_status, payout_date)
- `partner_certifications` (cert_name, level, expiry_date)
- `partners` (type, tier, region, prm_id) × `partner_programs` (discount_margin_pct, mdf_allocated/spent, effective_year)
- `co_sell_motions` (motion_type, status)

## Queues & rules
| Queue | Rule | Recommended action |
|---|---|---|
| REG-CONFLICT | > 1 partner with Submitted/Approved reg on the same account | Show both; earliest valid submission leads; CAM confirms source_type evidence |
| PROTECTION-EXPIRING | Submitted/Approved and protection expires ≤ 30d | Decide or extend; never let Approved silently lapse |
| ATTRIBUTION-LEAK | Approved reg but partner absent from `opportunity_partners` (T11) | Add partner to opp or reject reg — margin depends on it |
| PAYOUT-STALE | payment_status ≠ Paid and payout_date > 30d ago | Finance ticket with amount + type |
| CERT-LAPSED | partner on an open deal with expired cert | Enablement nudge; flag deals that require certified partner |
| MDF-OVERSPENT | mdf_spent > mdf_allocated (T12) | Escalate to program owner; block new MDF requests |

## Reasoning steps
1. Build the four queues; dedupe partners with multiple `prm_id`s; note duplicate program rows.
2. For each row, write the "why stuck" from the fields, not from policy assumptions.
3. For a partner question: identify the partner and account, pull their regs/opps/payouts/certs, and answer only from those rows. Unknown → "can't confirm from records".
4. Draft CAM action with specifics (which partner, which date, what to confirm).
5. Rank by open ARR at risk, then by protection expiry.

## Success metrics
Leading: deal-reg decision time (submission → decision), % of Approved regs with lapsed protection (baseline ~37%), CAM minutes per partner question. Lagging: partner-sourced win rate (baseline 51.7% vs 50.2% direct), partner NPS on ops responsiveness, payout SLA adherence.

## Non-goals
Portal UI · MDF planning · program design · legal terms · autonomous approvals.

## Edge cases
Partner with two `prm_id`s · account with parent/child both registered · reg on a churned account (T16) · payout to a partner with no deals (referral fee) · cert expired but partner is a Distributor (certs may not apply).

## Rollout
CAM worklist (internal) 2 weeks → partner reply drafts with CAM approval → measure decision time → portal Q&A over the same records in quarter 2.
