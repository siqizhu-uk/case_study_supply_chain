// Assumptions tab: every value in config/model.yaml, editable; "Run scenario" runs the whole model in a sandbox copy
// of the repo (runs/scenarios/<id>/repo) and shows its forecasts and changed outputs against the committed ones.
// The committed config and outputs are never written, except by the explicit "Save to config".
"use strict";

const A = { state: null, edits: {}, filter: "", onlyChanged: false, scenario: "", poll: null, open: new Set(["forecast"]) };

async function postJSON(url, body) {
  const r = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json", "X-Results-Page": "1" }, body: JSON.stringify(body) });
  const d = await r.json().catch(() => ({ error: `${r.status}` }));
  if (!r.ok) throw new Error(d.error || r.status);
  return d;
}

const fmtVal = v => v === null || v === undefined ? "null" : (typeof v === "object" ? JSON.stringify(v) : String(v));
const num = v => (v === null || v === undefined || v === "" || isNaN(Number(v))) ? null : Number(v);
const fmtNum = v => v === null ? "" : (Math.abs(v) >= 100 ? v.toFixed(1) : v.toFixed(2)).replace(/\.?0+$/, "");

function editedValue(lf) { return Object.prototype.hasOwnProperty.call(A.edits, lf.path) ? A.edits[lf.path] : lf.value; }
function isEdited(lf) { return Object.prototype.hasOwnProperty.call(A.edits, lf.path) && fmtVal(A.edits[lf.path]) !== fmtVal(lf.value); }

function inputFor(lf) {
  const v = editedValue(lf), p = esc(lf.path);
  if (lf.type === "bool") return `<input type="checkbox" class="a-in" aria-label="${p}" data-path="${p}"${v ? " checked" : ""}>`;
  const t = lf.type === "int" || lf.type === "float" ? `type="number" step="any"` : `type="text"`;
  return `<input ${t} class="a-in${lf.type === "str" ? " wide" : ""}" aria-label="${p}" data-path="${p}" value="${esc(fmtVal(v))}">`;
}

function leafRows(list, section) {
  return list.map(lf => {
    const ed = isEdited(lf);
    return `<tr class="${ed ? "a-edited" : ""}"><td class="path">${esc(lf.path.slice(section.length + 1) || lf.path)}</td>` +
           `<td>${inputFor(lf)}</td><td class="num muted" title="committed value">${esc(fmtVal(lf.value))}</td>` +
           `<td class="muted a-note">${esc(lf.note)}</td></tr>`;
  }).join("");
}

function editorHTML() {
  const q = A.filter.toLowerCase();
  const bySec = new Map();
  for (const lf of A.state.leaves) {
    if (q && !(lf.path + " " + lf.note + " " + fmtVal(lf.value)).toLowerCase().includes(q)) continue;
    if (A.onlyChanged && !isEdited(lf)) continue;
    if (!bySec.has(lf.section)) bySec.set(lf.section, []);
    bySec.get(lf.section).push(lf);
  }
  if (!bySec.size) return `<p class="muted">No assumption matches.</p>`;
  return [...bySec].map(([sec, list]) => {
    const n = list.filter(isEdited).length;
    const open = q || A.onlyChanged || A.open.has(sec) || n;
    return `<details class="card a-sec" data-sec="${esc(sec)}"${open ? " open" : ""}><summary>${esc(sec)} <span class="muted">(${list.length})</span>` +
           (n ? ` <span class="pill changed">${n} edited</span>` : "") + `</summary><div class="body">` +
           (A.state.sections[sec] ? `<p class="muted">${esc(A.state.sections[sec])}</p>` : "") +
           `<div class="tablewrap"><table><thead><tr><th>assumption</th><th>value</th><th>committed</th><th>note (from the YAML comment)</th></tr></thead>` +
           `<tbody>${leafRows(list, sec)}</tbody></table></div></div></details>`;
  }).join("");
}

function nEdits() { return A.state.leaves.filter(isEdited).length; }

function controlsHTML() {
  const run = A.state.run || {}, busy = run.state === "running", n = nEdits();
  const log = (run.log || []).length && run.state !== "done" ? `<pre class="a-log">${esc(run.log.join("\n"))}</pre>` : "";
  const secs = run.started ? Math.max(0, Math.round(Date.now() / 1000 - run.started)) : 0;
  const clock = `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}`;
  const st = busy ? `<span class="pill changed">running scenario ${esc(run.id)}… ${clock} elapsed (a run takes about 2–3 min)</span>` :
             run.state === "failed" ? `<span class="pill removed">last scenario failed (exit ${esc(run.exit_code)})</span>` :
             run.state === "done" ? `<span class="pill new">scenario ${esc(run.id)} finished</span>` : "";
  return `<div class="a-bar">
      <input id="a-name" class="filter" placeholder="scenario name (optional)">
      <button id="a-run" class="btn primary"${busy || !n ? " disabled" : ""}>Run scenario (${n} edit${n === 1 ? "" : "s"})</button>
      <button id="a-discard" class="btn"${n ? "" : " disabled"}>Discard edits</button>
      <button id="a-save" class="btn danger"${n && !busy ? "" : " disabled"} title="writes config/model.yaml and/or config/supply_graph.csv; your outputs are not re-run">Save to config…</button>
      ${st}</div>
    <p class="muted">Sandboxed: a scenario runs in a copy of the repo under <code>runs/scenarios/&lt;id&gt;/repo</code> (git-ignored). Your
      <code>config/model.yaml</code>, <code>config/supply_graph.csv</code> and every output stay as committed; only "Save to config" writes them, and even then
      nothing is re-run until you run <code>python scripts/run_all.py</code>. A scenario re-runs the whole model: about 2–3 minutes; its log streams below.</p>${log}`;
}

function intervalSVG(r) {
  const vals = [r.low_base, r.high_base, r.point_base, r.low_scen, r.high_scen, r.point_scen].map(num).filter(v => v !== null);
  if (!vals.length) return "";
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.05 || 1; lo -= pad; hi += pad;
  const W = 320, x = v => 8 + (v - lo) / (hi - lo) * (W - 16);
  const bar = (l, h, p, y, cls) => {
    const L = num(l), H = num(h), P = num(p);
    if (P === null) return "";
    return (L !== null && H !== null ? `<line x1="${x(L)}" x2="${x(H)}" y1="${y}" y2="${y}" class="${cls}" stroke-width="6" stroke-linecap="round"/>` : "") +
           `<circle cx="${x(P)}" cy="${y}" r="4.5" class="${cls}-pt"/>`;
  };
  return `<svg class="a-int" viewBox="0 0 ${W} 40" width="100%" role="img" aria-label="committed vs scenario range">` +
         bar(r.low_base, r.high_base, r.point_base, 12, "a-base") + bar(r.low_scen, r.high_scen, r.point_scen, 28, "a-scen") +
         `<text x="2" y="39" class="a-tick">${fmtNum(lo)}</text><text x="${W - 2}" y="39" text-anchor="end" class="a-tick">${fmtNum(hi)}</text></svg>`;
}

const EMBED = document.documentElement.classList.contains("embedded");   // framed by the dashboard's Predict tab: six forecasts only

function forecastsHTML(cmp, printsOnly = false) {
  const cell = (p, l, h, cls = "") => `<td class="num${cls}">${esc(fmtNum(num(p)))}<br><span class="muted a-rng">${esc(fmtNum(num(l)))}–${esc(fmtNum(num(h)))}</span></td>`;
  const delta = r => num(r.point_scen) !== null && num(r.point_base) !== null ? num(r.point_scen) - num(r.point_base) : null;
  const list = printsOnly ? cmp.forecasts.filter(r => r.group === "print") : cmp.forecasts;
  const rows = list.map((r, i) => {
    const head = r.group === "next" && (i === 0 || list[i - 1].group !== "next")
      ? `<tr><th colspan="4">Next quarter, graph-driven (edit a supply_graph.csv lag: GRg moves; GR only when a path crosses 2 quarters)</th></tr>` : "";
    const d = delta(r), dc = d === null || Math.abs(d) < 1e-9 ? "" : " chg";
    return head + `<tr><td>${esc(r.print)}<br><span class="muted">${esc(r.metric)}</span></td>` + cell(r.point_base, r.low_base, r.high_base) +
           cell(r.point_scen, r.low_scen, r.high_scen, dc) + `<td class="num${dc}">${d === null ? "" : (d > 0 ? "+" : "") + fmtNum(d)}</td></tr>`;
  }).join("");
  const table = `<div class="tablewrap"><table><thead><tr><th>forecast</th><th>committed<br><span class="muted">range</span></th><th>scenario<br><span class="muted">range</span></th><th>Δ point</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  if (printsOnly) return table;
  const plots = list.map(r => {
    const d = delta(r), moved = d !== null && Math.abs(d) >= 1e-9;
    return `<figure class="a-plot${moved ? " moved" : ""}"><figcaption>${esc(r.print)} · ${esc(r.metric)}${moved ? ` <span class="pill changed">${d > 0 ? "+" : ""}${esc(fmtNum(d))}</span>` : ""}</figcaption>${intervalSVG(r)}</figure>`;
  }).join("");
  return table +
         `<p class="muted"><span class="a-key a-base-pt"></span> committed <span class="a-key a-scen-pt"></span> scenario — point and forecast range</p><div class="a-plots">${plots}</div>`;
}

async function changedFileCard(sid, rel) {
  const name = rel.split("/").pop();
  if (/\.(png|svg)$/.test(rel)) {
    return card(name, `<div class="grid2"><figure><img src="${fileUrl(rel)}&t=${Date.now()}"><figcaption>committed</figcaption></figure>` +
      `<figure><img src="/api/scenario/file?id=${sid}&path=${encodeURIComponent(rel)}"><figcaption>scenario</figcaption></figure></div>`, { status: "changed", path: rel });
  }
  if (!rel.endsWith(".csv")) {
    return card(name, `<p class="muted">Differs from the committed version. <a target="_blank" href="/api/scenario/file?id=${sid}&path=${encodeURIComponent(rel)}">open the scenario's file ↗</a></p>`, { status: "changed", path: rel });
  }
  const [cur, prev] = await Promise.all([fetch(`/api/scenario/file?id=${sid}&path=${encodeURIComponent(rel)}`).then(r => r.text()), getText(rel)]);
  const c = parseCSV(cur), p = prev ? parseCSV(prev) : null, diff = diffTables(c, p);
  const id = "s" + Math.random().toString(36).slice(2, 9);
  return card(name, `<p class="muted">${diff.changedCells} cells differ from the committed file (hover a highlighted cell for the committed value)</p>` +
                    tableHTML(c, diff, id), { status: "changed", path: rel });
}

async function resultsHTML() {
  const sc = A.state.scenarios || [];
  if (!sc.length) return card("Scenario results", `<p class="muted">No scenario yet: edit a value above and press Run scenario.</p>`, { open: true });
  if (!sc.find(s => s.id === A.scenario)) A.scenario = sc[0].id;
  const s = sc.find(x => x.id === A.scenario);
  const pick = `<label>scenario <select id="a-pick">${sc.map(x => `<option value="${esc(x.id)}"${x.id === s.id ? " selected" : ""}>${esc(x.id)} · ${esc(x.name)} (${esc(x.state)})</option>`).join("")}</select></label>`;
  const ch = `<ul class="changes">${s.changes.map(c => `<li><span class="path">${esc(c.path)}</span>: ${esc(fmtVal(c.base))} → <b>${esc(fmtVal(c.value))}</b></li>`).join("")}</ul>` +
             `<p><button class="btn a-load" data-id="${esc(s.id)}">load these edits into the editor</button></p>`;
  if (s.state !== "done") {
    const tail = s.log_tail ? `<pre class="a-log">${esc(s.log_tail.join("\n"))}</pre>` : "";
    return card("Scenario results", pick + ch + `<p class="muted">State: ${esc(s.state)}.</p>` + tail, { open: true });
  }
  const cmp = await getJSON(`/api/scenario/compare?id=${encodeURIComponent(s.id)}`);
  if (EMBED) return card(`The six forecasts: committed vs scenario`, pick + ch + forecastsHTML(cmp, true), { open: true });
  const files = await Promise.all(cmp.changed_files.map(rel => changedFileCard(s.id, rel)));
  return card(`Scenario results: forecasts, committed vs scenario`, pick + ch + forecastsHTML(cmp), { open: true }) +
         card(`Outputs that differ from the committed run (${cmp.changed_files.length})`,
              cmp.changed_files.length ? files.join("") : `<p class="muted">No results file changed: this assumption does not reach the outputs shown on this page.</p>`,
              { open: true });
}

async function renderAssumptions(questionHTML) {
  A.state = await getJSON("/api/assumptions");
  $("#main").innerHTML = (EMBED ? "" : questionHTML) + `<div class="card"><div class="body" style="padding-top:12px">${controlsHTML()}</div></div>` +
    `<div id="a-results">${await resultsHTML()}</div>` +
    `<h3>Every assumption in <code>config/model.yaml</code> and every edge lag in <code>config/supply_graph.csv</code> (${A.state.leaves.length})</h3>` +
    `<div class="a-bar"><input id="a-filter" class="filter" placeholder="filter: path, note or value…" value="${esc(A.filter)}">` +
    `<label><input type="checkbox" id="a-only"${A.onlyChanged ? " checked" : ""}> edited only</label></div><div id="a-editor">${editorHTML()}</div>`;
  if (A.state.run && A.state.run.state === "running") startPoll();
}

function refreshEditor() { $("#a-editor").innerHTML = editorHTML(); refreshControls(); }
function refreshControls() { const c = document.querySelector(".a-bar"); if (c) c.parentElement.innerHTML = controlsHTML(); }

function startPoll() {
  if (A.poll) return;
  A.poll = setInterval(async () => {
    const st = await getJSON("/api/scenario/status").catch(() => null);
    if (!st) return;
    A.state.run = st; refreshControls();
    if (st.state !== "running") {
      clearInterval(A.poll); A.poll = null;
      A.state = await getJSON("/api/assumptions"); A.scenario = st.id;
      $("#a-results").innerHTML = await resultsHTML(); refreshControls();
      toast(st.state === "done" ? `Scenario ${st.id} finished` : `Scenario ${st.id} failed`);
    }
  }, 1500);
}

document.addEventListener("change", async e => {
  const t = e.target;
  if (t.classList.contains("a-in")) {
    const lf = A.state.leaves.find(l => l.path === t.dataset.path);
    const v = t.type === "checkbox" ? t.checked : (t.type === "number" ? (t.value === "" ? "" : Number(t.value)) : t.value);
    if (fmtVal(v) === fmtVal(lf.value)) delete A.edits[lf.path]; else A.edits[lf.path] = v;
    t.closest("tr").classList.toggle("a-edited", isEdited(lf));
    refreshControls();
  } else if (t.id === "a-only") { A.onlyChanged = t.checked; refreshEditor(); }
  else if (t.id === "a-pick") { A.scenario = t.value; $("#a-results").innerHTML = await resultsHTML(); }
});
document.addEventListener("input", e => { if (e.target.id === "a-filter") { A.filter = e.target.value; $("#a-editor").innerHTML = editorHTML(); } });
document.addEventListener("toggle", e => {
  const d = e.target;
  if (d.classList && d.classList.contains("a-sec")) d.open ? A.open.add(d.dataset.sec) : A.open.delete(d.dataset.sec);
}, true);
document.addEventListener("click", async e => {
  const id = e.target.id;
  try {
    if (id === "a-run") {
      const st = await postJSON("/api/scenario/run", { edits: A.edits, name: ($("#a-name") || {}).value || "" });
      A.state.run = st; refreshControls(); startPoll(); toast(`Scenario ${st.id} started (sandbox)`);
    } else if (id === "a-discard") { A.edits = {}; refreshEditor(); }
    else if (id === "a-save") {
      const list = A.state.leaves.filter(isEdited).map(l => `${l.path}: ${fmtVal(l.value)} → ${fmtVal(editedValue(l))}`).join("\n");
      if (!confirm(`Write these to config/model.yaml / config/supply_graph.csv?\n\n${list}\n\nYour outputs are not re-run.`)) return;
      const r = await postJSON("/api/assumptions/save", { edits: A.edits });
      A.edits = {}; toast(`Saved ${r.saved.length} assumption(s) to config`); await renderTab();
    } else if (e.target.classList.contains("a-load")) {
      const s = A.state.scenarios.find(x => x.id === e.target.dataset.id);
      A.edits = Object.fromEntries(s.changes.map(c => [c.path, c.value])); A.onlyChanged = true; refreshEditor();
    }
  } catch (err) { toast(`Not run: ${err.message}`); }
});
