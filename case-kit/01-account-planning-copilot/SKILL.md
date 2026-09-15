---
name: rubrik-case-01-account-planning
description: Run the "Account Planning Copilot" case — an AE has 20 minutes to prep for a QBR / exec meeting on a strategic account. Use when the interviewer's problem mentions account planning, QBR prep, account brief, strategic account, whitespace, stakeholder map, or "get the AE ready". Produces a one-page account brief from rubrik_gtm_synthetic_v5.db plus an eval rubric for Taste Validation.
---

# Case 1 — Account Planning Copilot

Read `_shared/DATA-MAP.md` first (join spine, traps T1–T20, anchor date 2026-09-15). Agent definition in `AGENT.md`; product spec (rules, metrics, rollout, edge cases) in `SPEC.md`. Output schema, guardrails and evaluation rubric are at the end of this file.

## How the prompt may land
- "An AE walks into a QBR with a $2M strategic account and has 20 minutes to prep. Design something that gets them ready."
- Variants: "build an account plan generator", "what should the AE know before the exec meeting", "summarise everything we know about account X".

## Phase 0 · Q&A (0–15 min) — ask 3, assume the rest aloud
| SCOPE | Question | Default if unanswered |
|---|---|---|
| Stakeholder | Is the consumer the AE prepping, or the manager reviewing the plan afterwards? | AE, 20-second scan before the meeting |
| Constraints | Read-only over the DB? Can I treat Gong transcripts as queryable? | Read-only; transcripts are queryable (they are, via FTS) |
| Outcome | What makes a QBR prep "good" for you — fewer surprises, more expansion found, less prep time? | Prep time ↓ and "no surprise" rate; expansion found is the bonus |
| Prior art | Does a `Champion Finder` / `Deal Desk Assistant` brief already exist that I should extend? (`ai_agents` says they do) | Extend: this brief is what those agents should feed |
| Edge | If the identity map is wrong for one system (T15), do we show a partial brief or block? | Show partial, label the missing source |

## Phase 1 · Solutioning (15–45 min)
Decision to say out loud: **one account, one artifact (a one-page brief), five sections, every line cited to a table row.** Not a chat assistant, not a RAG pipeline. Sections: (1) Where the money is, (2) Who we know / who we don't, (3) What they told us on calls, (4) What they're consuming, (5) Threats + next best action.

Explicitly out: multi-account rollups, writing the plan back to Salesforce, generating the slide deck.

## Phase 2 · Build (45–75 min)
Pick the account: default `account_id = 1428` (Quantum Systems, Enterprise customer, $3.29M open ARR). Run the five pulls, then hand the JSON to Claude with the prompt at the end.

```sql
-- 1. Money: open pipeline + signed base
SELECT o.opportunity_id, o.name, o.stage, o.deal_type, o.arr, o.close_date,
       f.forecast_category, f.clari_health_score, f.deal_slip_count,
       (o.close_date < '2026-09-15' AND o.stage NOT LIKE 'Closed%') AS past_close_flag
FROM opportunities o LEFT JOIN clari_opportunity_forecasts f USING(opportunity_id)
WHERE o.account_id = 1428 ORDER BY o.stage, o.arr DESC;
```
```sql
-- 2. People: stakeholder map by buying center × persona × seniority (T17: group by title)
SELECT bc.name buying_center, bc.maturity_level, bc.annual_budget,
       p.title persona, c.seniority_level, c.first_name || ' ' || c.last_name contact, c.job_title
FROM contacts c JOIN buying_centers bc USING(buying_center_id) JOIN buyer_personas p USING(persona_id)
WHERE c.account_id = 1428 ORDER BY bc.name, c.seniority_level;
```
```sql
-- 3. Voice of the buyer: last 5 calls with objection + takeaway (T7/T20: cite the transcript, not the summary)
SELECT t.transcript_id, t.call_date, t.call_title, t.top_objection_raised, g.competitor_tracker_hits,
       g.buyer_sentiment_score, g.multithread_contact_ratio, t.key_takeaways
FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id)
WHERE g.account_id = 1428 ORDER BY t.call_date DESC LIMIT 5;
```
```sql
-- 4. Consumption + installed base: entitlement utilisation (T9) and incumbent renewals (T16: Legacy Backup only)
SELECT 'entitlement' kind, c.msa_number ref, e.used_capacity_tb || '/' || e.allocated_capacity_tb AS tb_used_alloc,
       e.seat_count_active || '/' || e.seat_count_purchased AS seats_active_purchased, c.end_date AS when_
FROM contracts c JOIN entitlements e USING(contract_id) JOIN opportunities o USING(opportunity_id)
WHERE o.account_id = 1428 AND o.stage = 'Closed Won'
UNION ALL
SELECT 'incumbent', t.vendor_name, t.category, NULL, t.renewal_date
FROM technographics t WHERE t.account_id = 1428 AND t.category = 'Legacy Backup';
```
```sql
-- 5. Engagement: what content they actually consumed, and buyer comments
SELECT h.content_name, ROUND(AVG(h.completion_pct),2) completion, COUNT(*) views,
       GROUP_CONCAT(DISTINCT sv.buyer_comments) comments
FROM highspot_collateral_engagement h JOIN opportunities o USING(opportunity_id)
LEFT JOIN highspot_slide_views sv USING(engagement_id)
WHERE o.account_id = 1428 GROUP BY h.content_name ORDER BY completion DESC;
```

Prompt to Claude (paste after the five result sets):
```
You are the Account Planning Copilot defined in AGENT.md. Using ONLY the five result sets above,
write the one-page QBR brief for account 1428 in the output schema. Rules:
- every bullet ends with a citation like [opportunities#2210] or [gong_call_transcripts#8817]
- if two sources disagree (e.g. competitor named in the transcript vs competitor_tracker_hits), say so and prefer the transcript
- the "next best action" must reference a specific opp id, contact, or renewal date — reject anything that could apply to any account
- list what you could NOT determine from the data under "blind spots"
```

## Phase 3 · Taste Validation (75–105 min)
Generate the rubric before you look at the brief (§Evaluation rubric below), then score the brief, then regenerate two variants: (a) manager-facing, (b) "AE in the lift, 3 bullets". Compare.

Traps you will hit and should name: T1 (past close dates on open opps look like "closing now"), T2 (ignore probability_pct), T7 (competitor disagreement), T9 (over-consumed seats — expansion or data error?), T13 (the "owner" is a BDR), T15 (one source may be mis-matched).

The iteration to show live: the first brief will produce a generic "schedule an exec alignment meeting" next step. Add one line — *"the next best action must name the contact, the opp, and the date driving urgency"* — regenerate, and point at the difference.

## Known-gaps list (say aloud)
Multi-currency ARR · parent/child account rollup (111 accounts have a parent) · brief freshness / caching · non-English calls · what happens when the AE disagrees with the brief (no feedback loop yet).

---

# Contract used by the agent

## Output schema
```json
{
  "account": {"id": 1428, "name": "", "tier": "", "status": "", "children_included": false},
  "money": {"open_arr": 0, "by_stage": {}, "stale_opps": [{"id": 0, "close_date": "", "reason": "past close date"}], "commit_at_risk": []},
  "people": {"buying_centers": [{"name": "", "maturity": "", "budget": 0, "senior_contacts": [], "whitespace": true}], "missing_personas": []},
  "voice_of_buyer": [{"transcript_id": 0, "date": "", "objection": "", "prospect_commitment": "", "competitor": "", "source_conflict": ""}],
  "consumption": {"utilisation": [], "incumbent_renewals": []},
  "threats": [{"type": "", "evidence": "", "citation": ""}],
  "next_best_action": {"action": "", "opp_id": 0, "contact": "", "why_now": "", "citation": ""},
  "blind_spots": [],
  "confidence": {"identity_map_min_score": 0.0, "sections_low_confidence": []}
}
```

## Guardrails
- Never write to a system of record; the AE copies what they agree with.
- Never invent a commitment: a "commitment" must quote the transcript line.
- Never rank contacts by inferred influence beyond seniority + persona; no scraped personal data.
- Suppress a section rather than fill it from a source with identity confidence < 0.8 and no corroboration.

## Evaluation rubric (generate this before judging any brief)
| Axis | Good looks like | Subtle failure |
|---|---|---|
| Specificity | Every action names an opp id, contact, date | "Schedule an exec alignment" — true of any account |
| Groundedness | Every bullet cites a row | Confident competitor claim from the summary field only (T7) |
| Contradiction handling | Names T1/T7/T9 conflicts and picks a side | Averages the two amounts and reports one number |
| Scan-ability | 20-second read; threats before history | 900 words of chronology |
| Honesty about gaps | Blind-spots section is non-empty | Silent omission of a section with zero rows |
