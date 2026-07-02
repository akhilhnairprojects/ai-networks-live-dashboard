/* ==========================================================================
   app.js — renders the Week 1 LIVE dashboard (index.html) from
   docs/data/latest.json. Every visual element carries the inspection
   tooltip: two source bullets + the "why this value" reasoning line.
   ========================================================================== */

(async () => {
  const { latest, validation } = await Intel.load({
    latest: "data/latest.json",
    validation: "data/validation_report.json",
  });

  if (!latest) {
    document.getElementById("heatmap").innerHTML =
      '<p class="note">data/latest.json could not be loaded. Run the ' +
      '"build-baselines" workflow, then reload.</p>';
    return;
  }

  Intel.telemetry(document.getElementById("telemetry"), latest, validation);
  const topicIndex = Object.fromEntries(latest.topics.map(t => [t.topic, t]));

  /* ------------------------------------------------ 1. Trend heatmap --- */
  const SOURCE_TYPES = ["Analyst Report", "Industry News",
                        "Market Research", "Vendor (Primary)"];
  const grid = {};
  latest.heatmap.forEach(r => {
    (grid[r.topic] ??= {})[r.source_type] = r.count;
  });
  const topics = Object.keys(grid)
    .sort((a, b) => (topicIndex[b]?.total ?? 0) - (topicIndex[a]?.total ?? 0));
  const cellMax = Math.max(...latest.heatmap.map(r => r.count), 1);

  const hm = document.getElementById("heatmap");
  hm.innerHTML = "";
  const head = ["Topic", ...SOURCE_TYPES.map(s => s.replace(" (Primary)", "")),
                "Total"];
  head.forEach((h, i) => {
    const d = document.createElement("div");
    d.className = "h" + (i === 0 ? " topic-h" : "");
    d.textContent = h;
    hm.appendChild(d);
  });

  const tipForTopic = topic => () => {
    const t = topicIndex[topic] || {};
    return { title: topic, value: t.total, delta: t.delta_vs_prev,
             bullets: t.bullets, why: t.reasoning };
  };

  topics.forEach(topic => {
    const label = document.createElement("div");
    label.className = "topic-label";
    label.textContent = topic;
    Intel.tip.attach(label, tipForTopic(topic));
    hm.appendChild(label);

    SOURCE_TYPES.forEach(st => {
      const v = grid[topic][st] ?? 0;
      const cell = document.createElement("div");
      cell.className = "cell";
      cell.textContent = v;
      cell.style.background = Intel.heatColor(v, cellMax);
      cell.style.color = Intel.heatText(v, cellMax);
      Intel.tip.attach(cell, () => {
        const t = topicIndex[topic] || {};
        return {
          title: `${topic} · ${st}`, value: v,
          bullets: t.bullets,
          why: `${v} of the topic's ${t.total ?? "?"} articles were ` +
               `classified "${st}" by publisher domain. ` + (t.reasoning || ""),
        };
      });
      hm.appendChild(cell);
    });

    const total = document.createElement("div");
    total.className = "cell total";
    total.textContent = topicIndex[topic]?.total ?? 0;
    Intel.tip.attach(total, tipForTopic(topic));
    hm.appendChild(total);
  });

  /* ------------------------------------------- 2 & 3. Bar charts ------- */
  function bars(elId, rows, nameKey, alt) {
    const el = document.getElementById(elId);
    const max = Math.max(...rows.map(r => r.count), 1);
    el.innerHTML = "";
    rows.sort((a, b) => b.count - a.count).forEach(r => {
      const row = document.createElement("div");
      row.className = "bar-row";
      row.innerHTML = `
        <span class="name">${Intel.esc(r[nameKey])}
          <span class="cat">${Intel.esc(r.category || "")}</span></span>
        <span class="bar-track"><span class="bar-fill${alt ? " alt" : ""}"
          style="width:${(r.count / max) * 100}%"></span></span>
        <span class="val">${r.count}</span>`;
      Intel.tip.attach(row, () => ({
        title: r[nameKey], value: r.count, delta: r.delta,
        bullets: [
          `Category: ${r.category || "—"}`,
          `Counted once per unique article whose title or snippet mentions ` +
          `“${r[nameKey]}” (or a configured alias).`,
        ],
        why: r.delta === null || r.delta === undefined
          ? "No previous refresh to compare against yet."
          : `Change vs last refresh: ${r.delta > 0 ? "+" : ""}${r.delta}. ` +
            `Counts come from the same de-duplicated article pool as the heatmap.`,
      }));
      el.appendChild(row);
    });
  }
  bars("keywords", latest.keywords, "keyword", false);
  bars("vendors", latest.vendors, "vendor", true);

  /* ------------------------------------------------ 4. Top 10 trends --- */
  const tbody = document.querySelector("#trends tbody");
  tbody.innerHTML = "";
  latest.trends.forEach(tr => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td><span class="rank-chip">${Intel.esc(tr.rank)}</span></td>
      <td><strong>${Intel.esc(tr.trend)}</strong></td>
      <td>${Intel.esc(tr.description || "")}</td>`;
    Intel.tip.attach(row, () => {
      const t = topicIndex[tr.trend];
      return {
        title: `#${tr.rank} ${tr.trend}`,
        value: t?.total,
        bullets: t?.bullets?.length ? t.bullets
                 : [tr.evidence || tr.description || ""],
        why: t?.reasoning ||
             "Baseline trend carried from the Week 1 workbook; live ranking " +
             "begins with the first refresh.",
      };
    });
    tbody.appendChild(row);
  });

  /* ------------------------------------------------------- footer ------ */
  document.getElementById("stamp").textContent =
    `${latest.month} · refresh #${latest.refresh_number} · ` +
    `${latest.totals.articles} articles`;
})();
