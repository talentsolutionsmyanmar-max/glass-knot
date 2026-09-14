/* Glass Knot dashboard — mother test, featured knot, BFS graph, proof, history */

const $ = (id) => document.getElementById(id);

let STATE = { data: null, selected: 0, open: true };

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[c]));
}

function fmtUsd(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return "$" + n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function shortTs(ts) {
  if (!ts) return "—";
  return String(ts).replace("T", " ").replace("Z", "").slice(11, 19);
}

function gradeChip(grade, extra) {
  const g = grade || "FAIL";
  return `<span class="grade-chip ${g}${extra ? " " + extra : ""}">${esc(g)}</span>`;
}

function renderChips(data) {
  const el = $("chips");
  const demo = data.demo_mode;
  const calls = (data.api_calls && data.api_calls.total) || 0;
  const target = (data.api_calls && data.api_calls.target) || 1000;
  el.innerHTML = [
    `<span class="chip policy">NO COPY-TRADE</span>`,
    demo
      ? `<span class="chip demo">DEMO MODE</span>`
      : `<span class="chip live">LIVE NANSEN</span>`,
    `<span class="chip calls">API CALLS ${calls} / ${target}</span>`,
  ].join("");
}

function renderStats(data) {
  const s = data.stats || {};
  const g = s.grades || {};
  const calls = (data.api_calls && data.api_calls.total) || 0;
  const items = [
    ["Trades", s.trade_count ?? 0],
    ["Knots", s.knot_count ?? 0],
    ["FARM", g.FARM_CLUSTER ?? 0],
    ["SOLO", g.SOLO_SM ?? 0],
    ["RESEARCH", g.RESEARCH ?? 0],
    ["FAIL", g.FAIL ?? 0],
    ["API calls", calls],
  ];
  $("stats").innerHTML = items
    .map(([k, v]) => `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`)
    .join("");
}

function selectedKnot(data) {
  const knots = data.knots || [];
  if (!knots.length) return null;
  const i = Math.max(0, Math.min(STATE.selected, knots.length - 1));
  return knots[i];
}

function renderHero(data) {
  const k = selectedKnot(data);
  const el = $("hero");
  if (!k) {
    el.innerHTML = `<div class="hero-card"><p class="empty">No knot graded yet. Run poll (demo works with no key).</p></div>`;
    return;
  }
  const g = k.grade || "FAIL";
  const conf = Number(k.confidence);
  const pct = Number.isFinite(conf) ? Math.max(0, Math.min(100, conf)) : 0;
  const sample = k.sample_trade || {};
  const token = k.token_symbol || sample.bought || "?";
  const mint = k.token_mint_short || k.token_mint || sample.bought_address || "—";
  const reason = k.reason_plain || (k.reasons && k.reasons[0]) || "Graded from related-wallet structure.";
  el.innerHTML = `<article class="hero-card ${g}">
    <div>
      <p class="hero-kicker">Featured knot · ${esc(g === "FARM_CLUSTER" ? "clustered farm" : g === "SOLO_SM" ? "sparse solo" : "inspect")}</p>
      <h3 class="hero-token">${esc(token)}</h3>
      <div class="hero-mint">mint ${esc(mint)}</div>
      <div class="hero-seed">seed <strong>${esc(k.seed_short || k.seed_address)}</strong></div>
      <div class="hero-meta">
        <div>nodes<b>${esc(k.node_count ?? 0)}</b></div>
        <div>edges<b>${esc(k.edge_count ?? 0)}</b></div>
        <div>related<b>${esc(k.related_count ?? 0)}</b></div>
      </div>
    </div>
    <div class="hero-grade">
      ${gradeChip(g, "lg")}
      <div class="ring ${g}" style="--pct:${pct}"><span>${pct}%<small>conf</small></span></div>
    </div>
    <p class="hero-reason">${esc(reason)}</p>
  </article>`;
}

function renderProof(k) {
  const box = $("proof");
  const label = $("proof-grade");
  if (!k) {
    label.textContent = "";
    box.innerHTML = `<div class="empty">Select a knot.</div>`;
    return;
  }
  label.innerHTML = gradeChip(k.grade);
  const sig = k.signals || {};
  const density = sig.density != null ? Number(sig.density).toFixed(2) : "—";
  const mintD = sig.shared_mint_density != null ? Number(sig.shared_mint_density).toFixed(2) : "—";
  const labels = (sig.labels && sig.labels.length) ? sig.labels.join(", ") : "none";
  const age = sig.token_age_days != null ? `${sig.token_age_days}d` : "—";
  const ts = sig.sample_ts ? shortTs(sig.sample_ts) : "—";
  const reasons = (k.reasons && k.reasons.length ? k.reasons : k.grade_notes || [])
    .map((r) => `<li>${esc(r)}</li>`)
    .join("");
  box.innerHTML = `
    <div class="signals">
      <div class="sig"><div class="k">Related count</div><div class="v">${esc(sig.related_count ?? k.related_count ?? 0)}</div><div class="d">farm ≥ 4 · solo ≤ 1</div></div>
      <div class="sig"><div class="k">Shared-mint density</div><div class="v">${esc(mintD)}</div><div class="d">${esc(sig.related_on_mint || 0)} related also on this mint</div></div>
      <div class="sig"><div class="k">Labels</div><div class="v" style="font-size:13px">${esc(labels)}</div><div class="d">${sig.bad_labels && sig.bad_labels.length ? "risk flags" : "no risk flags"}</div></div>
      <div class="sig"><div class="k">Timing</div><div class="v">${esc(age)}</div><div class="d">touch ${esc(ts)} · not size</div></div>
    </div>
    <ul class="reasons">${reasons || "<li>No reasons attached.</li>"}</ul>`;
}

function renderHistory(data) {
  const items = data.history || [];
  const el = $("history");
  if (!items.length) {
    el.innerHTML = `<div class="empty">No grades yet — history fills after each poll.</div>`;
    return;
  }
  const shown = items.slice().reverse();
  el.innerHTML = shown
    .map((h) => {
      return `<div class="hist">
        <div class="top">${gradeChip(h.grade)}<span class="tok">${esc(h.token || "?")}</span></div>
        <div class="meta">${esc(h.seed_short || "?")} · ${esc(h.related_count ?? 0)} rel · ${esc(h.confidence ?? "—")}%</div>
      </div>`;
    })
    .join("");
}

function renderTape(data) {
  const tape = data.tape || [];
  $("tape-count").textContent = `${tape.length} rows · secondary`;
  if (!tape.length) {
    $("tape").innerHTML = `<div class="empty">No SM tape yet.</div>`;
    return;
  }
  $("tape").innerHTML = tape
    .slice(0, 24)
    .map((t) => {
      return `<div class="row">
        <div class="ts">${esc(shortTs(t.ts))}</div>
        <div class="main">
          <div class="title">${esc(t.bought || "?")} ← ${esc(t.sold || "?")}</div>
          <div class="meta">${esc(t.trader_short || "?")} · ${esc(t.trader_label || "SM")}</div>
        </div>
        <div class="usd">${esc(fmtUsd(t.value_usd))}</div>
      </div>`;
    })
    .join("");
}

function renderKnots(data) {
  const knots = data.knots || [];
  if (!knots.length) {
    $("knots").innerHTML = `<div class="empty">No knot expansions.</div>`;
    return;
  }
  $("knots").innerHTML = knots
    .map((k, idx) => {
      const nodes = (k.nodes || [])
        .map(
          (n) =>
            `<div><span class="depth">d${esc(n.depth)}</span> ${esc(n.address_short || n.address)} · ${esc(n.role)}${n.address === k.seed_address ? " · seed" : ""}</div>`
        )
        .join("");
      const edges = (k.edges || [])
        .slice(0, 40)
        .map((e) => {
          const a = String(e.from || "").slice(0, 6);
          const b = String(e.to || "").slice(0, 6);
          return `<div>${esc(a)}… → ${esc(b)}…</div>`;
        })
        .join("");
      const sample = k.sample_trade || {};
      const token = k.token_symbol || sample.bought || "?";
      const selected = idx === STATE.selected ? " selected" : "";
      const opened = idx === STATE.selected && STATE.open ? " open" : "";
      return `<div class="knot ${esc(k.grade || "")}${selected}${opened}" data-idx="${idx}">
        <div class="knot-head" role="button" tabindex="0">
          <div class="left">
            ${gradeChip(k.grade)}
            <span class="addr">${esc(k.seed_short || k.seed_address)}</span>
            <span class="hint">${esc(token)} · ${esc(k.confidence ?? "—")}%</span>
          </div>
          <span class="hint">${esc(k.related_count || 0)} related · ${esc(k.node_count || 0)}n/${esc(k.edge_count || 0)}e</span>
        </div>
        <div class="knot-body">
          <div class="detail-grid">
            <div>
              <h3>BFS nodes</h3>
              <div class="node-list">${nodes || "<div class='empty'>none</div>"}</div>
            </div>
            <div>
              <h3>Edges</h3>
              <div class="edge-list">${edges || "<div class='empty'>none</div>"}</div>
            </div>
          </div>
        </div>
      </div>`;
    })
    .join("");

  document.querySelectorAll(".knot-head").forEach((head) => {
    const pick = () => {
      const knot = head.parentElement;
      const idx = Number(knot.getAttribute("data-idx"));
      selectKnot(idx);
    };
    head.addEventListener("click", pick);
    head.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        pick();
      }
    });
  });
}

function selectKnot(idx) {
  const data = STATE.data;
  if (!data) return;
  const knots = data.knots || [];
  if (idx < 0 || idx >= knots.length) return;
  if (STATE.selected === idx) {
    STATE.open = !STATE.open;
  } else {
    STATE.selected = idx;
    STATE.open = true;
  }
  renderHero(data);
  renderProof(knots[idx]);
  drawGraph(knots[idx]);
  renderKnots(data);
}

/* ---------- SVG BFS graph ---------- */

function hashStr(s) {
  let h = 2166136261;
  for (let i = 0; i < String(s).length; i++) {
    h ^= String(s).charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function rng(seed) {
  let x = seed || 1;
  return () => {
    x ^= x << 13; x >>>= 0;
    x ^= x >> 17;
    x ^= x << 5; x >>>= 0;
    return (x >>> 0) / 4294967296;
  };
}

function convexHull(points) {
  const pts = points.slice().sort((a, b) => a.x - b.x || a.y - b.y);
  if (pts.length < 3) return pts;
  const cross = (o, a, b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  const lower = [];
  for (const p of pts) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) lower.pop();
    lower.push(p);
  }
  const upper = [];
  for (let i = pts.length - 1; i >= 0; i--) {
    const p = pts[i];
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) upper.pop();
    upper.push(p);
  }
  lower.pop();
  upper.pop();
  return lower.concat(upper);
}

function layoutKnot(knot, w, h) {
  const nodes = (knot.nodes || []).map((n) => ({ ...n }));
  const seed = knot.seed_address;
  const grade = knot.grade;
  const pad = 36;
  if (!nodes.length) return [];
  if (nodes.length === 1) {
    nodes[0].x = w / 2;
    nodes[0].y = h / 2;
    return nodes;
  }
  const rand = rng(hashStr(seed || "knot"));
  const cluster = grade === "FARM_CLUSTER";
  const sparse = grade === "SOLO_SM" || nodes.length <= 2;
  nodes.forEach((n, i) => {
    const ang = rand() * Math.PI * 2;
    const r = (cluster ? 28 : 70) + rand() * (cluster ? 36 : 90);
    n.x = w / 2 + Math.cos(ang) * r;
    n.y = h / 2 + Math.sin(ang) * r;
    if (n.address === seed || n.role === "seed") {
      n.x = w / 2;
      n.y = h / 2;
    }
    n.vx = 0;
    n.vy = 0;
    n._i = i;
  });
  const idx = {};
  nodes.forEach((n, i) => { idx[n.address] = i; });
  const links = (knot.edges || [])
    .map((e) => ({ s: idx[e.from], t: idx[e.to] }))
    .filter((l) => l.s != null && l.t != null);
  const rest = cluster ? 52 : sparse ? 140 : 88;
  const repulse = cluster ? 1100 : sparse ? 2800 : 1800;
  for (let iter = 0; iter < 140; iter++) {
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        let dx = nodes[j].x - nodes[i].x;
        let dy = nodes[j].y - nodes[i].y;
        let d2 = dx * dx + dy * dy + 0.05;
        const f = repulse / d2;
        const d = Math.sqrt(d2);
        dx /= d; dy /= d;
        nodes[i].vx -= dx * f;
        nodes[i].vy -= dy * f;
        nodes[j].vx += dx * f;
        nodes[j].vy += dy * f;
      }
    }
    for (const l of links) {
      const a = nodes[l.s];
      const b = nodes[l.t];
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const force = (d - rest) * 0.08;
      dx /= d; dy /= d;
      a.vx += dx * force;
      a.vy += dy * force;
      b.vx -= dx * force;
      b.vy -= dy * force;
    }
    for (const n of nodes) {
      n.vx += (w / 2 - n.x) * 0.01;
      n.vy += (h / 2 - n.y) * 0.01;
      if (n.address === seed || n.role === "seed") {
        n.x = w / 2;
        n.y = h / 2;
        n.vx = 0;
        n.vy = 0;
        continue;
      }
      n.x += n.vx * 0.12;
      n.y += n.vy * 0.12;
      n.vx *= 0.6;
      n.vy *= 0.6;
      n.x = Math.max(pad, Math.min(w - pad, n.x));
      n.y = Math.max(pad, Math.min(h - pad, n.y));
    }
  }
  return nodes;
}

function drawGraph(knot) {
  const svg = $("knot-graph");
  const cap = $("graph-caption");
  const legend = $("graph-legend");
  legend.innerHTML = `<span><i class="seed"></i>seed</span><span><i class="rel"></i>related</span>`;
  if (!knot) {
    svg.innerHTML = "";
    cap.textContent = "no knot selected";
    return;
  }
  const w = 640;
  const h = 360;
  const grade = knot.grade || "RESEARCH";
  const nodes = layoutKnot(knot, w, h);
  const pos = {};
  nodes.forEach((n) => { pos[n.address] = n; });
  const seed = knot.seed_address;
  const sparse = (knot.node_count || nodes.length) <= 2;
  cap.textContent = sparse
    ? `${knot.seed_short || "seed"} · sparse ${grade}`
    : `${knot.seed_short || "seed"} · ${knot.node_count || 0} nodes · ${knot.edge_count || 0} edges · ${grade}`;

  const hullClass =
    grade === "FARM_CLUSTER" ? "hull-farm"
    : grade === "SOLO_SM" ? "hull-solo"
    : grade === "FAIL" ? "hull-fail"
    : "hull-research";

  let hull = "";
  if (!sparse && nodes.length >= 3) {
    const hp = convexHull(nodes.map((n) => ({ x: n.x, y: n.y })));
    const d = hp.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ") + " Z";
    hull = `<path class="${hullClass}" d="${d}" stroke-width="1.2" />`;
  }

  let orbits = "";
  if (sparse) {
    orbits = `<circle cx="${w / 2}" cy="${h / 2}" r="92" fill="none" stroke="#1e2a3a" stroke-dasharray="4 6" />
      <text x="${w / 2}" y="36" text-anchor="middle" fill="#8b9bb0" font-size="12" font-family="IBM Plex Mono, monospace">sparse — no related cluster</text>`;
  } else if (grade === "FARM_CLUSTER") {
    orbits = `<text x="${w / 2}" y="22" text-anchor="middle" fill="#ff9f43" font-size="12" font-family="IBM Plex Mono, monospace">clustered farm</text>`;
  }

  const edgeColor = grade === "FARM_CLUSTER" ? "rgba(255,159,67,.45)" : "rgba(110,231,255,.28)";
  const edges = (knot.edges || [])
    .map((e) => {
      const a = pos[e.from];
      const b = pos[e.to];
      if (!a || !b) return "";
      return `<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" stroke="${edgeColor}" stroke-width="1.4" />`;
    })
    .join("");

  const dots = nodes
    .map((n) => {
      const isSeed = n.address === seed || n.role === "seed";
      const r = isSeed ? 11 : 6 + Math.min(3, Number(n.depth) || 0);
      const fill = isSeed
        ? (grade === "FARM_CLUSTER" ? "#ff9f43" : grade === "SOLO_SM" ? "#5eead4" : grade === "FAIL" ? "#ff6b7a" : "#6ee7ff")
        : "#7b8da3";
      const label = esc(n.address_short || "");
      const ring = isSeed
        ? `<circle cx="${n.x.toFixed(1)}" cy="${n.y.toFixed(1)}" r="${r + 6}" fill="none" stroke="${fill}" stroke-width="1.5" opacity="0.55" />`
        : "";
      const textY = n.y + r + 12;
      const seedTag = isSeed
        ? `<text x="${n.x.toFixed(1)}" y="${(n.y - r - 10).toFixed(1)}" text-anchor="middle" fill="${fill}" font-size="10" font-family="IBM Plex Mono, monospace">SEED</text>`
        : "";
      return `${ring}${seedTag}<circle cx="${n.x.toFixed(1)}" cy="${n.y.toFixed(1)}" r="${r}" fill="${fill}" stroke="#070b10" stroke-width="1.5">
        <title>${esc(n.address)} · ${esc(n.role)} · d${esc(n.depth)}</title>
      </circle>
      <text x="${n.x.toFixed(1)}" y="${textY.toFixed(1)}" text-anchor="middle" fill="#c5d0dc" font-size="10" font-family="IBM Plex Mono, monospace">${label}</text>`;
    })
    .join("");

  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.innerHTML = `${orbits}${hull}<g>${edges}</g><g>${dots}</g>`;
}

function applyBanner(data) {
  const b = (data.policy && data.policy.banner) || $("policy-banner").textContent;
  $("policy-banner").textContent = b;
}

function paint(data) {
  STATE.data = data;
  const knots = data.knots || [];
  if (STATE.selected >= knots.length) STATE.selected = 0;
  if (STATE._booted == null) {
    const feat = knots.findIndex((k) => k.featured);
    if (feat >= 0) STATE.selected = feat;
    STATE.open = true;
    STATE._booted = true;
  }
  applyBanner(data);
  renderChips(data);
  renderStats(data);
  renderHero(data);
  renderProof(selectedKnot(data));
  drawGraph(selectedKnot(data));
  renderHistory(data);
  renderTape(data);
  renderKnots(data);
}

async function loadLatest() {
  const res = await fetch("/api/latest");
  if (!res.ok) throw new Error("latest " + res.status);
  paint(await res.json());
}

async function pollNow() {
  const btn = $("btn-poll");
  btn.disabled = true;
  try {
    const res = await fetch("/api/poll", { method: "POST" });
    if (!res.ok) throw new Error("poll " + res.status);
    paint(await res.json());
  } finally {
    btn.disabled = false;
  }
}

$("btn-refresh").addEventListener("click", () => loadLatest().catch(console.error));
$("btn-poll").addEventListener("click", () => pollNow().catch(console.error));

loadLatest().catch(console.error);
setInterval(() => loadLatest().catch(() => {}), 15000);
