"""
build_baselines.py — run ONCE (via the "build-baselines" workflow).

Reads the two reference workbooks in source_files/ and produces:

  docs/data/baselines/week1_baseline.json   <- Week 1 heatmap, keywords,
                                               vendors, trends, findings
  docs/data/baselines/week3_accounts.json   <- 161 scored accounts, tiers,
                                               industries, model weights
  docs/data/latest.json                     <- SEED copy of Week 1 data so
                                               the site renders instantly
                                               (replaced by the first live
                                               refresh)
  docs/data/history.json                    <- [] (empty; its length is how
                                               refresh.py knows the 15-source
                                               first-run rule still applies)
  docs/data/validation_report.json          <- seed status placeholder

Safe to re-run: it simply rebuilds the same files from the workbooks.
It never overwrites latest.json/history.json once live data exists.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import config

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source_files"
W1 = SRC / "Week1_Market_Intelligence_Dataset.xlsx"
W3 = SRC / "accounts.xlsx"


def write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False, default=str)
    print(f"wrote {path.relative_to(ROOT)}")


def clean(value):
    """NaN -> None so the JSON stays valid."""
    return None if pd.isna(value) else value


# ---------------------------------------------------------------- Week 1 --
def build_week1() -> dict:
    heat = pd.read_excel(W1, sheet_name="Topic_Source_Heatmap")
    kw = pd.read_excel(W1, sheet_name="Keyword_Frequency")
    vend = pd.read_excel(W1, sheet_name="Vendor_Mentions")
    trends = pd.read_excel(W1, sheet_name="Top10_Trends")
    log = pd.read_excel(W1, sheet_name="Findings_Log")

    heatmap = [{"topic": r["Topic"], "source_type": r["Source_Type"],
                "count": int(r["Finding_Count"])}
               for _, r in heat.dropna(subset=["Topic"]).iterrows()]

    topic_totals = {}
    for row in heatmap:
        topic_totals[row["topic"]] = (topic_totals.get(row["topic"], 0)
                                      + row["count"])

    # Two real Week 1 finding summaries per topic -> seed tooltip bullets.
    bullets_by_topic = {}
    for topic in topic_totals:
        subset = log[log["Topic"] == topic]
        picks = []
        for _, r in subset.head(2).iterrows():
            src = clean(r["Source_Name"]) or "Week 1 log"
            summary = str(clean(r["Finding_Summary"]) or "").strip()
            if len(summary) > 150:
                summary = summary[:147].rstrip() + "…"
            picks.append(f"{src} — {summary}")
        bullets_by_topic[topic] = picks

    return {
        "label": "Week 1 baseline (curated workbook)",
        "generated_from": W1.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "findings_count": int(len(log)),
        "heatmap": heatmap,
        "topic_totals": topic_totals,
        "topic_bullets": bullets_by_topic,
        "keywords": [{"keyword": r["Keyword"], "category": r["Category"],
                      "count": int(r["Mention_Count (live)"]),
                      "trend": clean(r["Trend_Direction"])}
                     for _, r in kw.dropna(subset=["Keyword"]).iterrows()],
        "vendors": [{"vendor": r["Vendor"], "category": r["Category"],
                     "count": int(r["Mention_Count (live)"])}
                    for _, r in vend.dropna(subset=["Vendor"]).iterrows()],
        "trends": [{"rank": int(r["Rank"]), "trend": r["Market Trend"],
                    "description": clean(r["One-line Description"]),
                    "evidence": clean(r["Evidence (source example)"])}
                   for _, r in trends.dropna(subset=["Rank"]).iterrows()],
    }


# ---------------------------------------------------------------- Week 3 --
def build_week3() -> dict:
    df = pd.read_excel(W3, sheet_name="Account Scoring")
    core = df.dropna(subset=["Account"])

    weights = {}
    wcols = df[["MODEL WEIGHTS", "Unnamed: 14"]].dropna(how="all")
    for _, r in wcols.iterrows():
        name, val = clean(r["MODEL WEIGHTS"]), clean(r["Unnamed: 14"])
        if name and val is not None and name != "Total":
            weights[str(name)] = float(val)

    accounts = [{
        "account": r["Account"], "ticker": clean(r["Ticker"]),
        "industry": clean(r["Industry"]),
        "sub_industry": clean(r["Sub-Industry"]),
        "ai_hiring": clean(r["AI Hiring"]),
        "ai_announce": clean(r["AI Announce"]),
        "cloud": clean(r["Cloud"]), "global": clean(r["Global"]),
        "data_centre": clean(r["Data Centre"]),
        "score": clean(r["Score"]), "tier": clean(r["Tier"]),
    } for _, r in core.iterrows()]

    return {
        "label": "Week 3 account model",
        "generated_from": W3.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model_weights": weights,
        "account_count": len(accounts),
        "tier_counts": core["Tier"].value_counts().to_dict(),
        "industry_counts": core["Industry"].value_counts().to_dict(),
        "accounts": accounts,
    }


# -------------------------------------------------------------- Seeding --
def seed_latest(week1: dict) -> dict:
    """Restructure the Week 1 baseline into the exact shape refresh.py
    produces, flagged data_status='baseline_seed'. The website therefore
    works the moment it is deployed — no waiting for the first cron run."""
    topics = []
    for topic, total in week1["topic_totals"].items():
        topics.append({
            "topic": topic, "total": total,
            "unique_outlets": None, "window_days": None,
            "threshold": config.MIN_SOURCES_FIRST_REFRESH,
            "delta_vs_prev": None,
            "bullets": week1["topic_bullets"].get(topic, []),
            "reasoning": (f"Seed value = {total} curated findings recorded in "
                          f"the Week 1 workbook. The first live refresh "
                          f"replaces this with ≥"
                          f"{config.MIN_SOURCES_FIRST_REFRESH} web sources."),
            "top_keyword": "—",
        })
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "month": "baseline",
        "refresh_number": 0,
        "data_status": "baseline_seed",
        "heatmap": week1["heatmap"],
        "topics": topics,
        "keywords": [{**k, "delta": None} for k in week1["keywords"]],
        "vendors": [{**v, "delta": None} for v in week1["vendors"]],
        "industries": [{"industry": i, "count": 0, "delta": None}
                       for i in config.INDUSTRIES],
        "trends": week1["trends"],
        "totals": {"articles": week1["findings_count"], "outlets": None},
    }


def main() -> None:
    week1, week3 = build_week1(), build_week3()
    write(ROOT / config.BASELINE_WEEK1, week1)
    write(ROOT / config.BASELINE_WEEK3, week3)

    latest = ROOT / config.LATEST_JSON
    if not latest.exists() or json.loads(
            latest.read_text(encoding="utf-8")).get("data_status") == "baseline_seed":
        write(latest, seed_latest(week1))
    else:
        print("latest.json already holds live data — left untouched")

    history = ROOT / config.HISTORY_JSON
    if not history.exists():
        write(history, [])
    else:
        print("history.json exists — left untouched")

    validation = ROOT / config.VALIDATION_JSON
    if not validation.exists():
        write(validation, {
            "run_at": datetime.now(timezone.utc).isoformat(),
            "mode": "seed", "threshold": None, "per_topic": {},
            "schema_problems": [],
            "overall_pass": None,
            "note": "No live refresh has run yet. Trigger 'monthly-data-refresh'.",
        })

    print("Baselines built. Ticker:",
          f'{week3["account_count"]} accounts /',
          f'{week1["findings_count"]} Week-1 findings loaded.')


if __name__ == "__main__":
    main()
