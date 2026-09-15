#!/usr/bin/env python3
"""
Semantic catalog layer for rubrik_gtm_synthetic_v5.db.

Adds a searchable metadata layer ON TOP OF the existing V5 database (run
build_rubrik_gtm_db_v5.py first) so an agent can look up "what table/column
answers this question" via keyword search BEFORE writing SQL against the
31 raw tables -- rather than re-deriving the schema from scratch on every
turn, or hallucinating column names.

What this adds (3 new plain tables + 1 FTS5 index, all inside the SAME
.db file as your data -- nothing external to stand up):

  semantic_catalog_tables      -- one row per real table: business name,
                                   plain-English description, category,
                                   PK, live row count, example questions
                                   it can answer.
  semantic_catalog_columns     -- one row per real column: business
                                   synonyms, plain-English description,
                                   FK target (if any), example value.
  semantic_catalog_relationships -- one row per FK / junction relationship,
                                   with the actual JOIN clause to use.
  semantic_catalog_fts         -- FTS5 index over table + column
                                   descriptions/synonyms, so an agent can
                                   do `MATCH 'competitor pricing'` and get
                                   back ranked candidate tables/columns
                                   instead of scanning all 31 schemas.

Table/column descriptions are introspected live via PRAGMA (so they can
never drift out of sync with the real schema) and then enriched with
hand-curated business context for the columns that actually need it.

Usage:
    python3 build_semantic_catalog_v5.py [path/to/rubrik_gtm_synthetic_v5.db]

Agent usage pattern (see demo_agent_query() at the bottom):
    1. Extract keywords from the user's question.
    2. SELECT ... FROM semantic_catalog_fts WHERE semantic_catalog_fts MATCH ?
       -> ranked tables/columns/relationships that are actually relevant.
    3. Build SQL using the join hints in semantic_catalog_relationships.
    4. Only fall back to raw PRAGMA table_info() introspection if the
       catalog search returns nothing -- that's the "semantic layer first,
       raw schema second" pattern.
"""
import sqlite3, sys, os, time

DB_PATH = sys.argv[1] if len(sys.argv) > 1 else "rubrik_gtm_synthetic_v5.db"
if not os.path.exists(DB_PATH):
    print(f"ERROR: {DB_PATH} not found. Run build_rubrik_gtm_db_v5.py first to generate it.")
    sys.exit(1)

t0 = time.time()
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ============================================================
# 1. Hand-curated business context.
#    Only the non-obvious stuff needs curation -- everything else
#    (data type, PK/FK-ness, which table a FK points to) is pulled
#    live from PRAGMA below so it can never drift from the real schema.
# ============================================================

TABLE_META = {
    "accounts": ("Account", "Core", "A company Rubrik sells to or targets -- customer or prospect.",
        "Which accounts are in the Financial Services industry? | What's the ARR for Acme Corp?"),
    "buying_centers": ("Buying Center", "Core", "A budget-holding group within an account (e.g. SecOps, IT Infra) that funds purchases.",
        "Which buying center owns the budget for this deal? | How mature is this account's SecOps function?"),
    "technographics": ("Installed Technology", "Core", "A specific vendor/product an account already runs -- the incumbent stack Rubrik displaces.",
        "Which accounts run Cohesity? | What's this account's backup renewal date?"),
    "contacts": ("Contact", "Core", "An individual person at an account -- a buyer, champion, or stakeholder.",
        "Who is the economic buyer at this account? | Find all VP-level security contacts."),
    "buyer_personas": ("Buyer Persona", "Core", "A named buying role archetype (Economic Buyer, Champion, Security Blocker, etc).",
        "What are the pain points of a Security Blocker persona?"),
    "campaigns": ("Marketing Campaign", "Core", "A marketing program (event, webinar, email blast) that generates touchpoints.",
        "Which campaign drove the most touchpoints this quarter?"),
    "touchpoints": ("Engagement Signal", "Core", "A single logged interaction (download, demo request, site visit) tying a contact to a campaign.",
        "What is this contact's most recent engagement? | Which touchpoints came from Gong vs Marketo?"),
    "partners": ("Channel Partner", "Core", "A reseller/distributor/GSI that sources or co-sells deals (VAR, GSI, Distributor, MSP).",
        "Which partners are Platinum tier? | List all AWS Marketplace partners."),
    "partner_certifications": ("Partner Certification", "Core", "A technical certification a partner's team holds.",
        "Which partners are RSC Specialist certified?"),
    "deal_registrations": ("Deal Registration", "Core", "A partner's formal claim to source/influence a specific deal, for margin protection.",
        "Which deal registrations are still pending approval?"),
    "partner_programs": ("Partner Program", "Core", "The tiered program (discount %, MDF budget) a partner is enrolled in.",
        "How much MDF is unspent in the current partner program?"),
    "incentive_payouts": ("Partner Incentive Payout", "Core", "A rebate/SPIFF/referral payment made to a partner.",
        "What SPIFFs are still pending payment?"),
    "co_sell_motions": ("Co-Sell Motion", "Core", "A joint selling activity (account mapping, joint POC) between Rubrik and a partner on a deal.",
        "What co-sell motions are in progress on this opportunity?"),
    "opportunities": ("Sales Opportunity", "Core", "A tracked deal in the pipeline -- the central commercial entity most other tables hang off of.",
        "What's the total ARR of deals in Proposal stage? | Which opportunities are Closed Lost?"),
    "contracts": ("Contract / MSA", "Core", "The signed agreement that results from a won opportunity.",
        "Which contracts auto-renew this year? | What's the total contract value fulfilled by partners?"),
    "skus": ("Product SKU", "Core", "A sellable product module (e.g. Cyber Recovery Add-on, M365 Protection).",
        "What's the list price of the Cloud Vault SKU?"),
    "entitlements": ("License Entitlement", "Core", "The capacity/seats a customer purchased vs. is actively using under a contract.",
        "Which customers are using less than 50% of their purchased capacity?"),
    "employees": ("GTM Employee", "Core", "An internal Rubrik revenue employee (AE, BDR, SE, CAM).",
        "Which AE owns the most pipeline? | List all Solutions Engineers in APJ."),
    "ai_agents": ("GTM AI Agent", "Core", "An internal automation/AI bot that assists the revenue team (prospecting, deal desk, etc).",
        "Which AI agent has executed the most actions?"),

    "opportunity_partners": ("Opportunity <-> Partner link", "Junction", "N:M: which partner(s) co-sold which opportunity(ies), with influence weight and role.",
        "Which partner had the highest influence weight on this deal?"),
    "opportunity_skus": ("Opportunity <-> SKU link", "Junction", "N:M: which SKU(s) are included in which opportunity(ies), with quantity and negotiated price.",
        "What SKUs are quoted on this opportunity?"),
    "opportunity_employees": ("Opportunity <-> Employee link", "Junction", "N:M: which employee(s) are staffed on which opportunity(ies) and in what role.",
        "Who is the SE assigned to this opportunity?"),
    "agent_opportunity_assists": ("AI Agent <-> Opportunity link", "Junction", "N:M: which AI agent took which action on which opportunity, and when.",
        "What did the Deal Desk Assistant last do on this opportunity?"),

    "account_external_ids": ("Cross-System Identity Map", "RevOps Telemetry", "Maps one internal account to its record ID in each external RevOps tool (Salesforce, 6sense, Gong, Clari, Marketo, Outreach).",
        "What is this account's Salesforce record ID?"),
    "sixsense_account_intent": ("6sense Intent/ABM Profile", "RevOps Telemetry", "6sense's account-level buying intent score, funnel stage, and whether it's a qualified account (6QA).",
        "Which accounts are 6sense-qualified (6QA) and in the Decision stage?"),
    "gong_account_insights": ("Gong Call Analytics", "RevOps Telemetry", "Aggregated Gong call metrics for an opportunity: sentiment, competitor mentions, multithreading, talk time.",
        "Which opportunities have negative buyer sentiment? | Which deals mention Cohesity in calls?"),
    "clari_opportunity_forecasts": ("Clari AI Forecast", "RevOps Telemetry", "Clari's AI-driven health score and forecast category for an opportunity, vs. the rep's own forecast.",
        "Which Commit deals have a low Clari health score (forecast risk)?"),
    "outreach_sequence_activities": ("Outreach Sequence Step", "RevOps Telemetry", "One step of an Outreach.io sales engagement sequence run against a contact.",
        "Which sequence has the best reply rate?"),
    "highspot_collateral_engagement": ("Highspot Content Engagement", "RevOps Telemetry", "Summary of how long/how much of a piece of sales content a buyer viewed.",
        "What collateral got the most engagement on this deal?"),

    "gong_call_transcripts": ("Gong Full Call Transcript", "Unstructured", "The full multi-turn Rep/Prospect dialogue for a Gong call, with speaker-diarized JSON, the top objection raised, and a key takeaway.",
        "Find calls where the prospect objected on Cohesity pricing. | Summarize the key takeaway from this call."),
    "outreach_email_messages": ("Outreach Raw Email", "Unstructured", "The actual subject/body/reply text of one Outreach email, with a sentiment tag on the reply.",
        "Find emails with negative sentiment replies. | What did we pitch in the last email to this contact?"),
    "highspot_slide_views": ("Highspot Slide-Level View Log", "Unstructured", "Per-slide dwell time and any buyer comment within one Highspot content engagement.",
        "Which slide got the longest dwell time? | Did the buyer leave any comments on the deck?"),
    "sixsense_search_queries": ("6sense Search Query Log", "Unstructured", "An actual search term an anonymous account researcher typed, resolved back to the account, plus the landing page it drove to.",
        "What search terms is this account using to research competitors?"),
    "marketo_raw_form_fills": ("Marketo Raw Form Submission", "Unstructured", "The raw field-level JSON payload, UTM params, and referrer URL from one Marketo form fill.",
        "What campaign UTM drove this form fill? | What did this contact enter as their company size?"),
    "clari_forecast_history_logs": ("Clari Stage/Notes Audit Trail", "Unstructured", "A historical log entry of a stage or ARR change on an opportunity's forecast, with the rep's free-text notes.",
        "Why did this deal slip a stage? | Find rep notes explaining a Closed Lost deal."),
}

# column_name -> (business synonyms, description) -- only for columns worth
# annotating beyond their auto-generated description (see build_column_row below).
COLUMN_META = {
    "arr": ("annual recurring revenue, subscription value", "Annual recurring revenue in USD for this deal."),
    "tcv": ("total contract value", "Total contract value in USD across the full deal term."),
    "total_contract_value": ("TCV, deal size", "Total value in USD of the signed contract."),
    "stage": ("deal stage, funnel stage", "Sales funnel stage: Discovery, Validation, Proposal, Closed Won, or Closed Lost."),
    "intent_score": ("buying intent, interest level", "0-100 score; higher means stronger buying intent signal."),
    "is_6qa": ("6sense qualified account, 6QA flag", "1 if 6sense considers this a qualified in-market account, else 0."),
    "clari_health_score": ("deal health, forecast confidence", "0-100 AI-derived confidence that this deal closes as forecast; lower = at risk."),
    "buyer_sentiment_score": ("call sentiment, tone", "-1 (negative) to 1 (positive) sentiment detected across the buyer's call audio."),
    "competitor_tracker_hits": ("competitor mentions", "Which competitor name(s) Gong detected being discussed on the call."),
    "multithread_contact_ratio": ("multithreading, stakeholder coverage", "Share of distinct buying-committee contacts present across calls on this deal; low = single-threaded risk."),
    "sentiment_tag": ("email tone, reply sentiment", "Positive, Neutral, or Negative -- sentiment of the buyer's email reply."),
    "top_objection_raised": ("sales objection, pushback", "The primary objection the prospect raised on this call, usually tied to their incumbent vendor."),
    "full_transcript_text": ("call transcript, call recording text", "The complete multi-turn dialogue of the sales call, searchable via semantic_catalog's companion FTS5 tables gong_transcripts_fts."),
    "body_plain_text": ("email body, message text", "The plain-text body of the outbound sales email, searchable via outreach_emails_fts."),
    "reply_body_text": ("buyer reply, response text", "The buyer's reply text, if any -- null means no reply was received."),
    "vendor_name": ("incumbent vendor, installed tech", "The vendor product actually installed at this account (e.g. Cohesity, Commvault, AWS)."),
    "displacement_priority": ("competitive priority", "How high a priority this installed technology is for Rubrik to displace."),
    "forecast_category": ("Clari bucket, forecast confidence tier", "Clari's bucket for this deal: Commit, Best Case, Pipeline, or Omitted."),
    "influence_weight": ("partner influence, co-sell weight", "0-1 score of how much this partner influenced the deal outcome."),
    "match_confidence_score": ("identity match confidence", "0-1 confidence that this external system record was correctly matched to the account."),
    "seniority_level": ("job level, seniority", "C-Level, VP, Director, Manager, or Individual Contributor."),
    "probability_pct": ("win probability, close probability", "Percent likelihood (rep-estimated) this opportunity closes won."),
}

CATEGORY_ORDER = {"Core": 0, "Junction": 1, "RevOps Telemetry": 2, "Unstructured": 3}

# ============================================================
# 2. Schema.
# ============================================================
print("Creating semantic catalog tables + FTS5 index...")
cur.executescript("""
DROP TABLE IF EXISTS semantic_catalog_tables;
DROP TABLE IF EXISTS semantic_catalog_columns;
DROP TABLE IF EXISTS semantic_catalog_relationships;
DROP TABLE IF EXISTS semantic_catalog_fts;

CREATE TABLE semantic_catalog_tables (
  table_name TEXT PRIMARY KEY,
  business_name TEXT,
  category TEXT,
  description TEXT,
  primary_key TEXT,
  row_count INTEGER,
  example_questions TEXT
);

CREATE TABLE semantic_catalog_columns (
  table_name TEXT,
  column_name TEXT,
  data_type TEXT,
  is_primary_key INTEGER,
  is_foreign_key INTEGER,
  fk_table TEXT,
  fk_column TEXT,
  business_synonyms TEXT,
  description TEXT,
  PRIMARY KEY (table_name, column_name)
);

CREATE TABLE semantic_catalog_relationships (
  from_table TEXT,
  from_column TEXT,
  to_table TEXT,
  to_column TEXT,
  relationship_type TEXT,
  description TEXT,
  join_sql TEXT
);

CREATE VIRTUAL TABLE semantic_catalog_fts USING fts5(
  kind, ref_table, ref_column, content_text
);
""")

# ============================================================
# 3. Introspect the real schema live (PRAGMA) so nothing here can drift
#    from the actual tables, then merge in the curated business context.
# ============================================================
real_tables = [r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' "
    "AND name NOT LIKE '%_fts%' AND name NOT LIKE 'semantic_catalog%'"
).fetchall()]

def pretty(col):
    return col.replace("_id", "").replace("_", " ").strip().capitalize()

table_rows, column_rows, rel_rows, fts_rows = [], [], [], []

for t in real_tables:
    business_name, category, desc, examples = TABLE_META.get(
        t, (pretty(t), "Uncataloged", f"No curated description yet for '{t}'.", "")
    )
    pk_cols = [c[1] for c in cur.execute(f"PRAGMA table_info({t})") if c[5] > 0]
    fk_list = {fk[3]: (fk[2], fk[4]) for fk in cur.execute(f"PRAGMA foreign_key_list({t})")}  # from_col -> (to_table, to_col)
    row_count = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]

    table_rows.append((t, business_name, category, desc, ",".join(pk_cols), row_count, examples))
    fts_rows.append(("table", t, None, f"{t} {business_name} {desc} {examples}"))

    for cid, cname, ctype, notnull, dflt, pk in cur.execute(f"PRAGMA table_info({t})"):
        is_fk = cname in fk_list
        fk_table, fk_col = fk_list.get(cname, (None, None))
        synonyms, col_desc = COLUMN_META.get(cname, ("", ""))
        if not col_desc:
            if pk:
                col_desc = f"Primary key of {t}."
            elif is_fk:
                col_desc = f"Foreign key -> {fk_table}.{fk_col}."
            else:
                col_desc = f"{pretty(cname)} field on {t}."
        column_rows.append((t, cname, ctype, 1 if pk else 0, 1 if is_fk else 0, fk_table, fk_col, synonyms, col_desc))
        fts_rows.append(("column", t, cname, f"{t}.{cname} {synonyms} {col_desc}"))

        if is_fk:
            rel_rows.append((
                t, cname, fk_table, fk_col, "N:1",
                f"Each {t} row belongs to one {fk_table} row.",
                f"JOIN {fk_table} ON {t}.{cname} = {fk_table}.{fk_col}"
            ))

# Explicit N:M documentation for the 4 junction tables (2 FKs each -> 2 relationship rows already
# captured above via the loop; add a combined join hint for convenience).
JUNCTION_HINTS = {
    "opportunity_partners": ("opportunities", "partners", "opportunity_id", "partner_id"),
    "opportunity_skus": ("opportunities", "skus", "opportunity_id", "sku_id"),
    "opportunity_employees": ("opportunities", "employees", "opportunity_id", "employee_id"),
    "agent_opportunity_assists": ("ai_agents", "opportunities", "agent_id", "opportunity_id"),
}
for jt, (t1, t2, c1, c2) in JUNCTION_HINTS.items():
    rel_rows.append((
        t1, c1, t2, c2, "N:M via " + jt,
        f"{t1} and {t2} are linked many-to-many through {jt}.",
        f"JOIN {jt} ON {t1}.{c1} = {jt}.{c1} JOIN {t2} ON {jt}.{c2} = {t2}.{c2}"
    ))

table_rows.sort(key=lambda r: (CATEGORY_ORDER.get(r[2], 9), r[0]))

cur.executemany("INSERT INTO semantic_catalog_tables VALUES (?,?,?,?,?,?,?)", table_rows)
cur.executemany("INSERT INTO semantic_catalog_columns VALUES (?,?,?,?,?,?,?,?,?)", column_rows)
cur.executemany("INSERT INTO semantic_catalog_relationships VALUES (?,?,?,?,?,?,?)", rel_rows)
cur.executemany("INSERT INTO semantic_catalog_fts (kind, ref_table, ref_column, content_text) VALUES (?,?,?,?)", fts_rows)

conn.commit()
print(f"  semantic_catalog_tables: {len(table_rows)} rows")
print(f"  semantic_catalog_columns: {len(column_rows)} rows")
print(f"  semantic_catalog_relationships: {len(rel_rows)} rows")
print(f"  semantic_catalog_fts: {len(fts_rows)} rows")

size = os.path.getsize(DB_PATH)
print(f"\nCatalog added in {time.time()-t0:.1f}s. {DB_PATH} is now {size/1e6:.2f} MB total.")

# ============================================================
# 4. Demo: the "semantic layer first" agent pattern.
# ============================================================
import re

def _fts5_or_query(text: str) -> str:
    """
    Turn free-form text into a safe FTS5 MATCH expression: split into
    word tokens, double-quote each one (so hyphens/punctuation inside a
    token can never be parsed as FTS5 query-syntax operators like NOT or
    column filters), and OR them together for best recall on a keyword
    search. This is the defensive pattern to use any time the search
    string comes from a user question rather than a hand-written query.
    """
    tokens = re.findall(r"\w+", text)
    return " OR ".join(f'"{tok}"' for tok in tokens) if tokens else '""'

def demo_agent_query(question_keywords: str):
    """
    Step 1 of the agent pattern: search the semantic layer, NOT the raw
    tables, to find out what's relevant. Only after this would the agent
    go build/run real SQL against the base tables.
    """
    print(f"\n--- Agent semantic search for: {question_keywords!r} ---")
    hits = cur.execute("""
        SELECT kind, ref_table, ref_column, content_text
        FROM semantic_catalog_fts
        WHERE semantic_catalog_fts MATCH ?
        ORDER BY rank
        LIMIT 8
    """, (_fts5_or_query(question_keywords),)).fetchall()
    if not hits:
        print("  No catalog matches -- agent would fall back to raw PRAGMA schema introspection.")
        return
    for kind, ref_table, ref_column, text in hits:
        loc = f"{ref_table}.{ref_column}" if ref_column else ref_table
        print(f"  [{kind:6s}] {loc:40s} {text[:90]}")

if __name__ == "__main__":
    demo_agent_query("competitor pricing objection")
    demo_agent_query("win probability forecast confidence")
    demo_agent_query("partner co-sell influence")

conn.close()
print("\nDone. Semantic catalog is inside:", os.path.abspath(DB_PATH))
