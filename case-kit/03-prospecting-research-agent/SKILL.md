---
name: rubrik-case-03-prospecting-research
description: Run the "Prospecting / Account-Research Agent" case — SDRs spend an hour researching an account before the first touch; get it to five minutes. Use when the problem mentions SDR/BDR research, outbound, prospecting, first touch, 6sense intent, account research brief, or "why now". Produces a fixed-shape SDR brief + first-touch email from rubrik_gtm_synthetic_v5.db and an eval rubric.
---

# Case 3 — Prospecting / Account-Research Agent

Read `_shared/DATA-MAP.md` first. Agent definition in `AGENT.md`; product spec (rules, metrics, rollout, edge cases) in `SPEC.md`. Output schema, guardrails and evaluation rubric are at the end of this file. The trick in this case: the data already contains an `Outbound Prospecting Bot` and a `Drafted Outreach` action type — position yours as the *research + why-now* layer that makes the existing drafting bot specific instead of generic.

## How the prompt may land
- "SDRs spend an hour researching an account before the first outbound touch. Get that to five minutes."
- Variants: "6sense says these accounts are in-market, nobody works them", "our outbound reply rate is flat", "build a why-now generator".

## Phase 0 · Q&A
| SCOPE | Question | Default |
|---|---|---|
| Stakeholder | BDR doing outbound, or AE doing warm expansion? | BDR, net-new (`accounts.status='Prospect'`) |
| Constraints | Is 6sense intent in scope? Can I read prior Outreach threads so we don't re-email people who said "hold off"? | Yes and yes — both are in the DB |
| Outcome | Research time, or reply rate? | Research time is the ask; reply rate is the proof it's *good* research |
| Prior art | What does `Outbound Prospecting Bot` already do? | Drafts emails; doesn't decide who or why-now |
| Edge | Should the agent email anyone? | No — it drafts; BDR sends from Outreach |

## Phase 1 · Solutioning
Scope line: **a fixed-shape brief (5 fields) + one first-touch draft, for one account, generated from four evidence sources — and a "do not contact" check.** The output has to be actionable in < 1 minute, so the *shape* is the product, not the prose.

Whitespace to pick from: 6sense-qualified Decision-stage accounts with **no open opportunity** (78 of them — say the number). That's the population the existing bot isn't working.

## Phase 2 · Build
```sql
-- Who to work: 6QA Decision-stage accounts with no open opp, ranked by incumbent renewal urgency
SELECT a.account_id, a.name, a.industry, a.tier, a.status, s.intent_score, s.buying_stage, s.top_keywords,
       (SELECT vendor_name || ' renews ' || MIN(renewal_date) FROM technographics t
         WHERE t.account_id=a.account_id AND t.category='Legacy Backup' AND t.renewal_date >= '2026-09-15') incumbent_renewal
FROM accounts a JOIN sixsense_account_intent s USING(account_id)
WHERE s.is_6qa = 1 AND s.buying_stage = 'Decision'
  -- add  AND a.status IN ('Prospect','Churned')  for net-new only; Customer rows here are expansion whitespace
  AND NOT EXISTS (SELECT 1 FROM opportunities o WHERE o.account_id=a.account_id AND o.stage NOT LIKE 'Closed%')
ORDER BY incumbent_renewal IS NULL, incumbent_renewal LIMIT 15;
```
Pick one `account_id` from that list (call it :acct) and pull the four evidence sources:
```sql
-- Evidence 1: what they are researching (6sense queries → landing pages)
SELECT search_term, landing_page_url, search_timestamp FROM sixsense_search_queries
WHERE account_id = :acct ORDER BY search_timestamp DESC LIMIT 10;
```
```sql
-- Evidence 2: installed base (T16: Legacy Backup only) and renewal dates
SELECT category, vendor_name, install_date, renewal_date FROM technographics
WHERE account_id = :acct ORDER BY category='Legacy Backup' DESC, renewal_date;
```
```sql
-- Evidence 3: people — persona × seniority, and what they've already done (form fills, touches)
SELECT c.contact_id, c.first_name || ' ' || c.last_name name, c.job_title, c.seniority_level, p.title persona,
       (SELECT COUNT(*) FROM touchpoints tp WHERE tp.contact_id=c.contact_id) touches,
       (SELECT GROUP_CONCAT(form_name) FROM marketo_raw_form_fills m WHERE m.contact_id=c.contact_id) forms
FROM contacts c JOIN buyer_personas p USING(persona_id)
WHERE c.account_id = :acct ORDER BY c.seniority_level, touches DESC;
```
```sql
-- Evidence 4 / DO-NOT-CONTACT: prior Outreach threads — anyone who replied "hold off" or "pricing is a non-starter"
SELECT m.contact_id, a.sequence_name, a.step_number, a.response_status, m.subject_line, m.reply_body_text
FROM outreach_email_messages m JOIN outreach_sequence_activities a USING(activity_id)
JOIN contacts c ON c.contact_id = m.contact_id
WHERE c.account_id = :acct ORDER BY a.step_number DESC;
```
```sql
-- Baseline the proof metric: reply/meeting rate by sequence (T19: ignore sentiment_tag)
SELECT sequence_name, COUNT(*) steps,
       ROUND(1.0*SUM(response_status IN ('Replied','Meeting Booked'))/COUNT(*),3) reply_rate
FROM outreach_sequence_activities GROUP BY 1 ORDER BY reply_rate DESC;
```

Prompt to Claude:
```
You are the Prospecting Research agent in AGENT.md. From the four evidence sets, produce the SDR brief in the output schema:
why_now (3 bullets, each citing a search term, renewal date, or form fill by id), who (1 primary + 1 secondary contact with persona reasoning),
do_not_contact (anyone with a hold-off / pricing-non-starter reply), talk_track (the ONE pain from evidence, not the persona template — T17),
and a first-touch email ≤ 90 words that references at least one concrete why-now item.
Reject your own draft if any sentence could be sent to a different account unchanged.
```

## Phase 3 · Taste Validation
Rubric first (§Evaluation rubric below). Then generate three emails: (a) references the incumbent renewal date, (b) references the search terms, (c) references a form fill. Ask Claude which could "mislead or fail in the field" — the renewal-date one is the strongest *and* the creepiest; argue where the line is (public technographic ≠ private browsing).

Traps to name: T16 (nonsense technographic categories — filter to Legacy Backup), T17 (persona pains are identical templates — don't quote them), T18 (6QA and intent score are the same signal — don't stack them), T19 (sentiment_tag is fake — read the reply text), T15 (6sense → account match may be < 0.8).

Live iteration: first draft will open with "I noticed you're evaluating backup vendors" (generic). Add *"the first sentence must contain a date, a vendor name, or a document title"* → regenerate → show.

## Known-gaps list
Compliance/consent (`consent_marketing` in Marketo JSON — respect it) · GDPR regions in `accounts.country` · adoption risk: will BDRs edit every draft anyway? (measure edit distance) · intent decay window · dedupe against AE-owned accounts.

---

# Contract used by the agent

## Output schema
```json
{
  "account": {"id": 0, "name": "", "status": "Prospect|Churned", "mode": "net-new|win-back"},
  "why_now": [{"signal": "", "evidence": "", "citation": "technographics#123", "strength": "high|medium"}],
  "who": {"primary": {"contact_id": 0, "name": "", "title": "", "persona": "", "why": ""},
          "secondary": {"contact_id": 0, "name": "", "title": "", "persona": ""},
          "gaps": "no economic buyer known"},
  "do_not_contact": [{"contact_id": 0, "reason": "replied hold-off on 2026-05-02 [outreach_email_messages#…]"}],
  "talk_track": {"pain": "", "proof_point": "", "evidence": ""},
  "first_touch": {"subject": "", "body": "", "sequence": "Enterprise New Logo Outbound"},
  "confidence": {"identity_match_min": 0.0, "notes": []}
}
```

## Guardrails
- Never sends. Never contacts a do-not-contact person. Respects `consent_marketing=false`.
- Uses installed-tech and renewal dates (public technographic data) but never quotes individual search queries back to the prospect verbatim — summarise the topic.
- No fabricated news, funding, or org changes: if it's not in the DB, it's not in the brief.
- One draft per account per 14 days.

## Evaluation rubric
| Axis | Good | Subtle failure |
|---|---|---|
| Specificity | First sentence carries a date / vendor / doc title | "I noticed you're evaluating backup solutions" |
| Evidence honesty | Every why-now cites a row | Quoting persona template pains as if observed |
| Creep line | Topic-level intent, not verbatim queries | "I saw you searched 'air-gapped vault pricing'" |
| Suppression | Hold-off replies honoured | Re-emailing the CISO who said "non-starter" |
| Actionability | BDR can send in < 1 min with ≤ 1 edit | Brief needs the BDR to re-research to trust it |
