---
name: rubrik-case-04-call-to-crm
description: Run the "Call-to-CRM Notetaker & Deal-Risk Flag" case — after every Gong call, update Salesforce and tell the manager if the deal is at risk. Use when the problem mentions Gong, call transcripts, call summaries, CRM data entry, next steps extraction, deal risk after a call, or "reps hate updating Salesforce after calls". Produces a structured extraction from a real transcript in rubrik_gtm_synthetic_v5.db, proposed (not applied) field updates, and an eval rubric.
---

# Case 4 — Call-to-CRM Notetaker & Deal-Risk Flag

Read `_shared/DATA-MAP.md` first. Agent definition in `AGENT.md`; product spec (rules, metrics, rollout, edge cases) in `SPEC.md`. Output schema, guardrails and evaluation rubric are at the end of this file. Note that `Summarized Call` is already an action type in `agent_opportunity_assists` — Rubrik has a summariser; the differentiated piece is *proposed field updates with evidence + a risk flag with stated confidence*, behind a human approval step.

## How the prompt may land
- "Reps hate CRM data entry. After every Gong call, something should update Salesforce and tell the manager if the deal is at risk."
- Variants: "auto-fill next steps from calls", "catch deals going sideways from the call, not the forecast".

## Phase 0 · Q&A
| SCOPE | Question | Default |
|---|---|---|
| Constraints | Exactly which Salesforce fields may be touched? Who is accountable if the agent writes something wrong? | Propose only: NextStep, CloseDate, Stage, Competitor; rep approves; rep is accountable |
| Stakeholder | Is the risk flag for the rep, the manager, or Clari? | Manager digest + rep; Clari later |
| Outcome | Data-entry minutes saved, or field completeness, or risk caught earlier? | Field completeness (NextStep filled within 24h of a call) with risk-catch as the second metric |
| Edge | What happens when the transcript quality is poor or the speakers aren't labelled? | Emit "low confidence, no proposals" — never guess |

## Phase 1 · Solutioning
Split it into **two different jobs**, and say so: (1) *extract* — summary, prospect commitments, objections, competitor, next step — safe; (2) *write-back* — proposed field diffs with a quoted transcript line per diff, approved by the rep in one click. The risk flag is derived from extraction + the opp's current state, with a confidence and a reason.

Out of scope: autonomous writes, sentiment modelling (use Gong's), coaching feedback.

## Phase 2 · Build
```sql
-- Pick a call with contradictory signals: transcript competitor ≠ Gong tracker competitor (T7)
SELECT t.transcript_id, t.call_title, t.call_date, t.top_objection_raised, g.competitor_tracker_hits,
       g.buyer_sentiment_score, g.multithread_contact_ratio, g.opportunity_id
FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id)
WHERE t.top_objection_raised NOT LIKE g.competitor_tracker_hits || '%'
  AND t.top_objection_raised <> 'General budget timing'
ORDER BY t.call_date DESC LIMIT 5;
```
```sql
-- The transcript itself + the opp's current CRM state (what the diff is against)
SELECT t.transcript_id, t.call_date, t.full_transcript_text,
       o.opportunity_id, o.stage, o.close_date, o.arr, o.deal_type,
       f.forecast_category, f.clari_health_score,
       (SELECT rep_notes_text FROM clari_forecast_history_logs l WHERE l.opportunity_id=o.opportunity_id ORDER BY change_timestamp DESC LIMIT 1) last_rep_note
FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id)
JOIN opportunities o ON o.opportunity_id = g.opportunity_id
LEFT JOIN clari_opportunity_forecasts f ON f.opportunity_id = o.opportunity_id
WHERE t.transcript_id = 2;
```
```sql
-- Find calls that mention a specific commitment pattern (FTS) — useful for showing scale
SELECT COUNT(*) calls_with_budget_committee FROM gong_transcripts_fts WHERE gong_transcripts_fts MATCH '"budget committee"';
```
```sql
-- Baseline: how often does a call precede any CRM update within 7 days? (T6 — usually never)
SELECT ROUND(1.0*SUM(upd)/COUNT(*),3) share_calls_with_update_7d FROM (
  SELECT t.transcript_id,
         EXISTS (SELECT 1 FROM clari_forecast_history_logs l WHERE l.opportunity_id=g.opportunity_id
                 AND substr(l.change_timestamp,1,10) BETWEEN t.call_date AND date(t.call_date,'+7 day')) upd
  FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id)
  WHERE t.call_date BETWEEN '2026-01-01' AND '2026-09-15');
```

Prompt to Claude (paste the transcript row):
```
You are the Call-to-CRM agent in AGENT.md. From full_transcript_text only:
1. Extract: summary (≤ 60 words), prospect_commitments (quote the line + timestamp), rep_commitments, objections, competitor_named, next_step (who/what/when).
2. Compare against the current CRM state provided. Propose field diffs ONLY where the transcript gives explicit evidence; each diff = {field, current, proposed, quote, confidence}.
3. Risk flag: LOW/MED/HIGH with the single strongest reason and a confidence. Consider: economic buyer absent, competitor renewal timing, procurement/security review, budget freeze language.
4. If the tracker competitor (competitor_tracker_hits) differs from the transcript, say which you trust and why.
Never propose a diff you cannot quote. Never mark Closed Won/Lost.
```

## Phase 3 · Taste Validation
Rubric first (§Evaluation rubric below). The hallucination test: ask Claude to produce a second extraction *without* the "quote the line" rule and diff the two — the unconstrained one will typically upgrade "keep me posted on the roadmap" into a commitment. That's the failure mode to name: **invented commitments are worse than no summary because they enter the system of record.**

Traps to name: T7 (competitor disagreement), T20 (`key_takeaways` is one of 17 templates — extract from the text), T5 (last rep note may contradict the call), T6 (calls almost never precede a CRM update — the baseline proves the problem), T3 (Clari category may already be wrong for this opp).

Live iteration: ask for the risk flag without a confidence field first; it will say HIGH confidently on thin evidence. Add the confidence + "strongest single reason" requirement → regenerate → show it downgrades to MED with a cited reason.

## Known-gaps list
Speaker attribution errors · multi-opp calls (one call, two deals) · non-English calls · approval UX inside Salesforce (Lightning action vs Slack) · audit log of what the agent proposed vs what the rep accepted (needed to measure precision).

---

# Contract used by the agent

## Output schema
```json
{
  "transcript_id": 0, "opportunity_id": 0, "call_date": "", "low_quality": false,
  "summary": "",
  "extraction": {
    "prospect_commitments": [{"quote": "", "t_sec": 0}], "rep_commitments": [{"quote": "", "t_sec": 0}],
    "objections": [{"topic": "", "quote": ""}], "competitor_named": "", "competitor_conflict": "",
    "decision_process": [""], "economic_buyer_present": false
  },
  "proposed_diffs": [{"field": "NextStep|CloseDate|Stage|Competitor", "current": "", "proposed": "", "quote": "", "confidence": 0.0}],
  "risk": {"level": "LOW|MED|HIGH", "previous": "", "strongest_reason": "", "confidence": 0.0, "notify_manager": false},
  "not_proposed_because": [""]
}
```

## Guardrails
- Zero autonomous writes. Every diff carries a quote; no quote → no diff.
- Never propose Closed Won / Closed Lost, never move stage backwards, never change Amount/ARR.
- Risk flag never goes to the manager without also going to the rep.
- Retain nothing beyond the extraction; transcripts stay in Gong.

## Evaluation rubric
| Axis | Good | Subtle failure |
|---|---|---|
| No invented commitments | Every commitment quoted | "Prospect agreed to buy next quarter" from "keep me posted" |
| Diff precision | Rep accepts ≥ 85% of diffs | Proposing a close date from "sometime next year" |
| Conflict handling | Transcript vs tracker conflict surfaced | Silently using the tracker competitor |
| Risk calibration | HIGH only with a quoted reason; confidence stated | HIGH because sentiment score is −0.9 |
| Rep trust | Card takes < 20s to approve | Ten diffs per call, five of them trivial |
