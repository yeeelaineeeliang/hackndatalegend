from __future__ import annotations

import html
import json
import os

import pandas as pd
import streamlit as st

try:
    from data_access import (
        DATA_DIR,
        apply_review_status,
        filter_review_index,
        get_facility_bundle,
        load_ai_opinions,
        load_flags,
        load_review_index,
        values_as_list,
    )
    from review_store import DECISION_STATUSES, ReviewStore
except ModuleNotFoundError:
    from app.data_access import (
        DATA_DIR,
        apply_review_status,
        filter_review_index,
        get_facility_bundle,
        load_ai_opinions,
        load_flags,
        load_review_index,
        values_as_list,
    )
    from app.review_store import DECISION_STATUSES, ReviewStore


st.set_page_config(
    page_title="Data Readiness Desk",
    page_icon="DR",
    layout="wide",
    initial_sidebar_state="auto",
)

st.markdown(
    """
    <style>
    :root {
      --ink: #17242b;
      --muted: #617078;
      --paper: #f5f1e8;
      --surface: #fffdf8;
      --line: #d9d4c8;
      --teal: #087f78;
      --teal-deep: #075a57;
      --amber: #d58a22;
      --red: #b9483f;
      --navy: #183b50;
    }
    html, body, [class*="css"] {
      font-family: "Avenir Next", "Trebuchet MS", sans-serif;
      color: var(--ink);
    }
    .stApp {
      background:
        radial-gradient(circle at 90% -10%, rgba(8,127,120,.12), transparent 28rem),
        linear-gradient(180deg, #faf7f0 0%, var(--paper) 100%);
    }
    [data-testid="stSidebar"] {
      background: #173342;
      border-right: 1px solid rgba(255,255,255,.08);
    }
    [data-testid="stSidebar"] * { color: #f6f1e7 !important; }
    .block-container {
      max-width: 1500px;
      padding-top: 2.4rem;
      padding-bottom: 3rem;
    }
    header[data-testid="stHeader"] { background: rgba(250,247,240,.9); }
    [data-testid="stToolbar"] { visibility: hidden; }
    input, textarea { color: var(--ink) !important; }
    input::placeholder, textarea::placeholder {
      color: #66747b !important;
      opacity: 1 !important;
    }
    [data-baseweb="input"] > div,
    [data-baseweb="textarea"] > div,
    [data-baseweb="select"] > div {
      background: #fffdfa !important;
      border-color: #bfc8c7 !important;
    }
    [data-baseweb="input"] > div:focus-within,
    [data-baseweb="textarea"] > div:focus-within,
    [data-baseweb="select"] > div:focus-within {
      box-shadow: 0 0 0 3px rgba(8,127,120,.18) !important;
      border-color: var(--teal) !important;
    }
    div[data-testid="stForm"] {
      border: 1px solid var(--line);
      background: rgba(255,253,248,.94);
      padding: 1rem;
    }
    div[data-testid="stForm"] button {
      min-height: 2.65rem;
      font-weight: 750;
    }
    .desk-header {
      border: 1px solid var(--line);
      border-left: 6px solid var(--teal);
      background: rgba(255,253,248,.9);
      padding: 1.25rem 1.4rem 1.15rem;
      box-shadow: 0 12px 32px rgba(23,36,43,.06);
      margin-bottom: 1rem;
    }
    .eyebrow {
      color: var(--teal-deep);
      font-size: .72rem;
      font-weight: 800;
      letter-spacing: .14em;
      text-transform: uppercase;
    }
    .desk-title {
      font-family: "Charter", "Iowan Old Style", Georgia, serif;
      color: var(--ink);
      font-size: clamp(2rem, 4vw, 3.35rem);
      line-height: 1;
      margin: .35rem 0 .5rem;
      letter-spacing: -.035em;
    }
    .desk-subtitle { color: var(--muted); max-width: 58rem; margin: 0; }
    .workflow-strip {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: .55rem;
      margin: .75rem 0 1rem;
    }
    .workflow-step {
      background: rgba(255,253,248,.92);
      border: 1px solid var(--line);
      padding: .7rem .8rem;
      color: var(--muted);
      font-size: .78rem;
    }
    .workflow-step strong {
      color: var(--navy);
      display: block;
      font-size: .82rem;
      margin-bottom: .12rem;
    }
    .trust-banner {
      background: #e8f2ef;
      border: 1px solid #b8d8d1;
      color: #154f4c;
      padding: .75rem 1rem;
      margin: .6rem 0 1rem;
      font-size: .9rem;
    }
    .metric-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: .8rem;
      margin: .5rem 0 1.2rem;
    }
    .metric-card {
      background: var(--surface);
      border: 1px solid var(--line);
      padding: 1rem;
      min-height: 7.2rem;
      box-shadow: 0 7px 20px rgba(23,36,43,.04);
    }
    .metric-label {
      color: var(--muted);
      font-size: .68rem;
      font-weight: 800;
      letter-spacing: .11em;
      text-transform: uppercase;
    }
    .metric-value {
      color: var(--navy);
      font-family: "Charter", "Iowan Old Style", Georgia, serif;
      font-size: 2rem;
      font-weight: 700;
      margin: .2rem 0;
    }
    .metric-note { color: var(--muted); font-size: .78rem; }
    .data-note {
      color: var(--muted);
      font-size: .78rem;
      margin: -.2rem 0 .85rem;
    }
    .section-kicker {
      color: var(--teal-deep);
      font-size: .72rem;
      font-weight: 800;
      letter-spacing: .12em;
      text-transform: uppercase;
      margin-top: .6rem;
    }
    .facility-head {
      background: var(--navy);
      color: white;
      padding: 1.1rem 1.25rem;
      margin: 1.3rem 0 .9rem;
    }
    .facility-head h2 {
      color: white;
      font-family: "Charter", "Iowan Old Style", Georgia, serif;
      margin: .15rem 0;
    }
    .facility-head p { color: #c6d7df; margin: 0; }
    .facility-status {
      display: inline-block;
      border: 1px solid rgba(255,255,255,.28);
      border-radius: 999px;
      padding: .18rem .55rem;
      margin-top: .5rem;
      color: #e4f4f1;
      font-size: .72rem;
      font-weight: 750;
    }
    .score-row {
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: .55rem;
      margin-bottom: 1rem;
    }
    .score-box {
      background: var(--surface);
      border-top: 3px solid var(--teal);
      border-left: 1px solid var(--line);
      border-right: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
      padding: .7rem .8rem;
    }
    .score-box strong { color: var(--navy); font-size: 1.35rem; }
    .score-box span {
      display: block;
      color: var(--muted);
      font-size: .67rem;
      font-weight: 800;
      letter-spacing: .07em;
      text-transform: uppercase;
    }
    .evidence-warning {
      border-left: 4px solid var(--amber);
      background: #fff4dd;
      color: #674715;
      padding: .7rem .9rem;
      margin: .5rem 0;
      font-size: .85rem;
    }
    .flag-card {
      border: 1px solid var(--line);
      background: var(--surface);
      padding: .8rem .95rem;
      margin-bottom: .55rem;
    }
    .flag-card.high { border-left: 5px solid var(--red); }
    .flag-card.medium { border-left: 5px solid var(--amber); }
    .flag-card.low { border-left: 5px solid var(--teal); }
    .flag-meta {
      color: var(--muted);
      font-size: .68rem;
      font-weight: 800;
      letter-spacing: .08em;
      text-transform: uppercase;
    }
    .flag-card h4 { color: var(--ink); margin: .25rem 0; }
    .flag-card p { color: var(--muted); margin: .25rem 0; }
    .receipt {
      background: #eef1ef;
      color: #33434a;
      padding: .6rem .7rem;
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: .76rem;
      overflow-wrap: anywhere;
      margin-top: .55rem;
    }
    .method-card {
      background: var(--surface);
      border: 1px solid var(--line);
      padding: 1rem 1.1rem;
      min-height: 10rem;
    }
    .sidebar-step {
      border-left: 3px solid #54c2b5;
      padding: .2rem 0 .2rem .7rem;
      margin: .75rem 0;
      color: #dbe9ec !important;
      font-size: .82rem;
    }
    .sidebar-step strong {
      display: block;
      color: #ffffff !important;
      margin-bottom: .1rem;
    }
    .sidebar-meta {
      border-top: 1px solid rgba(255,255,255,.16);
      margin-top: 1rem;
      padding-top: .9rem;
      font-size: .76rem;
      color: #b9cbd1 !important;
    }
    div[data-testid="stDataFrame"] { border: 1px solid var(--line); }
    @media (max-width: 900px) {
      .metric-grid, .score-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .workflow-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .block-container { padding: 4rem .7rem 2rem; }
      .desk-title { font-size: clamp(2rem, 10vw, 2.7rem); }
      .desk-header { padding: 1rem 1rem .95rem; }
      button[role="tab"] {
        padding-left: .55rem !important;
        padding-right: .55rem !important;
      }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def app_manifest() -> dict:
    return json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))


@st.cache_resource
def review_store() -> ReviewStore:
    return ReviewStore()


def status_label(value: str) -> str:
    return str(value).replace("_", " ").title()


def flatten_options(series: pd.Series) -> list[str]:
    values = {
        item
        for value in series
        for item in values_as_list(value)
        if item and item != "nan"
    }
    return sorted(values)


def display_value(value: object, fallback: str = "unresolved") -> str:
    if value is None or pd.isna(value) or not str(value).strip():
        return fallback
    return str(value)


def metric_cards(items: list[tuple[str, str, str]]) -> None:
    cards = "".join(
        (
            '<div class="metric-card">'
            f'<div class="metric-label">{html.escape(label)}</div>'
            f'<div class="metric-value">{html.escape(value)}</div>'
            f'<div class="metric-note">{html.escape(note)}</div>'
            "</div>"
        )
        for label, value, note in items
    )
    st.markdown(f'<div class="metric-grid">{cards}</div>', unsafe_allow_html=True)


def score_row(summary: pd.Series) -> None:
    items = [
        ("Readiness", summary["readiness_score"]),
        ("Completeness", summary["completeness_score"]),
        ("Evidence", summary["evidence_support_score"]),
        ("Consistency", summary["consistency_score"]),
        ("Leverage", summary["high_leverage_score"]),
    ]
    cards = "".join(
        (
            '<div class="score-box">'
            f"<strong>{float(value):.1f}</strong>"
            f"<span>{html.escape(label)}</span>"
            "</div>"
        )
        for label, value in items
    )
    st.markdown(f'<div class="score-row">{cards}</div>', unsafe_allow_html=True)


def render_claims(label: str, values: object, status: object) -> None:
    claims = values_as_list(values)
    with st.expander(f"{label} · {len(claims)} entries · {status}", expanded=False):
        if not claims:
            st.caption("No parsed claim entries are available.")
            return
        for claim in claims[:20]:
            st.markdown(f"- {claim}")
        if len(claims) > 20:
            st.caption(f"Showing 20 of {len(claims)} entries.")


def render_facility_header(summary: pd.Series, detail: pd.Series) -> None:
    location = ", ".join(
        str(value)
        for value in [detail["address_city"], detail["address_stateOrRegion"]]
        if pd.notna(value) and str(value).strip()
    )
    current_status = status_label(str(summary.get("review_status", "unreviewed")))
    st.markdown(
        (
            '<div class="facility-head">'
            '<div class="eyebrow" style="color:#7cd0c7">Selected review record</div>'
            f"<h2>{html.escape(str(detail['name']))}</h2>"
            f"<p>{html.escape(location or 'Location unresolved')} · "
            f"PIN {html.escape(display_value(detail['pincode_normalized']))}</p>"
            f'<div class="facility-status">{html.escape(current_status)}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    score_row(summary)
    st.markdown(
        '<div class="evidence-warning"><strong>Evidence ceiling:</strong> '
        "source URLs are linked to the facility, not aligned to each exact claim. "
        "Evidence scores are capped at 75 and claims remain unverified until reviewed.</div>",
        unsafe_allow_html=True,
    )

def render_review_context(summary: pd.Series) -> None:
    st.markdown('<div class="section-kicker">Why this record is next</div>', unsafe_allow_html=True)
    st.write(
        f"Queue rank **#{int(summary['queue_rank']):,}** with "
        f"**{int(summary['flag_count'])} flags** and "
        f"**{int(summary['high_severity_flag_count'])} high-severity issues**."
    )
    st.write(
        f"Leverage reflects **{int(summary['claim_count'])} claims**, "
        f"**{int(summary['source_url_count'])} source URLs**, "
        f"capacity **{summary['capacity_normalized'] if pd.notna(summary['capacity_normalized']) else 'unknown'}**, "
        f"and doctors **{summary['number_doctors_normalized'] if pd.notna(summary['number_doctors_normalized']) else 'unknown'}**."
    )
    claimed_themes = int(summary.get("claimed_theme_count", 0) or 0)
    if claimed_themes:
        corroborated = int(summary.get("corroborated_theme_count", 0) or 0)
        unsupported_labels = values_as_list(summary.get("unsupported_themes"))
        st.write(
            f"**Claim corroboration:** {corroborated} of {claimed_themes} "
            "high-acuity themes have operational evidence."
        )
        if unsupported_labels:
            st.warning("Not fully corroborated: " + " · ".join(unsupported_labels))
    themes = values_as_list(summary["claim_themes"])
    st.caption("Claim themes are navigation aids, not verified classifications.")
    st.write(" · ".join(themes) if themes else "No claim themes detected")


def render_flag_card(flag: pd.Series) -> None:
    severity = str(flag["severity"]).lower()
    st.markdown(
        (
            f'<div class="flag-card {html.escape(severity)}">'
            f'<div class="flag-meta">{html.escape(severity)} · '
            f"{html.escape(str(flag['field_name']))} · "
            f"{html.escape(str(flag['validation_status']))}</div>"
            f"<h4>{html.escape(str(flag['reason_code']).replace('_', ' ').title())}</h4>"
            f"<p>{html.escape(str(flag['explanation']))}</p>"
            f'<div class="receipt">{html.escape(str(flag["evidence_text"]))}</div>'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_ai_second_opinion(opinion: pd.Series | None) -> None:
    if opinion is None:
        return
    verdict = str(opinion["ai_opinion"]).strip()
    agrees = verdict.upper().startswith("AGREE")
    border = "#087f78" if agrees else "#d58a22"
    st.markdown(
        (
            f'<div class="flag-card" style="border-left: 5px solid {border};">'
            '<div class="flag-meta">AI validator · independent second opinion · '
            f"{html.escape(str(opinion['model']))}</div>"
            f"<p style=\"color: var(--ink); margin-top:.4rem\">{html.escape(verdict)}</p>"
            '<p style="font-size:.75rem">Advisory only. Generated from the record '
            "text via Databricks ai_query as a self-correction check on the "
            "rule-based flag; it never overrides human review.</p>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_facility_evidence(
    detail: pd.Series,
    facility_flags: pd.DataFrame,
    ai_opinion: pd.Series | None = None,
) -> None:
    profile_col, description_col = st.columns([0.9, 1.1], gap="large")
    with profile_col:
        st.markdown('<div class="section-kicker">Facility profile</div>', unsafe_allow_html=True)
        profile = pd.DataFrame(
            [
                ("Type", detail["facility_type_normalized"]),
                ("Operator", detail["operator_type_normalized"]),
                ("Doctors", detail["numberDoctors_normalized"]),
                ("Capacity", detail["capacity_normalized"]),
                ("Established", detail["yearEstablished_normalized"]),
                ("PIN geography", detail["pincode_join_confidence"]),
                ("Coordinate status", detail["coordinate_pair_status"]),
            ],
            columns=["Field", "Value"],
        )
        profile["Value"] = profile["Value"].map(display_value)
        st.dataframe(profile, hide_index=True, width="stretch")
    with description_col:
        st.markdown('<div class="section-kicker">Source description</div>', unsafe_allow_html=True)
        if pd.notna(detail["description"]) and str(detail["description"]).strip():
            st.write(detail["description"])
        else:
            st.info("No source description is available for this facility.")

    st.markdown(
        f'<div class="section-kicker">Highest-priority receipts · {len(facility_flags)} total</div>',
        unsafe_allow_html=True,
    )
    render_ai_second_opinion(ai_opinion)
    primary_flags = facility_flags.head(4)
    for _, flag in primary_flags.iterrows():
        render_flag_card(flag)
    remaining_flags = facility_flags.iloc[4:]
    if not remaining_flags.empty:
        with st.expander(
            f"Show {len(remaining_flags)} additional flag receipts",
            expanded=False,
        ):
            for _, flag in remaining_flags.iterrows():
                render_flag_card(flag)

    claims_tab, sources_tab = st.tabs(["Extracted claims", "Source trail"])
    with claims_tab:
        render_claims(
            "Capabilities", detail["capability_parsed"], detail["capability_parse_status"]
        )
        render_claims(
            "Procedures", detail["procedure_parsed"], detail["procedure_parse_status"]
        )
        render_claims(
            "Equipment", detail["equipment_parsed"], detail["equipment_parse_status"]
        )
    with sources_tab:
        urls = values_as_list(detail["source_urls_parsed"])
        if not urls:
            st.warning("No source URLs are available for this facility.")
        for index, url in enumerate(urls[:12], start=1):
            if url.startswith(("https://", "http://")):
                st.link_button(f"Open source {index}", url, width="stretch")
        if len(urls) > 12:
            st.caption(f"Showing 12 of {len(urls)} source URLs.")


def clear_queue_filters() -> None:
    defaults = {
        "queue_search": "",
        "queue_states": [],
        "queue_issue_types": [],
        "queue_claim_themes": [],
        "queue_severities": [],
        "queue_review_statuses": [],
        "queue_min_priority": 0,
    }
    for key, value in defaults.items():
        st.session_state[key] = value


store = review_store()
index = load_review_index()
flags = load_flags()
ai_opinions = load_ai_opinions()
manifest = app_manifest()
decision_log = store.load_decisions()
latest_decisions = (
    decision_log.drop_duplicates("facility_id", keep="first")
    if not decision_log.empty
    else decision_log
)
index = apply_review_status(index, latest_decisions)

st.markdown(
    """
    <div class="desk-header">
      <div class="eyebrow">India healthcare · Data Readiness Desk</div>
      <div class="desk-title">The trust gate before planning.</div>
      <p class="desk-subtitle">
        Turn noisy facility records into an auditable review queue. Every issue
        carries a reason, a receipt, and an explicit validation state.
      </p>
    </div>
    <div class="workflow-strip" aria-label="Reviewer workflow">
      <div class="workflow-step"><strong>1 · Triage</strong>Start with highest review impact.</div>
      <div class="workflow-step"><strong>2 · Inspect</strong>Read claims, gaps, and receipts.</div>
      <div class="workflow-step"><strong>3 · Decide</strong>Record a status and durable note.</div>
      <div class="workflow-step"><strong>4 · Audit</strong>Carry history into planning.</div>
    </div>
    <div class="trust-banner">
      <strong>Missing data is not missing care.</strong>
      This desk ranks data uncertainty for review; it does not label a region a medical desert.
    </div>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("## 60-second judge path")
    st.markdown(
        """
        <div class="sidebar-step"><strong>1 · See the risk</strong>
        Overview quantifies unsupported and contradictory facility data.</div>
        <div class="sidebar-step"><strong>2 · Open rank #1</strong>
        The queue explains why this record should be reviewed first.</div>
        <div class="sidebar-step"><strong>3 · Read the receipt</strong>
        The exact claim text and missing corroboration stay visible.</div>
        <div class="sidebar-step"><strong>4 · Record a decision</strong>
        The status updates and the audit log preserves the history.</div>
        """,
        unsafe_allow_html=True,
    )
    backend_label = (
        "Lakebase · durable"
        if store.backend == "lakebase"
        else "SQLite · local demo"
    )
    generated_at = pd.Timestamp(manifest["generated_at"]).strftime(
        "%d %b %Y · %H:%M UTC"
    )
    st.markdown(
        (
            '<div class="sidebar-meta">'
            "<strong>Dataset snapshot</strong><br>"
            f"{manifest['queue_rows']:,} queued facilities · "
            f"{manifest['flag_rows']:,} flags<br>"
            f"Rules v1.1.0 · {html.escape(generated_at)}<br><br>"
            f"<strong>Decision store</strong><br>{html.escape(backend_label)}"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    if store.backend == "sqlite" and "unavailable" in store.backend_detail:
        st.error("Lakebase is configured but unavailable. Decisions are not durable.")

overview_tab, queue_tab, log_tab, method_tab = st.tabs(
    ["Overview", "Review queue", "Audit log", "Method"]
)

with overview_tab:
    st.markdown("## Most eligible facility records need human review before planning")
    st.markdown(
        (
            '<div class="data-note">'
            f"Precomputed snapshot: {html.escape(generated_at)} · "
            "Source: challenge facility export · Trust rules v1.1.0"
            "</div>"
        ),
        unsafe_allow_html=True,
    )
    contradiction_count = int(index["has_contradiction"].sum())
    weak_evidence_count = int(index["has_weak_evidence"].sum())
    high_leverage_count = int(index["high_leverage_score"].ge(75).sum())
    eligible_rows = int(manifest.get("eligible_rows", 9989))
    metric_cards(
        [
            (
                "Flagged facilities",
                f"{len(index):,}",
                f"{100 * len(index) / eligible_rows:.1f}% of eligible records",
            ),
            ("Contradictions", f"{contradiction_count:,}", "Cross-field or source conflicts"),
            ("Weak evidence", f"{weak_evidence_count:,}", "Placeholder or missing trace"),
            ("High leverage", f"{high_leverage_count:,}", "Leverage score of 75+"),
        ]
    )
    reviewed = index[index["review_status"] != "unreviewed"]
    resolved_count = int(
        index["review_status"].isin(["resolved", "confirmed_accurate"]).sum()
    )
    reviewed_share = 100 * len(reviewed) / len(index) if len(index) else 0.0
    metric_cards(
        [
            ("Decisions recorded", f"{len(decision_log):,}", "Durable audit trail"),
            ("Facilities reviewed", f"{len(reviewed):,}", f"{reviewed_share:.1f}% of the queue"),
            ("Resolved or confirmed", f"{resolved_count:,}", "Safe for planners"),
            (
                "Awaiting first review",
                f"{len(index) - len(reviewed):,}",
                "Highest priority ranked first",
            ),
        ]
    )
    left, right = st.columns([0.9, 1.1], gap="large")
    with left:
        st.markdown('<div class="section-kicker">Issue load</div>', unsafe_allow_html=True)
        issue_counts = (
            flags.groupby("flag_type")["unique_id"]
            .nunique()
            .sort_values(ascending=False)
            .rename("Facilities")
            .to_frame()
        )
        st.bar_chart(issue_counts, horizontal=True, color="#087f78")
    with right:
        st.markdown(
            '<div class="section-kicker">Highest-priority reviews</div>',
            unsafe_allow_html=True,
        )
        st.dataframe(
            index.head(10)[
                [
                    "queue_rank",
                    "name",
                    "address_state",
                    "review_priority_score",
                    "readiness_score",
                    "primary_issue",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "queue_rank": "Rank",
                "name": "Facility",
                "address_state": "State",
                "review_priority_score": st.column_config.NumberColumn(
                    "Priority", format="%.1f"
                ),
                "readiness_score": st.column_config.NumberColumn(
                    "Readiness", format="%.1f"
                ),
                "primary_issue": "Primary issue",
            },
        )

with queue_tab:
    st.markdown("## Review the records where human attention matters most")
    st.caption(
        "Search by facility, city, or PIN. Refine only when needed; deterministic "
        "queue rank is preserved."
    )
    search = st.text_input(
        "Search queue",
        placeholder="Facility name, city, or PIN",
        key="queue_search",
    )
    state_options = sorted(
        value for value in index["address_state"].dropna().unique() if str(value).strip()
    )
    with st.expander("Filter queue", expanded=False):
        filter_row_one = st.columns(3, gap="medium")
        with filter_row_one[0]:
            states = st.multiselect(
                "State or region",
                state_options,
                key="queue_states",
            )
        with filter_row_one[1]:
            issue_types = st.multiselect(
                "Issue type",
                flatten_options(index["flag_types"]),
                format_func=lambda value: value.replace("_", " ").title(),
                key="queue_issue_types",
            )
        with filter_row_one[2]:
            claim_themes = st.multiselect(
                "Claim theme",
                flatten_options(index["claim_themes"]),
                key="queue_claim_themes",
            )
        filter_row_two = st.columns(3, gap="medium")
        with filter_row_two[0]:
            severities = st.multiselect(
                "Severity",
                ["high", "medium", "low"],
                format_func=str.title,
                key="queue_severities",
            )
        with filter_row_two[1]:
            review_statuses = st.multiselect(
                "Review status",
                ["unreviewed", *DECISION_STATUSES],
                format_func=status_label,
                key="queue_review_statuses",
            )
        with filter_row_two[2]:
            min_priority = st.slider(
                "Minimum priority",
                min_value=0,
                max_value=50,
                value=0,
                help="Priority combines readiness risk and leverage.",
                key="queue_min_priority",
            )
        st.button(
            "Clear all filters",
            on_click=clear_queue_filters,
            width="stretch",
        )

    filtered = filter_review_index(
        index,
        search=search,
        states=states,
        issue_types=issue_types,
        claim_themes=claim_themes,
        severities=severities,
        review_statuses=review_statuses,
        min_priority=min_priority,
    )
    st.markdown(
        (
            f'<div class="section-kicker">{len(filtered):,} of '
            f"{len(index):,} queue records match</div>"
        ),
        unsafe_allow_html=True,
    )
    if filtered.empty:
        st.warning("No records match. Clear or broaden the queue filters.")
    else:
        table = filtered.head(250)
        st.dataframe(
            table[
                [
                    "queue_rank",
                    "name",
                    "address_state",
                    "primary_issue",
                    "readiness_score",
                    "high_leverage_score",
                    "review_priority_score",
                    "high_severity_flag_count",
                    "review_status",
                ]
            ],
            hide_index=True,
            width="stretch",
            height=330,
            column_config={
                "queue_rank": "Rank",
                "name": "Facility",
                "address_state": "State",
                "primary_issue": "Primary issue",
                "readiness_score": st.column_config.ProgressColumn(
                    "Readiness", min_value=0, max_value=100, format="%.1f"
                ),
                "high_leverage_score": st.column_config.NumberColumn(
                    "Leverage", format="%.1f"
                ),
                "review_priority_score": st.column_config.NumberColumn(
                    "Priority", format="%.1f"
                ),
                "high_severity_flag_count": "High flags",
                "review_status": "Review status",
            },
        )
        if len(filtered) > 250:
            st.caption("Table previews the first 250 matches; every match remains selectable below.")
        labels = {
            row["unique_id"]: (
                f"#{int(row['queue_rank']):,} · {row['name']} · "
                f"priority {float(row['review_priority_score']):.1f}"
            )
            for _, row in filtered.iterrows()
        }
        selected_id = st.selectbox(
            "Selected review record",
            options=list(labels),
            format_func=labels.get,
        )
        summary, detail, facility_flags = get_facility_bundle(
            selected_id, index, flags
        )
        render_facility_header(summary, detail)
        if store.backend != "lakebase" and os.environ.get("PGHOST"):
            st.error(
                "Durable persistence unavailable: Lakebase is configured but "
                "unreachable, so decisions are falling back to local ephemeral "
                "storage and may not survive an app restart. "
                f"Reason: {store.backend_detail[:200]}"
            )
        if st.session_state.pop("decision_saved_for", None) == selected_id:
            st.success("Decision recorded. The queue and audit log now reflect this review.")
        current_status = str(summary.get("review_status", "unreviewed"))
        reviewed_by = summary.get("reviewed_by")
        decision_panel, context_panel = st.columns([1, 1], gap="large")
        with decision_panel:
            st.markdown(
                '<div class="section-kicker">Record reviewer decision</div>',
                unsafe_allow_html=True,
            )
            if current_status != "unreviewed":
                st.info(
                    f"Current status: **{status_label(current_status)}**"
                    + (f" · by {reviewed_by}" if pd.notna(reviewed_by) else "")
                )
            with st.form(f"decision_form_{selected_id}"):
                decision_status = st.selectbox(
                    "Decision",
                    DECISION_STATUSES,
                    format_func=status_label,
                    help="The latest decision defines the record's review status.",
                )
                reviewer_name = st.text_input(
                    "Reviewer",
                    value=st.session_state.get("reviewer_name", ""),
                    placeholder="Name or review team",
                )
                decision_note = st.text_area(
                    "Decision note",
                    placeholder=(
                        "What did you verify, override, or fail to confirm? "
                        "This note becomes part of the audit trail."
                    ),
                )
                submitted = st.form_submit_button(
                    "Record decision",
                    type="primary",
                    width="stretch",
                )
        with context_panel:
            render_review_context(summary)
        if submitted:
            store.append_decision(
                facility_id=selected_id,
                facility_name=str(detail["name"]),
                review_status=decision_status,
                reviewer=reviewer_name,
                note=decision_note,
            )
            st.session_state["reviewer_name"] = reviewer_name
            st.session_state["decision_saved_for"] = selected_id
            st.rerun()
        facility_history = decision_log[
            decision_log["facility_id"].eq(selected_id)
        ]
        if not facility_history.empty:
            with st.expander(
                f"Decision history · {len(facility_history)} entries", expanded=False
            ):
                st.dataframe(
                    facility_history[
                        ["decided_at", "review_status", "reviewer", "note"]
                    ],
                    hide_index=True,
                    width="stretch",
                )
        opinion_match = ai_opinions[ai_opinions["unique_id"].eq(selected_id)]
        with st.expander(
            f"Inspect evidence, source trail, and {len(facility_flags)} flag receipts",
            expanded=True,
        ):
            render_facility_evidence(
                detail,
                facility_flags,
                opinion_match.iloc[0] if not opinion_match.empty else None,
            )

with log_tab:
    st.markdown("## Durable reviewer audit log")
    if store.backend == "lakebase":
        st.caption(
            "Decisions persist in Lakebase across app restarts and redeploys. "
            "The latest decision defines queue status; older entries remain as history."
        )
    else:
        st.caption(
            "Local development mode: decisions persist in SQLite on this machine. "
            "A deployed submission uses Lakebase for restart-safe history."
        )
    if decision_log.empty:
        st.info(
            "No decisions recorded yet. Open a facility in the review queue and "
            "record the first decision."
        )
    else:
        st.dataframe(
            decision_log[
                [
                    "decided_at",
                    "facility_name",
                    "review_status",
                    "reviewer",
                    "note",
                ]
            ],
            hide_index=True,
            width="stretch",
            column_config={
                "decided_at": "Decided at (UTC)",
                "facility_name": "Facility",
                "review_status": "Decision",
                "reviewer": "Reviewer",
                "note": "Note",
            },
        )
        st.download_button(
            "Download decisions as CSV",
            decision_log.to_csv(index=False).encode("utf-8"),
            file_name="review_decisions.csv",
            mime="text/csv",
        )

with method_tab:
    st.markdown("## Inspectable by design")
    cols = st.columns(3, gap="large")
    method_items = [
        (
            "01 · Readiness",
            "40% completeness, 30% evidence support, and 30% consistency. "
            "Missing and empty claim lists are not treated as the same state.",
        ),
        (
            "02 · Claims vs. evidence",
            "High-acuity claims (ICU, trauma, NICU, maternity, oncology, cardiac, "
            "dialysis, surgery) are checked for operational evidence — equipment, "
            "staff, procedures — across fields. Uncorroborated claims are flagged "
            "with receipts, and evidence support stays capped at 75 until exact "
            "source spans are verified.",
        ),
        (
            "03 · Review priority",
            "75% readiness risk plus 25% high leverage. The queue favors poor "
            "data quality while still elevating records that matter to planning.",
        ),
    ]
    for column, (title, body) in zip(cols, method_items, strict=True):
        with column:
            st.markdown(
                (
                    '<div class="method-card">'
                    f"<h3>{html.escape(title)}</h3>"
                    f"<p>{html.escape(body)}</p>"
                    "</div>"
                ),
                unsafe_allow_html=True,
            )
    st.markdown("### Known limitation")
    st.info(
        "Capacity and establishment-year contradictions use narrow text patterns. "
        "They are review candidates, never automatic corrections. State/PIN checks "
        "run only when the source value is a recognized state or union territory."
    )
