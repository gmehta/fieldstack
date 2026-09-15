# SPEC — Prospecting Research & Why-Now Agent

| | |
|---|---|
| **Job to be done** | Turn an hour of tab-hopping into a 5-field brief the BDR can act on in one minute, with a first touch that could only have been written for *this* account. |
| **Primary user** | BDR (net-new). Secondary: AE for warm expansion. |
| **Trigger** | Account enters 6QA + Decision stage with no open opp; or BDR asks "research {account}". |
| **Mode** | Read-only. Drafts into Outreach as *unsent* sequence step. BDR sends. |

> Product spec backing the agent in `AGENT.md`. Show this if asked "how would you productionise it?" — it is not needed to run the demo.

## Inputs
1. `sixsense_account_intent` (intent_score, buying_stage, is_6qa, top_keywords) + `sixsense_search_queries` (search_term, landing_page_url)
2. `technographics` WHERE category='Legacy Backup' (vendor_name, renewal_date)
3. `contacts` × `buyer_personas` (title only — T17) × `touchpoints` × `marketo_raw_form_fills` (form_name, raw_fields_json.consent_marketing)
4. `outreach_sequence_activities` × `outreach_email_messages.reply_body_text` — do-not-contact and "what we already said"
5. `opportunities` — exclude accounts with open pipeline (already owned)
6. `account_external_ids` (6sense, Outreach, Marketo confidence)

## Reasoning steps
1. Eligibility: Prospect or Churned status, no open opp, 6QA. Churned = "win-back", label it.
2. Why-now candidates, ranked: (a) incumbent renewal ≤ 180 days, (b) competitor-comparison searches / landing pages (`/compare/`), (c) high-intent form fills (assessment, ROI whitepaper). Keep top 3, each with a citation.
3. Who: primary = most senior contact with persona ∈ {Economic Buyer, Champion}; secondary = Technical Evaluator. If no senior contact exists, say "no economic buyer known" — that's a finding.
4. Do-not-contact: any contact whose last reply contains "hold off" / "non-starter", or `consent_marketing=false` in Marketo. List them explicitly.
5. Talk track: one pain, derived from evidence (search terms / forms), not the persona template.
6. Draft first touch ≤ 90 words; first sentence must contain a date, vendor, or document title.
7. Self-check: would any sentence survive unchanged for a different account? If yes, rewrite.

## Success metrics
Leading: research minutes per account (60 → ≤ 5, BDR-logged), % drafts sent with ≤ 1 edit. Lagging: reply rate vs sequence baseline (currently 38–41% across sequences), meetings booked per BDR-week, pipeline created from 6QA-no-opp accounts (78 today).

## Non-goals
Sending · scoring accounts (6sense does that) · multi-step sequence authoring · enrichment from outside the warehouse.

## Edge cases
Churned account (win-back framing; cite the contract end) · account with 22 contacts (cap to senior + persona-complete) · no search queries and no technographics (brief degrades to "who" only — say so) · low identity confidence on 6sense row.

## Rollout
5 BDRs × 2 weeks, brief in Slack, log edit distance → A/B first-touch templates by why-now type → hand the winning why-now taxonomy to the existing Outbound Prospecting Bot.
