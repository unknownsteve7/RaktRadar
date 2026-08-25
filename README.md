# RaktRadar

Early-warning analytics for blood stock shortages across India, built on live, continuously-updating government data — not a static download.

## The Problem

Blood banks in India run short of specific blood groups in specific regions, and it's usually only visible once it's already urgent. If there's a detectable pattern leading up to a shortage — a region draining faster than it's replenished, a recurring dip tied to certain days or festivals — that's something worth surfacing before it becomes a crisis, not after.

## Data Source

[eRaktKosh](https://eraktkosh.mohfw.gov.in) — India's national blood stock tracking portal, run by the Ministry of Health and Family Welfare (C-DAC). Public, no authentication required.

Mid-development, the live portal turned out to have two versions running in parallel: a legacy jQuery/DataTables site (`.../BLDAHIMS/bloodbank/...`) and a newer React/Ant Design "Beta" rebuild (`.../eraktkoshPortal/...`). This project targets the **Beta API** — cleaner structured JSON, no HTML embedded in response fields, and noticeably fresher `entrydate` timestamps on records during side-by-side testing.

**Endpoints in use:**
- `POST /eraktkoshPortal/eraktkosh/master/all` — reference data: states, nested districts, blood groups, blood components. Static; cached locally, refreshed weekly rather than on every run.
- `GET /eraktkoshPortal/eraktkosh/blood-availability` — live stock per state/district/blood group/component combination.

## Status

**Infrastructure phase complete, collection not yet running.** Both core data-pulling functions are built and verified against manually-confirmed ground truth (state/district/blood-group/component codes cross-checked directly against the live site's DOM). No live time-series data has been collected yet — that only starts once the automated pipeline is deployed and left running for several weeks.

- [x] Reverse-engineer and verify the reference-data endpoint (`master/all`)
- [x] Reverse-engineer and verify the stock endpoint (`blood-availability`)
- [x] Build `run_collection.py` — the full state × district × blood group × component loop with append-per-call persistence, logging, and failure isolation
- [x] Deploy as a scheduled GitHub Actions workflow (daily; independent of any local machine)
- [ ] Accumulate several weeks of real history
- [ ] Descriptive analysis — which regions/blood groups run chronically short vs. surplus
- [ ] Diagnostic analysis — weekday effects, festival correlation, handling stale/unreported entries
- [ ] Stretch goal — early-warning/trend flag, if data quality supports it
- [ ] Streamlit dashboard

## Notable Technical Decisions

A few things worth recording while they're fresh, since some of this shaped real design choices:

- **Dropped the original census-2011-based reference dataset.** It undercounted Delhi (9 districts vs. the current 11 — Delhi was reorganized in 2012) and used a different code scheme than eRaktKosh's own internal IDs entirely for some fields. Reference data (states, districts, blood group/component codes) is now sourced live from the portal's own `master/all` endpoint instead, and cross-validated against values read directly off the site's DOM.
- **Zero-padding mismatch.** The old reference source stored district codes as zero-padded strings (`"098"`); the API expects unpadded values (`"98"`) for codes under 100. Fixed via explicit `int()` casting at the point of use — but this isn't applied as a blanket rule elsewhere, since other fields (like state codes) turned out to need the opposite treatment.
- **`master/all` requires an explicit JSON content type.** A form-encoded POST body returns `415 Unsupported Media Type`; fixed by passing `json=` instead of `data=` in `requests`.
- **Stale timestamps are a real signal, not noise.** Some blood bank entries carry `entrydate` values months old. A "Not Available" status on a stale record likely means "unreported," not "confirmed empty" — this needs explicit handling in the eventual analysis, not just a blanket true/false read.
- **`hospitalCode` (not blood bank name) is the correct join key** across time-series pulls — names have inconsistent capitalization/spacing across records; the numeric hospital code is stable.

## Tech Stack

Python, `requests` — GitHub Actions (scheduling) — pandas (analysis, planned) — Streamlit (dashboard, planned)


`master_data.json` is cached locally after the first run and reused — it isn't refetched on every collection cycle, since the underlying reference data doesn't change day to day.

## Author

Naga Mohan Madicharla
[github.com/unknownsteve7](https://github.com/unknownsteve7) · [nagamohan.me](https://nagamohan.me)