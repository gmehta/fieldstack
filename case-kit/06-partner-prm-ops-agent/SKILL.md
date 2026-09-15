---
name: rubrik-case-06-partner-prm-ops
description: Run the "Partner / PRM Operations Agent" case — managed-service and channel partners get stuck on deal registration, protection, incentives, and enablement. Use when the problem mentions PRM, partners, MSP, channel, deal registration, deal reg conflict, co-sell, SPIFF/rebate payouts, MDF, partner certifications, or "partners ask the same questions". Produces a partner-ops worklist (deal-reg conflicts, expiring protection, pending payouts, lapsed certs) from rubrik_gtm_synthetic_v5.db plus grounded partner answers and an eval rubric.
---

# Case 6 — Partner / PRM Operations Agent

Read `_shared/DATA-MAP.md` first (T11, T12 are this case's core). Agent definition in `AGENT.md`; product spec (rules, metrics, rollout, edge cases) in `SPEC.md`. Output schema, guardrails and evaluation rubric are at the end of this file.

**Re-scope vs the original case bank:** the original framed this as a FAQ/retrieval bot over partner docs. This DB has *no docs* but has the full PRM object model — `deal_registrations`, `opportunity_partners`, `co_sell_motions`, `incentive_payouts`, `partner_certifications`, `partner_programs` (with MDF). So the higher-likelihood and better-grounded version is: **answer the partner's "why am I stuck" question from their own records, and give the Channel Ops Manager a worklist of what's actually stuck.** If they hand you docs, bolt retrieval on; the record-grounded answer is the base.

## How the prompt may land
- "Our managed-service partners ask the same onboarding and pricing questions over and over. Build something that gets them unstuck."
- Variants: "deal reg conflicts eat channel managers' weeks", "partners don't know why their SPIFF hasn't paid", "MSP tier is growing and our CAMs can't scale".

## Phase 0 · Q&A
| SCOPE | Question | Default |
|---|---|---|
| Outcome | What is "stuck" — deal-reg decision time, payout delays, or enablement questions? Pin one metric. | Deal-reg decision time + conflict rate; payouts second |
| Stakeholder | Partner-facing (portal) or CAM-facing (internal)? | CAM-facing first: internal audience audits the answer before a partner sees it |
| Constraints | May the agent approve/reject deal regs? | No — recommend with evidence; CAM decides |
| Prior art | `Co-Sell Router` exists (`ai_agents`, `Routed Co-Sell` action) — what does it own? | Routing only; conflict detection and partner comms are open |
| Edge | Two partners register the same account — who wins? | Earliest valid submission; agent surfaces both, CAM rules |

## Phase 1 · Solutioning
Scope line: **a CAM worklist with four queues, each row explained and cited, plus a "partner reply draft" the CAM approves.** Queues: (1) deal-reg conflicts & expiring protection, (2) approved regs whose partner isn't on the opp (attribution leak), (3) pending payouts past 30 days, (4) partners with lapsed certifications on active deals.

Out: portal UI, MDF planning, autonomous approvals, contract/legal terms.

## Phase 2 · Build
```sql
-- Queue 1: deal regs submitted or approved with protection expiring in 30 days, plus conflicts (same account, >1 partner)
SELECT d.deal_reg_id, d.status, d.source_type, d.submission_date, d.protection_expiration_date,
       p.name partner, p.type, p.tier, a.name account,
       (SELECT COUNT(DISTINCT partner_id) FROM deal_registrations d2 WHERE d2.account_id=d.account_id AND d2.status IN ('Submitted','Approved')) partners_on_account
FROM deal_registrations d JOIN partners p USING(partner_id) JOIN accounts a USING(account_id)
WHERE d.status IN ('Submitted','Approved')
  AND d.protection_expiration_date BETWEEN '2026-09-15' AND '2026-10-15'
ORDER BY partners_on_account DESC, d.protection_expiration_date LIMIT 20;
```
```sql
-- Queue 2: attribution leak — approved deal reg but the partner is not on the opportunity (T11)
SELECT o.opportunity_id, o.stage, o.arr, d.deal_reg_id, p.name reg_partner,
       (SELECT GROUP_CONCAT(p2.name || ' (' || op.partner_role || ')') FROM opportunity_partners op JOIN partners p2 USING(partner_id)
         WHERE op.opportunity_id=o.opportunity_id) partners_on_opp
FROM opportunities o JOIN deal_registrations d USING(deal_reg_id) JOIN partners p ON p.partner_id=d.partner_id
WHERE d.status='Approved' AND o.stage NOT LIKE 'Closed%'
  AND NOT EXISTS (SELECT 1 FROM opportunity_partners op WHERE op.opportunity_id=o.opportunity_id AND op.partner_id=d.partner_id)
ORDER BY o.arr DESC LIMIT 15;
```
```sql
-- Queue 3: payouts pending > 30 days, by partner
SELECT p.name partner, p.tier, ip.payout_type, COUNT(*) n, ROUND(SUM(ip.amount)) amount, MIN(ip.payout_date) oldest
FROM incentive_payouts ip JOIN partners p USING(partner_id)
WHERE ip.payment_status <> 'Paid' AND ip.payout_date < '2026-08-15'
GROUP BY 1,2,3 ORDER BY amount DESC LIMIT 15;
```
```sql
-- Queue 4: partners on open deals whose certifications have lapsed
SELECT p.name partner, p.type, pc.cert_name, pc.level, pc.expiry_date,
       COUNT(DISTINCT op.opportunity_id) open_deals, ROUND(SUM(o.arr)) open_arr
FROM partner_certifications pc JOIN partners p USING(partner_id)
JOIN opportunity_partners op USING(partner_id) JOIN opportunities o USING(opportunity_id)
WHERE pc.expiry_date < '2026-09-15' AND o.stage NOT LIKE 'Closed%'
GROUP BY 1,2,3,4,5 ORDER BY open_arr DESC LIMIT 15;
```
```sql
-- Context for a partner question: program terms incl. MDF status (T12: duplicate program rows, overspend)
SELECT program_id, program_name, effective_year, discount_margin_pct, mdf_allocated, mdf_spent,
       ROUND(mdf_spent - mdf_allocated) overspend
FROM partner_programs ORDER BY effective_year DESC, program_id;
```

Prompt to Claude (paste queue results + program table):
```
You are the Partner Ops agent in AGENT.md. Produce the CAM worklist: for each queue, top 5 rows with a one-line "why it's stuck" and the recommended CAM action, citing deal_reg_id / opportunity_id / payout_id.
Then answer this partner question using ONLY those records: "We registered <account> in <month> — why hasn't it been approved, and is our margin protected?"
Every sentence of the answer must cite a record. If the records cannot answer, say "I can't confirm that from your records; your CAM will follow up" — never guess policy.
```

## Phase 3 · Taste Validation
Rubric first (§Evaluation rubric below). Then: generate the partner answer once with "cite every sentence" and once without — the ungrounded one will invent an approval SLA or a margin percentage. That's the failure to name: **for a channel-facing tool an ungrounded answer is a partner-trust incident, not a bug.**

Traps to name: T11 (Approved ≠ protected — ~37% of approved regs have expired protection; deal-reg partner absent from the opp on 2,411 opps), T12 (six programs overspent MDF; duplicate program names — which is canonical?), T10 (contracts on un-won deals — "fulfilled by partner" can't be trusted without the opp stage), T15 (partner `prm_id` ↔ account identity).

Live iteration: the first CAM action for a conflict will say "review the conflict". Add *"the action must say which partner has the earlier valid submission and what the CAM must confirm"* → regenerate → show.

## Known-gaps list
Partner portal delivery channel · legal/contract terms · MDF planning · regional program variants (`partners.region`) · escalation path when CAM and partner disagree · audit trail of agent-drafted vs CAM-sent replies.

---

# Contract used by the agent

## Output schema
```json
{
  "run_date": "2026-09-15",
  "queues": {
    "reg_conflict": [{"account": "", "regs": [{"deal_reg_id": 0, "partner": "", "status": "", "submitted": "", "expires": ""}], "leader": "", "cam_action": ""}],
    "protection_expiring": [{"deal_reg_id": 0, "partner": "", "account": "", "expires": "", "cam_action": ""}],
    "attribution_leak": [{"opportunity_id": 0, "arr": 0, "reg_partner": "", "partners_on_opp": [], "cam_action": ""}],
    "payout_stale": [{"partner": "", "type": "", "amount": 0, "oldest": "", "cam_action": ""}],
    "cert_lapsed": [{"partner": "", "cert": "", "expired": "", "open_arr": 0, "cam_action": ""}]
  },
  "partner_answer": {"question": "", "answer_sentences": [{"text": "", "citation": ""}], "unanswerable": [""], "cam_approval_required": true},
  "data_caveats": ["duplicate program rows for 2023", "…"]
}
```

## Guardrails
- Never approves, rejects, or pays. Never states a policy, SLA, or margin % that is not in a record.
- Partner-facing text is drafted, CAM-approved, then sent by the CAM.
- Never discloses another partner's identity in a conflict reply — only "another registration exists".
- Payout amounts echoed from `incentive_payouts.amount`, never computed.

## Evaluation rubric
| Axis | Good | Subtle failure |
|---|---|---|
| Groundedness | Every partner-facing sentence cites a record | Inventing a "5-business-day approval SLA" |
| Conflict handling | Both regs shown, leader named with reason | "Review the conflict" |
| Confidentiality | Competing partner never named to the other | Leaking the rival VAR's name |
| Prioritisation | ARR-at-risk ordering | Alphabetical worklist |
| Honesty | "Can't confirm from records" used when true | Confident guess about margin protection |
