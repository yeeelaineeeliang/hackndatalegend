# Pramaan (प्रमाण) — proof before planning

**A lie detector for hospital capability claims.**
Hack-Nation × Databricks · "Data Legend" Challenge · Track: `Data Readiness Desk`

**Live app:** https://data-readiness-desk-7474649574693760.aws.databricksapps.com *(Databricks Apps, Free Edition)*

*Pramaan* is Sanskrit for **proof** — the one thing we demand from every hospital record before a planner is allowed to trust it.

---

## The Problem, in Four Numbers

In India, a family can drive six hours to a hospital whose ICU was a claim, not a capability. We cross-examined every capability claim in the 10,000-facility challenge dataset against the operational evidence in its own record — equipment, staff, procedures. The results are the argument for this product:

| Finding | Count |
|---|---|
| Facilities claiming an **ICU with zero supporting evidence** anywhere in their record | **1,061** |
| Facilities claiming high-acuity care (ICU, trauma, NICU, maternity, oncology, cardiac, dialysis, surgery) | 6,616 |
| … of which are **fully evidence-backed** | **681 (~10%)** |
| Share of the entire dataset carrying **at least one claim with no textual support** | **38%** |

And the record ranked #1 for review? Its maternity claim literally cites *a different hospital*.

## What Pramaan Does

Pramaan is the trust gate between messy facility data and life-or-death planning decisions:

1. **Scores** all 10k records for completeness, evidence support, consistency, and leverage — precomputed, reproducible, versioned rules (`config/trust_scoring_rules.json`).
2. **Cross-examines** every high-acuity capability claim against operational evidence across fields. Every flag carries a **receipt**: the exact text searched, and what was — or wasn't — found.
3. **Ranks** a review queue by where human attention most improves the dataset, not just by what's worst.
4. **Persists** reviewer decisions in **Lakebase Postgres** — an append-only audit trail that survives sessions, restarts, and redeploys. Human judgment becomes institutional knowledge.
5. **Admits what it doesn't know.** Evidence scores are hard-capped until claims align to exact source spans, and missing data is never presented as missing care.
6. **Double-checks its own work.** A Databricks foundation model (`ai_query` batch) issues an independent AGREE/DISAGREE second opinion on each of the top 150 flags. It concurs on 59% — and its dissents are displayed, not hidden. Advisory only; human review always wins.

## The Reviewer's Minute

> Open the overview → see 9,958 records ranked by review priority → open the #1 facility → read the receipt showing exactly why its claim failed cross-examination → read the AI validator's independent opinion → record a decision with a note → watch the queue and the durable audit log update.

That's the whole product. No chat box. No black box.

## Architecture

```
raw CSV (10,118 rows)
   │  intake gate: schema, parsing, claim-shape, geography checks
   ▼
facilities_analysis_base ── 51 raw columns preserved + 36 provenance columns
   │  trust engine: completeness · evidence · consistency · corroboration · leverage
   ▼
trust_signals + 43,255 receipt-backed flags + ranked review_queue
   │  packaged as sharded parquet (largest shard 4.2 MB < 10 MB Apps limit)
   ▼
Streamlit app on Databricks Apps ──── reviewer decisions ──► Lakebase Postgres
   ▲                                                          (append-only audit trail)
   └── AI second opinions: ai_query batch over top 150 flags
```

Every stage emits a machine-readable validation report and fails loudly (`outputs/validation/`). The suite of 34 unit tests covers intake, normalization, scoring, app assets, and the decision store.

**Databricks stack:** Apps · Lakebase · Unity Catalog (`workspace.data_readiness`, 5 tables) · serverless SQL warehouse · foundation-model batch inference (`ai_query`).

**Deliberate tradeoff:** scoring is precomputed and the app serves from packaged tables. We chose a demo that cannot fail over live inference that might. The AI validator runs as batch for the same reason.

## Run It

```bash
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -r requirements.txt

# full pipeline, each stage gated by validation
python3 -m src.ingestion.facility_intake data/raw/facilities/healthcare_facilities.csv
python3 -m src.processing.normalize_facilities
python3 -m src.scoring.build_trust_signals
python3 -m src.app_data.build_app_assets
python3 -m unittest discover -v

# the app
cd app && streamlit run app.py
```

The raw challenge CSV is not redistributed in this repo; `data/raw/facilities/source_manifest.json` records its checksum. Deployment notes (including a hard-won `app.yaml` pitfall) live in `docs/APP.md`.

## Documentation

| Doc | What it covers |
|---|---|
| `docs/TRUST_SCORING.md` | Score formulas, flag taxonomy, corroboration rules, limitations |
| `docs/APP.md` | Reviewer workflow, deployment package, Databricks Apps + Lakebase setup |
| `docs/NORMALIZED_FACILITY_LAYER.md` | Analysis-base transformations and provenance policy |
| `docs/EXTRACTION_CONTRACT.md` | Reconciled facility schema and upstream prompt caveats |
| `docs/FACILITY_INTAKE.md` · `docs/REFERENCE_LAYER.md` · `DATA_SOURCES.md` | Intake gates, supplemental geography reference layer, join-risk policy |

## Why It Matters

"Probably has an ICU" is not good enough. A wrong referral is not a failed query — it is a family that drove six hours for nothing. Pramaan turns 10,000 unverifiable claims into decisions a planner can trust, defend, and save — with receipts at every step, honesty about every gap, and a durable memory of every human judgment.

**Pramaan: proof before planning.**
