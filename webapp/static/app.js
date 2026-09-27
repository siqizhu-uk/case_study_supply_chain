// Results page: one tab per step; reads outputs from disk through /api, highlights what changed since a chosen run,
// and re-renders by itself when a re-run rewrites the outputs (polls every 3 s).
"use strict";

const S = { data: null, tab: location.hash.slice(1) || "overview", base: "", sig: "" };
if (window.self !== window.top) document.documentElement.classList.add("embedded");   // framed by the dashboard's Predict tab
const $ = sel => document.querySelector(sel);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const fileUrl = (path, run) => `/api/file?path=${encodeURIComponent(path)}${run ? `&run=${encodeURIComponent(run)}` : ""}`;

async function getJSON(url) {
  const r = await fetch(url, { cache: "no-store" });
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}
async function getText(path, run) {
  const r = await fetch(fileUrl(path, run), { cache: "no-store" });
  return r.ok ? r.text() : null;
}

function signature(d) {
  return JSON.stringify(d.tabs.map(t => t.files.map(f => [f.path, f.mtime, f.status])));
}

function toast(msg) {
  const t = $("#toast");
  t.textContent = msg; t.hidden = false;
  clearTimeout(toast.h); toast.h = setTimeout(() => (t.hidden = true), 4000);
}

async function load(force = false) {
  let d;
  try { d = await getJSON(`/api/tabs${S.base ? `?base=${encodeURIComponent(S.base)}` : ""}`); }
  catch (e) { $("#status").textContent = "server not reachable — run python scripts/serve.py"; return; }
  const sig = signature(d);
  const changed = S.sig && sig !== S.sig;
  if (!force && !changed) return;               // nothing new on disk: leave the page alone
  if (!force && S.tab === "assumptions") { S.data = d; S.sig = sig; renderTabs(); return; }   // keep unsaved edits
  S.data = d; S.sig = sig;
  renderBaseline(); renderTabs();
  $("#status").textContent = d.baseline ? `baseline run ${d.baseline}` : "no earlier run to compare with yet";
  if (force || changed) { await renderTab(); if (changed) toast(`Outputs updated ${new Date().toLocaleTimeString()}`); }
}

function renderBaseline() {
  const sel = $("#baseline");
  const opts = S.data.runs.map(r => `<option value="${esc(r.id)}"${r.id === S.data.baseline ? " selected" : ""}>${esc(r.created)}</option>`);
  sel.innerHTML = opts.join("") || `<option>no runs yet</option>`;
}

function renderTabs() {
  $("#tabs").innerHTML = S.data.tabs.map(t =>
    `<button class="tab" role="tab" data-id="${t.id}" aria-selected="${t.id === S.tab}">${esc(t.title)}` +
    (t.n_changed ? `<span class="badge" title="files changed vs baseline">${t.n_changed}</span>` : "") + `</button>`).join("");
}

const pill = s => `<span class="pill ${s}">${s === "same" ? "unchanged" : s}</span>`;

function card(title, body, { open = false, status = "", path = "" } = {}) {
  return `<details class="card"${open ? " open" : ""}><summary>${esc(title)} ${status ? pill(status) : ""}` +
         (path ? `<span class="path">${esc(path)}</span>` : "") + `</summary><div class="body">${body}</div></details>`;
}

function renderMarkdown(md, dir) {
  const fixed = md.replace(/!\[([^\]]*)\]\((?!https?:|\/)([^)]+)\)/g, (_, alt, src) => `![${alt}](${fileUrl(dir + "/" + src)})`);
  return window.marked ? marked.parse(fixed) : `<pre>${esc(md)}</pre>`;
}

function tableHTML(cur, diff, id) {
  const head = "<tr>" + cur.header.map(h => `<th>${esc(h)}${diff.newCols.includes(h) ? " " + pill("new") : ""}</th>`).join("") + "</tr>";
  const body = cur.rows.map((r, ri) => {
    const cls = diff.newRows.has(ri) ? ' class="row-new"' : "";
    return `<tr${cls}>` + cur.header.map((_, ci) => {
      const v = r[ci] ?? "", k = ri + ":" + ci, old = diff.cells.get(k);
      const c = [isNum(v) ? "num" : "", old !== undefined ? "chg" : ""].join(" ").trim();
      return `<td${c ? ` class="${c}"` : ""}${old !== undefined ? ` title="was: ${esc(old)}"` : ""}>${esc(v)}</td>`;
    }).join("") + "</tr>";
  }).join("");
  const removed = diff.removed.map(r => `<tr class="row-removed">${r.map(v => `<td>${esc(v)}</td>`).join("")}</tr>`).join("");
  return `<input class="filter" placeholder="filter rows…" data-table="${id}">` +
         `<div class="tablewrap"><table id="${id}"><thead>${head}</thead><tbody>${body}${removed}</tbody></table></div>`;
}

async function tableCard(f, base, openIfChanged = true) {
  const text = await getText(f.path);
  if (text == null) return "";
  const cur = parseCSV(text);
  let prev = null;
  if (f.status === "changed" && base) { const p = await getText(f.path, base); if (p) prev = parseCSV(p); }
  const diff = diffTables(cur, prev);
  const note = prev ? `<p class="muted">${diff.changedCells} cells changed, ${diff.newRows.size} new rows, ${diff.removed.length} removed rows ` +
                      `(hover a highlighted cell for the old value)</p>` : "";
  const id = "t" + Math.random().toString(36).slice(2, 9);
  return card(f.name, note + tableHTML(cur, diff, id), { open: openIfChanged && f.status !== "same", status: f.status, path: f.path });
}

async function changesCard(tab) {
  const ch = tab.files.filter(f => f.status !== "same");
  const body = ch.length ? `<ul class="changes">${ch.map(f => `<li>${pill(f.status)} <span class="path">${esc(f.path)}</span></li>`).join("")}</ul>`
                         : `<p class="muted">Nothing in this tab changed against the baseline run.</p>`;
  return card(`What changed since the baseline run (${ch.length})`, body, { open: ch.length > 0 });
}

async function overviewExtra() {
  const rows = S.data.tabs.filter(t => t.n_changed).map(t =>
    `<li><a href="#${t.id}">${esc(t.title)}</a> — ${t.n_changed} file(s): ` +
    t.files.filter(f => f.status !== "same").map(f => `<span class="path">${esc(f.name)}</span>`).join(", ") + "</li>");
  return card("Changes across all steps", rows.length ? `<ul class="changes">${rows.join("")}</ul>` : `<p class="muted">No changes against the baseline run.</p>`, { open: true });
}

async function renderTab() {
  const tab = S.data.tabs.find(t => t.id === S.tab) || S.data.tabs[0];
  S.tab = tab.id;
  const base = S.data.baseline;
  const by = role => tab.files.filter(f => f.role === role);
  const parts = [];
  const readme = by("readme")[0];
  let question = tab.question;
  if (!question && readme) {
    const md = await getText(readme.path);
    const m = md && md.match(/\*\*Question\.\*\*\s*([^\n]+)/);
    question = m ? m[1] : "";
  }
  parts.push(`<p class="question"><b>${esc(tab.title)}.</b> ${esc(question)}` +
             (tab.link ? ` <a href="/dashboard" target="_blank">open the dashboard ↗</a>` : "") + "</p>");
  if (tab.id === "assumptions") return renderAssumptions(parts.join(""));   // webapp/static/assumptions.js
  if (tab.id === "overview") parts.push(await overviewExtra());
  parts.push(await changesCard(tab));
  for (const f of by("report")) {
    const md = await getText(f.path);
    const dir = f.path.split("/").slice(0, -1).join("/");
    let prevBtn = "";
    if (f.status === "changed" && base) prevBtn = `<p><button class="showprev" data-path="${esc(f.path)}" data-dir="${esc(dir)}">show the previous version of this analysis</button></p><div class="prev"></div>`;
    parts.push(card("Analysis (generated from the current data)", prevBtn + `<div class="md">${renderMarkdown(md || "", dir)}</div>`,
                    { open: true, status: f.status, path: f.path }));
  }
  for (const f of by("decisions")) parts.push(await tableCard(f, base, false).then(h => h.replace("<details class=\"card\"", "<details class=\"card\" open")));
  const figs = by("figure");
  if (figs.length) {
    parts.push(card(`Figures (${figs.length})`, `<div class="figs">` + figs.map(f =>
      `<figure><img loading="lazy" src="${fileUrl(f.path)}&t=${f.mtime}" alt="${esc(f.name)}"><figcaption>${pill(f.status)} ${esc(f.name)}</figcaption></figure>`).join("") + "</div>",
      { open: figs.some(f => f.status !== "same") || tab.id !== "overview" }));
  }
  for (const f of by("table")) parts.push(await tableCard(f, base));
  for (const f of by("config")) parts.push(await tableCard(f, base, false));
  for (const f of by("json")) parts.push(card(f.name, `<pre>${esc(await getText(f.path))}</pre>`, { status: f.status, path: f.path }));
  for (const f of by("report_extra")) parts.push(card(f.name, `<div class="md">${renderMarkdown(await getText(f.path) || "", f.path.split("/").slice(0, -1).join("/"))}</div>`, { status: f.status, path: f.path }));
  if (readme) parts.push(card("README (how this step works)", `<div class="md">${renderMarkdown(await getText(readme.path) || "", tab.folder)}</div>`, { status: readme.status, path: readme.path }));
  $("#main").innerHTML = parts.join("");
}

document.addEventListener("click", async e => {
  const t = e.target.closest(".tab");
  if (t) { S.tab = t.dataset.id; location.hash = S.tab; renderTabs(); await renderTab(); return; }
  const b = e.target.closest(".showprev");
  if (b) {
    const md = await getText(b.dataset.path, S.data.baseline);
    b.parentElement.nextElementSibling.innerHTML = `<div class="card"><div class="body md"><p class="muted">Previous version (run ${esc(S.data.baseline)}):</p>` +
      renderMarkdown(md || "", b.dataset.dir) + "</div></div>";
    b.remove();
  }
});
document.addEventListener("input", e => {
  if (!e.target.classList.contains("filter")) return;
  const q = e.target.value.toLowerCase();
  document.querySelectorAll(`#${e.target.dataset.table} tbody tr`).forEach(tr => { tr.hidden = q && !tr.textContent.toLowerCase().includes(q); });
});
$("#baseline").addEventListener("change", e => { S.base = e.target.value; load(true); });
window.addEventListener("hashchange", () => { const id = location.hash.slice(1); if (id && id !== S.tab) { S.tab = id; renderTabs(); renderTab(); } });

load(true);
setInterval(() => load(false), 3000);
