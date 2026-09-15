# DATA-MAP — rubrik_gtm_synthetic_v5.db

Shared reference for every case skill. Read this once; each SKILL.md links back here instead of repeating it.
Run any query with `python3 _shared/gtm_query.py "<sql>"` (read-only connection).

**Anchor date: treat `2026-09-15` as today.** The data runs from 2023-01 to 2027-12, so "past close date", "renewing in 180 days" etc. are meaningless until you fix a date. Say this out loud in the room.

## 1. How the DB maps to the Rubrik stack (the diagram)

| Stack layer (diagram) | Tables | Grain |
|---|---|---|
| Salesforce — system of record | `accounts`, `contacts`, `buying_centers`, `buyer_personas`, `opportunities`, `opportunity_employees`, `opportunity_skus`, `skus`, `employees`, `contracts`, `entitlements` | account / contact / opp / contract |
| Salesforce PRM + channel | `partners`, `partner_programs`, `partner_certifications`, `deal_registrations`, `opportunity_partners`, `co_sell_motions`, `incentive_payouts` | partner / deal-reg / opp-partner |
| Clari — forecasting | `clari_opportunity_forecasts` (1 row per opp), `clari_forecast_history_logs` (stage/ARR change log + rep notes) | opp / change event |
| Gong — conversation intel | `gong_account_insights` (1 row per call, opp-level metrics), `gong_call_transcripts` (+ `gong_transcripts_fts` full-text) | call |
| Outreach — sales engagement | `outreach_sequence_activities`, `outreach_email_messages` (+ `outreach_emails_fts`) | sequence step / email |
| 6sense — intent & ABM | `sixsense_account_intent` (1 row per account), `sixsense_search_queries` | account / search |
| Marketo — MAP | `marketo_raw_form_fills`, `campaigns`, `touchpoints` (100k, all source systems) | form fill / touch |
| Highspot — enablement | `highspot_collateral_engagement`, `highspot_slide_views` | engagement / slide |
| Technographics (ZoomInfo-class) | `technographics` — incumbent vendor + `renewal_date` | account × install |
| Identity layer | `account_external_ids` — account → record id in each tool, with `match_confidence_score` | account × system |
| Existing GTM AI | `ai_agents`, `agent_opportunity_assists` | agent / assist event |
| Semantic layer | `semantic_catalog_tables`, `semantic_catalog_columns`, `semantic_catalog_relationships`, `semantic_catalog_fts` | metadata |

Key enums: `opportunities.stage` ∈ Discovery, Validation, Proposal, Closed Won, Closed Lost · `deal_type` ∈ New Logo, Upsell, Renewal · `accounts.status` ∈ Prospect, Customer, Churned · `accounts.tier` ∈ Enterprise, Mid-Market · `clari.forecast_category` ∈ Commit, Best Case, Pipeline, Omitted · `deal_registrations.status` ∈ Submitted, Approved, Rejected, Expired · `partners.type` ∈ VAR, GSI, Distributor, Cloud Marketplace, MSP · `employees.role` ∈ AE, BDR, SE, CAM · `agent action_type` ∈ Routed Co-Sell, Flagged Renewal Risk, Drafted Outreach, Summarized Call, Scored Intent.

## 2. Join spine (memorise this)

```
accounts ─┬─ contacts ─┬─ touchpoints ─ campaigns
          │            ├─ outreach_sequence_activities ─ outreach_email_messages
          │            └─ marketo_raw_form_fills
          ├─ buying_centers
          ├─ technographics
          ├─ sixsense_account_intent ─ sixsense_search_queries
          ├─ account_external_ids
          ├─ deal_registrations ─ partners ─ partner_programs / partner_certifications / incentive_payouts
          └─ opportunities ─┬─ clari_opportunity_forecasts / clari_forecast_history_logs
                            ├─ gong_account_insights ─ gong_call_transcripts
                            ├─ highspot_collateral_engagement ─ highspot_slide_views
                            ├─ opportunity_skus ─ skus
                            ├─ opportunity_employees ─ employees   (also opportunities.employee_id = owner)
                            ├─ opportunity_partners ─ partners ; co_sell_motions
                            └─ contracts ─ entitlements
```
`semantic_catalog_relationships.join_sql` has the literal JOIN clause for all 52 edges.

## 3. Known traps (verified 2026-09-15) — the Taste Validation ammunition

The data was generated with deliberate incoherence. A good answer *names* the trap it hit and states how it handled it. A bad answer averages over it.

| # | Trap | Evidence | Handle it by |
|---|---|---|---|
| T1 | 40% of open opps have `close_date` in the past | 1,628 of 2,432 open opps < 2026-09-15 | Treat as stale-flag input, never as "will close" |
| T2 | `probability_pct` is uniform 5–95 in every stage | avg ≈ 50 in Discovery *and* Closed Won | Ignore it; derive likelihood from stage + Clari health |
| T3 | Clari `forecast_category` is independent of stage | 193 Closed Won opps are "Omitted"; 243 open Commit opps have health < 40 | Surface as a hygiene defect, not a forecast |
| T4 | Two "amounts" disagree | `rep_forecast_amount` vs `opportunities.arr` differ ~81% on avg | Pick one as source of truth, say why |
| T5 | Only 5 distinct `rep_notes_text` strings, and notes contradict transitions | "downgrading confidence" attached to Proposal → Closed Won | Notes are weak evidence; flag contradictions |
| T6 | Sparse change logs | only 31% of open opps have any Clari log in the last 60 days | "No update" ≠ "no risk" — it's a data-quality signal |
| T7 | Two sources for "which competitor" disagree | `gong_call_transcripts.top_objection_raised` ≠ `gong_account_insights.competitor_tracker_hits` on 4,737 / 12,000 calls | Prefer the transcript (primary source) and cite it |
| T8 | SKU pricing is chaotic | same SKU name under multiple `sku_id`s with list prices $1.9k–$47.5k; `negotiated_price` exceeds list by up to 25×; Σ(qty × negotiated) vs `opp.arr` off ~3× | Never compute a discount without showing both numbers; flag negative discounts |
| T9 | Entitlements over-consumed | 945 / 2,000 rows have `seat_count_active` > `seat_count_purchased`; `expiration_date` never equals `contracts.end_date` | Over-use = expansion signal *or* data error — state both readings |
| T10 | Contracts exist for un-won deals | only 321 / 1,500 contracts belong to Closed Won opps | Filter on opp stage before calling anything "a customer" |
| T11 | Deal-reg partner ≠ co-sell partner | 2,411 opps' `deal_registrations.partner_id` not in `opportunity_partners`; ~37% of *Approved* regs have expired `protection_expiration_date` | Channel-conflict detection is a real case; Approved ≠ protected |
| T12 | MDF overspent, duplicate programs | 6 / 20 `partner_programs` have `mdf_spent` > `mdf_allocated`; program names repeat per year | Ask which program row is canonical |
| T13 | Opp owner is usually not an AE | `opportunities.employee_id` is BDR/SE/CAM 81% of the time; 2,765 opps have no AE in `opportunity_employees` | Say "owner" not "AE"; route nudges to whoever is on the opp |
| T14 | No control group for agent impact | every one of 4,000 opps has ≥ 1 `agent_opportunity_assists` row; `ai_agents` repeats names across versions | Compare by agent *version* / action mix, not agent vs none |
| T15 | Identity resolution is lossy | ~19% of `account_external_ids` rows have `match_confidence_score` < 0.8 | Caveat any cross-system join; show the confidence |
| T16 | Churned accounts carry open pipeline | 756 open opps sit on `status = 'Churned'` accounts; `technographics` category/vendor pairs are nonsensical (Cohesity as IaaS) | Filter on `category = 'Legacy Backup'` for competitors; question the status field |
| T17 | Personas duplicated | 2 rows per persona title, identical pains for all 10 | Group by `title`, not `persona_id` |
| T18 | `is_6qa` ≡ `intent_score ≈ 90` | perfectly collinear | Don't present both as independent evidence |
| T19 | Outreach `sentiment_tag` is a function of `response_status` | Bounced → Neutral, Meeting Booked → Positive, always | Sentiment adds nothing; use the reply text |
| T20 | Transcripts are templated | 12,000 unique texts but only 17 `key_takeaways` and 5 objections | Extract from `full_transcript_text`, don't trust `key_takeaways` blindly |

## 4. Starter queries (all verified)

```sql
-- pipeline snapshot
SELECT stage, COUNT(*) n, ROUND(SUM(arr)/1e6,1) arr_m,
       SUM(close_date < '2026-09-15') past_close
FROM opportunities GROUP BY stage;
```
```sql
-- one rich opportunity, all sources joined (change the id)
SELECT o.opportunity_id, a.name account, a.tier, a.status, o.stage, o.deal_type, o.arr, o.close_date,
       f.forecast_category, f.clari_health_score, f.rep_forecast_amount, f.ai_forecast_amount, f.deal_slip_count,
       (SELECT ROUND(AVG(buyer_sentiment_score),2) FROM gong_account_insights g WHERE g.opportunity_id=o.opportunity_id) gong_sentiment,
       (SELECT COUNT(*) FROM gong_account_insights g WHERE g.opportunity_id=o.opportunity_id) calls,
       (SELECT GROUP_CONCAT(DISTINCT e.role) FROM opportunity_employees oe JOIN employees e USING(employee_id) WHERE oe.opportunity_id=o.opportunity_id) staffed_roles
FROM opportunities o JOIN accounts a USING(account_id)
LEFT JOIN clari_opportunity_forecasts f USING(opportunity_id)
WHERE o.opportunity_id = 1424;
```
```sql
-- full-text search over calls (quote hyphenated terms)
SELECT t.transcript_id, t.call_title, t.call_date, t.top_objection_raised
FROM gong_transcripts_fts fts JOIN gong_call_transcripts t ON t.transcript_id = fts.rowid
WHERE gong_transcripts_fts MATCH '"pen-test" OR "budget committee"' LIMIT 10;
```
```sql
-- semantic catalog lookup
SELECT kind, ref_table, ref_column FROM semantic_catalog_fts WHERE semantic_catalog_fts MATCH 'renewal' LIMIT 10;
```

## 5. Good demo records

| Use | Pick | Why |
|---|---|---|
| Strategic account | `account_id` 1428 "Quantum Systems" (Enterprise, Customer, 4 open opps, $3.29M open ARR) | richest joins |
| Alternative | 1457 "Vantage Media", 753 "Meridian Bank" | |
| Rich call | `transcript_id` 1 (Opp 1424, Cohesity objection) or 2 (Opp 3815, NetApp, "budget committee") | contradictory signals present |

## 6. Ground rules baked into every skill
1. Read-only. `gtm_query.py` opens the DB read-only; every agent spec is advisory with human-in-the-loop write-back.
2. Cite the row. Every claim in an output names the table + id it came from.
3. Name the trap. When a query touches T1–T20, the output says so.
4. Thin slice first. One account / one opp / one call / one quote before any batch.
5. Eval axes before output. Generate the rubric, then the artifact, then critique it against the rubric.
