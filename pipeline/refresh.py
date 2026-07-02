"""
refresh.py — the monthly engine.

Run order (also what the GitHub Actions log will show):
  1. FETCH      pull articles per topic from Google News RSS + curated feeds
  2. CLASSIFY   assign each article a source type by publisher domain
  3. COUNT      topic x source-type heatmap, keywords, vendors, industries
  4. SUMMARIZE  2 tooltip bullets + a "why this value" line per topic
  5. VALIDATE   enforce the >=15 (first run) / >=12 (repeat) sources-per-topic
                rule, widening the lookback window 35 -> 60 -> 90 days
  6. WRITE      docs/data/latest.json, monthly archive, history.json,
                validation_report.json, and latest_data.xlsx (Tableau source)

If validation fails after every window, the script exits with code 1.
The workflow then stops BEFORE the commit step, so the previous month's
good data stays live on the site. Nothing half-validated ever publishes.

No API keys. Google News RSS and the curated feeds are public endpoints.
"""

import json
import re
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import feedparser
import requests

import config

# Repo root = one level up from this file, so the script works no matter
# which directory the Actions runner starts in.
ROOT = Path(__file__).resolve().parent.parent
NOW = datetime.now(timezone.utc)
MONTH_KEY = NOW.strftime("%Y-%m")

GOOGLE_NEWS_URL = ("https://news.google.com/rss/search"
                   "?q={query}&hl=en-US&gl=US&ceid=US:en")


# ===========================================================================
# STEP 1 — FETCH
# ===========================================================================

def http_get(url: str) -> bytes | None:
    """One polite HTTP GET. Returns None on any failure instead of crashing —
    a single dead feed must never take down the whole refresh."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": config.USER_AGENT},
            timeout=config.REQUEST_TIMEOUT_SECONDS,
        )
        if resp.status_code == 200:
            return resp.content
        print(f"    ! HTTP {resp.status_code} for {url[:90]}")
    except requests.RequestException as exc:
        print(f"    ! request failed ({exc.__class__.__name__}) for {url[:90]}")
    return None


def parse_feed(raw: bytes, fallback_source: str = "") -> list[dict]:
    """Turn raw RSS/Atom bytes into a clean list of article dicts."""
    parsed = feedparser.parse(raw)
    articles = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        if not title:
            continue
        # Google News puts the real publisher in entry.source.title.
        source = ""
        if entry.get("source") and entry.source.get("title"):
            source = entry.source.title.strip()
        source = source or fallback_source or "Unknown"
        published = None
        stamp = entry.get("published_parsed") or entry.get("updated_parsed")
        if stamp:
            published = datetime(*stamp[:6], tzinfo=timezone.utc)
        articles.append({
            "title": title,
            "link": (entry.get("link") or "").strip(),
            "source": source,
            "published": published,
            "snippet": re.sub(r"<[^>]+>", " ",
                              entry.get("summary", ""))[:400].strip(),
        })
    return articles


def normalize_title(title: str) -> str:
    """Deduplication key: lowercase, accents stripped, punctuation removed.
    The same story syndicated to three outlets should count once."""
    t = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-z0-9 ]", "", t.lower())
    return re.sub(r"\s+", " ", t).strip()


def fetch_google_news(query: str, window_days: int) -> list[dict]:
    """Google News RSS supports a `when:Nd` operator that limits results to
    the last N days — that is how the lookback window is enforced upstream."""
    q = quote_plus(f"{query} when:{window_days}d")
    raw = http_get(GOOGLE_NEWS_URL.format(query=q))
    time.sleep(config.SECONDS_BETWEEN_REQUESTS)
    return parse_feed(raw, "Google News") if raw else []


def fetch_curated_feeds() -> list[dict]:
    """Pull every outlet named in the internship brief once. Failures are
    logged and skipped; these feeds are a supplement, not a dependency."""
    items = []
    for name, url in config.CURATED_FEEDS:
        raw = http_get(url)
        time.sleep(config.SECONDS_BETWEEN_REQUESTS)
        if raw:
            got = parse_feed(raw, name)
            print(f"    curated feed ok: {name} ({len(got)} items)")
            items.extend(got)
        else:
            print(f"    curated feed skipped: {name}")
    return items


def within_window(article: dict, window_days: int) -> bool:
    """Undated articles are kept — Google News already windowed them with
    `when:Nd`, and dropping them would undercount real coverage."""
    if article["published"] is None:
        return True
    return article["published"] >= NOW - timedelta(days=window_days)


def collect_topic(topic: str, spec: dict, curated: list[dict],
                  window_days: int) -> list[dict]:
    """All unique articles for one topic within one lookback window."""
    pool: dict[str, dict] = {}

    for query in spec["queries"]:
        for art in fetch_google_news(query, window_days):
            if within_window(art, window_days):
                pool.setdefault(normalize_title(art["title"]), art)

    # Curated-feed articles join a topic when a match term appears.
    terms = [t.lower() for t in spec["match_terms"]]
    for art in curated:
        text = f'{art["title"]} {art["snippet"]}'.lower()
        if any(term in text for term in terms) and within_window(art, window_days):
            pool.setdefault(normalize_title(art["title"]), art)

    return list(pool.values())


# ===========================================================================
# STEP 2 — CLASSIFY
# ===========================================================================

def classify_source_type(article: dict) -> str:
    """Map the publisher to one of the four Week 1 heatmap columns.
    Checks the link's domain first, then the publisher name."""
    domain = urlparse(article["link"]).netloc.lower()
    haystack = f'{domain} {article["source"].lower()}'
    for source_type, domains in config.SOURCE_TYPE_DOMAINS.items():
        for d in domains:
            if d.split(".")[0] in haystack:
                return source_type
    return config.DEFAULT_SOURCE_TYPE


# ===========================================================================
# STEP 3 — COUNT
# ===========================================================================

def text_of(article: dict) -> str:
    return f'{article["title"]} {article["snippet"]}'.lower()


def count_aliased(articles: list[dict], spec_map: dict) -> dict[str, int]:
    """Generic counter for KEYWORDS and VENDORS: an article counts once per
    term when any alias appears (or all of `require_all`, if set)."""
    counts = {name: 0 for name in spec_map}
    for art in articles:
        text = text_of(art)
        for name, spec in spec_map.items():
            need_all = spec.get("require_all")
            if need_all:
                if all(term in text for term in need_all):
                    counts[name] += 1
            elif any(alias in text for alias in spec["aliases"]):
                counts[name] += 1
    return counts


def count_industries(articles: list[dict]) -> dict[str, int]:
    counts = {name: 0 for name in config.INDUSTRIES}
    for art in articles:
        text = text_of(art)
        for industry, terms in config.INDUSTRIES.items():
            if any(term in text for term in terms):
                counts[industry] += 1
    return counts


# ===========================================================================
# STEP 4 — SUMMARIZE (this is what the hover tooltips display)
# ===========================================================================

SOURCE_TYPE_WEIGHT = {"Analyst Report": 3, "Market Research": 2,
                      "Industry News": 1, "Vendor (Primary)": 1}


def rank_articles(articles: list[dict]) -> list[dict]:
    """Recency + source authority. Analyst coverage outranks a press release
    of the same age; within a tier, newer wins."""
    def score(a):
        age_days = 999
        if a["published"]:
            age_days = max((NOW - a["published"]).days, 0)
        return (SOURCE_TYPE_WEIGHT.get(classify_source_type(a), 1),
                -age_days)
    return sorted(articles, key=score, reverse=True)


def two_bullets(articles: list[dict]) -> list[str]:
    """Two bullets from the two strongest DISTINCT outlets, so the tooltip
    never shows the same publisher twice. Format: 'Outlet — headline (date)'."""
    bullets, seen_outlets = [], set()
    for art in rank_articles(articles):
        outlet = art["source"]
        if outlet.lower() in seen_outlets:
            continue
        seen_outlets.add(outlet.lower())
        date_txt = (art["published"].strftime("%b %d")
                    if art["published"] else "recent")
        headline = art["title"]
        if len(headline) > 110:
            headline = headline[:107].rstrip() + "…"
        bullets.append(f"{outlet} — {headline} ({date_txt})")
        if len(bullets) == 2:
            break
    return bullets


def reasoning_line(topic: str, articles: list[dict], window_days: int,
                   threshold: int, prev_total: int | None) -> str:
    """The 'why is this value what it is' sentence for the tooltip."""
    outlets = {a["source"] for a in articles}
    top3 = [o for o, _ in sorted(
        ((o, sum(1 for a in articles if a["source"] == o)) for o in outlets),
        key=lambda kv: -kv[1])][:3]
    delta = ""
    if prev_total is not None:
        diff = len(articles) - prev_total
        delta = f" Change vs last refresh: {diff:+d}."
    return (f"Value = {len(articles)} unique articles from {len(outlets)} "
            f"distinct outlets in the last {window_days} days "
            f"(rule: ≥{threshold}).{delta} "
            f"Leading outlets: {', '.join(top3) if top3 else 'n/a'}.")


def top_cooccurring_keyword(articles: list[dict]) -> str:
    counts = count_aliased(articles, config.KEYWORDS)
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    return ranked[0][0] if ranked and ranked[0][1] > 0 else "—"


# ===========================================================================
# STEP 5 — VALIDATE
# ===========================================================================

def load_json(path: Path, default):
    if path.exists():
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    return default


def required_threshold(history: list) -> tuple[int, bool]:
    """First live refresh must reach 15 sources per topic; every refresh
    after that must reach 12. History length is the ground truth."""
    first = len(history) == 0
    return (config.MIN_SOURCES_FIRST_REFRESH if first
            else config.MIN_SOURCES_REPEAT_REFRESH), first


def validate_payload(payload: dict) -> list[str]:
    """Schema + sanity gate. Returns a list of problems (empty = pass)."""
    problems = []
    for key in ("generated_at", "month", "heatmap", "topics", "keywords",
                "vendors", "industries", "trends", "totals"):
        if key not in payload:
            problems.append(f"missing key: {key}")
    if payload.get("totals", {}).get("articles", 0) <= 0:
        problems.append("zero articles collected overall")
    if len(payload.get("topics", [])) != len(config.TOPICS):
        problems.append("topic count drifted from config")
    return problems


# ===========================================================================
# STEP 6 — WRITE
# ===========================================================================

def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False, default=str)
    print(f"    wrote {path.relative_to(ROOT)}")


def write_excel(payload: dict, per_topic_articles: dict) -> None:
    """Mirror the Week 1 workbook layout so Tableau (or the manager) can
    point at one auto-refreshing file: docs/data/latest_data.xlsx."""
    import pandas as pd
    from openpyxl.styles import Font

    xlsx_path = ROOT / config.LATEST_XLSX
    articles_rows = []
    for topic, arts in per_topic_articles.items():
        for a in arts:
            articles_rows.append({
                "Topic": topic,
                "Source_Type": classify_source_type(a),
                "Source_Name": a["source"],
                "Pub_Date": a["published"].date().isoformat()
                            if a["published"] else "",
                "Title": a["title"],
                "Source_URL": a["link"],
            })

    sheets = {
        "Articles": pd.DataFrame(articles_rows),
        "Topic_Source_Heatmap": pd.DataFrame(payload["heatmap"]),
        "Keyword_Frequency": pd.DataFrame(payload["keywords"]),
        "Vendor_Mentions": pd.DataFrame(payload["vendors"]),
        "Industry_Mentions": pd.DataFrame(payload["industries"]),
        "Top10_Trends": pd.DataFrame(payload["trends"]),
    }
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
        for ws in writer.book.worksheets:          # consistent, professional
            for cell in ws[1]:
                cell.font = Font(name="Arial", bold=True)
            for row in ws.iter_rows(min_row=2):
                for cell in row:
                    cell.font = Font(name="Arial")
    print(f"    wrote {xlsx_path.relative_to(ROOT)}")


# ===========================================================================
# MAIN
# ===========================================================================

def main() -> int:
    print(f"== Monthly refresh started {NOW.isoformat()} ==")
    history = load_json(ROOT / config.HISTORY_JSON, [])
    threshold, first_run = required_threshold(history)
    prev_totals = history[-1]["topic_totals"] if history else None
    print(f"   mode: {'FIRST refresh' if first_run else 'repeat refresh'} "
          f"-> threshold {threshold} sources/topic")

    print("-- STEP 1/2: fetching curated feeds")
    curated = fetch_curated_feeds()

    per_topic_articles: dict[str, list[dict]] = {}
    window_used: dict[str, int] = {}

    for topic, spec in config.TOPICS.items():
        articles = []
        for window in config.LOOKBACK_WINDOWS_DAYS:
            print(f"-- fetching '{topic}' (window {window}d)")
            articles = collect_topic(topic, spec, curated, window)
            print(f"    {len(articles)} unique articles")
            if len(articles) >= threshold:
                window_used[topic] = window
                break
        else:
            window_used[topic] = config.LOOKBACK_WINDOWS_DAYS[-1]
        per_topic_articles[topic] = articles

    # ----- STEP 3: counts ---------------------------------------------------
    print("-- STEP 3: counting")
    heatmap = []
    for topic, arts in per_topic_articles.items():
        by_type = defaultdict(int)
        for a in arts:
            by_type[classify_source_type(a)] += 1
        for st in config.SOURCE_TYPES:
            heatmap.append({"topic": topic, "source_type": st,
                            "count": by_type.get(st, 0)})

    # One global de-duplicated pool for keyword/vendor/industry counting.
    global_pool = {normalize_title(a["title"]): a
                   for arts in per_topic_articles.values() for a in arts}
    all_articles = list(global_pool.values())

    kw_counts = count_aliased(all_articles, config.KEYWORDS)
    vendor_counts = count_aliased(all_articles, config.VENDORS)
    industry_counts = count_industries(all_articles)

    prev = history[-1] if history else {}

    def delta(current: int, prev_map_name: str, key: str):
        prev_map = prev.get(prev_map_name) or {}
        return current - prev_map[key] if key in prev_map else None

    # ----- STEP 4: summaries & trends ---------------------------------------
    print("-- STEP 4: summarizing")
    topics_out, trend_rows = [], []
    for topic, arts in per_topic_articles.items():
        prev_total = (prev_totals or {}).get(topic)
        topics_out.append({
            "topic": topic,
            "total": len(arts),
            "unique_outlets": len({a["source"] for a in arts}),
            "window_days": window_used[topic],
            "threshold": threshold,
            "delta_vs_prev": (len(arts) - prev_total
                              if prev_total is not None else None),
            "bullets": two_bullets(arts),
            "reasoning": reasoning_line(topic, arts, window_used[topic],
                                        threshold, prev_total),
            "top_keyword": top_cooccurring_keyword(arts),
        })

    for rank, t in enumerate(
            sorted(topics_out, key=lambda x: -x["total"])[:10], start=1):
        arts = per_topic_articles[t["topic"]]
        lead = arts[0]["source"] if arts else "n/a"
        trend_rows.append({
            "rank": rank,
            "trend": t["topic"],
            "description": (f'{t["total"]} articles across '
                            f'{t["unique_outlets"]} outlets this window; '
                            f'leading theme: {t["top_keyword"]}.'),
            "evidence": t["bullets"][0] if t["bullets"] else lead,
        })

    payload = {
        "generated_at": NOW.isoformat(),
        "month": MONTH_KEY,
        "refresh_number": len(history) + 1,
        "data_status": "live",
        "heatmap": heatmap,
        "topics": topics_out,
        "keywords": [{"keyword": k, "category": v["category"],
                      "count": kw_counts[k],
                      "delta": delta(kw_counts[k], "keyword_counts", k)}
                     for k, v in config.KEYWORDS.items()],
        "vendors": [{"vendor": k, "category": v["category"],
                     "count": vendor_counts[k],
                     "delta": delta(vendor_counts[k], "vendor_counts", k)}
                    for k, v in config.VENDORS.items()],
        "industries": [{"industry": k, "count": c,
                        "delta": delta(c, "industry_counts", k)}
                       for k, c in industry_counts.items()],
        "trends": trend_rows,
        "totals": {"articles": len(all_articles),
                   "outlets": len({a["source"] for a in all_articles})},
    }

    # ----- STEP 5: validation ----------------------------------------------
    print("-- STEP 5: validating")
    per_topic_report, all_pass = {}, True
    for t in topics_out:
        ok = t["total"] >= threshold
        all_pass = all_pass and ok
        per_topic_report[t["topic"]] = {
            "sources": t["total"], "threshold": threshold,
            "window_days": t["window_days"], "pass": ok,
        }
        print(f'    {"PASS" if ok else "FAIL"}  {t["topic"]}: '
              f'{t["total"]}/{threshold} (window {t["window_days"]}d)')

    schema_problems = validate_payload(payload)
    for p in schema_problems:
        print(f"    FAIL schema: {p}")

    report = {
        "run_at": NOW.isoformat(), "month": MONTH_KEY,
        "mode": "first_refresh" if first_run else "repeat_refresh",
        "threshold": threshold, "per_topic": per_topic_report,
        "schema_problems": schema_problems,
        "overall_pass": all_pass and not schema_problems,
    }
    write_json(ROOT / config.VALIDATION_JSON, report)

    if not report["overall_pass"]:
        print("== VALIDATION FAILED — nothing will be committed; the "
              "previous data stays live. See validation_report.json. ==")
        return 1

    # ----- STEP 6: write ----------------------------------------------------
    print("-- STEP 6: writing outputs")
    write_json(ROOT / config.LATEST_JSON, payload)
    write_json(ROOT / config.ARCHIVE_DIR / f"{MONTH_KEY}.json", payload)

    history.append({
        "month": MONTH_KEY,
        "refresh_number": payload["refresh_number"],
        "total_articles": payload["totals"]["articles"],
        "topic_totals": {t["topic"]: t["total"] for t in topics_out},
        "keyword_counts": kw_counts,
        "vendor_counts": vendor_counts,
        "industry_counts": industry_counts,
    })
    write_json(ROOT / config.HISTORY_JSON, history)
    write_excel(payload, per_topic_articles)

    print("== Refresh complete: all topics passed validation ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
