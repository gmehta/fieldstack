#!/usr/bin/env python3
"""
gtm_query.py -- tiny SQL runner for rubrik_gtm_synthetic_v5.db (needs only stdlib).

Usage:
  python3 gtm_query.py "SELECT ..."                 # run SQL, print a markdown table
  python3 gtm_query.py --catalog renewal            # search the semantic catalog (tables + columns)
  python3 gtm_query.py --tables                     # list tables with business names and row counts
  python3 gtm_query.py --describe opportunities     # columns, synonyms, descriptions, FK joins
  python3 gtm_query.py --json "SELECT ..."          # JSON rows instead of a table (feed back to Claude)
  echo "SELECT ..." | python3 gtm_query.py -        # SQL from stdin

DB path: --db PATH, else $GTM_DB, else rubrik_gtm_synthetic*.db in cwd, ../../data-model (repo layout), or uploads.
Writes are blocked: the connection is opened read-only. Every case in this kit is read-only by design.
"""
import glob, json, os, sqlite3, sys

def find_db(explicit=None):
    if explicit: return explicit
    if os.environ.get("GTM_DB"): return os.environ["GTM_DB"]
    here = os.path.dirname(os.path.abspath(__file__))
    for pat in ["rubrik_gtm_synthetic*.db", os.path.join(here, "..", "..", "data-model", "rubrik_gtm_synthetic*.db"), "/mnt/user-data/uploads/rubrik_gtm_synthetic*.db",
                os.path.expanduser("~/mnt/*/rubrik_gtm_synthetic*.db"), "**/rubrik_gtm_synthetic*.db"]:
        hits = sorted(glob.glob(pat, recursive=True))
        if hits: return hits[-1]
    sys.exit("No rubrik_gtm_synthetic*.db found. Pass --db PATH or set GTM_DB.")

def md_table(cols, rows, limit=60):
    if not rows: return "(0 rows)"
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in rows[:limit]:
        out.append("| " + " | ".join("" if v is None else str(v).replace("\n", " ")[:120] for v in r) + " |")
    if len(rows) > limit: out.append(f"... {len(rows) - limit} more rows")
    return "\n".join(out)

def main():
    args = sys.argv[1:]
    db = None
    if "--db" in args:
        i = args.index("--db"); db = args[i + 1]; del args[i:i + 2]
    con = sqlite3.connect(f"file:{find_db(db)}?mode=ro", uri=True)
    cur = con.cursor()

    if not args or args[0] in ("-h", "--help"):
        print(__doc__); return
    if args[0] == "--tables":
        cur.execute("SELECT table_name, business_name, category, row_count FROM semantic_catalog_tables ORDER BY category, table_name")
        print(md_table([d[0] for d in cur.description], cur.fetchall(), 100)); return
    if args[0] == "--describe":
        t = args[1]
        cur.execute("SELECT column_name, data_type, is_primary_key pk, fk_table, business_synonyms, description FROM semantic_catalog_columns WHERE table_name=? ORDER BY rowid", (t,))
        print(md_table([d[0] for d in cur.description], cur.fetchall(), 100))
        cur.execute("SELECT from_table, from_column, to_table, to_column, relationship_type FROM semantic_catalog_relationships WHERE from_table=? OR to_table=?", (t, t))
        print("\nJoins:\n" + md_table([d[0] for d in cur.description], cur.fetchall(), 100)); return
    if args[0] == "--catalog":
        term = " ".join(args[1:])
        cur.execute("SELECT kind, ref_table, ref_column, substr(content_text,1,140) hit FROM semantic_catalog_fts WHERE semantic_catalog_fts MATCH ? LIMIT 25", (term,))
        print(md_table([d[0] for d in cur.description], cur.fetchall())); return

    as_json = False
    if args[0] == "--json": as_json = True; args = args[1:]
    sql = sys.stdin.read() if args[0] == "-" else " ".join(args)
    cur.execute(sql)
    cols = [d[0] for d in cur.description] if cur.description else []
    rows = cur.fetchall()
    if as_json: print(json.dumps([dict(zip(cols, r)) for r in rows], indent=1, default=str))
    else: print(md_table(cols, rows)); print(f"\n({len(rows)} rows)")

if __name__ == "__main__":
    main()
