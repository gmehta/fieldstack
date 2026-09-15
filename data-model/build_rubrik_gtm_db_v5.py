#!/usr/bin/env python3
"""
Rubrik B2B GTM Data Model Specification V5 -> SQLite.

V5 = V4's 25 tables (19 core GTM + 6 structured RevOps telemetry tables)
   + 6 new UNSTRUCTURED RAW PAYLOAD tables (full Gong transcripts,
     Outreach email bodies, Highspot slide-level logs, 6sense search
     queries, Marketo raw form JSON, Clari stage/notes audit history)
   + 2 FTS5 full-text-search virtual tables over the Gong transcripts
     and Outreach email bodies, per the doc's "Storage Optimization"
     requirement.
31 tables total. Where the doc asks for it, generated text is biased
toward each account's actual installed technographic vendor (e.g. an
account running Cohesity gets Cohesity-flavored objections/searches)
so the unstructured text is logically consistent with the structured
rows, not just random lorem ipsum.

Run: python3 build_db_v5.py
Output: rubrik_gtm_synthetic_v5.db
"""
import sqlite3, random, time, os, json, datetime

random.seed(19)
DB_PATH = "rubrik_gtm_synthetic_v5.db"
if os.path.exists(DB_PATH):
    os.remove(DB_PATH)

t0 = time.time()
conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=OFF")
conn.execute("PRAGMA synchronous=OFF")
cur = conn.cursor()

# ---------------- synthetic value pools ----------------
FIRST = ["James","Mary","Robert","Patricia","John","Jennifer","Michael","Linda","David","Elizabeth",
         "William","Barbara","Richard","Susan","Joseph","Jessica","Thomas","Sarah","Charles","Karen",
         "Priya","Wei","Ananya","Chen","Fatima","Hiroshi","Olga","Diego","Amara","Lars"]
LAST = ["Smith","Johnson","Williams","Brown","Jones","Garcia","Miller","Davis","Rodriguez","Martinez",
        "Hernandez","Lopez","Gonzalez","Wilson","Anderson","Thomas","Taylor","Moore","Jackson","Martin"]
COMPANY_WORD = ["Global","Summit","Pinnacle","Vertex","Nova","Horizon","Atlas","Quantum","Meridian","Apex",
                "Northstar","Ironclad","Bluewave","Crestline","Ridgeline","Fusion","Catalyst","Orbit","Sterling","Vantage"]
COMPANY_SUFFIX = ["Systems","Health","Financial","Logistics","Retail","Energy","Bio","Media","Bank","Manufacturing"]
INDUSTRY = ["Financial Services","Healthcare","Retail","Manufacturing","Energy","Media & Telecom",
            "Public Sector","Technology","Insurance","Transportation & Logistics"]
COUNTRY_STATE = [("USA","CA"),("USA","NY"),("USA","TX"),("USA","IL"),("USA","WA"),
                  ("UK",""),("Germany",""),("Australia",""),("Japan",""),("Canada","ON")]
TIER = ["Enterprise","Mid-Market"]; STATUS = ["Customer","Prospect","Churned"]
BC_NAME = ["IT Infrastructure","SecOps","Cloud Ops","Procurement"]
MATURITY = ["Nascent","Developing","Mature","Best-in-Class"]
TECH_CATEGORY = ["IaaS","Legacy Backup","Data Lake","Hypervisor"]
TECH_VENDOR = ["AWS","Azure","VMware","Cohesity","Commvault","GCP","Veeam","NetApp"]
INCUMBENT_VENDORS = ["Cohesity","Commvault","Veeam","NetApp"]  # vendors Rubrik actually displaces / competes with
JOB_TITLE = ["CISO","VP Infrastructure","Director of IT","Cloud Architect","Security Analyst",
             "SOC Manager","IT Manager","VP Engineering","Storage Admin","Procurement Manager"]
SENIORITY = ["C-Level","VP","Director","Manager","Individual Contributor"]
PERSONA_TITLES = ["Economic Buyer","Technical Evaluator","Champion","Security Blocker","End User"]
CAMPAIGN_TYPE = ["Event","Executive Dinner","Webinar","Outbound Email","Content Download"]
CAMPAIGN_CHANNEL = ["Field","Digital","ABM","Partner Co-Marketing"]
TOUCH_EVENT = ["Whitepaper Download","Demo Request","Website Visit","G2 Review","Booth Scan"]
SOURCE_SYSTEM = ["Salesforce","Marketo","Gong","6sense","Highspot"]
PARTNER_TYPE = ["VAR","GSI","Distributor","MSP","Cloud Marketplace"]
PARTNER_TIER = ["Gold","Platinum","Elite"]; REGION = ["AMER","EMEA","APJ","LATAM"]
CERT_NAME = ["RSC Specialist","AWS Storage Competency","Cyber Recovery Master","Azure Data Protection Expert"]
DEALREG_STATUS = ["Submitted","Approved","Rejected","Expired"]
DEALREG_SOURCE = ["Partner-Sourced","Partner-Influenced"]
PAYOUT_TYPE = ["Upfront Margin","Back-end Rebate","SPIFF","Referral Fee"]
PAYOUT_STATUS = ["Pending","Paid","Claws-backed"]
MOTION_TYPE = ["Account Mapping","Joint POC","Executive Briefing","AWS Co-Sell"]
MOTION_STATUS = ["Planned","In Progress","Completed"]
OPP_STAGE_SEQ = ["Discovery","Validation","Proposal","Closed Won"]  # forward progression order
OPP_STAGE = ["Discovery","Validation","Proposal","Closed Won","Closed Lost"]
DEAL_TYPE = ["New Logo","Upsell","Renewal"]
SKU_NAMES = ["Rubrik Security Cloud Edition","Cyber Recovery Add-on","M365 Protection","Cloud Vault",
             "Enterprise Edition","Cloud Native Protection","Anomaly Detection Add-on"]
EMP_ROLE = ["Account Executive","BDR","Solutions Engineer","Channel Account Manager"]
AGENT_NAME = ["Outbound Prospecting Bot","Deal Desk Assistant","Champion Finder","Co-Sell Router"]
ACTION_TYPE = ["Drafted Outreach","Scored Intent","Routed Co-Sell","Summarized Call","Flagged Renewal Risk"]

EXT_SYSTEMS = ["Salesforce","6sense","Gong","Clari","Marketo","Outreach"]
BUYING_STAGE = ["Awareness","Consideration","Decision"]
COMPETITOR_HITS = ["Cohesity","Commvault","Cohesity, Commvault","Veeam","None Detected"]
FORECAST_CATEGORY = ["Commit","Best Case","Pipeline","Omitted"]
SEQUENCE_NAME = ["Enterprise New Logo Outbound","Champion Multithread","Renewal Save Play","Partner Co-Sell Warm Intro","Executive Gifting Sequence"]
ACTIVITY_TYPE = ["Email","Call","LinkedIn"]
RESPONSE_STATUS = ["No Response","Opened","Replied","Bounced","Meeting Booked"]
CONTENT_NAME = ["Cyber Resilience ROI Calculator","Ransomware Readiness Whitepaper","Rubrik vs Cohesity Battlecard",
                "Zero Trust Data Security Deck","Customer Reference: Global Bank Case Study","Cloud Vault Demo Video"]

def rw(pool): return random.choice(pool)
def rdate(sy=2019, ey=2026):
    return datetime.date(random.randint(sy,ey), random.randint(1,12), random.randint(1,28)).isoformat()
def rts(sy=2023, ey=2026):
    return f"{rdate(sy,ey)}T{random.randint(0,23):02d}:{random.randint(0,59):02d}:00Z"
def domain_for(n): return n.lower().replace(" ","") + ".com"

BATCH = 5000
def bulk(table, cols, rows, total):
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})"
    buf, n = [], 0
    for r in rows:
        buf.append(r)
        if len(buf) >= BATCH:
            cur.executemany(sql, buf); n += len(buf); buf = []
    if buf:
        cur.executemany(sql, buf); n += len(buf)
    assert n == total, f"{table}: {n} != {total}"
    print(f"  {table}: {n:,} rows")

# ---- V5 target volumes ----
N_ACC=2500; N_BC=7500; N_TECH=15000; N_CONTACT=20000; N_PERSONA=10; N_CAMP=50
N_TOUCH=100000; N_PARTNER=150; N_CERT=450; N_DEALREG=2500; N_PROGRAM=20
N_PAYOUT=1500; N_MOTION=1200; N_OPP=4000; N_CONTRACT=1500; N_SKU=50
N_ENT=2000; N_EMP=250; N_AGENT=20
N_EXT_IDS=15000; N_SIXSENSE=2500; N_GONG=12000; N_CLARI=4000; N_OUTREACH=15000; N_HIGHSPOT=8000
# unstructured payload tables (new in V5)
N_GONG_TRANSCRIPTS=12000; N_EMAIL_MSGS=15000; N_SLIDE_VIEWS=25000
N_SEARCH_QUERIES=10000; N_FORM_FILLS=8000; N_CLARI_HISTORY=10000

print("Creating schema (31 tables: 19 core + 4 junction + 6 RevOps telemetry + 6 unstructured payload + 2 FTS5)...")
cur.executescript("""
PRAGMA foreign_keys=ON;

-- ===================== 19 CORE GTM TABLES =====================
CREATE TABLE accounts (
  account_id INTEGER PRIMARY KEY, name TEXT, domain TEXT, industry TEXT,
  employee_count INTEGER, annual_revenue INTEGER, tier TEXT, status TEXT,
  country TEXT, state TEXT, parent_account_id INTEGER REFERENCES accounts(account_id)
);
CREATE TABLE buyer_personas (
  persona_id INTEGER PRIMARY KEY, title TEXT, primary_pains TEXT, key_value_props TEXT
);
CREATE TABLE partner_programs (
  program_id INTEGER PRIMARY KEY, program_name TEXT, discount_margin_pct REAL,
  mdf_allocated REAL, mdf_spent REAL, effective_year INTEGER
);
CREATE TABLE campaigns (
  campaign_id INTEGER PRIMARY KEY, name TEXT, type TEXT, channel TEXT,
  start_date TEXT, end_date TEXT, total_budget REAL
);
CREATE TABLE skus (
  sku_id INTEGER PRIMARY KEY, name TEXT, pricing_metric TEXT, list_price REAL
);
CREATE TABLE employees (
  employee_id INTEGER PRIMARY KEY, full_name TEXT, email TEXT, role TEXT,
  territory TEXT, quota REAL
);
CREATE TABLE ai_agents (
  agent_id INTEGER PRIMARY KEY, name TEXT, capability_description TEXT,
  system_version TEXT, total_actions_executed INTEGER
);
CREATE TABLE buying_centers (
  buying_center_id INTEGER PRIMARY KEY, account_id INTEGER REFERENCES accounts(account_id),
  name TEXT, budget_owner_id INTEGER, annual_budget REAL, maturity_level TEXT
);
CREATE TABLE technographics (
  technographic_id INTEGER PRIMARY KEY, account_id INTEGER REFERENCES accounts(account_id),
  category TEXT, vendor_name TEXT, install_date TEXT, renewal_date TEXT
);
CREATE TABLE contacts (
  contact_id INTEGER PRIMARY KEY, account_id INTEGER REFERENCES accounts(account_id),
  buying_center_id INTEGER REFERENCES buying_centers(buying_center_id),
  persona_id INTEGER REFERENCES buyer_personas(persona_id),
  first_name TEXT, last_name TEXT, email TEXT, job_title TEXT, seniority_level TEXT
);
CREATE TABLE touchpoints (
  touchpoint_id INTEGER PRIMARY KEY, contact_id INTEGER REFERENCES contacts(contact_id),
  campaign_id INTEGER REFERENCES campaigns(campaign_id),
  source_system TEXT, event_type TEXT, timestamp TEXT, intent_score INTEGER
);
CREATE TABLE partners (
  partner_id INTEGER PRIMARY KEY, program_id INTEGER REFERENCES partner_programs(program_id),
  name TEXT, type TEXT, tier TEXT, prm_id TEXT, region TEXT
);
CREATE TABLE partner_certifications (
  cert_id INTEGER PRIMARY KEY, partner_id INTEGER REFERENCES partners(partner_id),
  cert_name TEXT, level TEXT, issued_date TEXT, expiry_date TEXT
);
CREATE TABLE deal_registrations (
  deal_reg_id INTEGER PRIMARY KEY, partner_id INTEGER REFERENCES partners(partner_id),
  account_id INTEGER REFERENCES accounts(account_id),
  submission_date TEXT, status TEXT, source_type TEXT, protection_expiration_date TEXT
);
CREATE TABLE incentive_payouts (
  payout_id INTEGER PRIMARY KEY, partner_id INTEGER REFERENCES partners(partner_id),
  payout_type TEXT, amount REAL, payment_status TEXT, payout_date TEXT
);
CREATE TABLE opportunities (
  opportunity_id INTEGER PRIMARY KEY, account_id INTEGER REFERENCES accounts(account_id),
  deal_reg_id INTEGER REFERENCES deal_registrations(deal_reg_id),
  employee_id INTEGER REFERENCES employees(employee_id),
  name TEXT, stage TEXT, deal_type TEXT, arr REAL, tcv REAL, close_date TEXT, probability_pct INTEGER
);
CREATE TABLE co_sell_motions (
  motion_id INTEGER PRIMARY KEY, opportunity_id INTEGER REFERENCES opportunities(opportunity_id),
  motion_type TEXT, date TEXT, status TEXT, notes TEXT
);
CREATE TABLE contracts (
  contract_id INTEGER PRIMARY KEY, opportunity_id INTEGER REFERENCES opportunities(opportunity_id),
  fulfilling_partner_id INTEGER REFERENCES partners(partner_id),
  msa_number TEXT, start_date TEXT, end_date TEXT, total_contract_value REAL, auto_renew INTEGER
);
CREATE TABLE entitlements (
  entitlement_id INTEGER PRIMARY KEY, contract_id INTEGER REFERENCES contracts(contract_id),
  allocated_capacity_tb REAL, used_capacity_tb REAL,
  seat_count_purchased INTEGER, seat_count_active INTEGER, expiration_date TEXT
);

-- ===================== 4 JUNCTION (N:M) TABLES =====================
CREATE TABLE opportunity_partners (
  opportunity_id INTEGER REFERENCES opportunities(opportunity_id),
  partner_id INTEGER REFERENCES partners(partner_id),
  influence_weight REAL, partner_role TEXT,
  PRIMARY KEY (opportunity_id, partner_id)
);
CREATE TABLE opportunity_skus (
  opportunity_id INTEGER REFERENCES opportunities(opportunity_id),
  sku_id INTEGER REFERENCES skus(sku_id),
  quantity INTEGER, negotiated_price REAL,
  PRIMARY KEY (opportunity_id, sku_id)
);
CREATE TABLE opportunity_employees (
  opportunity_id INTEGER REFERENCES opportunities(opportunity_id),
  employee_id INTEGER REFERENCES employees(employee_id),
  role TEXT, assigned_date TEXT,
  PRIMARY KEY (opportunity_id, employee_id)
);
CREATE TABLE agent_opportunity_assists (
  agent_id INTEGER REFERENCES ai_agents(agent_id),
  opportunity_id INTEGER REFERENCES opportunities(opportunity_id),
  last_action_timestamp TEXT, action_type TEXT,
  PRIMARY KEY (agent_id, opportunity_id, last_action_timestamp)
);

-- ===================== 6 STRUCTURED REVOPS TELEMETRY TABLES =====================
CREATE TABLE account_external_ids (
  id INTEGER PRIMARY KEY,
  account_id INTEGER REFERENCES accounts(account_id),
  system_name TEXT, external_record_id TEXT,
  match_confidence_score REAL, last_synced_at TEXT
);
CREATE TABLE sixsense_account_intent (
  intent_id INTEGER PRIMARY KEY,
  account_id INTEGER REFERENCES accounts(account_id),
  intent_score INTEGER, buying_stage TEXT, profile_fit_score REAL,
  is_6qa INTEGER, top_keywords TEXT
);
CREATE TABLE gong_account_insights (
  gong_id INTEGER PRIMARY KEY,
  account_id INTEGER REFERENCES accounts(account_id),
  opportunity_id INTEGER REFERENCES opportunities(opportunity_id),
  buyer_sentiment_score REAL, competitor_tracker_hits TEXT,
  multithread_contact_ratio REAL, total_call_duration_mins INTEGER
);
CREATE TABLE clari_opportunity_forecasts (
  forecast_id INTEGER PRIMARY KEY,
  opportunity_id INTEGER REFERENCES opportunities(opportunity_id),
  clari_health_score INTEGER, forecast_category TEXT,
  rep_forecast_amount REAL, ai_forecast_amount REAL, deal_slip_count INTEGER
);
CREATE TABLE outreach_sequence_activities (
  activity_id INTEGER PRIMARY KEY,
  contact_id INTEGER REFERENCES contacts(contact_id),
  employee_id INTEGER REFERENCES employees(employee_id),
  sequence_name TEXT, step_number INTEGER, activity_type TEXT, response_status TEXT
);
CREATE TABLE highspot_collateral_engagement (
  engagement_id INTEGER PRIMARY KEY,
  opportunity_id INTEGER REFERENCES opportunities(opportunity_id),
  contact_id INTEGER REFERENCES contacts(contact_id),
  content_name TEXT, view_duration_seconds INTEGER, completion_pct REAL, pages_viewed INTEGER
);

-- ===================== 6 UNSTRUCTURED RAW PAYLOAD TABLES (NEW IN V5) =====================
CREATE TABLE gong_call_transcripts (
  transcript_id INTEGER PRIMARY KEY,
  gong_id INTEGER REFERENCES gong_account_insights(gong_id),
  call_title TEXT, call_date TEXT,
  full_transcript_text TEXT, speaker_diarization_json TEXT,
  top_objection_raised TEXT, key_takeaways TEXT
);
CREATE TABLE outreach_email_messages (
  message_id INTEGER PRIMARY KEY,
  activity_id INTEGER REFERENCES outreach_sequence_activities(activity_id),
  contact_id INTEGER REFERENCES contacts(contact_id),
  employee_id INTEGER REFERENCES employees(employee_id),
  thread_id TEXT, subject_line TEXT, body_plain_text TEXT,
  reply_body_text TEXT, sentiment_tag TEXT
);
CREATE TABLE highspot_slide_views (
  slide_view_id INTEGER PRIMARY KEY,
  engagement_id INTEGER REFERENCES highspot_collateral_engagement(engagement_id),
  slide_number INTEGER, slide_title TEXT, dwell_time_seconds INTEGER,
  buyer_comments TEXT, share_method TEXT
);
CREATE TABLE sixsense_search_queries (
  query_id INTEGER PRIMARY KEY,
  intent_id INTEGER REFERENCES sixsense_account_intent(intent_id),
  account_id INTEGER REFERENCES accounts(account_id),
  search_term TEXT, search_timestamp TEXT, landing_page_url TEXT
);
CREATE TABLE marketo_raw_form_fills (
  fill_id INTEGER PRIMARY KEY,
  touchpoint_id INTEGER REFERENCES touchpoints(touchpoint_id),
  contact_id INTEGER REFERENCES contacts(contact_id),
  form_name TEXT, raw_fields_json TEXT,
  utm_source TEXT, utm_campaign TEXT, referrer_url TEXT
);
CREATE TABLE clari_forecast_history_logs (
  history_id INTEGER PRIMARY KEY,
  forecast_id INTEGER REFERENCES clari_opportunity_forecasts(forecast_id),
  opportunity_id INTEGER REFERENCES opportunities(opportunity_id),
  change_timestamp TEXT, old_stage TEXT, new_stage TEXT,
  old_arr REAL, new_arr REAL, rep_notes_text TEXT
);

-- ===================== FTS5 FULL-TEXT SEARCH TABLES (NEW IN V5) =====================
CREATE VIRTUAL TABLE gong_transcripts_fts USING fts5(
  full_transcript_text, key_takeaways,
  content='gong_call_transcripts', content_rowid='transcript_id'
);
CREATE VIRTUAL TABLE outreach_emails_fts USING fts5(
  subject_line, body_plain_text, reply_body_text,
  content='outreach_email_messages', content_rowid='message_id'
);
""")

print("Populating core tables (parents first, per FK direction)...")

def gen_persona():
    for i, t in enumerate(PERSONA_TITLES + PERSONA_TITLES[:N_PERSONA-len(PERSONA_TITLES)], 1):
        yield (i, t, "Ransomware exposure, audit failures, slow recovery", "Instant recovery, immutable backups, cyber posture visibility")
bulk("buyer_personas", ["persona_id","title","primary_pains","key_value_props"], gen_persona(), N_PERSONA)

def gen_program():
    for i in range(1, N_PROGRAM+1):
        yield (i, f"Partner Program {2020+i%6}", round(random.uniform(5,30),1), round(random.uniform(100_000,2_000_000),2), round(random.uniform(50_000,1_800_000),2), 2020+i%6)
bulk("partner_programs", ["program_id","program_name","discount_margin_pct","mdf_allocated","mdf_spent","effective_year"], gen_program(), N_PROGRAM)

def gen_campaign():
    for i in range(1, N_CAMP+1):
        s = rdate(2023,2026); yield (i, f"{rw(CAMPAIGN_TYPE)} - {rw(INDUSTRY)} {2023+i%3}", rw(CAMPAIGN_TYPE), rw(CAMPAIGN_CHANNEL), s, s, round(random.uniform(5_000,250_000),2))
bulk("campaigns", ["campaign_id","name","type","channel","start_date","end_date","total_budget"], gen_campaign(), N_CAMP)

def gen_sku():
    for i in range(1, N_SKU+1):
        yield (i, f"{rw(SKU_NAMES)} v{1+i%4}", rw(["per TB","per User","per Node"]), round(random.uniform(500,50_000),2))
bulk("skus", ["sku_id","name","pricing_metric","list_price"], gen_sku(), N_SKU)

def gen_emp():
    for i in range(1, N_EMP+1):
        f, l = rw(FIRST), rw(LAST)
        yield (i, f"{f} {l}", f"{f.lower()}.{l.lower()}@rubrik.com", rw(EMP_ROLE), rw(REGION), round(random.uniform(500_000,3_000_000),2))
bulk("employees", ["employee_id","full_name","email","role","territory","quota"], gen_emp(), N_EMP)

def gen_agent():
    for i in range(1, N_AGENT+1):
        yield (i, rw(AGENT_NAME), "Automates GTM workflow via LLM reasoning over CRM and product telemetry", f"v{1+i%5}.{i%10}", random.randint(100,50000))
bulk("ai_agents", ["agent_id","name","capability_description","system_version","total_actions_executed"], gen_agent(), N_AGENT)

def gen_account():
    for i in range(1, N_ACC+1):
        cname = f"{rw(COMPANY_WORD)} {rw(COMPANY_SUFFIX)}"
        country, state = rw(COUNTRY_STATE)
        parent = random.randint(1, i-1) if i > 1 and random.random() < 0.05 else None
        yield (i, cname, domain_for(cname), rw(INDUSTRY), random.randint(200,50000),
               random.randint(10_000_000,5_000_000_000), rw(TIER), rw(STATUS), country, state, parent)
bulk("accounts", ["account_id","name","domain","industry","employee_count","annual_revenue","tier","status","country","state","parent_account_id"], gen_account(), N_ACC)

def gen_bc():
    for i in range(1, N_BC+1):
        yield (i, random.randint(1,N_ACC), rw(BC_NAME), random.randint(1,N_CONTACT), round(random.uniform(50_000,5_000_000),2), rw(MATURITY))
bulk("buying_centers", ["buying_center_id","account_id","name","budget_owner_id","annual_budget","maturity_level"], gen_bc(), N_BC)

# Track each account's installed vendors so downstream unstructured text (objections,
# search queries) can reference the SAME incumbent the account actually runs.
account_incumbents = {}  # account_id -> list of vendor_name (restricted to INCUMBENT_VENDORS)
def gen_tech():
    for i in range(1, N_TECH+1):
        acc = random.randint(1,N_ACC)
        vendor = rw(TECH_VENDOR)
        if vendor in INCUMBENT_VENDORS:
            account_incumbents.setdefault(acc, []).append(vendor)
        yield (i, acc, rw(TECH_CATEGORY), vendor, rdate(2018,2025), rdate(2025,2028))
bulk("technographics", ["technographic_id","account_id","category","vendor_name","install_date","renewal_date"], gen_tech(), N_TECH)

def incumbent_for(account_id):
    lst = account_incumbents.get(account_id)
    return rw(lst) if lst else None

def gen_contact():
    for i in range(1, N_CONTACT+1):
        f, l = rw(FIRST), rw(LAST)
        yield (i, random.randint(1,N_ACC), random.randint(1,N_BC), random.randint(1,N_PERSONA),
               f, l, f"{f.lower()}.{l.lower()}{random.randint(1,999)}@example.com", rw(JOB_TITLE), rw(SENIORITY))
bulk("contacts", ["contact_id","account_id","buying_center_id","persona_id","first_name","last_name","email","job_title","seniority_level"], gen_contact(), N_CONTACT)

touch_contact = {}  # touchpoint_id -> contact_id (used later by marketo_raw_form_fills)
def gen_touch():
    for i in range(1, N_TOUCH+1):
        c = random.randint(1,N_CONTACT)
        touch_contact[i] = c
        yield (i, c, random.randint(1,N_CAMP), rw(SOURCE_SYSTEM), rw(TOUCH_EVENT), rts(2023,2026), random.randint(1,100))
bulk("touchpoints", ["touchpoint_id","contact_id","campaign_id","source_system","event_type","timestamp","intent_score"], gen_touch(), N_TOUCH)

def gen_partner():
    for i in range(1, N_PARTNER+1):
        pname = f"{rw(COMPANY_WORD)} {rw(['Partners','Solutions','Group','Consulting'])}"
        yield (i, random.randint(1,N_PROGRAM), pname, rw(PARTNER_TYPE), rw(PARTNER_TIER), f"PRM-{100000+i}", rw(REGION))
bulk("partners", ["partner_id","program_id","name","type","tier","prm_id","region"], gen_partner(), N_PARTNER)

def gen_cert():
    for i in range(1, N_CERT+1):
        yield (i, random.randint(1,N_PARTNER), rw(CERT_NAME), rw(["Associate","Professional","Master"]), rdate(2021,2025), rdate(2025,2027))
bulk("partner_certifications", ["cert_id","partner_id","cert_name","level","issued_date","expiry_date"], gen_cert(), N_CERT)

def gen_dealreg():
    for i in range(1, N_DEALREG+1):
        yield (i, random.randint(1,N_PARTNER), random.randint(1,N_ACC), rdate(2023,2026), rw(DEALREG_STATUS), rw(DEALREG_SOURCE), rdate(2026,2027))
bulk("deal_registrations", ["deal_reg_id","partner_id","account_id","submission_date","status","source_type","protection_expiration_date"], gen_dealreg(), N_DEALREG)

def gen_payout():
    for i in range(1, N_PAYOUT+1):
        yield (i, random.randint(1,N_PARTNER), rw(PAYOUT_TYPE), round(random.uniform(500,150_000),2), rw(PAYOUT_STATUS), rdate(2023,2026))
bulk("incentive_payouts", ["payout_id","partner_id","payout_type","amount","payment_status","payout_date"], gen_payout(), N_PAYOUT)

opp_info = {}  # opportunity_id -> dict(account_id, arr, stage)
def gen_opp():
    for i in range(1, N_OPP+1):
        arr = round(random.triangular(50_000,1_000_000,180_000),2)
        dealreg = random.randint(1,N_DEALREG) if random.random() < 0.6 else None
        acc = random.randint(1,N_ACC)
        stage = rw(OPP_STAGE)
        opp_info[i] = {"account_id": acc, "arr": arr, "stage": stage}
        yield (i, acc, dealreg, random.randint(1,N_EMP),
               f"OPP-{2023+i%3}-{i:06d}", stage, rw(DEAL_TYPE), arr, round(arr*random.uniform(1,3),2), rdate(2024,2027), random.randint(5,95))
bulk("opportunities", ["opportunity_id","account_id","deal_reg_id","employee_id","name","stage","deal_type","arr","tcv","close_date","probability_pct"], gen_opp(), N_OPP)

def gen_motion():
    for i in range(1, N_MOTION+1):
        yield (i, random.randint(1,N_OPP), rw(MOTION_TYPE), rdate(2023,2026), rw(MOTION_STATUS), "Joint account planning session notes and next steps")
bulk("co_sell_motions", ["motion_id","opportunity_id","motion_type","date","status","notes"], gen_motion(), N_MOTION)

def gen_contract():
    for i in range(1, N_CONTRACT+1):
        fp = random.randint(1,N_PARTNER) if random.random() < 0.55 else None
        yield (i, random.randint(1,N_OPP), fp, f"MSA-{100000+i}", rdate(2022,2026), rdate(2026,2029), round(random.uniform(50_000,3_000_000),2), random.randint(0,1))
bulk("contracts", ["contract_id","opportunity_id","fulfilling_partner_id","msa_number","start_date","end_date","total_contract_value","auto_renew"], gen_contract(), N_CONTRACT)

def gen_ent():
    for i in range(1, N_ENT+1):
        alloc = round(random.uniform(10,5000),1)
        yield (i, random.randint(1,N_CONTRACT), alloc, round(alloc*random.uniform(0.2,0.95),1), random.randint(10,2000), random.randint(5,2000), rdate(2025,2028))
bulk("entitlements", ["entitlement_id","contract_id","allocated_capacity_tb","used_capacity_tb","seat_count_purchased","seat_count_active","expiration_date"], gen_ent(), N_ENT)

print("Populating junction (N:M) tables...")

def gen_opp_partners():
    seen = set()
    for _ in range(int(N_OPP*0.4)):
        while True:
            key = (random.randint(1,N_OPP), random.randint(1,N_PARTNER))
            if key not in seen:
                seen.add(key); break
        yield (*key, round(random.uniform(0,1),2), rw(["Sourcing","Influencing","Fulfilling"]))
opp_partner_rows = list(gen_opp_partners())
bulk("opportunity_partners", ["opportunity_id","partner_id","influence_weight","partner_role"], iter(opp_partner_rows), len(opp_partner_rows))

def gen_opp_skus():
    seen = set(); out=[]
    for opp in range(1, N_OPP+1):
        for _ in range(random.choice([1,1,2,2,3])):
            sku = random.randint(1,N_SKU)
            if (opp,sku) in seen: continue
            seen.add((opp,sku))
            out.append((opp, sku, random.randint(1,50), round(random.uniform(500,50000),2)))
    return out
opp_sku_rows = gen_opp_skus()
bulk("opportunity_skus", ["opportunity_id","sku_id","quantity","negotiated_price"], iter(opp_sku_rows), len(opp_sku_rows))

def gen_opp_emps():
    seen = set(); out=[]
    for opp in range(1, N_OPP+1):
        for _ in range(random.choice([1,1,2])):
            emp = random.randint(1,N_EMP)
            if (opp,emp) in seen: continue
            seen.add((opp,emp))
            out.append((opp, emp, rw(["AE","SE","Overlay","CAM"]), rdate(2023,2026)))
    return out
opp_emp_rows = gen_opp_emps()
bulk("opportunity_employees", ["opportunity_id","employee_id","role","assigned_date"], iter(opp_emp_rows), len(opp_emp_rows))

def gen_agent_assists():
    seen = set(); out=[]
    for opp in range(1, N_OPP+1):
        for _ in range(random.choice([1,1,2,3])):
            agent = random.randint(1,N_AGENT)
            ts = rts()
            key=(agent,opp,ts)
            if key in seen: continue
            seen.add(key)
            out.append((agent, opp, ts, rw(ACTION_TYPE)))
    return out
assist_rows = gen_agent_assists()
bulk("agent_opportunity_assists", ["agent_id","opportunity_id","last_action_timestamp","action_type"], iter(assist_rows), len(assist_rows))

print("Populating RevOps stack extension tables...")

def gen_ext_ids():
    i = 1
    for acc in range(1, N_ACC+1):
        for sysname in EXT_SYSTEMS:
            yield (i, acc, sysname, f"{sysname[:3].upper()}-{100000+acc}-{i}", round(random.uniform(0.75,1.0),3), rts(2025,2026))
            i += 1
bulk("account_external_ids", ["id","account_id","system_name","external_record_id","match_confidence_score","last_synced_at"], gen_ext_ids(), N_EXT_IDS)

def gen_sixsense():
    for i in range(1, N_SIXSENSE+1):
        score = random.randint(1,100)
        yield (i, i, score, rw(BUYING_STAGE), round(random.uniform(0,1),2), 1 if score>=80 else 0,
               ",".join(random.sample(["ransomware recovery","cyber resilience","immutable backup","air-gapped vault","zero trust data security","M365 protection"], 3)))
bulk("sixsense_account_intent", ["intent_id","account_id","intent_score","buying_stage","profile_fit_score","is_6qa","top_keywords"], gen_sixsense(), N_SIXSENSE)

gong_info = {}  # gong_id -> dict(account_id, opportunity_id, competitor_tracker_hits)
def gen_gong():
    for i in range(1, N_GONG+1):
        opp = random.randint(1,N_OPP)
        acc = opp_info[opp]["account_id"]
        incumbent = incumbent_for(acc)
        hits = incumbent if incumbent else rw(COMPETITOR_HITS)
        gong_info[i] = {"account_id": acc, "opportunity_id": opp, "hits": hits}
        yield (i, acc, opp, round(random.uniform(-1,1),2), hits, round(random.uniform(0.1,1.0),2), random.randint(10,90))
bulk("gong_account_insights", ["gong_id","account_id","opportunity_id","buyer_sentiment_score","competitor_tracker_hits","multithread_contact_ratio","total_call_duration_mins"], gen_gong(), N_GONG)

def gen_clari():
    for i in range(1, N_CLARI+1):
        rep_amt = round(random.triangular(50_000,1_000_000,180_000),2)
        yield (i, i, random.randint(1,100), rw(FORECAST_CATEGORY), rep_amt, round(rep_amt*random.uniform(0.7,1.3),2), random.randint(0,4))
bulk("clari_opportunity_forecasts", ["forecast_id","opportunity_id","clari_health_score","forecast_category","rep_forecast_amount","ai_forecast_amount","deal_slip_count"], gen_clari(), N_CLARI)

activity_info = {}  # activity_id -> (contact_id, employee_id, activity_type, response_status)
def gen_outreach():
    for i in range(1, N_OUTREACH+1):
        c = random.randint(1,N_CONTACT); e = random.randint(1,N_EMP)
        atype = rw(ACTIVITY_TYPE); resp = rw(RESPONSE_STATUS)
        activity_info[i] = (c, e, atype, resp)
        yield (i, c, e, rw(SEQUENCE_NAME), random.randint(1,12), atype, resp)
bulk("outreach_sequence_activities", ["activity_id","contact_id","employee_id","sequence_name","step_number","activity_type","response_status"], gen_outreach(), N_OUTREACH)

def gen_highspot():
    for i in range(1, N_HIGHSPOT+1):
        opp = random.randint(1,N_OPP)
        yield (i, opp, random.randint(1,N_CONTACT), rw(CONTENT_NAME), random.randint(15,900), round(random.uniform(0.1,1.0),2), random.randint(1,40))
bulk("highspot_collateral_engagement", ["engagement_id","opportunity_id","contact_id","content_name","view_duration_seconds","completion_pct","pages_viewed"], gen_highspot(), N_HIGHSPOT)

conn.commit()
print(f"\nStructured tables loaded in {time.time()-t0:.1f}s.")

# ================= UNSTRUCTURED RAW PAYLOAD GENERATION (new in V5) =================
print("\nGenerating unstructured payload tables (Gong transcripts, Outreach emails, Highspot slide logs, 6sense search queries, Marketo form JSON, Clari audit history)...")

PAIN_TOPICS = ["ransomware recovery time", "immutable backup coverage", "M365 protection gaps",
               "air-gapped vault requirements", "cyber posture audit findings", "cloud-native workload backup"]
REP_OPENERS = ["Thanks for hopping on -- I know you've got a lot on your plate this quarter.",
               "Appreciate the time today. Wanted to pick up where we left off on your {topic} concerns.",
               "Good to see you again. Last time we talked about {topic} -- has anything changed on your end?"]
REP_PITCHES = ["Our platform gives you instant recovery with an immutable, air-gapped copy, so a ransomware event doesn't touch your backups.",
               "With Rubrik you get a single control plane across on-prem and cloud, which cuts your recovery time from days to minutes.",
               "The Cyber Recovery module specifically targets the blast-radius problem you mentioned with {incumbent}."]
PROSPECT_OBJECTIONS = ["Honestly, switching off {incumbent} feels risky given how embedded it is in our runbooks.",
                       "Our current {incumbent} contract still has 14 months left, so budget timing is tight.",
                       "The team's biggest worry is data migration effort off {incumbent} -- how disruptive is that really?",
                       "Pricing on your side looked higher than what we're paying {incumbent} today for similar capacity."]
REP_REBUTTALS = ["That's fair -- most of our new logos run us in parallel with {incumbent} for 60-90 days before cutting over, so there's no cliff-edge risk.",
                 "We can structure the deal to align with your {incumbent} renewal date so you're not paying twice.",
                 "Our SEs typically handle migration tooling directly, so your team isn't hand-rolling scripts."]
PROSPECT_CLOSERS = ["Okay, that helps. Let's get a technical deep-dive scheduled with our infrastructure team.",
                    "I'll need to loop in our CISO before we go further, but this is promising.",
                    "Send over the ROI numbers and I'll take it to the budget committee next week.",
                    "We're still early, but keep me posted on the roadmap for {topic}."]
KEY_TAKEAWAY_TMPL = ["Buyer is timing the deal around their {incumbent} renewal; recommend proposing bridge pricing.",
                     "Strong technical fit on {topic}; blocker is internal migration bandwidth, not budget.",
                     "Economic buyer not yet in the room -- champion is gathering ammo for an internal pitch.",
                     "Competitive deal against {incumbent}; price objection surfaced but not disqualifying."]

def make_transcript(incumbent, topic):
    incumbent_disp = incumbent or "their legacy backup vendor"
    lines = []
    t = 0
    def add(speaker, text):
        nonlocal t
        text = text.format(incumbent=incumbent_disp, topic=topic)
        lines.append({"speaker": speaker, "start_sec": t, "end_sec": t+random.randint(15,45), "text": text})
        t = lines[-1]["end_sec"] + random.randint(2,8)
    add("Rep", rw(REP_OPENERS))
    add("Prospect", f"Yeah, {topic} is still top of mind for our security team.")
    add("Rep", rw(REP_PITCHES))
    add("Prospect", rw(PROSPECT_OBJECTIONS))
    add("Rep", rw(REP_REBUTTALS))
    add("Prospect", "That's a reasonable point. What does the actual cutover process look like?")
    add("Rep", "We run a parallel-write phase first, validate recovery points, then decommission the old target.")
    add("Prospect", rw(PROSPECT_CLOSERS))
    add("Rep", "Sounds good -- I'll get that follow-up over to you by end of week.")
    transcript_text = "\n".join(f"[{l['start_sec']:>4}s] {l['speaker']}: {l['text']}" for l in lines)
    objection = f"{incumbent_disp} pricing/migration" if incumbent else "General budget timing"
    takeaway = rw(KEY_TAKEAWAY_TMPL).format(incumbent=incumbent_disp, topic=topic)
    return transcript_text, lines, objection, takeaway

def gen_gong_transcripts():
    for i in range(1, N_GONG_TRANSCRIPTS+1):
        g = gong_info[i]
        incumbent = incumbent_for(g["account_id"])
        topic = rw(PAIN_TOPICS)
        text, diarization, objection, takeaway = make_transcript(incumbent, topic)
        yield (i, i, f"Rubrik / {rw(['Discovery','Technical Deep Dive','Negotiation','Champion Check-in'])} Call - Opp {g['opportunity_id']}",
               rdate(2024,2026), text, json.dumps(diarization), objection, takeaway)
bulk("gong_call_transcripts", ["transcript_id","gong_id","call_title","call_date","full_transcript_text","speaker_diarization_json","top_objection_raised","key_takeaways"], gen_gong_transcripts(), N_GONG_TRANSCRIPTS)

EMAIL_SUBJECTS = ["Following up on our {topic} conversation", "Quick question on your {incumbent} renewal timeline",
                  "Resources on Cyber Recovery for {topic}", "Re: Proposal next steps", "Checking in before your budget cycle closes"]
EMAIL_BODIES = ["Hi {first}, great connecting today. As discussed, immutable snapshots would close the gap you flagged around {topic}. Attaching the battlecard vs {incumbent} for your team to review. Open to a technical session next week?",
                "Hi {first}, wanted to follow up on the recovery-time numbers you asked about. Our median RTO for enterprise customers displacing {incumbent} is under 4 hours. Happy to bring an SE on the next call.",
                "Hi {first}, checking in ahead of your budget cycle -- do you have what you need from us to move this forward internally?"]
REPLY_POSITIVE = ["Thanks, this is helpful -- let's get the SE session on the calendar for next week.", "Appreciate the detail. Forwarding this to our CISO now."]
REPLY_NEUTRAL = ["Got it, will review internally and circle back.", "Thanks for the info -- still gathering input from the team."]
REPLY_NEGATIVE = ["We've decided to hold off for now given the {incumbent} contract we're locked into.", "Pricing is a non-starter for this cycle, sorry."]

def gen_emails():
    for i in range(1, N_EMAIL_MSGS+1):
        act_id = i if i in activity_info else random.randint(1, N_OUTREACH)
        contact_id, employee_id, atype, resp = activity_info[act_id]
        incumbent = None  # contacts aren't directly tied to a single account's tech row here; keep generic if unknown
        topic = rw(PAIN_TOPICS)
        subj = rw(EMAIL_SUBJECTS).format(topic=topic, incumbent=rw(INCUMBENT_VENDORS))
        body = rw(EMAIL_BODIES).format(first=rw(FIRST), topic=topic, incumbent=rw(INCUMBENT_VENDORS))
        if resp in ("Replied","Meeting Booked"):
            reply = rw(REPLY_POSITIVE); sentiment = "Positive"
        elif resp in ("Opened",):
            reply = rw(REPLY_NEUTRAL); sentiment = "Neutral"
        elif resp == "Bounced":
            reply = None; sentiment = "Neutral"
        else:  # No Response
            reply = rw(REPLY_NEGATIVE).format(incumbent=rw(INCUMBENT_VENDORS)) if random.random()<0.3 else None
            sentiment = "Negative" if reply else "Neutral"
        yield (i, act_id, contact_id, employee_id, f"THREAD-{100000+act_id}", subj, body, reply, sentiment)
bulk("outreach_email_messages", ["message_id","activity_id","contact_id","employee_id","thread_id","subject_line","body_plain_text","reply_body_text","sentiment_tag"], gen_emails(), N_EMAIL_MSGS)

SLIDE_TITLES = ["Cover: Cyber Resilience for {industry}", "The Ransomware Blast Radius Problem", "Rubrik Security Cloud Architecture",
                "Immutable Backup vs {incumbent} Snapshots", "Instant Recovery Demo", "Customer Reference: {industry} Peer",
                "ROI & TCO Summary", "Next Steps & Timeline"]
BUYER_COMMENTS = [None, None, None, "Can we get the TCO slide sent separately?", "This matches what our SOC team flagged.",
                  "How does this compare against our current {incumbent} setup?", "Sharing internally with the security team."]

def gen_slide_views():
    for i in range(1, N_SLIDE_VIEWS+1):
        eng = random.randint(1,N_HIGHSPOT)
        industry = rw(INDUSTRY)
        incumbent = rw(INCUMBENT_VENDORS)
        title = rw(SLIDE_TITLES).format(industry=industry, incumbent=incumbent)
        comment = rw(BUYER_COMMENTS)
        if comment:
            comment = comment.format(incumbent=incumbent)
        yield (i, eng, random.randint(1,12), title, random.randint(5,180), comment, rw(["Internal Share","Email Link","Direct View"]))
bulk("highspot_slide_views", ["slide_view_id","engagement_id","slide_number","slide_title","dwell_time_seconds","buyer_comments","share_method"], gen_slide_views(), N_SLIDE_VIEWS)

SEARCH_TEMPLATES = ["Rubrik vs {incumbent} ransomware recovery", "{incumbent} alternative for M365 backup",
                    "cyber resilience platform comparison {incumbent}", "immutable backup vendor evaluation",
                    "air-gapped vault pricing", "zero trust data security {industry}"]
LANDING_PAGES = ["/solutions/cyber-recovery","/compare/rubrik-vs-cohesity","/compare/rubrik-vs-commvault",
                  "/products/cloud-vault","/resources/ransomware-readiness-report","/demo-request"]

def gen_search_queries():
    for i in range(1, N_SEARCH_QUERIES+1):
        intent_id = random.randint(1,N_SIXSENSE)
        acc = intent_id  # sixsense_account_intent.intent_id was generated 1:1 with account_id
        incumbent = incumbent_for(acc) or rw(INCUMBENT_VENDORS)
        term = rw(SEARCH_TEMPLATES).format(incumbent=incumbent, industry=rw(INDUSTRY))
        yield (i, intent_id, acc, term, rts(2024,2026), f"rubrik.com{rw(LANDING_PAGES)}")
bulk("sixsense_search_queries", ["query_id","intent_id","account_id","search_term","search_timestamp","landing_page_url"], gen_search_queries(), N_SEARCH_QUERIES)

FORM_NAMES = ["Ransomware Readiness Assessment","Demo Request Form","Whitepaper Gate: Cyber Recovery ROI","Webinar Registration","Contact Sales"]
UTM_SOURCE = ["google","linkedin","direct","partner-referral","email-nurture"]
UTM_CAMPAIGN = ["fy26-cyber-resilience","fy26-abm-enterprise","fy26-partner-cosell","fy26-webinar-series"]

def gen_form_fills():
    for i in range(1, N_FORM_FILLS+1):
        tp = random.randint(1,N_TOUCH)
        contact_id = touch_contact.get(tp, random.randint(1,N_CONTACT))
        fields = {
            "first_name": rw(FIRST), "last_name": rw(LAST), "email_domain": rw(["gmail.com","corp-internal.com","outlook.com"]),
            "job_title": rw(JOB_TITLE), "company_size": rw(["1-500","501-2000","2001-10000","10000+"]),
            "consent_marketing": random.choice([True, False])
        }
        yield (i, tp, contact_id, rw(FORM_NAMES), json.dumps(fields), rw(UTM_SOURCE), rw(UTM_CAMPAIGN), f"https://rubrik.com{rw(LANDING_PAGES)}?ref=form")
bulk("marketo_raw_form_fills", ["fill_id","touchpoint_id","contact_id","form_name","raw_fields_json","utm_source","utm_campaign","referrer_url"], gen_form_fills(), N_FORM_FILLS)

REP_NOTES = ["Champion confirmed budget is approved for this fiscal year; pushing for signature before quarter close.",
             "Security review board requested additional pen-test documentation before advancing.",
             "Deal slipped one cycle -- procurement backlog on their end, not a competitive loss.",
             "Economic buyer newly engaged after exec briefing; re-scoring health upward.",
             "Buyer flagged internal reorg; timeline uncertain, keeping in pipeline but downgrading confidence."]

def gen_clari_history():
    for i in range(1, N_CLARI_HISTORY+1):
        forecast_id = random.randint(1,N_CLARI)
        opp_id = forecast_id  # clari_opportunity_forecasts was generated 1:1 with opportunity_id
        cur_stage = opp_info[opp_id]["stage"]
        cur_arr = opp_info[opp_id]["arr"]
        if cur_stage in OPP_STAGE_SEQ:
            idx = OPP_STAGE_SEQ.index(cur_stage)
            old_stage = OPP_STAGE_SEQ[max(0, idx-1)] if idx > 0 else "Discovery"
            new_stage = cur_stage
        else:  # Closed Lost
            old_stage, new_stage = rw(OPP_STAGE_SEQ[:3]), "Closed Lost"
        old_arr = round(cur_arr * random.uniform(0.7,1.0), 2)
        yield (i, forecast_id, opp_id, rts(2024,2026), old_stage, new_stage, old_arr, cur_arr, rw(REP_NOTES))
bulk("clari_forecast_history_logs", ["history_id","forecast_id","opportunity_id","change_timestamp","old_stage","new_stage","old_arr","new_arr","rep_notes_text"], gen_clari_history(), N_CLARI_HISTORY)

conn.commit()
t_data = time.time()
size_no_index = os.path.getsize(DB_PATH)
print(f"\nAll data loaded in {t_data-t0:.1f}s. File size (before FTS5 populate / indexes): {size_no_index/1e6:.2f} MB")

print("\nPopulating FTS5 full-text indexes (rebuild from content tables)...")
cur.execute("INSERT INTO gong_transcripts_fts(gong_transcripts_fts) VALUES('rebuild')")
cur.execute("INSERT INTO outreach_emails_fts(outreach_emails_fts) VALUES('rebuild')")
conn.commit()
size_after_fts = os.path.getsize(DB_PATH)
print(f"File size (after FTS5 rebuild): {size_after_fts/1e6:.2f} MB")

print("\nCreating indexes on all FK columns...")
cur.executescript("""
CREATE INDEX ix_acc_parent ON accounts(parent_account_id);
CREATE INDEX ix_bc_acc ON buying_centers(account_id);
CREATE INDEX ix_tech_acc ON technographics(account_id);
CREATE INDEX ix_contact_acc ON contacts(account_id);
CREATE INDEX ix_contact_bc ON contacts(buying_center_id);
CREATE INDEX ix_contact_persona ON contacts(persona_id);
CREATE INDEX ix_touch_contact ON touchpoints(contact_id);
CREATE INDEX ix_touch_campaign ON touchpoints(campaign_id);
CREATE INDEX ix_partner_program ON partners(program_id);
CREATE INDEX ix_cert_partner ON partner_certifications(partner_id);
CREATE INDEX ix_dealreg_partner ON deal_registrations(partner_id);
CREATE INDEX ix_dealreg_acc ON deal_registrations(account_id);
CREATE INDEX ix_payout_partner ON incentive_payouts(partner_id);
CREATE INDEX ix_opp_acc ON opportunities(account_id);
CREATE INDEX ix_opp_dealreg ON opportunities(deal_reg_id);
CREATE INDEX ix_opp_emp ON opportunities(employee_id);
CREATE INDEX ix_motion_opp ON co_sell_motions(opportunity_id);
CREATE INDEX ix_contract_opp ON contracts(opportunity_id);
CREATE INDEX ix_contract_partner ON contracts(fulfilling_partner_id);
CREATE INDEX ix_ent_contract ON entitlements(contract_id);
CREATE INDEX ix_op_partner ON opportunity_partners(partner_id);
CREATE INDEX ix_os_sku ON opportunity_skus(sku_id);
CREATE INDEX ix_oe_emp ON opportunity_employees(employee_id);
CREATE INDEX ix_aoa_agent ON agent_opportunity_assists(agent_id);
CREATE INDEX ix_contact_email ON contacts(email);
CREATE INDEX ix_account_domain ON accounts(domain);
CREATE INDEX ix_extids_acc ON account_external_ids(account_id);
CREATE INDEX ix_extids_system ON account_external_ids(system_name);
CREATE INDEX ix_sixsense_acc ON sixsense_account_intent(account_id);
CREATE INDEX ix_gong_acc ON gong_account_insights(account_id);
CREATE INDEX ix_gong_opp ON gong_account_insights(opportunity_id);
CREATE INDEX ix_clari_opp ON clari_opportunity_forecasts(opportunity_id);
CREATE INDEX ix_outreach_contact ON outreach_sequence_activities(contact_id);
CREATE INDEX ix_outreach_emp ON outreach_sequence_activities(employee_id);
CREATE INDEX ix_highspot_opp ON highspot_collateral_engagement(opportunity_id);
CREATE INDEX ix_highspot_contact ON highspot_collateral_engagement(contact_id);

-- V5 unstructured payload table indexes
CREATE INDEX ix_transcripts_gong ON gong_call_transcripts(gong_id);
CREATE INDEX ix_emails_activity ON outreach_email_messages(activity_id);
CREATE INDEX ix_emails_contact ON outreach_email_messages(contact_id);
CREATE INDEX ix_emails_employee ON outreach_email_messages(employee_id);
CREATE INDEX ix_slideviews_engagement ON highspot_slide_views(engagement_id);
CREATE INDEX ix_searchq_intent ON sixsense_search_queries(intent_id);
CREATE INDEX ix_searchq_acc ON sixsense_search_queries(account_id);
CREATE INDEX ix_formfills_touchpoint ON marketo_raw_form_fills(touchpoint_id);
CREATE INDEX ix_formfills_contact ON marketo_raw_form_fills(contact_id);
CREATE INDEX ix_clarihist_forecast ON clari_forecast_history_logs(forecast_id);
CREATE INDEX ix_clarihist_opp ON clari_forecast_history_logs(opportunity_id);
""")
conn.commit()
size_with_index = os.path.getsize(DB_PATH)
print(f"File size (with indexes): {size_with_index/1e6:.2f} MB")

print("\nRunning VACUUM...")
conn.execute("VACUUM")
size_vacuumed = os.path.getsize(DB_PATH)
print(f"File size (after VACUUM): {size_vacuumed/1e6:.2f} MB")

tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
total_rows = 0
print("\nRow counts (base tables only, excludes FTS5 shadow tables):")
for t in tables:
    if t.endswith("_fts") or "_fts_" in t or t.startswith("sqlite_"):
        continue
    c = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    total_rows += c
    print(f"  {t}: {c:,}")
print(f"\nTOTAL ROWS: {total_rows:,}")
print(f"Total elapsed: {time.time()-t0:.1f}s")
conn.close()
print("\nDone:", os.path.abspath(DB_PATH))
