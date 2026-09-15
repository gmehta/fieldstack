# SPEC — Competitive Displacement (Takeout) Agent

| | |
|---|---|
| **Job to be done** | Find the accounts where an incumbent backup vendor is renewing soon *and* the account is showing competitor-comparison intent *and/or* has voiced that competitor on a call — then hand the AE the play with the timing, the objection to pre-empt, and the battlecard. |
| **Primary user** | AE / BDR (run the play). Secondary: ABM marketing (list), competitive desk (objection trends). |
| **Trigger** | Weekly refresh; incumbent renewal enters the 270-day window; new competitor search or call objection on a windowed account. |
| **Mode** | Read-only. Ranked list + play; drafting handed to Case 3's agent; no sending. |

> Product spec backing the agent in `AGENT.md`. Show this if asked "how would you productionise it?" — it is not needed to run the demo.

## Inputs (three independent sources — independence is the design)
1. `technographics` WHERE category='Legacy Backup' AND vendor_name ∈ {Cohesity, Veeam, Commvault, NetApp} (vendor_name, renewal_date) — *timing*
2. `sixsense_search_queries` (search_term, landing_page_url, last 6 months) — *intent*, vendor-matched to the incumbent
3. `gong_call_transcripts.top_objection_raised` + `full_transcript_text` — *voiced*; prefer transcript over `gong_account_insights.competitor_tracker_hits` (T7)
Support: `highspot_collateral_engagement` (battlecard views), `outreach_email_messages.reply_body_text` ("locked into"), `opportunities` (open opp?), `accounts.status`, `sixsense_account_intent.is_6qa` (once — T18)

## Scoring
`sources_agreeing` (0–3) is the primary sort; ties broken by renewal proximity, then tier.
- 3 = act now · 2 = qualified takeout · 1 = lead (send to BDR research, Case 3) · 0 = not on list
- If sources name *different* competitors → mark "sources disagree", score on timing only, flag for research.
- Existing customer with a competitor in another BU → lane = expansion-takeout.
- Open opp exists → lane = support-AE (attach evidence to the opp, don't create pipeline).

## Reasoning steps
1. Build the window from technographics. 2. Attach vendor-matched intent hits. 3. Attach vendor-matched call objections with a quoted line. 4. Score and lane. 5. Assemble the evidence pack. 6. Write the play: battlecard (from Highspot content names), objection to pre-empt (quoted), timing window (renewal − 120d to − 30d), first sentence, and the do-not-say list (no verbatim search queries).

## Success metrics
Leading: takeout list acceptance by AEs (≥ 70% of score-3 rows worked within 2 weeks), pipeline created from score-3 rows. Lagging: competitive win rate by incumbent (baseline from query 4), takeout ARR closed, objection trend shifts.

## Non-goals
Pricing / bridge offers · ABM campaign execution · win/loss modelling · news/funding enrichment.

## Edge cases
Account running two competitors (two rows, one per incumbent) · renewal_date in the past (stale technographic — drop, flag for refresh) · churned Rubrik customer now on a competitor (win-back lane; cite the contract) · parent/child with different incumbents.

## Rollout
Score-3 list to 5 AEs for 2 weeks → measure worked-rate and pipeline → add score-2 → hand objection trends to the competitive desk monthly.
