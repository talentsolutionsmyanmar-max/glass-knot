/* Glass Knot dashboard — sticky policy, tape, knot expansion, grade chips, api_calls */

const $ = (id) => document.getElementById(id);

function fmtUsd(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return "—";
  return "$" + n.toLocaleString(undefined, { maximumFractionDigits: 0 });
}

function shortTs(ts) {
  if (!ts) return "—";
  return String(ts).replace("T", " ").replace("Z", "").slice(11, 19);
}

function gradeChip(grade) {
  const g = grade || "FAIL";
  return `<span class="grade-chip ${g}">${g}</span>`;
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
    ["FARM_CLUSTER", g.FARM_CLUSTER ?? 0],
    ["SOLO_SM", g.SOLO_SM ?? 0],
    ["RESEARCH", g.RESEARCH ?? 0],
    ["FAIL", g.FAIL ?? 0],
    ["API calls", calls],
  ];
  $("stats").innerHTML = items
    .map(
      ([k, v]) =>
        `<div class="stat"><div class="k">${k}</div><div class="v">${v}</div></div>`
    )
    .join("");
}

function renderTape(data) {
  const tape = data.tape || [];
  $("tape-count").textContent = `${tape.length} rows`;
  if (!tape.length) {
    $("tape").innerHTML = `<div class="empty">No SM tape yet.</div>`;
    return;
  }
  $("tape").innerHTML = tape
    .map((t) => {
      return `<div class="row">
        <div class="ts">${shortTs(t.ts)}</div>
        <div class="main">
          <div class="title">${t.bought || "?"} ← ${t.sold || "?"} · ${t.trader_label || "SM"}</div>
          <div class="meta">${t.trader_short || "?"} · ${t.tx ? String(t.tx).slice(0, 18) + "…" : ""}</div>
        </div>
        <div class="usd">${fmtUsd(t.value_usd)}</div>
      </div>`;
    })
    .join("");
}

function renderGradeSummary(data) {
  const knots = data.knots || [];
  if (!knots.length) {
    $("grade-summary").innerHTML = `<div class="empty">No knots graded.</div>`;
    return;
  }
  $("grade-summary").innerHTML = knots
    .map((k) => {
      return `<div class="row">
        <div class="ts">${k.related_count ?? 0} rel</div>
        <div class="main">
          <div class="title">${gradeChip(k.grade)} ${k.seed_short || ""}</div>
          <div class="meta">${k.seed_trade_label || ""} · nodes ${k.node_count || 0} · edges ${k.edge_count || 0}</div>
        </div>
        <div class="usd">${fmtUsd(k.sample_trade && k.sample_trade.value_usd)}</div>
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
            `<div><span class="depth">d${n.depth}</span> ${n.address_short || n.address} · ${n.role}</div>`
        )
        .join("");
      const edges = (k.edges || [])
        .slice(0, 40)
        .map((e) => {
          const a = String(e.from || "").slice(0, 6);
          const b = String(e.to || "").slice(0, 6);
          return `<div>${a}… → ${b}…</div>`;
        })
        .join("");
      const notes = (k.grade_notes || [])
        .map((n) => `<li>${n}</li>`)
        .join("");
      const sample = k.sample_trade || {};
      return `<div class="knot" data-idx="${idx}">
        <div class="knot-head" role="button" tabindex="0">
          <div class="left">
            ${gradeChip(k.grade)}
            <span class="addr">${k.seed_short || k.seed_address}</span>
            <span class="hint">${k.seed_trade_label || ""} · ${sample.bought || "?"} · ${fmtUsd(sample.value_usd)}</span>
          </div>
          <span class="hint">${k.related_count || 0} related · expand</span>
        </div>
        <div class="knot-body">
          <div class="graph">
            <div>
              <h3>BFS nodes</h3>
              <div class="node-list">${nodes || "<div class='empty'>none</div>"}</div>
            </div>
            <div>
              <h3>Edges</h3>
              <div class="edge-list">${edges || "<div class='empty'>none</div>"}</div>
            </div>
          </div>
          <div style="margin-top:12px">
            <h3 style="margin:0 0 8px;font-size:11px;color:var(--muted);font-family:var(--mono);text-transform:uppercase;letter-spacing:.06em">Grade notes</h3>
            <ul class="notes">${notes || "<li>none</li>"}</ul>
          </div>
        </div>
      </div>`;
    })
    .join("");

  document.querySelectorAll(".knot-head").forEach((head) => {
    head.addEventListener("click", () => head.parentElement.classList.toggle("open"));
    head.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        head.parentElement.classList.toggle("open");
      }
    });
  });
}

function applyBanner(data) {
  const b = (data.policy && data.policy.banner) || $("policy-banner").textContent;
  $("policy-banner").textContent = b;
}

async function loadLatest() {
  const res = await fetch("/api/latest");
  if (!res.ok) throw new Error("latest " + res.status);
  const data = await res.json();
  applyBanner(data);
  renderChips(data);
  renderStats(data);
  renderTape(data);
  renderGradeSummary(data);
  renderKnots(data);
  return data;
}

async function pollNow() {
  const btn = $("btn-poll");
  btn.disabled = true;
  try {
    const res = await fetch("/api/poll", { method: "POST" });
    if (!res.ok) throw new Error("poll " + res.status);
    const data = await res.json();
    applyBanner(data);
    renderChips(data);
    renderStats(data);
    renderTape(data);
    renderGradeSummary(data);
    renderKnots(data);
  } finally {
    btn.disabled = false;
  }
}

$("btn-refresh").addEventListener("click", () => loadLatest().catch(console.error));
$("btn-poll").addEventListener("click", () => pollNow().catch(console.error));

loadLatest().catch(console.error);
setInterval(() => loadLatest().catch(() => {}), 15000);
