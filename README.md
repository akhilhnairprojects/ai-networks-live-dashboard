# AI-Ready Networks — Live Intelligence Dashboard

A self-refreshing market-intelligence site. GitHub Actions pulls fresh
articles from Google News RSS and seven networking trade feeds on the **1st
of every month**, validates coverage (**≥15 sources per topic on the first
refresh, ≥12 after**), rebuilds the datasets — including a Tableau-friendly
`latest_data.xlsx` — and publishes everything through GitHub Pages. No
servers, no API keys, no manual steps after setup.

## Pages

| Page | What it shows |
|---|---|
| `docs/index.html` | Week 1 live board: topic × source-type heatmap, keyword and vendor bars, Top-10 trends. Hover anything for a two-bullet source digest + reasoning. |
| `docs/week4.html` | Week 4 summary: KPIs, topic momentum chart, movers vs the frozen Week 1 baseline, industry momentum, Tier-1 account spotlight from the Week 3 model, data-quality gate, auto-written takeaways. |

## Layout

```
pipeline/            Python: config, monthly refresh, baseline builder
.github/workflows/   build-baselines (run once) · monthly-refresh (cron)
source_files/        the two reference workbooks (Week 1, Week 3)
docs/                the published site (GitHub Pages serves this folder)
docs/data/           latest.json · history.json · validation_report.json
                     latest_data.xlsx · archive/ · baselines/
```

