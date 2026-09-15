---
name: rubrik-case-10-competitive-displacement
description: Run the "Competitive Displacement Play" case — find accounts running Cohesity / Veeam / Commvault / NetApp whose incumbent contract renews soon and who are showing competitor-comparison intent, and arm the seller with the takeout play. Use when the problem mentions competitors, displacement, takeout, incumbent renewal, battlecards, win/loss, competitive intel, or "who should we be attacking". Produces a ranked takeout list from rubrik_gtm_synthetic_v5.db, per-account evidence, and a play + eval rubric.
---

# Case 10 — Competitive Displacement Play  *(added — Rubrik-specific)*

Why this case is likely: this is the one case that is *about Rubrik's market*, not generic GTM. The DB is built for it — technographics carry the incumbent **and its renewal date**, 6sense logs competitor-comparison searches and `/compare/` landing pages, every Gong call has a competitor objection, Highspot has a "Rubrik vs Cohesity Battlecard", and Outreach replies say "locked into the X contract". An interviewer from Rubrik IT-GTM who wants to see domain sense will reach for this.

Read `_shared/DATA-MAP.md` first (T7, T16, T18 matter here). Agent definition in `AGENT.md`; product spec (rules, metrics, rollout, edge cases) in `SPEC.md`. Output schema, guardrails and evaluation rubric are at the end of this file.

## How the prompt may land
- "Half our new logos are takeouts from Cohesity and Veeam. Build something that finds the next 50 and tells the rep how to run it."
- Variants: "we lose to Veeam on price — what would you build?", "competitive win-loss from calls", "arm AEs with the right battlecard at the right time".

## Phase 0 · Q&A
| SCOPE | Question | Default |
|---|---|---|
| Outcome | New-logo pipeline created, or win rate on competitive deals? | Pipeline created from a ranked list; win rate later |
| Constraints | Which competitor sources can I trust — technographics, 6sense, or Gong? They disagree (T7) | Rank by agreement: 2+ sources agreeing beats 1 |
| Stakeholder | AE (run the play) or marketing (ABM campaign)? | AE, with the list shared to ABM as a by-product |
| Prior art | Is there a competitive desk / battlecard owner already? | Assume Highspot battlecards exist (they do in the data) |
| Edge | What about current customers running a competitor in another BU? | In — "expansion takeout"; label it |

## Phase 1 · Solutioning
Scope line: **a ranked takeout list scored on three independent signals — incumbent renewal timing (technographics), competitor-comparison intent (6sense), and voiced competitor objection (Gong) — with a per-account play that names the battlecard, the objection, and the timing.** Independence matters: two sources agreeing is the evidence, one source is a lead.

Out: pricing (Case 5), ABM campaign build, autonomous outreach (Case 3 drafts), win/loss modelling.

## Phase 2 · Build
```sql
-- 1. Takeout universe: Legacy Backup incumbents (T16 filter) renewing in the next 2 quarters
SELECT t.vendor_name incumbent, COUNT(DISTINCT t.account_id) accounts,
       SUM(a.status='Customer') already_customer, SUM(a.status='Prospect') prospects, SUM(a.status='Churned') churned
FROM technographics t JOIN accounts a USING(account_id)
WHERE t.category='Legacy Backup' AND t.vendor_name IN ('Cohesity','Veeam','Commvault','NetApp')
  AND t.renewal_date BETWEEN '2026-09-15' AND '2027-03-15'
GROUP BY 1 ORDER BY accounts DESC;
```
```sql
-- 2. Ranked takeout list: three signals, score = number of independent sources agreeing (+ urgency)
WITH inc AS (
  SELECT account_id, vendor_name, MIN(renewal_date) renewal_date FROM technographics
  WHERE category='Legacy Backup' AND vendor_name IN ('Cohesity','Veeam','Commvault','NetApp')
    AND renewal_date BETWEEN '2026-09-15' AND '2027-06-15' GROUP BY 1,2),
intent AS (
  SELECT q.account_id, COUNT(*) compare_searches,
         SUM(q.search_term LIKE '%Cohesity%' OR q.landing_page_url LIKE '%cohesity%') cohesity,
         SUM(q.search_term LIKE '%Veeam%' OR q.landing_page_url LIKE '%veeam%') veeam,
         SUM(q.search_term LIKE '%Commvault%' OR q.landing_page_url LIKE '%commvault%') commvault,
         SUM(q.search_term LIKE '%NetApp%' OR q.landing_page_url LIKE '%netapp%') netapp
  FROM sixsense_search_queries q WHERE q.search_timestamp >= '2026-03-15' GROUP BY 1),
voiced AS (
  SELECT g.account_id, t.top_objection_raised, MAX(t.call_date) last_call
  FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id)
  WHERE t.call_date >= '2026-03-15' GROUP BY 1,2)
SELECT a.account_id, a.name, a.tier, a.status, inc.vendor_name incumbent, inc.renewal_date,
       s.is_6qa, s.buying_stage,
       CASE inc.vendor_name WHEN 'Cohesity' THEN it.cohesity WHEN 'Veeam' THEN it.veeam WHEN 'Commvault' THEN it.commvault ELSE it.netapp END intent_hits_same_vendor,
       (v.top_objection_raised LIKE inc.vendor_name || '%') voiced_same_vendor,
       (inc.vendor_name IS NOT NULL)
       + (CASE inc.vendor_name WHEN 'Cohesity' THEN it.cohesity WHEN 'Veeam' THEN it.veeam WHEN 'Commvault' THEN it.commvault ELSE it.netapp END > 0)
       + COALESCE(v.top_objection_raised LIKE inc.vendor_name || '%', 0) sources_agreeing,
       EXISTS (SELECT 1 FROM opportunities o WHERE o.account_id=a.account_id AND o.stage NOT LIKE 'Closed%') has_open_opp
FROM inc JOIN accounts a USING(account_id)
LEFT JOIN sixsense_account_intent s USING(account_id)
LEFT JOIN intent it USING(account_id)
LEFT JOIN voiced v USING(account_id)
ORDER BY sources_agreeing DESC, inc.renewal_date LIMIT 25;
```
```sql
-- 3. Per-account evidence pack (pick :acct from the list): searches, last call objection lines, battlecard engagement, locked-in replies
SELECT 'search' src, search_term || ' → ' || landing_page_url evidence, search_timestamp ts FROM sixsense_search_queries WHERE account_id=:acct
UNION ALL
SELECT 'call', t.call_title || ' | ' || t.top_objection_raised, t.call_date FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id) WHERE g.account_id=:acct
UNION ALL
SELECT 'battlecard', h.content_name || ' ' || ROUND(h.completion_pct*100) || '% viewed', '' FROM highspot_collateral_engagement h JOIN opportunities o USING(opportunity_id) WHERE o.account_id=:acct AND h.content_name LIKE '%Battlecard%'
UNION ALL
SELECT 'reply', m.reply_body_text, '' FROM outreach_email_messages m JOIN contacts c USING(contact_id) WHERE c.account_id=:acct AND m.reply_body_text LIKE '%locked into%'
ORDER BY src, ts DESC;
```
```sql
-- 4. Win/loss reality check: competitive deals by voiced competitor, win rate (correlation; T7 caveat)
SELECT t.top_objection_raised competitor_objection, COUNT(DISTINCT o.opportunity_id) closed_opps,
       ROUND(1.0*SUM(o.stage='Closed Won')/COUNT(*),3) win_rate
FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id) JOIN opportunities o ON o.opportunity_id=g.opportunity_id
WHERE o.stage LIKE 'Closed%' GROUP BY 1 ORDER BY closed_opps DESC;
```

Prompt to Claude (paste list + one evidence pack):
```
You are the Competitive Displacement agent in AGENT.md. For the top 10 accounts: state the incumbent, the renewal date, how many independent sources agree (and which), whether we already have an open opp (then it's a "support the AE" not a "create pipeline" row), and the play: battlecard to use, the objection to pre-empt (quote it from the call), the timing window (renewal minus 120 days), and the first sentence the AE should say.
Where 6sense searches mention a different competitor than technographics, say "sources disagree" and do not add the intent point.
Never quote a search query verbatim to the prospect; summarise the topic.
```

## Phase 3 · Taste Validation
Rubric first (§Evaluation rubric below). Then produce the list with a naive score (any mention of any competitor counts) and compare to the independence-scored list; show that the naive one is dominated by single-source noise (T7: 40% of calls disagree with the tracker; T16: technographics categories are noisy). The taste call: **fewer, better-evidenced accounts beat a long list an AE won't trust.**

Traps to name: T7, T16, T18 (6QA duplicates intent score — don't double count), T15 (6sense identity confidence), the creep line (public technographics vs private research), and "already a customer" rows (expansion takeout, different play).

Live iteration: first play will say "lead with the battlecard". Add *"the first sentence must reference the renewal timing and the objection they themselves raised"* → regenerate → show.

## Known-gaps list
No pricing/TCO data for a bridge-pricing play · no win/loss reasons beyond the 5 canned objections · technographic freshness (`install_date` only) · partner-sourced takeouts (Case 6 overlap) · competitor moves (news) not in DB.

---

# Contract used by the agent

## Output schema
```json
{
  "run_date": "2026-09-15", "window": "2026-09-15..2027-06-15",
  "rows": [{
    "account_id": 0, "name": "", "tier": "", "status": "", "lane": "create-pipeline|support-AE|expansion-takeout|research",
    "incumbent": "", "renewal_date": "", "sources_agreeing": 0, "sources": {"technographics": true, "intent": false, "voiced": false}, "disagreement": "",
    "evidence": [{"src": "", "text": "", "citation": ""}],
    "play": {"window": "", "battlecard": "", "objection_to_preempt": {"quote": "", "citation": ""}, "first_sentence": "", "do_not_say": []},
    "handoff": "Case 3 draft | attach to opp 1234"
  }],
  "trend": {"objections_by_competitor_90d": {}, "win_rate_by_competitor": {}}
}
```

## Guardrails
- Never quotes a prospect's search queries back to them; topic-level only.
- Never claims the incumbent's contract terms beyond `renewal_date` (no invented pricing or dissatisfaction).
- Never adds an intent point for a competitor other than the incumbent on file.
- Never contacts anyone; never creates opps.

## Evaluation rubric
| Axis | Good | Subtle failure |
|---|---|---|
| Evidence independence | Score = distinct sources agreeing | Counting 6QA and intent_score as two signals (T18) |
| Disagreement handling | "Sources disagree" rows flagged, not scored up | Treating tracker competitor as confirmation (T7) |
| Play specificity | Quoted objection + renewal window + battlecard name | "Lead with our differentiation" |
| Creep line | Topic summaries only | "I saw you searched for Cohesity pricing" |
| Lane correctness | Existing opp → support-AE | Creating duplicate pipeline on a worked account |
