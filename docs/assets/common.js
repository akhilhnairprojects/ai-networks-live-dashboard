/* ==========================================================================
   common.js — shared plumbing for both dashboard pages.

   Exposes one global object, `Intel`, with:
     Intel.load(paths)        fetch several JSON files in parallel
     Intel.esc(text)          HTML-escape untrusted strings (article titles
                              come from the open web — ALWAYS escape them)
     Intel.heatColor(v, max)  Week 1 heat scale: paper -> teal -> route blue
     Intel.deltaChip(n)       renders +3 / -2 / 0 with the right color
     Intel.tip                the tooltip engine (mouse + keyboard)
     Intel.telemetry(...)     fills the status strip in the header
   ========================================================================== */

window.Intel = (() => {

  // ---- data loading -------------------------------------------------------
  async function load(paths) {
    const out = {};
    await Promise.all(Object.entries(paths).map(async ([key, url]) => {
      try {
        const res = await fetch(url, { cache: "no-store" });
        out[key] = res.ok ? await res.json() : null;
      } catch (err) {
        console.error("Could not load", url, err);
        out[key] = null;
      }
    }));
    return out;
  }

  // ---- safety: escape anything that came from the open web ---------------
  function esc(text) {
    return String(text ?? "")
      .replaceAll("&", "&amp;").replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;").replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  // ---- heat scale ---------------------------------------------------------
  // 0 = near-paper, mid = signal teal (#0E7C7B), max = route blue (#1D4E89).
  const STOPS = [[232, 240, 240], [14, 124, 123], [29, 78, 137]];
  function lerp(a, b, t) { return Math.round(a + (b - a) * t); }
  function heatColor(value, max) {
    if (!max || value <= 0) return "rgb(238,243,244)";
    const t = Math.min(value / max, 1);
    const [c0, c1, seg] = t < 0.5
      ? [STOPS[0], STOPS[1], t / 0.5]
      : [STOPS[1], STOPS[2], (t - 0.5) / 0.5];
    return `rgb(${lerp(c0[0], c1[0], seg)},${lerp(c0[1], c1[1], seg)},${lerp(c0[2], c1[2], seg)})`;
  }
  function heatText(value, max) {          // readable ink on light cells
    return (max && value / max > 0.45) ? "#FFFFFF" : "#101B24";
  }

  // ---- delta chip ---------------------------------------------------------
  function deltaChip(n) {
    if (n === null || n === undefined) return '<span class="delta-flat">—</span>';
    if (n > 0) return `<span class="delta-up">▲ +${n}</span>`;
    if (n < 0) return `<span class="delta-down">▼ ${n}</span>`;
    return '<span class="delta-flat">0</span>';
  }

  // ---- tooltip engine -----------------------------------------------------
  // One reusable card. Attach with:
  //   Intel.tip.attach(element, () => ({title, value, delta, bullets, why}))
  // Works on hover AND keyboard focus (elements get tabindex="0").
  const tip = (() => {
    const el = document.createElement("div");
    el.id = "tooltip";
    document.body.appendChild(el);

    function render(spec) {
      const bullets = (spec.bullets || []).slice(0, 2)
        .map(b => `<li>${esc(b)}</li>`).join("");
      el.innerHTML = `
        <div class="t-head">
          <span><b>${esc(spec.title)}</b></span>
          <span>${spec.value !== undefined ? "value " + esc(spec.value) : ""}
                ${spec.delta !== undefined && spec.delta !== null
                  ? " · Δ " + esc(spec.delta > 0 ? "+" + spec.delta : spec.delta)
                  : ""}</span>
        </div>
        ${bullets ? `<ul>${bullets}</ul>` : ""}
        ${spec.why ? `<div class="t-why">${esc(spec.why)}</div>` : ""}`;
    }

    function place(x, y) {
      const pad = 14, w = el.offsetWidth, h = el.offsetHeight;
      let left = x + pad, top = y + pad;
      if (left + w > innerWidth - 8) left = x - w - pad;
      if (top + h > innerHeight - 8) top = y - h - pad;
      el.style.left = Math.max(8, left) + "px";
      el.style.top = Math.max(8, top) + "px";
    }

    function attach(target, buildSpec) {
      target.setAttribute("tabindex", "0");
      target.addEventListener("mouseenter", e => {
        render(buildSpec()); el.classList.add("show");
        place(e.clientX, e.clientY);
      });
      target.addEventListener("mousemove", e => place(e.clientX, e.clientY));
      target.addEventListener("mouseleave", () => el.classList.remove("show"));
      target.addEventListener("focus", () => {
        render(buildSpec()); el.classList.add("show");
        const r = target.getBoundingClientRect();
        place(r.right, r.top);
      });
      target.addEventListener("blur", () => el.classList.remove("show"));
    }
    addEventListener("keydown", e => {
      if (e.key === "Escape") el.classList.remove("show");
    });
    return { attach };
  })();

  // ---- telemetry strip ----------------------------------------------------
  function nextRunText() {
    const now = new Date();
    const next = new Date(Date.UTC(now.getUTCFullYear(),
                                   now.getUTCMonth() + 1, 1, 6, 17));
    return next.toISOString().slice(0, 10) + " 06:17 UTC";
  }

  function telemetry(container, latest, validation) {
    const seed = !latest || latest.data_status !== "live";
    const vPass = validation && validation.overall_pass;
    const ledClass = seed ? "seed" : (vPass === false ? "fail" : "");
    const state = seed ? "SEED (Week 1 workbook)"
                : vPass === false ? "LAST RUN FAILED VALIDATION"
                : "LIVE";
    container.innerHTML = `
      <span class="cell"><span class="led ${ledClass}"></span><b>${state}</b></span>
      <span class="cell"><span class="label">refresh #</span><b>${esc(latest?.refresh_number ?? 0)}</b></span>
      <span class="cell"><span class="label">generated</span><b>${esc((latest?.generated_at || "").slice(0, 16).replace("T", " ")) || "—"} UTC</b></span>
      <span class="cell"><span class="label">articles</span><b>${esc(latest?.totals?.articles ?? "—")}</b></span>
      <span class="cell"><span class="label">rule</span><b>≥15 first · ≥12 after</b></span>
      <span class="cell"><span class="label">next auto-run</span><b>${nextRunText()}</b></span>`;
  }

  return { load, esc, heatColor, heatText, deltaChip, tip, telemetry };
})();
