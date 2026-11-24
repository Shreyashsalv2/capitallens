/* CapitalLens dashboard. Plain JS + SVG; every data string goes into the DOM with textContent. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const SVGNS = "http://www.w3.org/2000/svg";
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  const usd = (v) => {
    const s = v < 0 ? "-" : "", a = Math.abs(v);
    if (a >= 1e9) return `${s}$${(a / 1e9).toFixed(2)}bn`;
    if (a >= 1e6) return `${s}$${(a / 1e6).toFixed(2)}m`;
    if (a >= 1e3) return `${s}$${(a / 1e3).toFixed(0)}k`;
    return `${s}$${a.toFixed(0)}`;
  };
  const tick = (v) => {
    const s = v < 0 ? "-" : "", a = Math.abs(v);
    if (a >= 1e6) return `${s}$${+(a / 1e6).toFixed(1)}m`;
    if (a >= 1e3) return `${s}$${+(a / 1e3).toFixed(0)}k`;
    return `${s}$${a.toFixed(0)}`;
  };
  const signed = (v, f = usd) => (v > 0 ? "+" : v < 0 ? "−" : "") + f(Math.abs(v));
  const pct = (v, d = 0) => `${(v * 100).toFixed(d)}%`;
  const fmtDate = (d) => new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });

  function el(tag, attrs = {}, text) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function svg(tag, attrs = {}, text) {
    const n = document.createElementNS(SVGNS, tag);
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
    if (text !== undefined) n.textContent = text;
    return n;
  }
  function niceTicks(min, max, count = 5) {
    const span = max - min || 1;
    const step0 = span / count, mag = Math.pow(10, Math.floor(Math.log10(step0)));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= count) || 10 * mag;
    const out = [];
    for (let v = Math.ceil(min / step) * step; v <= max + 1e-9; v += step) out.push(Math.abs(v) < step / 1e6 ? 0 : v);
    return out;
  }

  // ---------- tooltip ----------
  function tooltip(host) {
    const t = el("div", { class: "tooltip", role: "status" });
    host.appendChild(t);
    return {
      show(x, y, head, rows) {
        t.replaceChildren(el("div", { class: "t-head" }, head));
        for (const r of rows) {
          const row = el("div", { class: "t-row" });
          if (r.color) { const k = el("span", { class: "lk" }); k.style.background = r.color; row.appendChild(k); }
          row.appendChild(el("b", {}, r.value));
          row.appendChild(el("span", {}, r.label));
          t.appendChild(row);
        }
        t.style.display = "block";
        const w = host.clientWidth, tw = t.offsetWidth;
        t.style.left = `${Math.min(Math.max(0, x + 14), w - tw)}px`;
        t.style.top = `${Math.max(0, y - 10)}px`;
      },
      hide() { t.style.display = "none"; },
    };
  }

  // ---------- back-testing chart ----------
  function renderBacktest(host, bt) {
    host.replaceChildren();
    const W = host.clientWidth, H = W < 560 ? 240 : 300;
    const m = { l: 58, r: 10, t: 10, b: 26 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b, n = bt.pnl.length;
    const lossLine = bt.var_forecast.map((v) => -v);
    let lo = Math.min(...bt.pnl, ...lossLine), hi = Math.max(...bt.pnl, 0);
    const pad = (hi - lo) * 0.06; lo -= pad; hi += pad;
    const y = (v) => m.t + ((hi - v) / (hi - lo)) * ih;
    const bw = iw / n, x = (i) => m.l + i * bw;
    const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img",
      "aria-label": `Daily P&L and VaR forecast for the last ${n} days, ${bt.exceptions} exceptions` });
    for (const v of niceTicks(lo, hi, 5)) {
      s.appendChild(svg("line", { x1: m.l, x2: W - m.r, y1: y(v), y2: y(v), stroke: v === 0 ? css("--axis") : css("--grid"), "stroke-width": 1 }));
      s.appendChild(svg("text", { x: m.l - 8, y: y(v) + 4, "text-anchor": "end" }, tick(v)));
    }
    let lastMonth = "", every = W < 560 ? 3 : 2, k = 0;
    bt.dates.forEach((d, i) => {
      const mo = d.slice(0, 7);
      if (mo !== lastMonth) {
        if (lastMonth && k % every === 0) {
          const lbl = new Date(d + "T00:00:00Z").toLocaleDateString("en-GB", { month: "short", year: "2-digit", timeZone: "UTC" });
          s.appendChild(svg("text", { x: x(i), y: H - 6, "text-anchor": "middle" }, lbl));
        }
        if (lastMonth) k++;
        lastMonth = mo;
      }
    });
    const barW = Math.max(1, bw - (bw > 3 ? 1 : 0.4));
    bt.pnl.forEach((v, i) => {
      const y0 = y(0), y1 = y(v);
      s.appendChild(svg("rect", { x: x(i), y: Math.min(y0, y1), width: barW, height: Math.max(0.5, Math.abs(y1 - y0)),
        fill: bt.hits[i] ? css("--critical") : css("--neutral-bar") }));
    });
    const path = lossLine.map((v, i) => `${i ? "L" : "M"}${(x(i) + barW / 2).toFixed(1)},${y(v).toFixed(1)}`).join("");
    s.appendChild(svg("path", { d: path, fill: "none", stroke: css("--blue"), "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    bt.hits.forEach((h, i) => {
      if (!h) return;
      const cx = x(i) + barW / 2, by = m.t + ih - 2;
      s.appendChild(svg("path", { d: `M${cx - 5},${by} L${cx + 5},${by} L${cx},${by - 8} Z`, fill: css("--critical"), stroke: css("--surface"), "stroke-width": 1.5 }));
    });
    const cross = svg("line", { y1: m.t, y2: m.t + ih, stroke: css("--ink-2"), "stroke-width": 1, visibility: "hidden" });
    s.appendChild(cross);
    const hit = svg("rect", { x: m.l, y: m.t, width: iw, height: ih, fill: "transparent", tabindex: 0, "aria-label": "Back-testing chart. Use arrow keys to step through days." });
    s.appendChild(hit);
    host.appendChild(s);
    const tip = tooltip(host);
    let cur = n - 1;
    const show = (i) => {
      cur = Math.max(0, Math.min(n - 1, i));
      const cx = x(cur) + barW / 2;
      cross.setAttribute("x1", cx); cross.setAttribute("x2", cx); cross.setAttribute("visibility", "visible");
      tip.show(cx, m.t + 10, fmtDate(bt.dates[cur]), [
        { value: usd(bt.pnl[cur]), label: "P&L", color: bt.hits[cur] ? css("--critical") : css("--neutral-bar") },
        { value: usd(-bt.var_forecast[cur]), label: "VaR forecast", color: css("--blue") },
        { value: bt.hits[cur] ? "▲ Exception" : "Within VaR", label: "" },
      ]);
    };
    hit.addEventListener("pointermove", (e) => {
      const r = s.getBoundingClientRect();
      show(Math.floor(((e.clientX - r.left) * (W / r.width) - m.l) / bw));
    });
    hit.addEventListener("pointerleave", () => { tip.hide(); cross.setAttribute("visibility", "hidden"); });
    hit.addEventListener("focus", () => show(cur));
    hit.addEventListener("blur", () => { tip.hide(); cross.setAttribute("visibility", "hidden"); });
    hit.addEventListener("keydown", (e) => {
      if (e.key === "ArrowLeft") { show(cur - 1); e.preventDefault(); }
      if (e.key === "ArrowRight") { show(cur + 1); e.preventDefault(); }
    });
  }

  // ---------- P&L histogram ----------
  function renderHistogram(host, pnl, var1, es1) {
    host.replaceChildren();
    const W = host.clientWidth, H = W < 560 ? 220 : 260;
    const m = { l: 34, r: 10, t: 22, b: 26 };
    const iw = W - m.l - m.r, ih = H - m.t - m.b;
    const lo = Math.min(...pnl), hi = Math.max(...pnl), nb = W < 560 ? 18 : 26, step = (hi - lo) / nb;
    const counts = new Array(nb).fill(0);
    for (const v of pnl) counts[Math.min(nb - 1, Math.floor((v - lo) / step))]++;
    const cmax = Math.max(...counts);
    const x = (v) => m.l + ((v - lo) / (hi - lo)) * iw;
    const y = (c) => m.t + ih - (c / cmax) * ih;
    const s = svg("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", "aria-label": "Histogram of daily P&L over the last 250 days" });
    for (const c of niceTicks(0, cmax, 4)) {
      s.appendChild(svg("line", { x1: m.l, x2: W - m.r, y1: y(c), y2: y(c), stroke: c === 0 ? css("--axis") : css("--grid") }));
      s.appendChild(svg("text", { x: m.l - 6, y: y(c) + 4, "text-anchor": "end" }, String(c)));
    }
    for (const v of niceTicks(lo, hi, W < 560 ? 3 : 5)) s.appendChild(svg("text", { x: x(v), y: H - 6, "text-anchor": "middle" }, tick(v)));
    const tip = tooltip(host);
    const slot = iw / nb, bwid = Math.min(24, slot - 2);
    counts.forEach((c, i) => {
      if (!c) return;
      const a = lo + i * step, b = a + step, bx = m.l + i * slot + (slot - bwid) / 2, top = y(c), base = m.t + ih;
      const r = Math.min(4, bwid / 2, base - top);
      const d = `M${bx},${base} V${top + r} Q${bx},${top} ${bx + r},${top} H${bx + bwid - r} Q${bx + bwid},${top} ${bx + bwid},${top + r} V${base} Z`;
      const tail = (a + b) / 2 < -var1;
      const bar = svg("path", { d, fill: tail ? css("--red") : css("--blue"), tabindex: 0 });
      const hitR = svg("rect", { x: m.l + i * slot, y: m.t, width: slot, height: ih, fill: "transparent" });
      const show = () => tip.show(bx + bwid / 2, top, `${tick(a)} to ${tick(b)}`, [{ value: `${c} day${c > 1 ? "s" : ""}`, label: tail ? "worse than VaR" : "", color: tail ? css("--red") : css("--blue") }]);
      for (const n of [hitR, bar]) { n.addEventListener("pointermove", show); n.addEventListener("pointerleave", () => tip.hide()); }
      bar.addEventListener("focus", show); bar.addEventListener("blur", () => tip.hide());
      s.appendChild(bar); s.appendChild(hitR);
    });
    for (const [v, name, anchor] of [[-var1, "VaR", "start"], [-es1, "ES", "end"]]) {
      s.appendChild(svg("line", { x1: x(v), x2: x(v), y1: m.t - 4, y2: m.t + ih, stroke: css("--ink-2"), "stroke-width": 1 }));
      const t = svg("text", { x: x(v) + (anchor === "start" ? 4 : -4), y: m.t + 6, "text-anchor": anchor }, `${name} ${usd(-v)}`);
      t.style.fill = css("--ink-2");
      s.appendChild(t);
    }
    host.insertBefore(s, host.firstChild);
  }

  // ---------- risk drivers ----------
  function renderDrivers(host, positions, measure) {
    host.replaceChildren();
    const key = measure === "svar" ? "svar_contribution" : "es_contribution";
    const rows = [...positions].sort((a, b) => b[key] - a[key]);
    const vals = rows.map((p) => p[key]);
    const lo = Math.min(0, ...vals), hi = Math.max(0, ...vals), span = hi - lo || 1;
    const zero = (-lo / span) * 100;
    for (const p of rows) {
      const v = p[key];
      const row = el("div", { class: "drow", tabindex: 0, "aria-label": `${p.desc}: ${usd(v)}` });
      const name = el("div", { class: "name" }, p.desc);
      if (String(p.id).startsWith("new")) name.appendChild(el("span", { class: "tag" }, "new"));
      const track = el("div", { class: "track" });
      const z = el("div", { class: "zero" }); z.style.left = `${zero}%`;
      const bar = el("div", { class: `bar ${v >= 0 ? "pos" : "neg"}` });
      const w = (Math.abs(v) / span) * 100;
      bar.style.left = `${v >= 0 ? zero : zero - w}%`;
      bar.style.width = `${Math.max(w, 0.4)}%`;
      track.append(z, bar);
      row.append(name, track, el("div", { class: "val" }, usd(v)));
      host.appendChild(row);
    }
  }

  // ---------- page ----------
  let REPORT = null, MEASURE = "es";
  const ZONE_COLOR = { green: "--good", amber: "--warning", red: "--critical" };
  const ZONE_ICON = { green: "●", amber: "▲", red: "■" };

  function zoneNode(zone) {
    const s = el("span", { class: "status" });
    const icon = el("span", { class: "icon", "aria-hidden": "true" }, ZONE_ICON[zone]);
    icon.style.color = css(ZONE_COLOR[zone]);
    s.append(icon, document.createTextNode(`${zone[0].toUpperCase()}${zone.slice(1)}`));
    return s;
  }

  function renderSummary(r) {
    const m = r.metrics, c = r.capital, bt = r.backtest;
    $("asof").textContent = `Market data ${fmtDate(r.data.first_date)} – ${fmtDate(r.data.last_date)} · ${r.data.days.toLocaleString("en-GB")} trading days · as of ${fmtDate(r.as_of)}`;
    $("t-capital").textContent = usd(c.total);
    $("t-rwa").textContent = `${usd(c.rwa)} risk-weighted assets`;
    $("t-var").textContent = usd(m.var_1d);
    $("t-var10").textContent = `${usd(m.var_10d)} over 10 days`;
    $("t-es").textContent = usd(m.es_1d);
    $("t-es10").textContent = `${usd(m.es_10d)} over 10 days`;
    $("t-svar").textContent = usd(m.svar_10d);
    $("t-stress").textContent = `Stress period ${fmtDate(r.stress.start)} – ${fmtDate(r.stress.end)}`;
    $("t-exc").textContent = String(bt.exceptions);
    $("t-exp").textContent = `in 250 days · ${bt.kupiec.expected.toFixed(1)} expected at 99%`;
    $("t-zone").replaceChildren(zoneNode(bt.zone));
    $("t-mult").textContent = `Capital multiplier ${bt.multiplier.toFixed(2)}`;
    $("t-pos").textContent = String(r.positions.length);
    const ex = $("explain"); ex.replaceChildren(...r.explanation.map((t) => el("li", {}, t)));

    const seg = $("segbar"); seg.replaceChildren();
    seg.setAttribute("aria-label", `VaR term ${usd(c.var_term)}, stressed-VaR term ${usd(c.svar_term)}, total ${usd(c.total)}`);
    for (const [v, col, name] of [[c.var_term, "--blue", "VaR term"], [c.svar_term, "--orange", "Stressed-VaR term"]]) {
      const b = el("div", { title: `${name}: ${usd(v)} (${pct(v / c.total)})` });
      b.style.background = css(col); b.style.flex = `${v} 1 0`;
      seg.appendChild(b);
      requestAnimationFrame(() => { if (b.clientWidth > 130) b.textContent = `${usd(v)} · ${pct(v / c.total)}`; });
    }
    $("formula").replaceChildren(
      el("div", {}, `VaR term  = max(${usd(c.var_last)}, ${c.multiplier.toFixed(2)} × ${usd(c.var_avg)})  = ${usd(c.var_term)}  (${c.var_binding} binds)`),
      el("div", {}, `sVaR term = max(${usd(c.svar_last)}, ${c.multiplier.toFixed(2)} × ${usd(c.svar_avg)}) = ${usd(c.svar_term)}  (${c.svar_binding} binds)`),
      el("div", {}, `Capital   = ${usd(c.total)}   ·   RWA = 12.5 × capital = ${usd(c.rwa)}`),
    );

    const st = $("bt-stats"); st.replaceChildren();
    const stat = (label, value) => { const s = el("span", {}, `${label} `); s.appendChild(el("b", {}, value)); st.appendChild(s); };
    stat("Exceptions:", `${bt.exceptions} of 250`);
    stat("Zone:", `${bt.zone} (multiplier ${bt.multiplier.toFixed(2)})`);
    stat("Kupiec p-value:", bt.kupiec.p_value.toFixed(2));
    stat("Christoffersen p-value:", bt.christoffersen.p_value.toFixed(2));
    const tb = $("bt-table").querySelector("tbody"); tb.replaceChildren();
    bt.hits.forEach((h, i) => {
      if (!h) return;
      const tr = el("tr");
      for (const v of [fmtDate(bt.dates[i]), usd(bt.pnl[i]), usd(-bt.var_forecast[i]), usd(-bt.pnl[i] - bt.var_forecast[i])]) tr.appendChild(el("td", {}, v));
      tb.appendChild(tr);
    });

    const bk = $("book").querySelector("tbody"); bk.replaceChildren();
    for (const p of r.positions) {
      const tr = el("tr");
      for (const v of [p.desc, p.factor_label, usd(p.exposure_usd), usd(p.standalone_var_1d), usd(p.es_contribution), usd(p.svar_contribution)]) tr.appendChild(el("td", {}, v));
      bk.appendChild(tr);
    }
    const tot = el("tr");
    for (const v of ["Book total", "", "", "", usd(m.es_1d), usd(m.svar_1d)]) tot.appendChild(el("td", { style: "font-weight:600" }, v));
    bk.appendChild(tot);
  }

  function renderCharts() {
    if (!REPORT) return;
    renderBacktest($("bt-chart"), REPORT.backtest);
    renderHistogram($("dist-chart"), REPORT.distribution.pnl, REPORT.metrics.var_1d, REPORT.metrics.es_1d);
    renderDrivers($("drivers"), REPORT.positions, MEASURE);
  }

  // ---------- what-if ----------
  const QTY_UNIT = { BRENT: "barrels", HENRYHUB: "MMBtu", EUR: "EUR", GBP: "GBP", AUD: "AUD", JPY: "JPY", INR: "INR", CAD: "CAD" };
  const DEFAULT_VOL = { EUR: 8, GBP: 9, AUD: 11, JPY: 10, INR: 5, CAD: 7, BRENT: 35, HENRYHUB: 60 };
  const PRESETS = [
    { label: "Sell a Brent 90% put (500k bbl)", t: { type: "option", factor: "BRENT", side: -1, option: "put", qty: 500000, strike: 90, vol: 35, expiry: 3 } },
    { label: "Hedge: sell $35m Brent futures", t: { type: "linear", factor: "BRENT", side: -1, notional: 35 } },
    { label: "Buy a Henry Hub 120% call (2m MMBtu)", t: { type: "option", factor: "HENRYHUB", side: 1, option: "call", qty: 2000000, strike: 120, vol: 60, expiry: 3 } },
    { label: "Add $50m long AUD/USD", t: { type: "linear", factor: "AUD", side: 1, notional: 50 } },
    { label: "Buy a EUR/USD 95% put (€20m)", t: { type: "option", factor: "EUR", side: 1, option: "put", qty: 20000000, strike: 95, vol: 8, expiry: 6 } },
  ];

  function syncForm() {
    const isOpt = $("wi-type").value === "option";
    document.querySelectorAll("#wi-form .opt").forEach((n) => { n.hidden = !isOpt; });
    document.querySelectorAll("#wi-form .lin").forEach((n) => { n.hidden = isOpt; });
    $("wi-qty-label").textContent = `Quantity (${QTY_UNIT[$("wi-factor").value]})`;
  }

  function fillForm(t) {
    $("wi-type").value = t.type; $("wi-factor").value = t.factor; $("wi-side").value = String(t.side);
    if (t.type === "linear") $("wi-notional").value = t.notional;
    else { $("wi-option").value = t.option; $("wi-qty").value = t.qty; $("wi-strike").value = t.strike; $("wi-vol").value = t.vol; $("wi-expiry").value = t.expiry; }
    syncForm();
  }

  function readTrade() {
    const side = Number($("wi-side").value), factor = $("wi-factor").value;
    if ($("wi-type").value === "linear") {
      const n = Number($("wi-notional").value);
      if (!(n > 0 && n <= 1000)) throw new Error("Size must be between 0.1 and 1,000 (USD millions).");
      return { type: "linear", factor, notional: side * n * 1e6 };
    }
    const q = Number($("wi-qty").value), k = Number($("wi-strike").value), v = Number($("wi-vol").value), e = Number($("wi-expiry").value);
    if (!(q > 0)) throw new Error("Quantity must be a positive number.");
    if (!(k >= 20 && k <= 500)) throw new Error("Strike must be between 20% and 500% of spot.");
    if (!(v >= 1 && v <= 300)) throw new Error("Implied vol must be between 1% and 300%.");
    if (!(e >= 1 && e <= 60)) throw new Error("Expiry must be between 1 and 60 months.");
    return { type: "option", factor, option: $("wi-option").value, quantity: side * q, strike_pct: k / 100, vol: v / 100, expiry_years: e / 12 };
  }

  async function runWhatIf() {
    $("wi-error").textContent = "";
    let trade;
    try { trade = readTrade(); } catch (err) { $("wi-error").textContent = err.message; return; }
    const btn = $("wi-run"); btn.disabled = true; btn.textContent = "Running…";
    $("wi-result").style.opacity = "0.5";
    try {
      const res = await fetch("/api/what-if", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ trades: [trade] }) });
      const body = await res.json();
      if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : "The trade was rejected. Check the inputs.");
      showWhatIf(body);
    } catch (err) {
      $("wi-error").textContent = err.message || "Could not reach the risk engine.";
    } finally {
      btn.disabled = false; btn.textContent = "Run what-if"; $("wi-result").style.opacity = "1";
    }
  }

  function showWhatIf(w) {
    $("wi-explain").replaceChildren(...w.explanation.map((t) => el("li", {}, t)));
    const b = w.before, a = w.after;
    const rows = [
      ["1-day VaR (99%)", b.metrics.var_1d, a.metrics.var_1d, usd],
      ["Expected Shortfall (97.5%)", b.metrics.es_1d, a.metrics.es_1d, usd],
      ["Stressed VaR (10-day)", b.metrics.svar_10d, a.metrics.svar_10d, usd],
      ["Back-testing exceptions", b.backtest.exceptions, a.backtest.exceptions, (v) => String(v)],
      ["Capital multiplier", b.backtest.multiplier, a.backtest.multiplier, (v) => v.toFixed(2)],
      ["VaR term", b.capital.var_term, a.capital.var_term, usd],
      ["Stressed-VaR term", b.capital.svar_term, a.capital.svar_term, usd],
      ["Market-risk capital", b.capital.total, a.capital.total, usd],
      ["Risk-weighted assets", b.capital.rwa, a.capital.rwa, usd],
    ];
    const tb = $("wi-table").querySelector("tbody"); tb.replaceChildren();
    for (const [name, x, y, f] of rows) {
      const d = y - x, tr = el("tr");
      tr.append(el("td", {}, name), el("td", {}, f(x)), el("td", {}, f(y)));
      const cls = Math.abs(d) < 1e-9 ? "" : d > 0 ? "up" : "down";
      const txt = Math.abs(d) < 1e-9 ? "no change" : `${d > 0 ? "▲ " : "▼ "}${f === usd ? signed(d) : (d > 0 ? "+" : "−") + f(Math.abs(d))}`;
      tr.appendChild(el("td", cls ? { class: cls } : {}, txt));
      tb.appendChild(tr);
    }
    let after = $("wi-drivers");
    if (!after) {
      const wrap = el("div", { style: "margin-top:18px" });
      wrap.appendChild(el("h3", { style: "font-size:15px;margin:0 0 4px" }, "Risk drivers after the trade (share of Expected Shortfall)"));
      after = el("div", { class: "drivers", id: "wi-drivers" });
      wrap.appendChild(after);
      $("wi-result").appendChild(wrap);
    }
    renderDrivers(after, a.positions, "es");
    $("wi-result").hidden = false;
  }

  async function init() {
    try {
      const res = await fetch("/api/summary");
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      REPORT = await res.json();
    } catch (err) {
      $("app").textContent = `The risk engine didn't respond (${err.message}). Refresh to try again.`;
      return;
    }
    $("app").remove();
    $("content").hidden = false;
    const sel = $("wi-factor");
    for (const f of REPORT.factors) sel.appendChild(el("option", { value: f.code }, f.label));
    sel.value = "BRENT";
    sel.addEventListener("change", () => { $("wi-vol").value = DEFAULT_VOL[sel.value]; syncForm(); });
    $("wi-type").addEventListener("change", syncForm);
    syncForm();
    const pr = $("presets");
    for (const p of PRESETS) {
      const btn = el("button", { type: "button" }, p.label);
      btn.addEventListener("click", () => { fillForm(p.t); runWhatIf(); });
      pr.appendChild(btn);
    }
    $("wi-form").addEventListener("submit", (e) => { e.preventDefault(); runWhatIf(); });
    document.querySelectorAll(".toggle button").forEach((b) => b.addEventListener("click", () => {
      MEASURE = b.dataset.m;
      document.querySelectorAll(".toggle button").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      $("drv-sub").textContent = MEASURE === "es"
        ? "Each position's share of Expected Shortfall: its average P&L on the book's worst days. The bars add up to the book's total."
        : `Each position's P&L in the scenario that sets stressed VaR (stress period ${fmtDate(REPORT.stress.start)} – ${fmtDate(REPORT.stress.end)}). The bars add up to the 1-day stressed VaR.`;
      renderDrivers($("drivers"), REPORT.positions, MEASURE);
    }));
    renderSummary(REPORT);
    renderCharts();
    let t;
    window.addEventListener("resize", () => { clearTimeout(t); t = setTimeout(renderCharts, 150); });
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => { renderSummary(REPORT); renderCharts(); });
  }

  init();
})();
