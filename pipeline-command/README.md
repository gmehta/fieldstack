# Pipeline Command — VP of Sales and AE views

A login-gated, single-file pipeline dashboard built on `data-model/rubrik_gtm_synthetic_v5.db`. Two seats, one data model:

| Login | Password | View |
|---|---|---|
| `vp` | `vp-rubrik` | Global forecast, pipeline by stage / segment / LOB / channel, hygiene flags, AE leaderboard, partner channel, renewal book, competitive + top-of-funnel |
| `ae` | `ae-rubrik` | One AE's quarter, deal table with expandable full brief (stakeholders, Gong calls, CPQ quote, Highspot, buyer signals, Clari history), alerts, whitespace, renewals, activity |

Open `index.html` directly, or serve via GitHub Pages at `/pipeline-command/`. Credentials are client-side only — this is a demo.

## How it is built
- `build_dash_data.py` computes every number from the database (as of 2026-09-15, Rubrik fiscal calendar: FY ends Jan 31, so FY27 Q3 = Aug–Oct 2026) into a JSON snapshot.
- `index.html` embeds that snapshot and renders both views with inline SVG charts — no external libraries.
- Flags (STALE-DATE, SILENT-60D, COMMIT-AT-RISK, SLIPPED-3X, SINGLE-THREADED, CHURNED-ACCOUNT), renewal lanes (SAVE / GROW / STEADY / DATA-CHECK) and next-best-actions use the same explainable rules as the agents in `../case-kit/`, so the dashboard and the agents tell one story.
- LOB = dominant product family on the quote (SKU name with version stripped). Channel = deal-registration partner type; Direct = no registration.

Regenerate after changing the database:
```bash
python3 build_dash_data.py            # writes dash_data.json next to the script
# then paste the JSON into index.html in place of the <script id="dash-data"> contents
```
