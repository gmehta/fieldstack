import sqlite3, json, re, collections
import os, sys
DB = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data-model", "rubrik_gtm_synthetic_v5.db")
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
con.row_factory = sqlite3.Row
def q(sql, *a): return [dict(r) for r in con.execute(sql, a).fetchall()]
def one(sql, *a): r = q(sql, *a); return r[0] if r else {}

TODAY = "2026-09-15"
Q_START, Q_END = "2026-08-01", "2026-10-31"      # Rubrik FY27 Q3 (FY ends Jan 31)
NQ_START, NQ_END = "2026-11-01", "2027-01-31"    # FY27 Q4
FY_START = "2026-02-01"
D60 = "2026-07-17"; D30 = "2026-08-16"; D90 = "2026-06-17"; D180 = "2027-03-15"
OPEN = "o.stage NOT LIKE 'Closed%'"

def lob(name): return re.sub(r"\s+v\d+$", "", name)

# ---------- shared opp enrichment ----------
open_opps = q(f"""
SELECT o.opportunity_id id, o.name, o.stage, o.deal_type, o.arr, o.tcv, o.close_date, o.employee_id owner_id,
       a.account_id, a.name account, a.tier, a.industry, a.status acct_status, a.country,
       e.full_name owner, e.role owner_role, e.territory,
       f.forecast_category fc, f.clari_health_score health, f.rep_forecast_amount rep_fcst, f.ai_forecast_amount ai_fcst, f.deal_slip_count slips,
       (SELECT MAX(change_timestamp) FROM clari_forecast_history_logs l WHERE l.opportunity_id=o.opportunity_id) last_log,
       (SELECT rep_notes_text FROM clari_forecast_history_logs l WHERE l.opportunity_id=o.opportunity_id ORDER BY change_timestamp DESC LIMIT 1) last_note,
       (SELECT ROUND(AVG(buyer_sentiment_score),2) FROM gong_account_insights g WHERE g.opportunity_id=o.opportunity_id) sentiment,
       (SELECT ROUND(AVG(multithread_contact_ratio),2) FROM gong_account_insights g WHERE g.opportunity_id=o.opportunity_id) multithread,
       (SELECT COUNT(*) FROM gong_account_insights g WHERE g.opportunity_id=o.opportunity_id) calls,
       (SELECT MAX(t.call_date) FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id) WHERE g.opportunity_id=o.opportunity_id) last_call,
       (SELECT t.top_objection_raised FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id) WHERE g.opportunity_id=o.opportunity_id ORDER BY t.call_date DESC LIMIT 1) objection,
       (SELECT p.name || ' (' || p.type || ')' FROM deal_registrations d JOIN partners p USING(partner_id) WHERE d.deal_reg_id=o.deal_reg_id) partner,
       (SELECT d.status FROM deal_registrations d WHERE d.deal_reg_id=o.deal_reg_id) reg_status,
       (SELECT p.type FROM deal_registrations d JOIN partners p USING(partner_id) WHERE d.deal_reg_id=o.deal_reg_id) partner_type,
       (SELECT vendor_name FROM technographics t WHERE t.account_id=a.account_id AND t.category='Legacy Backup' AND t.vendor_name IN ('Cohesity','Veeam','Commvault','NetApp') ORDER BY renewal_date LIMIT 1) incumbent,
       (SELECT MIN(renewal_date) FROM technographics t WHERE t.account_id=a.account_id AND t.category='Legacy Backup' AND t.renewal_date>=? ) incumbent_renewal,
       (SELECT s.intent_score FROM sixsense_account_intent s WHERE s.account_id=a.account_id) intent,
       (SELECT s.is_6qa FROM sixsense_account_intent s WHERE s.account_id=a.account_id) is6qa
FROM opportunities o JOIN accounts a USING(account_id) JOIN employees e USING(employee_id)
LEFT JOIN clari_opportunity_forecasts f USING(opportunity_id)
WHERE {OPEN}""", TODAY)

# LOB share per opp from SKU lines (proportional to net line value)
sku_rows = q("SELECT os.opportunity_id id, s.name, os.quantity*os.negotiated_price net FROM opportunity_skus os JOIN skus s USING(sku_id)")
lob_share = collections.defaultdict(lambda: collections.defaultdict(float))
for r in sku_rows: lob_share[r["id"]][lob(r["name"])] += max(r["net"], 0)
def opp_lob(oid):
    d = lob_share.get(oid)
    if not d: return "Unassigned"
    return max(d.items(), key=lambda kv: kv[1])[0]
for o in open_opps:
    o["lob"] = opp_lob(o["id"])
    flags = []
    if o["close_date"] < TODAY: flags.append("STALE-DATE")
    if (o["last_log"] or "2000") < D60: flags.append("SILENT-60D")
    if o["fc"] == "Commit" and (o["health"] or 0) < 40: flags.append("COMMIT-AT-RISK")
    if (o["slips"] or 0) >= 3: flags.append("SLIPPED-3X")
    if o["multithread"] is not None and o["multithread"] < 0.3: flags.append("SINGLE-THREADED")
    if o["acct_status"] == "Churned": flags.append("CHURNED-ACCOUNT")
    o["flags"] = flags
    o["channel"] = "Direct" if not o["partner_type"] else o["partner_type"]
    o["in_q"] = Q_START <= o["close_date"] <= Q_END
    o["in_nq"] = NQ_START <= o["close_date"] <= NQ_END

def agg(rows, key):
    d = collections.OrderedDict()
    for r in rows:
        k = r[key] if isinstance(key, str) else key(r)
        d.setdefault(k, {"n": 0, "arr": 0.0})
        d[k]["n"] += 1; d[k]["arr"] += r["arr"]
    return [{"k": k, "n": v["n"], "arr": round(v["arr"])} for k, v in d.items()]

# ---------- VP ----------
won_q = one("SELECT COUNT(*) n, COALESCE(SUM(arr),0) arr FROM opportunities WHERE stage='Closed Won' AND close_date BETWEEN ? AND ?", Q_START, Q_END)
lost_q = one("SELECT COUNT(*) n, COALESCE(SUM(arr),0) arr FROM opportunities WHERE stage='Closed Lost' AND close_date BETWEEN ? AND ?", Q_START, Q_END)
won_fy = one("SELECT COUNT(*) n, COALESCE(SUM(arr),0) arr FROM opportunities WHERE stage='Closed Won' AND close_date BETWEEN ? AND ?", FY_START, TODAY)
quota_total = one("SELECT SUM(quota) q, COUNT(*) n FROM employees WHERE role='Account Executive'")
inq = [o for o in open_opps if o["in_q"]]
def sum_fc(rows, cat): return round(sum(o["arr"] for o in rows if o["fc"] == cat))
q_quota = quota_total["q"] / 4
kpis = {
  "quarter": "FY27 Q3", "window": f"{Q_START} → {Q_END}", "as_of": TODAY,
  "quota_q": round(q_quota), "won_q": round(won_q["arr"]), "won_q_n": won_q["n"], "lost_q": round(lost_q["arr"]), "lost_q_n": lost_q["n"],
  "commit": sum_fc(inq, "Commit"), "best_case": sum_fc(inq, "Best Case"), "pipeline": sum_fc(inq, "Pipeline"), "omitted": sum_fc(inq, "Omitted"),
  "ai_forecast": round(sum((o["ai_fcst"] or 0) for o in inq if o["fc"] in ("Commit", "Best Case"))),
  "rep_forecast": round(sum((o["rep_fcst"] or 0) for o in inq if o["fc"] in ("Commit", "Best Case"))),
  "open_q_arr": round(sum(o["arr"] for o in inq)), "open_q_n": len(inq),
  "open_total_arr": round(sum(o["arr"] for o in open_opps)), "open_total_n": len(open_opps),
  "next_q_arr": round(sum(o["arr"] for o in open_opps if o["in_nq"])), "next_q_n": sum(1 for o in open_opps if o["in_nq"]),
  "won_fytd": round(won_fy["arr"]), "quota_fytd": round(quota_total["q"] * 7.5 / 12),
  "ae_count": quota_total["n"],
}
kpis["gap_to_quota"] = round(q_quota - won_q["arr"] - kpis["commit"])
kpis["coverage"] = round(kpis["open_q_arr"] / q_quota, 2); kpis["attain_q"] = round(won_q["arr"] / q_quota, 2); kpis["attain_fytd"] = round(won_fy["arr"] / kpis["quota_fytd"], 2)

# forecast by territory (in-quarter)
terr = collections.OrderedDict()
for t in ["AMER", "EMEA", "APJ", "LATAM"]:
    rows = [o for o in inq if o["territory"] == t]
    qq = one("SELECT SUM(quota)/4 q FROM employees WHERE role='Account Executive' AND territory=?", t)["q"] or 0
    w = one("SELECT COALESCE(SUM(o.arr),0) arr FROM opportunities o JOIN employees e USING(employee_id) WHERE o.stage='Closed Won' AND o.close_date BETWEEN ? AND ? AND e.territory=?", Q_START, Q_END, t)["arr"]
    terr[t] = {"territory": t, "quota": round(qq), "won": round(w), "commit": sum_fc(rows, "Commit"), "best_case": sum_fc(rows, "Best Case"),
               "pipeline": sum_fc(rows, "Pipeline"), "ai": round(sum((o["ai_fcst"] or 0) for o in rows if o["fc"] in ("Commit", "Best Case"))),
               "open_n": len(rows), "at_risk_n": sum(1 for o in rows if "COMMIT-AT-RISK" in o["flags"])}
    terr[t]["gap"] = round(qq - w - terr[t]["commit"])

vp = {"kpis": kpis, "by_territory": list(terr.values()),
  "funnel": [next((x for x in agg(open_opps, "stage") if x["k"] == s), {"k": s, "n": 0, "arr": 0}) for s in ["Discovery", "Validation", "Proposal"]],
  "by_segment": agg(open_opps, "tier"), "by_deal_type": agg(open_opps, "deal_type"),
  "by_lob": sorted(agg(open_opps, "lob"), key=lambda x: -x["arr"]),
  "by_channel": sorted(agg(open_opps, "channel"), key=lambda x: -x["arr"]),
  "by_industry": sorted(agg(open_opps, "industry"), key=lambda x: -x["arr"])[:8],
  "health": {
    "stale": sum(1 for o in open_opps if "STALE-DATE" in o["flags"]), "stale_arr": round(sum(o["arr"] for o in open_opps if "STALE-DATE" in o["flags"])),
    "silent": sum(1 for o in open_opps if "SILENT-60D" in o["flags"]),
    "commit_at_risk": sum(1 for o in open_opps if "COMMIT-AT-RISK" in o["flags"]), "commit_at_risk_arr": round(sum(o["arr"] for o in open_opps if "COMMIT-AT-RISK" in o["flags"])),
    "slipped": sum(1 for o in open_opps if "SLIPPED-3X" in o["flags"]),
    "single_threaded": sum(1 for o in open_opps if "SINGLE-THREADED" in o["flags"]),
    "churned_acct": sum(1 for o in open_opps if "CHURNED-ACCOUNT" in o["flags"]),
    "rep_vs_arr_gap": round(one("SELECT AVG(ABS(f.rep_forecast_amount-o.arr)/o.arr) g FROM clari_opportunity_forecasts f JOIN opportunities o USING(opportunity_id) WHERE o.stage NOT LIKE 'Closed%'")["g"], 2),
  },
}
# win rate by fiscal quarter (last 8)
def fq(d):
    y, m = int(d[:4]), int(d[5:7]); fy = y + 1 if m >= 2 else y
    qn = ((m - 2) % 12) // 3 + 1
    return f"FY{str(fy)[2:]} Q{qn}"
closed = q("SELECT stage, arr, close_date, deal_type FROM opportunities WHERE stage LIKE 'Closed%' AND close_date BETWEEN '2024-08-01' AND ?", Q_END)
wq = collections.OrderedDict()
for r in closed:
    k = fq(r["close_date"]); wq.setdefault(k, {"won": 0, "lost": 0, "won_arr": 0.0})
    if r["stage"] == "Closed Won": wq[k]["won"] += 1; wq[k]["won_arr"] += r["arr"]
    else: wq[k]["lost"] += 1
vp["win_rate_trend"] = [{"q": k, "won": v["won"], "lost": v["lost"], "rate": round(v["won"] / max(v["won"] + v["lost"], 1), 3), "won_arr": round(v["won_arr"])} for k, v in wq.items()]
vp["win_rate_cuts"] = {
  "deal_type": q("SELECT deal_type k, ROUND(1.0*SUM(stage='Closed Won')/SUM(stage LIKE 'Closed%'),3) rate, SUM(stage LIKE 'Closed%') n FROM opportunities GROUP BY 1"),
  "tier": q("SELECT a.tier k, ROUND(1.0*SUM(o.stage='Closed Won')/SUM(o.stage LIKE 'Closed%'),3) rate, SUM(o.stage LIKE 'Closed%') n FROM opportunities o JOIN accounts a USING(account_id) GROUP BY 1"),
  "channel": q("SELECT COALESCE(p.type,'Direct') k, ROUND(1.0*SUM(o.stage='Closed Won')/SUM(o.stage LIKE 'Closed%'),3) rate, SUM(o.stage LIKE 'Closed%') n FROM opportunities o LEFT JOIN deal_registrations d ON d.deal_reg_id=o.deal_reg_id LEFT JOIN partners p ON p.partner_id=d.partner_id GROUP BY 1 ORDER BY n DESC"),
  "territory": q("SELECT e.territory k, ROUND(1.0*SUM(o.stage='Closed Won')/SUM(o.stage LIKE 'Closed%'),3) rate, SUM(o.stage LIKE 'Closed%') n FROM opportunities o JOIN employees e USING(employee_id) GROUP BY 1"),
}
vp["cycle_days"] = q("SELECT o.stage k, ROUND(AVG(julianday(o.close_date)-julianday(substr(l.first_ts,1,10)))) days, COUNT(*) n FROM opportunities o JOIN (SELECT opportunity_id, MIN(change_timestamp) first_ts FROM clari_forecast_history_logs GROUP BY 1) l USING(opportunity_id) WHERE o.stage LIKE 'Closed%' GROUP BY 1")

def slim(o):
    return {k: o[k] for k in ["id", "name", "account", "tier", "stage", "deal_type", "arr", "close_date", "owner", "owner_role", "territory", "fc", "health", "slips", "flags", "channel", "partner", "lob", "sentiment", "multithread", "objection", "incumbent", "last_log", "last_note", "calls"]}
vp["at_risk"] = [slim(o) for o in sorted([o for o in open_opps if o["fc"] == "Commit" and (o["health"] or 0) < 40], key=lambda o: -o["arr"])[:15]]
vp["top_deals_q"] = [slim(o) for o in sorted(inq, key=lambda o: -o["arr"])[:12]]

# leaderboard (AEs)
aes = q("SELECT employee_id, full_name, territory, quota FROM employees WHERE role='Account Executive'")
lb = []
for a in aes:
    mine = [o for o in open_opps if o["owner_id"] == a["employee_id"]]
    won = one("SELECT COALESCE(SUM(arr),0) arr, COUNT(*) n FROM opportunities WHERE employee_id=? AND stage='Closed Won' AND close_date BETWEEN ? AND ?", a["employee_id"], FY_START, TODAY)
    wq_ = one("SELECT COALESCE(SUM(arr),0) arr FROM opportunities WHERE employee_id=? AND stage='Closed Won' AND close_date BETWEEN ? AND ?", a["employee_id"], Q_START, Q_END)["arr"]
    calls = one("SELECT COUNT(*) n FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id) JOIN opportunities o ON o.opportunity_id=g.opportunity_id WHERE o.employee_id=? AND t.call_date>=?", a["employee_id"], D30)["n"]
    steps = one("SELECT COUNT(*) n, SUM(response_status IN ('Replied','Meeting Booked')) r FROM outreach_sequence_activities WHERE employee_id=?", a["employee_id"])
    lb.append({"id": a["employee_id"], "name": a["full_name"], "territory": a["territory"], "quota": round(a["quota"]),
               "won_fytd": round(won["arr"]), "won_q": round(wq_), "attain_fytd": round(won["arr"] / (a["quota"] * 7.5 / 12), 2),
               "open_arr": round(sum(o["arr"] for o in mine)), "open_n": len(mine), "commit_q": round(sum(o["arr"] for o in mine if o["in_q"] and o["fc"] == "Commit")),
               "coverage": round(sum(o["arr"] for o in mine) / max(a["quota"] / 4, 1), 1), "flags": sum(len(o["flags"]) for o in mine),
               "calls_30d": calls, "reply_rate": round((steps["r"] or 0) / max(steps["n"] or 1, 1), 2)})
vp["leaderboard"] = sorted(lb, key=lambda r: -r["attain_fytd"])

# partner channel
vp["partner"] = {
  "reg_pending": one("SELECT COUNT(*) n FROM deal_registrations WHERE status='Submitted'")["n"],
  "reg_expiring_30d": one("SELECT COUNT(*) n FROM deal_registrations WHERE status IN ('Submitted','Approved') AND protection_expiration_date BETWEEN ? AND date(?,'+30 day')", TODAY, TODAY)["n"],
  "approved_lapsed": one("SELECT COUNT(*) n FROM deal_registrations WHERE status='Approved' AND protection_expiration_date < ?", TODAY)["n"],
  "conflicts": one("SELECT COUNT(*) n FROM (SELECT account_id FROM deal_registrations WHERE status IN ('Submitted','Approved') GROUP BY 1 HAVING COUNT(DISTINCT partner_id)>1)")["n"],
  "payouts_pending": one("SELECT COUNT(*) n, ROUND(COALESCE(SUM(amount),0)) amt FROM incentive_payouts WHERE payment_status<>'Paid' AND payout_date < date(?,'-30 day')", TODAY),
  "by_type": [x for x in vp["by_channel"] if x["k"] != "Direct"],
  "top_partners": q(f"SELECT p.name, p.type, p.tier, COUNT(*) n, ROUND(SUM(o.arr)) arr FROM opportunities o JOIN deal_registrations d ON d.deal_reg_id=o.deal_reg_id JOIN partners p ON p.partner_id=d.partner_id WHERE {OPEN} GROUP BY 1,2,3 ORDER BY arr DESC LIMIT 10"),
  "cosell_open": q("SELECT motion_type k, COUNT(*) n FROM co_sell_motions WHERE status='In Progress' GROUP BY 1 ORDER BY n DESC"),
}
# renewals
ren = q("""SELECT c.contract_id, a.name account, a.tier, a.status acct_status, c.end_date, c.auto_renew, ROUND(c.total_contract_value) tcv,
  ROUND(1.0*e.seat_count_active/NULLIF(e.seat_count_purchased,0),2) seat_util, ROUND(e.used_capacity_tb/NULLIF(e.allocated_capacity_tb,0),2) tb_util,
  emp.full_name owner, emp.territory,
  EXISTS(SELECT 1 FROM opportunities o2 WHERE o2.account_id=a.account_id AND o2.deal_type='Renewal' AND o2.stage NOT LIKE 'Closed%') renewal_opp
  FROM contracts c JOIN opportunities o USING(opportunity_id) JOIN accounts a USING(account_id) JOIN employees emp ON emp.employee_id=o.employee_id
  LEFT JOIN entitlements e USING(contract_id) WHERE o.stage='Closed Won' AND c.end_date BETWEEN ? AND ? ORDER BY c.end_date""", TODAY, D180)
for r in ren:
    su, tu = r["seat_util"], r["tb_util"]
    if r["acct_status"] == "Churned" or (su and su > 1.2): r["lane"] = "DATA-CHECK"
    elif r["auto_renew"] == 0 and ((su is not None and su < 0.5) or (tu is not None and tu < 0.5)): r["lane"] = "SAVE"
    elif (su and 1.0 < su <= 1.2) or (tu and tu > 1.0): r["lane"] = "GROW"
    else: r["lane"] = "STEADY"
vp["renewals"] = {"rows": ren, "count": len(ren), "tcv": round(sum(r["tcv"] for r in ren)),
  "lanes": [{"k": l, "n": sum(1 for r in ren if r["lane"] == l), "tcv": round(sum(r["tcv"] for r in ren if r["lane"] == l))} for l in ["SAVE", "GROW", "STEADY", "DATA-CHECK"]],
  "no_renewal_opp": sum(1 for r in ren if not r["renewal_opp"])}
# competitive
vp["competitive"] = q(f"""SELECT x.objection k, COUNT(*) n, ROUND(SUM(o.arr)) arr FROM opportunities o JOIN (
  SELECT g.opportunity_id, MAX(t.top_objection_raised) objection FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id) GROUP BY 1) x USING(opportunity_id)
  WHERE {OPEN} GROUP BY 1 ORDER BY arr DESC""")
vp["competitive_wr"] = q("SELECT x.objection k, ROUND(1.0*SUM(o.stage='Closed Won')/COUNT(*),3) rate, COUNT(*) n FROM opportunities o JOIN (SELECT g.opportunity_id, MAX(t.top_objection_raised) objection FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id) GROUP BY 1) x USING(opportunity_id) WHERE o.stage LIKE 'Closed%' GROUP BY 1")
vp["takeouts_180d"] = q("SELECT t.vendor_name k, COUNT(DISTINCT t.account_id) n FROM technographics t JOIN sixsense_account_intent s USING(account_id) WHERE t.category='Legacy Backup' AND t.vendor_name IN ('Cohesity','Veeam','Commvault','NetApp') AND t.renewal_date BETWEEN ? AND ? AND s.is_6qa=1 GROUP BY 1 ORDER BY n DESC", TODAY, D180)
# top of funnel
vp["tofu"] = {
  "sixqa_no_opp": one("SELECT COUNT(*) n FROM sixsense_account_intent s WHERE s.is_6qa=1 AND s.buying_stage='Decision' AND NOT EXISTS (SELECT 1 FROM opportunities o WHERE o.account_id=s.account_id AND o.stage NOT LIKE 'Closed%')")["n"],
  "sixqa_total": one("SELECT COUNT(*) n FROM sixsense_account_intent WHERE is_6qa=1")["n"],
  "sequences": q("SELECT sequence_name k, COUNT(*) n, ROUND(1.0*SUM(response_status IN ('Replied','Meeting Booked'))/COUNT(*),3) rate, SUM(response_status='Meeting Booked') meetings FROM outreach_sequence_activities GROUP BY 1 ORDER BY rate DESC"),
  "campaigns_90d": q("SELECT c.name k, c.type, COUNT(*) n, SUM(t.event_type='Demo Request') demos FROM touchpoints t JOIN campaigns c USING(campaign_id) WHERE t.timestamp >= ? GROUP BY 1,2 ORDER BY n DESC LIMIT 8", D90),
  "touch_by_source_90d": q("SELECT source_system k, COUNT(*) n FROM touchpoints WHERE timestamp >= ? GROUP BY 1 ORDER BY n DESC", D90),
  "new_opps_90d": one("SELECT COUNT(*) n, ROUND(COALESCE(SUM(o.arr),0)) arr FROM opportunities o JOIN (SELECT opportunity_id, MIN(change_timestamp) f FROM clari_forecast_history_logs GROUP BY 1) l USING(opportunity_id) WHERE substr(l.f,1,10) >= ?", D90),
}
vp["agents"] = q("SELECT ag.name k, COUNT(*) n, GROUP_CONCAT(DISTINCT x.action_type) actions FROM agent_opportunity_assists x JOIN ai_agents ag USING(agent_id) WHERE x.last_action_timestamp >= ? GROUP BY 1 ORDER BY n DESC", D90)

# ---------- AE ----------
AE_ID = 112  # Barbara Jones, LATAM
rep = one("SELECT employee_id id, full_name name, email, territory, quota FROM employees WHERE employee_id=?", AE_ID)
mine = [o for o in open_opps if o["owner_id"] == AE_ID]
won_fy_ae = one("SELECT COALESCE(SUM(arr),0) arr, COUNT(*) n FROM opportunities WHERE employee_id=? AND stage='Closed Won' AND close_date BETWEEN ? AND ?", AE_ID, FY_START, TODAY)
won_q_ae = one("SELECT COALESCE(SUM(arr),0) arr, COUNT(*) n FROM opportunities WHERE employee_id=? AND stage='Closed Won' AND close_date BETWEEN ? AND ?", AE_ID, Q_START, Q_END)
lost_q_ae = one("SELECT COALESCE(SUM(arr),0) arr, COUNT(*) n FROM opportunities WHERE employee_id=? AND stage='Closed Lost' AND close_date BETWEEN ? AND ?", AE_ID, Q_START, Q_END)
minq = [o for o in mine if o["in_q"]]
ae_k = {"quota_q": round(rep["quota"] / 4), "quota_fytd": round(rep["quota"] * 7.5 / 12), "won_fytd": round(won_fy_ae["arr"]), "won_fytd_n": won_fy_ae["n"],
        "won_q": round(won_q_ae["arr"]), "won_q_n": won_q_ae["n"], "lost_q_n": lost_q_ae["n"],
        "commit_q": sum_fc(minq, "Commit"), "best_q": sum_fc(minq, "Best Case"), "pipe_q": sum_fc(minq, "Pipeline"),
        "open_arr": round(sum(o["arr"] for o in mine)), "open_n": len(mine), "next_q_arr": round(sum(o["arr"] for o in mine if o["in_nq"])),
        "flags": sum(len(o["flags"]) for o in mine)}
ae_k["gap_q"] = round(ae_k["quota_q"] - ae_k["won_q"] - ae_k["commit_q"]); ae_k["coverage"] = round(ae_k["open_arr"] / max(ae_k["quota_q"], 1), 1)

def deal_detail(o):
    oid, aid = o["id"], o["account_id"]
    d = slim(o); d.update({k: o[k] for k in ["tcv", "rep_fcst", "ai_fcst", "industry", "acct_status", "incumbent_renewal", "intent", "is6qa", "reg_status", "last_call", "in_q", "in_nq"]})
    d["stakeholders"] = q("""SELECT c.first_name||' '||c.last_name name, c.job_title title, c.seniority_level seniority, p.title persona, bc.name buying_center,
        (SELECT COUNT(*) FROM touchpoints t WHERE t.contact_id=c.contact_id AND t.timestamp>=?) touches_90d
        FROM contacts c JOIN buyer_personas p USING(persona_id) LEFT JOIN buying_centers bc USING(buying_center_id)
        WHERE c.account_id=? ORDER BY CASE c.seniority_level WHEN 'C-Level' THEN 0 WHEN 'VP' THEN 1 WHEN 'Director' THEN 2 WHEN 'Manager' THEN 3 ELSE 4 END LIMIT 8""", D90, aid)
    d["calls"] = q("""SELECT t.call_date date, t.call_title title, t.top_objection_raised objection, t.key_takeaways takeaway, g.buyer_sentiment_score sentiment, g.multithread_contact_ratio mt
        FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id) WHERE g.opportunity_id=? ORDER BY t.call_date DESC LIMIT 5""", oid)
    d["content"] = q("""SELECT h.content_name name, ROUND(AVG(h.completion_pct)*100) pct, COUNT(*) views, GROUP_CONCAT(DISTINCT sv.buyer_comments) comments
        FROM highspot_collateral_engagement h LEFT JOIN highspot_slide_views sv USING(engagement_id) WHERE h.opportunity_id=? GROUP BY 1 ORDER BY pct DESC LIMIT 5""", oid)
    d["skus"] = q("SELECT s.name, s.pricing_metric metric, os.quantity qty, ROUND(s.list_price) list, ROUND(os.negotiated_price) net, ROUND(1-os.negotiated_price/s.list_price,2) disc FROM opportunity_skus os JOIN skus s USING(sku_id) WHERE os.opportunity_id=?", oid)
    d["quote_total"] = round(sum(r["qty"] * r["net"] for r in d["skus"]))
    d["team"] = q("SELECT e.full_name name, oe.role FROM opportunity_employees oe JOIN employees e USING(employee_id) WHERE oe.opportunity_id=?", oid)
    d["cosell"] = q("SELECT motion_type, status, date FROM co_sell_motions WHERE opportunity_id=? ORDER BY date DESC LIMIT 4", oid)
    d["history"] = q("SELECT substr(change_timestamp,1,10) date, old_stage, new_stage, ROUND(old_arr) old_arr, ROUND(new_arr) new_arr, rep_notes_text note FROM clari_forecast_history_logs WHERE opportunity_id=? ORDER BY change_timestamp DESC LIMIT 6", oid)
    d["searches"] = q("SELECT search_term, landing_page_url url FROM sixsense_search_queries WHERE account_id=? ORDER BY search_timestamp DESC LIMIT 5", aid)
    d["emails"] = q("""SELECT m.subject_line subject, m.reply_body_text reply, a.sequence_name seq, a.response_status status FROM outreach_email_messages m JOIN outreach_sequence_activities a USING(activity_id)
        JOIN contacts c ON c.contact_id=m.contact_id WHERE c.account_id=? ORDER BY m.message_id DESC LIMIT 5""", aid)
    # next-best-action heuristic (rule-based, explainable)
    nba = []
    if "STALE-DATE" in o["flags"]: nba.append(f"Close date {o['close_date']} is in the past — update it or move to Omitted.")
    if "COMMIT-AT-RISK" in o["flags"]: nba.append(f"Commit with Clari health {o['health']} — confirm with the champion before Friday's call.")
    if "SINGLE-THREADED" in o["flags"]: nba.append("Single-threaded (multithread < 0.3) — get a second stakeholder on the next call.")
    eb = [s for s in d["stakeholders"] if s["persona"] == "Economic Buyer"]
    if not eb: nba.append("No Economic Buyer identified on the account — ask the champion for an intro.")
    if o["incumbent"] and o["incumbent_renewal"]: nba.append(f"{o['incumbent']} renews {o['incumbent_renewal']} — time the proposal 120 days ahead.")
    if "SILENT-60D" in o["flags"]: nba.append("No CRM update in 60 days — log the last call's outcome.")
    if not nba: nba.append("Healthy — keep cadence; next step per last note.")
    d["next_actions"] = nba[:3]
    return d

ae_deals = sorted([deal_detail(o) for o in mine], key=lambda d: (not d["in_q"], -d["arr"]))
# AE alerts
alerts = []
for d in ae_deals:
    for f in d["flags"]:
        alerts.append({"opp": d["id"], "account": d["account"], "arr": d["arr"], "flag": f, "close": d["close_date"]})
# AE whitespace in territory: 6QA decision accounts with no open opp whose contacts are in territory owner's country? No territory on accounts; use accounts with any opp previously owned by this AE OR untouched 6QA accounts (sample 8)
whitespace = q("""SELECT a.account_id, a.name, a.industry, a.tier, s.intent_score, s.buying_stage, s.top_keywords,
   (SELECT vendor_name||' · '||MIN(renewal_date) FROM technographics t WHERE t.account_id=a.account_id AND t.category='Legacy Backup' AND t.renewal_date>=?) incumbent
   FROM accounts a JOIN sixsense_account_intent s USING(account_id) WHERE s.is_6qa=1 AND s.buying_stage='Decision' AND a.status IN ('Prospect','Churned')
   AND NOT EXISTS (SELECT 1 FROM opportunities o WHERE o.account_id=a.account_id AND o.stage NOT LIKE 'Closed%') ORDER BY incumbent IS NULL, incumbent LIMIT 8""", TODAY)
my_ren = [r for r in ren if r["owner"] == rep["name"]]
activity = {
  "calls_30d": one("SELECT COUNT(*) n FROM gong_call_transcripts t JOIN gong_account_insights g USING(gong_id) JOIN opportunities o ON o.opportunity_id=g.opportunity_id WHERE o.employee_id=? AND t.call_date BETWEEN ? AND ?", AE_ID, D30, TODAY)["n"],
  "sequences": q("SELECT sequence_name k, COUNT(*) n, SUM(response_status IN ('Replied','Meeting Booked')) replies, SUM(response_status='Meeting Booked') meetings FROM outreach_sequence_activities WHERE employee_id=? GROUP BY 1 ORDER BY n DESC", AE_ID),
  "agent_assists_90d": q("SELECT x.action_type k, COUNT(*) n FROM agent_opportunity_assists x JOIN opportunities o USING(opportunity_id) WHERE o.employee_id=? AND x.last_action_timestamp>=? GROUP BY 1 ORDER BY n DESC", AE_ID, D90),
  "upcoming_closes": [{"id": d["id"], "account": d["account"], "close": d["close_date"], "arr": d["arr"], "fc": d["fc"]} for d in sorted(ae_deals, key=lambda d: d["close_date"]) if d["close_date"] >= TODAY][:6],
}
ae = {"rep": rep, "kpis": ae_k, "deals": ae_deals, "alerts": sorted(alerts, key=lambda a: -a["arr"]), "whitespace": whitespace, "renewals": my_ren, "activity": activity,
      "by_stage": agg(mine, "stage"), "by_fc": agg(mine, "fc"), "by_lob": agg(mine, "lob")}

data = {"meta": {"as_of": TODAY, "fiscal": "Rubrik FY ends Jan 31; FY27 Q3 = Aug–Oct 2026", "source": "rubrik_gtm_synthetic_v5.db (synthetic)", "lob_note": "LOB = dominant product family on the quote (SKU lines, version stripped)"}, "vp": vp, "ae": ae}
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dash_data.json")
json.dump(data, open(out, "w"), separators=(",", ":"), default=str)
import os; print("bytes", os.path.getsize(out))
print(json.dumps(kpis, indent=1)); print(json.dumps(ae_k, indent=1)); print(vp["by_lob"]); print(vp["by_channel"]); print(vp["renewals"]["lanes"]); print(len(ae_deals), "AE deals")
