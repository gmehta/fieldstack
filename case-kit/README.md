# Rubrik Staff PM (IT-GTM) — Onsite Case Kit

Ten rehearsal cases for the 105-minute case round (Problem Sharing → Solutioning → POC Build → Taste Validation), each grounded in `rubrik_gtm_synthetic_v5.db`. Every SQL block in this kit has been executed against that DB (53 queries, 0 failures, 2026-09-15).

```
case-kit/
├── README.md                     ← this file: how I decided, how to use, how to review
├── _shared/
│   ├── DATA-MAP.md               ← schema ↔ stack map, join spine, 20 verified data traps, starter queries
│   └── gtm_query.py              ← stdlib-only SQL runner (read-only), catalog search, table describe
│
│   each case folder holds three files:
│     AGENT.md  ← the agent definition: identity + system prompt + which skill it invokes (~35 lines). This is what runs.
│     SKILL.md  ← the know-how: phase runbook, verified SQL, output schema, guardrails, eval rubric. The agent invokes this.
│     SPEC.md   ← the product spec behind the agent (rules, metrics, rollout, edge cases). Show only if asked.
├── 01-account-planning-copilot/      AGENT.md  SKILL.md  SPEC.md
├── 02-pipeline-hygiene-forecast-risk/ AGENT.md  SKILL.md  SPEC.md
├── 03-prospecting-research-agent/     AGENT.md  SKILL.md  SPEC.md
├── 04-call-to-crm-deal-risk/          AGENT.md  SKILL.md  SPEC.md
├── 05-cpq-quote-guardrail/            AGENT.md  SKILL.md  SPEC.md
├── 06-partner-prm-ops-agent/          AGENT.md  SKILL.md  SPEC.md
├── 07-renewal-risk-expansion/         AGENT.md  SKILL.md  SPEC.md   (added)
├── 08-gtm-ai-portfolio-prioritization/ AGENT.md  SKILL.md  SPEC.md   (added — the "what would you build first" meta-case)
├── 09-agent-outcome-measurement/      AGENT.md  SKILL.md  SPEC.md   (added)
└── 10-competitive-displacement-play/  AGENT.md  SKILL.md  SPEC.md   (added — Rubrik-specific)
```

## 1. Are six cases enough? — No; ten covers the JD, six leaves four holes

I scored candidates against three things: the JD's literal language, the systems spine it names (Salesforce → PRM → CPQ → billing; Clari), and what the mock DB can actually support (a case you can't build in 30 minutes on the data in the room is a weak rehearsal).

| # | Case | JD hook | Likelihood | Data support |
|---|---|---|---|---|
| 1 | Account Planning Copilot | "account planning" | High | Very strong (all sources join at account) |
| 2 | Pipeline Hygiene & Forecast Risk | "pipeline", Clari, "pipeline velocity and close rates" | **Very high** | Very strong — and full of planted traps |
| 3 | Prospecting / Research | "prospecting", 6sense, Outreach | High | Strong |
| 4 | Call-to-CRM & Deal Risk | Gong → Salesforce | High | Strong (12k transcripts + FTS) |
| 5 | CPQ Guardrail | "CPQ, billing" | Medium-high | Strong but chaotic (T8) — good for taste |
| 6 | Partner / PRM Ops | "PRM", MSP channel ops posting | Medium | Strong — *re-scoped* from FAQ-bot to record-grounded ops (DB has no docs, has the full PRM model) |
| 7 | Renewal Risk & Expansion | "relationship management", "Renewals" in Rubrik's own SFDC postings | **High** | Strong (contracts, entitlements, churn, existing `Flagged Renewal Risk` action) |
| 8 | GTM AI Portfolio Prioritisation | "needs assessments… prioritise features with highest ROI" | **High** | Uses everything; it's how you'd rank 1–7, 9, 10 |
| 9 | Agent Outcome Measurement | "accountability for outcomes", "shipping production agents" | Medium-high | `ai_agents` + 7,055 assists; the honest answer is "no control group" |
| 10 | Competitive Displacement | Rubrik's market (Cohesity/Veeam/Commvault/NetApp takeouts) | Medium-high | Purpose-built: incumbent renewal dates × competitor searches × call objections |

## 1a. Case catalogue — what each case is, and how to route a prompt to it

> **Routing instruction for Claude.** When Gaurav pastes the interviewer's problem statement, read this section, match it against the *Route here when* column (words the interviewer is likely to use, and the underlying problem shape), and reply with: the best-fit case folder, a one-line reason, the runner-up, and — if the prompt is open-ended with no single agent named — Case 8. Then open that case's `AGENT.md` (what runs), `SKILL.md` (what it invokes) and `SPEC.md` (backing spec). If two cases fit, prefer the one whose *Problem* line matches the interviewer's stated pain, not the systems they mention.

**Case 1 — Account Planning Copilot** · `01-account-planning-copilot/`
- **Problem:** an AE prepping for a QBR/exec meeting on a strategic account has to pull from Salesforce, Clari, Gong, Highspot and usage data by hand; prep takes hours and still misses threats or whitespace.
- **What it builds:** a one-page, row-cited account brief (money, people, voice of buyer, consumption, threats + next best action) for one account.
- **Route here when:** "account planning", "QBR / EBC prep", "account brief", "strategic account", "whitespace", "stakeholder map", "get the AE ready", "everything we know about account X".

**Case 2 — Pipeline Hygiene & Forecast-Risk Agent** · `02-pipeline-hygiene-forecast-risk/`
- **Problem:** the forecast slips because opportunity records are stale, silent, or contradict Clari; managers spend Mondays chasing reps.
- **What it builds:** a rules-based stale / at-risk / data-defect classifier over open opps, with drafted rep nudges and a forecast-accuracy baseline.
- **Route here when:** "reps don't update Salesforce", "pipeline hygiene", "stale opps", "forecast accuracy", "Commit deals keep missing", "Clari", "slipped deals", "nudge reps".

**Case 3 — Prospecting / Account-Research Agent** · `03-prospecting-research-agent/`
- **Problem:** SDR/BDRs spend an hour researching an account before the first touch, and the resulting outreach is still generic.
- **What it builds:** a fixed-shape SDR brief (why-now, who, do-not-contact, talk track) plus a first-touch email, from 6sense intent, technographics, contacts and prior Outreach threads.
- **Route here when:** "SDR / BDR research", "outbound", "prospecting", "first touch", "6sense / intent", "why now", "reply rate is flat", "in-market accounts nobody works".

**Case 4 — Call-to-CRM Notetaker & Deal-Risk Flag** · `04-call-to-crm-deal-risk/`
- **Problem:** after Gong calls, nothing reliable makes it into Salesforce, and managers learn a deal went sideways from the forecast, not the call.
- **What it builds:** a quoted-evidence extraction from a transcript, proposed (human-approved) field diffs, and a risk flag with stated confidence.
- **Route here when:** "Gong", "call transcripts / summaries", "CRM data entry", "next steps from calls", "deal risk after a call", "reps hate updating Salesforce after calls", "hallucinated commitments".

**Case 5 — Quote-to-Cash / CPQ Guardrail** · `05-cpq-quote-guardrail/`
- **Problem:** reps build off-policy or arithmetically wrong quotes (bad bundles, wrong renewal terms, discounts outside band); deal desk becomes the bottleneck.
- **What it builds:** an advisory quote validator with explicit rules (price above list, discount band, SKU ambiguity, ARR mismatch, renewal-term checks), plain-language violations, and routing.
- **Route here when:** "CPQ", "quotes / quoting", "pricing", "discount approval", "deal desk", "bundles", "renewal terms", "billing errors", "quote-to-cash".

**Case 6 — Partner / PRM Operations Agent** · `06-partner-prm-ops-agent/`
- **Problem:** channel and MSP partners get stuck on deal registration, protection, payouts and enablement; CAMs answer the same questions from memory and can't scale.
- **What it builds:** a CAM worklist (deal-reg conflicts, expiring protection, attribution leaks, stale payouts, lapsed certs) and record-grounded partner replies.
- **Route here when:** "PRM", "partners / channel / MSP", "deal registration", "deal reg conflict", "co-sell", "SPIFF / rebate / MDF", "partner certifications", "partners ask the same questions".

**Case 7 — Renewal Risk & Expansion Agent** · `07-renewal-risk-expansion/`
- **Problem:** churn is discovered when the renewal quote bounces; over-consuming customers are never upsold; renewal owners have too many accounts to watch.
- **What it builds:** a SAVE / GROW / STEADY / DATA-CHECK worklist for contracts ending in 180 days, scored on four explainable signals with a recommended play.
- **Route here when:** "renewals", "churn", "retention", "GRR / NRR", "entitlements / utilisation / consumption", "expansion / upsell", "customer health", "relationship management".

**Case 8 — GTM AI Portfolio Prioritisation** (the meta-case) · `08-gtm-ai-portfolio-prioritization/`
- **Problem:** leadership wants to know where AI should go first in the seller journey; the ask is *what* to build, not *how*.
- **What it builds:** a five-number funnel diagnosis with trap-adjusted confidence, candidate bets sized on one ROI formula, one first bet, a not-doing list, and the questions that would flip the answer.
- **Route here when:** the prompt is open-ended or names no single agent — "roadmap", "prioritise", "needs assessment", "ROI", "where's the biggest leak", "pipeline velocity / close rates", "what would you build first", "here's our data, go".

**Case 9 — Agent Outcome Measurement** · `09-agent-outcome-measurement/`
- **Problem:** Rubrik already runs GTM agents (Deal Desk Assistant, Champion Finder, Outbound Prospecting Bot, Co-Sell Router); leadership wants the ROI and nobody can prove it.
- **What it builds:** an honest can-say / cannot-say verdict from observational data (no control group exists), a per-version scorecard with intervals, and a holdout + eval + logging design for next quarter.
- **Route here when:** "are our agents working", "AI ROI", "evals", "observability", "attribution", "holdout / A/B", "which version to roll back", "accountability for outcomes".

**Case 10 — Competitive Displacement Play** · `10-competitive-displacement-play/`
- **Problem:** takeouts from Cohesity / Veeam / Commvault / NetApp are the growth engine, but finding the next ones and timing them to the incumbent's renewal is manual.
- **What it builds:** a ranked takeout list scored on independent sources agreeing (incumbent renewal date × competitor-comparison intent × voiced objection on calls), with a per-account play and battlecard.
- **Route here when:** "competitors", "displacement / takeout", "incumbent renewal", "battlecards", "win/loss", "competitive intel", "we lose to Veeam on price", "who should we attack".

**Ambiguity rules.** Renewal *quote* errors → Case 5, renewal *risk* → Case 7. Call summaries → Case 4; account brief that *uses* calls → Case 1. Partner-sourced deals with pricing questions → Case 6 for the reg/margin, Case 5 for the quote. Anything about the agents Rubrik already has → Case 9. Anything that starts "where would you…" or "what would you build…" → Case 8, which then ranks the others.

Considered and cut: MQL→SQL lead routing (marketing-ops, not seller journey), cross-system identity resolution (a data-engineering case; instead it's a caveat inside every case via T15), rep coaching from calls (Gong sells it; low IT-GTM novelty).

## 2. What the mock data is really for

The DB is deliberately incoherent in ~20 places — `_shared/DATA-MAP.md` §3 lists them with verified numbers. Examples: 40% of open opps have close dates in the past; `probability_pct` is uniform in every stage; Clari category is independent of stage; negotiated SKU prices exceed list by up to 25×; 47% of entitlements have more active seats than purchased; every opportunity has an agent assist (no control group).

This changes what "good" looks like in the room. A candidate who runs a clean query and presents a clean number is averaging over noise. The Taste Validation phase almost certainly exists to catch exactly that. So every skill here makes Claude **name the trap it hit and state how it handled it** — the contradiction *is* the insight.

## 3. How each case is built (the design)

Every case is three files with one job each — and the demo story for the panel is the relationship between the first two:

**`AGENT.md` — the agent. This is what runs.** A short definition in the Claude Code / Cowork agent shape: frontmatter (`name`, `description`, `skills: [...]`, `tools`), the input it needs, a one-line invocation you paste into Cowork, and a system prompt. The system prompt says who the agent is, which skill to invoke against the DB, the constraints it must honour (read-only, cite every claim, name the data traps, self-score against the rubric), and the artefact to produce. It contains no SQL and no schema — it delegates all of that to the skill.

**`SKILL.md` — the know-how the agent invokes.** Phase-by-phase runbook for the room (the SCOPE questions, the scope sentence, the queries, the taste moves), plus the contract the agent needs at the end: output JSON schema, guardrails, evaluation rubric with subtle failure modes. Every SQL block has been executed against the DB.

**`SPEC.md` — the product spec behind the agent.** Job-to-be-done, rule tables, reasoning steps, success metrics with DB baselines, non-goals, edge cases, rollout. Not needed to run the demo; it is what you show if the CIO asks "and how would you productionise this?"

What you say to the panel: *"I built a skill that knows this data and how to produce this artefact, and a thin agent that invokes it inside the Cowork harness under explicit guardrails. Watch it run."* Then paste the invocation line from AGENT.md.

Design choices worth defending in the room:
1. **Rules decide, LLM explains.** Cases 2, 5, 6, 7, 10 use explicit rule tables. It makes precision measurable and the nudge/explanation the only generative part.
2. **Cite the row.** Every output schema has a `citation` field. Groundedness is the axis most likely to be tested in Taste Validation.
3. **Read-only first, always.** Every agent recommends; a human clicks. Rollout sections say when autonomy is earned (a quarter of > 80–90% precision).
4. **Separate rep-behaviour from system defects.** Case 2's AMOUNT-DISAGREE is systemic (81% average gap) — nudging reps about it would burn trust. That distinction is a Staff-level move.
5. **Refuse to over-claim.** Case 9's verdict is "cannot say — here's the 6-week plan to be able to." That's the answer, not a failure to answer.

## 4. Using it on the day — 30-minute build, scoping done live with the CIO

The format: Phases 0–1 (problem sharing, SCOPE questions, solutioning) happen face-to-face with no Claude. Then a single 30-minute build window. So all loading moves *before* the CIO conversation, and the build collapses into one kickoff prompt plus three short follow-ups.

**A. Pre-load (5 min, before meeting the CIO).** In Cowork, connect the folder holding `case-kit/` and the `.db`, then:
```
Read case-kit/README.md and case-kit/_shared/DATA-MAP.md fully.
Run python3 case-kit/_shared/gtm_query.py --tables to confirm the DB is live.
Treat 2026-09-15 as today. Don't do anything else yet — I'll return with a problem
statement and scope answers in about an hour. Keep this conversation open.
```
Routing catalogue, join spine and the 20 traps are now in context. Leave the conversation open.

**B. With the CIO (no Claude).** Ask SCOPE from memory — Stakeholder, Constraints (real vs mocked; write-back?), Outcome (the metric), Prior art, Edge case. Write the five answers as five short lines. State your one-sentence scope at the end of solutioning.

**C. Build — four prompts.**

*Min 0–2 · kickoff (does routing, loading, re-scoping, queries and the agent output in one go):*
```
Problem from the CIO: "<paste>".
SCOPE answers: Stakeholder = <…> / Constraints = <…> / Outcome = <…> / Prior art = <…> / Edge = <…>.
Scope I committed to: "<one sentence>".

Do all of this now, without pausing for confirmation:
1. Route: pick the case from README §1a, say why in one line, name the runner-up.
2. Read that case's AGENT.md, SKILL.md and SPEC.md.
3. Re-cut the agent for my SCOPE answers: show the revised system prompt (≤ 15 lines) and any change to the
   skill's output schema or guardrails. I'll narrate this to the CIO.
4. Then run it: act as the agent in AGENT.md, following its system prompt exactly — invoke the skill, run the
   Phase 2 queries with gtm_query.py (default record unless the CIO named one), name the traps, produce the
   artefact in the output schema with citations, self-score against the rubric, list blind spots.
```
While it runs (~8–10 min), narrate: the scaffold, read-only by design, the traps it's about to hit. That's Taste credit banked early.

*Min 12–17 · rubric + self-score:*
```
Using the skill's Evaluation rubric, score the output you just produced against it
axis by axis. Name the specific failure mode wherever it falls short — no vibes.
```

*Min 17–25 · the live iteration (what they're grading):*
```
The flaw I'm calling is "<pick one>". Add exactly this rule to the agent prompt: "<rule>".
Regenerate the output and show me only what changed and why.
```
Each SKILL.md names a ready rule under Phase 3; if the CIO's constraints exposed a different flaw, write your own one-liner. The edit lands in the agent's system prompt — say so: “I’m changing the agent, not the data.”

*Min 25–28 · close:*
```
List the known gaps from SKILL.md plus anything new we hit, in the order I should say them aloud.
```
Minutes 28–30 are slack.

**D. If something breaks.** No Python → tell Claude to open the `.db` with whatever SQLite it has (the SQL is plain SQLite; `gtm_query.py` is convenience). Routing picks a case you disagree with → override in one line ("use Case 7 instead") and let it continue. A query returns zero rows → usually a rule firing (the skills say so inline); have Claude state it, not hide it. Closed-book instruction from the recruiter → honour it; the moves are rehearsed either way.

## 5. What to review first

- `_shared/DATA-MAP.md` §3 — decide which traps you'd lead with; they're your Taste Validation script.
- `08-…/SKILL.md` — the ROI formula and the "not doing" discipline; it's the frame for everything else.
- `02-…/SPEC.md` rule table and `05-…/SPEC.md` rule table — the two places where "explainable rules + LLM language" is most concrete.
- Any `AGENT.md` — paste its invocation line into Cowork with the DB connected and watch the full run; that is the demo.
