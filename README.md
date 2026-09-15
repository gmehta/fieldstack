# Fieldstack

A login-gated scaffold of the ten seats in a B2B GTM org — SDR through Finance — built to prep for a Rubrik Staff PM case round on shipping AI agents across the seller/GTM journey (CRM, PRM, CPQ, billing).

Instead of one generic CRM dashboard, each seat opens onto the actual workspace that role lives in day to day: an SDR sees a sequence queue and intent alerts, an AE spends their day in a Slack-style deal room (with CRM fields arriving only through a Scratchpad-style overlay, not a native record), a Deal Desk seat sees a CPQ quote builder and approval queue, Legal sees a contract/redline tracker, and so on. Every seat tracks the same deal — Northfield Robotics, closing Sep 26 — as it moves through Lead → Opportunity → Quote → Cash, so switching seats shows how one deal looks from ten different desks.

This mirrors the "GTM Surface Transformation" thesis: modern revenue teams increasingly work in Slack, sales-engagement tools, CPQ platforms, and CLM software as their systems of engagement, while the CRM (Salesforce/HubSpot) recedes into a system of record synced in the background.

## Live demo

Open `index.html` directly, or serve the repo with GitHub Pages (Settings → Pages → deploy from `main` / root).

### Demo accounts

All ten accounts use the password `password`.

| Username | Seat | Primary surface |
|---|---|---|
| `sdr` | SDR / BDR | Sales Engagement Workspace |
| `marketing` | Demand Gen & Marketing Ops | Campaign & ABM Console |
| `ae` | Account Executive | Deal Workspace (Slack + CRM overlay) |
| `revops` | Revenue Operations | Routing & Data Ops Console |
| `se` | Solutions Engineer | Technical Workspace |
| `dealdesk` | Deal Desk | CPQ & Approvals Console |
| `legal` | Legal & Procurement | Contract Lifecycle Console |
| `salesleader` | VP, Sales | Revenue Intelligence Dashboard |
| `finance` | Finance & Billing (AR) | Billing & Collections Console |
| `csm` | Customer Success | Customer Health Console |

Everything in the app — accounts, deals, messages, numbers — is illustrative sample data, not live data.

## `data-model/build_rubrik_gtm_db_v5.py`

A standalone synthetic-data generator, separate from the front-end scaffold above. It builds `rubrik_gtm_synthetic_v5.db`, a 31-table SQLite database modeling a Rubrik-style B2B GTM data estate: 19 core GTM tables (accounts, contacts, opportunities, contracts, partners, deal registrations, entitlements, etc.), 4 junction tables, 6 structured RevOps telemetry tables (6sense intent, Gong call insights, Clari forecasts, Outreach activity, Highspot engagement, external-ID crosswalks), 6 unstructured raw-payload tables (full Gong transcripts, Outreach email bodies, Highspot slide-level logs, 6sense search queries, Marketo raw form JSON, Clari stage/notes audit history), and 2 FTS5 full-text search tables over the transcripts and email bodies.

Generated text is biased toward each account's actual installed technographic vendor, so an account running Cohesity gets Cohesity-flavored objections, competitor-tracker hits, and search queries — the unstructured text stays logically consistent with the structured rows instead of being random filler.

Run it with:

```bash
cd data-model
python3 build_rubrik_gtm_db_v5.py
```

This produces `rubrik_gtm_synthetic_v5.db` (git-ignored — regenerate it locally rather than committing it) along with a console summary of row counts and file size at each build stage (raw data, after FTS5 rebuild, after indexing, after `VACUUM`).

## Status

Both pieces are prep scaffolding for an upcoming case interview, not a production build. Sample data throughout (Northfield Robotics, Bramblewood Health, Solstice Freight, and the synthetic GTM database) is fictional.
