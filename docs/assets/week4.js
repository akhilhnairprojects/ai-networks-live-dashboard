/* ==========================================================================
   week4.js — renders the Week 4 SUMMARY dashboard (week4.html).

   This page answers one question: "What is the live market signal doing
   RIGHT NOW, measured against the Week 1 research baseline and the Week 3
   account model?"  It reads five files:

     data/latest.json                     current live (or seeded) snapshot
     data/history.json                    one entry per completed refresh
     data/validation_report.json          the 15/12-per-topic quality gate
     data/baselines/week1_baseline.json   frozen Week 1 workbook
     data/baselines/week3_accounts.json   frozen Week 3 account scoring model

   Every number on the page carries a tooltip that explains how it was
   computed — same contract as the Week 1 live page.
   ========================================================================== */

(async () => {
  const { latest, history, validation, week1, week3 } = await Intel.load({
    latest:     "data/latest.json",
    history:    "data/history.json",
    validation: "data/validation_report.json",
    week1:      "data/baselines/week1_baseline.json",
    week3:      "data/baselines/week3_accounts.json",
  });

  if (!latest || !week1 || !week3) {
    document.getElementById("kpis").innerHTML =
      '<p class="note">Data files are missing. Run the "build-baselines" ' +
      'workflow once, then reload this page.</p>';
    return;
  }

  Intel.telemetry(document.getElementById("telemetry"), latest, validation);

  const seed = latest.data_status !== "live";
  const topicIndex = Object.fromEntries(latest.topics.map(t => [t.topic, t]));
  const w1Totals = week1.topic_totals || {};

  /* ------------------------------------------------------------------ */
  /* Shared computations                                                 */
  /* ------------------------------------------------------------------ */

  // Movers: every topic's live total vs its frozen Week 1 total.
  const movers = latest.topics.map(t => ({
    topic: t.topic,
    live: t.total,
    base: w1Totals[t.topic] ?? 0,
    delta: t.total - (w1Totals[t.topic] ?? 0),
    vsPrev: t.delta_vs_prev,
    bullets: t.bullets || [],
    reasoning: t.reasoning || "",
  })).sort((a, b) => b.delta - a.delta || b.live - a.live);

  const rising = movers.filter(m => m.delta > 0).length;

  // Quality: per-topic pass rate from the last validation run.
  const perTopic = validation?.per_topic || {};
  const qRows = Object.entries(perTopic);
  const qPassed = qRows.filter(([, r]) => r.pass).length;
  const qualityPct = qRows.length
    ? Math.round((qPassed / qRows.length) * 100) : null;

  // Industry momentum, richest first. In the seeded state every live count
  // is 0, so fall back to Week 3 account coverage for a meaningful order.
  const industries = [...(latest.industries || [])]
    .sort((a, b) => (b.count - a.count) ||
                    ((b.delta ?? 0) - (a.delta ?? 0)));
  const liveSignal = industries.some(i => i.count > 0);
  const rankedIndustries = liveSignal
    ? industries
    : [...industries].sort((a, b) =>
        (week3.industry_counts?.[b.industry] ?? 0) -
        (week3.industry_counts?.[a.industry] ?? 0));
  const focusIndustries = rankedIndustries.slice(0, 2).map(i => i.industry);

  /* ------------------------------------------------------------------ */
  /* 1. KPI strip                                                        */
  /* ------------------------------------------------------------------ */
  const kpis = [
    {
      label: "Articles this cycle",
      value: latest.totals?.articles ?? "—",
      note: seed ? "seeded from the Week 1 workbook"
                 : `${latest.totals?.outlets ?? "?"} unique outlets`,
      tip: () => ({
        title: "Articles this cycle",
        value: latest.totals?.articles,
        bullets: [
          `De-duplicated article count across all 13 topics for ${latest.month}.`,
          `Outlets contributing: ${latest.totals?.outlets ?? "—"}.`,
        ],
        why: seed
          ? "No live refresh yet — this is the Week 1 workbook restated. " +
            "Trigger the monthly-data-refresh workflow to go live."
          : "Each article is counted once even if several feeds syndicated it " +
            "(matched on normalized title).",
      }),
    },
    {
      label: "Topics above Week 1",
      value: seed ? "—" : `${rising}/13`,
      note: seed ? "awaiting first live refresh"
                 : "live total > frozen Week 1 total",
      tip: () => ({
        title: "Topics above Week 1 baseline",
        value: seed ? undefined : `${rising} of 13`,
        bullets: [
          "Compares each topic's live article total against the same topic's " +
          "count in the frozen Week 1 workbook.",
          seed ? "The seed restates Week 1, so every delta is zero by definition."
               : "See the Movers table below for the per-topic breakdown.",
        ],
        why: "Baseline totals never change after upload; only the live side moves.",
      }),
    },
    {
      label: "Data-quality gate",
      value: qualityPct === null ? "—" : qualityPct + "%",
      note: qualityPct === null
        ? "runs with the first refresh"
        : `${qPassed}/${qRows.length} topics ≥ ${validation.threshold} sources`,
      tip: () => ({
        title: "Data-quality gate",
        value: qualityPct === null ? undefined : qualityPct + "%",
        bullets: [
          "Rule: ≥15 sources per topic on the first refresh, ≥12 on every " +
          "refresh after that.",
          "A failing run exits before committing, so the site keeps serving " +
          "the last good dataset.",
        ],
        why: qualityPct === null
          ? "The gate has not run yet — it executes inside every " +
            "monthly-data-refresh."
          : `Last run: ${validation.mode} at threshold ${validation.threshold}.`,
      }),
    },
    {
      label: "Refresh cycle",
      value: "#" + (latest.refresh_number ?? 0),
      note: "next auto-run: 1st of the month, 06:17 UTC",
      tip: () => ({
        title: "Refresh cycle",
        value: latest.refresh_number,
        bullets: [
          "GitHub Actions cron fires on the 1st of every month.",
          "Each successful run appends one point to history.json — that file " +
          "feeds the momentum chart.",
        ],
        why: "Refresh #0 means only the seed exists; #1 is the first live pull.",
      }),
    },
  ];

  const kEl = document.getElementById("kpis");
  kEl.innerHTML = "";
  kpis.forEach(k => {
    const card = document.createElement("div");
    card.className = "kpi";
    card.innerHTML = `
      <div class="k-label">${Intel.esc(k.label)}</div>
      <div class="k-value">${Intel.esc(k.value)}</div>
      <div class="k-note">${Intel.esc(k.note)}</div>`;
    Intel.tip.attach(card, k.tip);
    kEl.appendChild(card);
  });

  /* ------------------------------------------------------------------ */
  /* 2. Momentum chart (history.json → Chart.js)                         */
  /* ------------------------------------------------------------------ */
  const chartNote = document.getElementById("chart-note");
  const hist = Array.isArray(history) ? history : [];

  if (typeof Chart === "undefined") {
    chartNote.textContent =
      "Chart.js could not be loaded (offline or CDN blocked). The table " +
      "below carries the same numbers.";
  } else if (hist.length < 2) {
    chartNote.textContent = hist.length === 0
      ? "The momentum chart starts drawing after the first live refresh " +
        "writes history.json."
      : "One refresh recorded — the line appears once a second point exists " +
        "(next month, or trigger the workflow manually).";
  } else {
    chartNote.textContent = "";
    const labels = hist.map(h => h.month);
    const top5 = [...latest.topics]
      .sort((a, b) => b.total - a.total).slice(0, 5).map(t => t.topic);
    const palette = ["#0E7C7B", "#1D4E89", "#2F9E62", "#DB9A2E", "#B3472F"];
    new Chart(document.getElementById("momentum-chart"), {
      type: "line",
      data: {
        labels,
        datasets: top5.map((topic, i) => ({
          label: topic,
          data: hist.map(h => h.topic_totals?.[topic] ?? 0),
          borderColor: palette[i],
          backgroundColor: palette[i],
          tension: 0.25,
          pointRadius: 3,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { position: "bottom",
                             labels: { boxWidth: 10, font: { size: 11 } } } },
        scales: {
          y: { beginAtZero: true,
               title: { display: true, text: "articles / cycle" } },
        },
      },
    });
  }

  /* ------------------------------------------------------------------ */
  /* 3. Movers table — live vs Week 1 baseline                           */
  /* ------------------------------------------------------------------ */
  const mBody = document.querySelector("#movers tbody");
  mBody.innerHTML = "";
  movers.forEach(m => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${Intel.esc(m.topic)}</td>
      <td class="num">${m.base}</td>
      <td class="num">${m.live}</td>
      <td class="num">${Intel.deltaChip(seed ? null : m.delta)}</td>`;
    Intel.tip.attach(row, () => ({
      title: m.topic,
      value: m.live,
      delta: seed ? null : m.delta,
      bullets: m.bullets.length ? m.bullets
        : ["No source bullets available for this topic yet."],
      why: (seed
        ? "Seed state: live = baseline, so the delta is suppressed. "
        : `Week 1 baseline ${m.base} → live ${m.live} ` +
          `(${m.delta >= 0 ? "+" : ""}${m.delta}). `) + m.reasoning,
    }));
    mBody.appendChild(row);
  });

  /* ------------------------------------------------------------------ */
  /* 4. Industry momentum bars                                           */
  /* ------------------------------------------------------------------ */
  const iEl = document.getElementById("industries");
  const iMax = Math.max(...industries.map(i => i.count), 1);
  iEl.innerHTML = "";
  industries.forEach(ind => {
    const row = document.createElement("div");
    row.className = "bar-row";
    const focus = focusIndustries.includes(ind.industry);
    row.innerHTML = `
      <span class="name">${Intel.esc(ind.industry)}
        <span class="cat">${week3.industry_counts?.[ind.industry] ?? 0} accts</span></span>
      <span class="bar-track"><span class="bar-fill${focus ? "" : " alt"}"
        style="width:${(ind.count / iMax) * 100}%"></span></span>
      <span class="val">${ind.count}</span>`;
    Intel.tip.attach(row, () => ({
      title: ind.industry,
      value: ind.count,
      delta: ind.delta,
      bullets: [
        `Live articles whose text matches this industry's keyword set ` +
        `(defined in pipeline/config.py).`,
        `Week 3 account book: ${week3.industry_counts?.[ind.industry] ?? 0} ` +
        `named accounts in this industry.`,
      ],
      why: focus
        ? "Highlighted: one of the top-2 momentum industries — it drives the " +
          "Account Spotlight selection below."
        : (seed
           ? "Seed state shows 0: industry tagging only runs on live articles."
           : "Counted from the same de-duplicated article pool as the topics."),
    }));
    iEl.appendChild(row);
  });

  /* ------------------------------------------------------------------ */
  /* 5. Account spotlight — Week 3 Tier 1 × live industry momentum       */
  /* ------------------------------------------------------------------ */
  const spotlight = (week3.accounts || [])
    .filter(a => a.tier === "Tier 1" && focusIndustries.includes(a.industry))
    .sort((a, b) => b.score - a.score)
    .slice(0, 8);

  document.getElementById("accounts-note").textContent =
    `Tier 1 accounts from the Week 3 model inside the two ` +
    (liveSignal ? "highest-momentum" : "largest-coverage") +
    ` industries: ${focusIndustries.join(" · ")}.` +
    (liveSignal ? "" : " (Momentum ranking activates with the first live refresh.)");

  const aBody = document.querySelector("#accounts tbody");
  aBody.innerHTML = "";
  const w = week3.model_weights || {};
  spotlight.forEach(a => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><span class="tier-1">${Intel.esc(a.account)}</span>
          <span class="cat">${Intel.esc(a.ticker || "")}</span></td>
      <td>${Intel.esc(a.industry)}</td>
      <td>${Intel.esc(a.sub_industry || "—")}</td>
      <td class="num">${a.score}</td>`;
    Intel.tip.attach(row, () => ({
      title: `${a.account} — Tier 1`,
      value: `score ${a.score}`,
      bullets: [
        `Factor scores → AI hiring ${a.ai_hiring} · AI announcements ` +
        `${a.ai_announce} · cloud ${a.cloud} · global ${a.global} · ` +
        `data centre ${a.data_centre}.`,
        `Weights (Week 3 model): hiring ${w["AI Hiring"] ?? "?"}, announce ` +
        `${w["AI Announce"] ?? "?"}, cloud ${w["Cloud"] ?? "?"}, global ` +
        `${w["Global"] ?? "?"}, DC ${w["Data Centre"] ?? "?"}.`,
      ],
      why: `Selected because "${a.industry}" is a top-2 industry by live ` +
           `article momentum this cycle and the account is Tier 1 by ` +
           `weighted score in the frozen Week 3 workbook.`,
    }));
    aBody.appendChild(row);
  });
  if (!spotlight.length) {
    aBody.innerHTML =
      '<tr><td colspan="4" class="note">No Tier 1 accounts fall inside the ' +
      "current focus industries.</td></tr>";
  }

  /* ------------------------------------------------------------------ */
  /* 6. Data-quality table                                               */
  /* ------------------------------------------------------------------ */
  const qBody = document.querySelector("#quality tbody");
  const qNote = document.getElementById("quality-note");
  qBody.innerHTML = "";
  if (!qRows.length) {
    qNote.textContent = validation?.note ||
      "The validation gate runs inside every monthly-data-refresh.";
    qBody.innerHTML =
      '<tr><td colspan="4"><span class="badge seed">SEED</span> ' +
      "No live validation yet — every topic will be checked against the " +
      "≥15-source rule on the first refresh.</td></tr>";
  } else {
    qNote.textContent =
      `Last gate: ${validation.mode} on ${String(validation.run_at || "")
        .slice(0, 16).replace("T", " ")} UTC · threshold ≥${validation.threshold}.`;
    qRows
      .sort((a, b) => a[1].sources - b[1].sources)
      .forEach(([topic, r]) => {
        const row = document.createElement("tr");
        row.innerHTML = `
          <td>${Intel.esc(topic)}</td>
          <td class="num">${r.sources}/${r.threshold}</td>
          <td class="num">${r.window_days}d</td>
          <td>${r.pass ? '<span class="badge pass">PASS</span>'
                       : '<span class="badge fail">FAIL</span>'}</td>`;
        Intel.tip.attach(row, () => ({
          title: `${topic} — quality gate`,
          value: `${r.sources} sources`,
          bullets: [
            `Needed ≥${r.threshold}; found ${r.sources} unique articles.`,
            `Lookback window auto-widened to ${r.window_days} days ` +
            `(ladder: 35 → 60 → 90).`,
          ],
          why: r.pass
            ? "Passed — the topic contributed to the committed dataset."
            : "Failed — the whole run aborted before commit, so the previous " +
              "month's data stayed live.",
        }));
        qBody.appendChild(row);
      });
  }

  /* ------------------------------------------------------------------ */
  /* 7. Executive takeaways (auto-written from the numbers above)        */
  /* ------------------------------------------------------------------ */
  const points = [];
  if (seed) {
    points.push(
      "Status: baseline seed. The page restates the Week 1 workbook; live " +
      "deltas, industry momentum and the quality gate activate on the first " +
      "monthly-data-refresh run.",
      `Week 1 anchor: ${week1.findings_count} curated findings across 13 ` +
      `topics; heaviest coverage on ${movers[0]?.topic ?? "—"}.`,
      `Week 3 anchor: ${week3.account_count} scored accounts, ` +
      `${week3.tier_counts?.["Tier 1"] ?? "?"} of them Tier 1 — the spotlight ` +
      `panel will re-rank them by live industry momentum each month.`,
    );
  } else {
    const up = movers[0], down = movers[movers.length - 1];
    if (up && up.delta > 0) points.push(
      `Fastest riser vs Week 1: ${up.topic} (+${up.delta}, now ${up.live} ` +
      `articles) — check its tooltip for the two leading sources.`);
    if (down && down.delta < 0) points.push(
      `Largest cool-down vs Week 1: ${down.topic} (${down.delta}), worth a ` +
      `manual scan before deprioritising.`);
    points.push(
      `${rising} of 13 topics run above their Week 1 baseline this cycle ` +
      `(${latest.totals.articles} articles from ${latest.totals.outlets} outlets).`);
    if (focusIndustries.length) points.push(
      `Demand-side focus: ${focusIndustries.join(" and ")} lead industry ` +
      `momentum — ${spotlight.length} Tier 1 accounts surfaced for outreach.`);
    points.push(qualityPct === 100
      ? `Data quality: all ${qRows.length} topics cleared the ` +
        `≥${validation.threshold}-source gate.`
      : `Data quality: ${qPassed}/${qRows.length} topics cleared the gate — ` +
        `inspect the FAIL rows above.`);
  }
  document.getElementById("takeaways").innerHTML =
    points.map(p => `<li>${Intel.esc(p)}</li>`).join("");

  /* ------------------------------------------------------------------ */
  document.getElementById("stamp").textContent =
    `${latest.month} · refresh #${latest.refresh_number} · Week 1 baseline: ` +
    `${week1.findings_count} findings · Week 3 model: ${week3.account_count} accounts`;
})();
