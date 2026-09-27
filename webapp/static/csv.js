// CSV parsing and table diffing for the results page (no dependencies).
"use strict";

function parseCSV(text) {
  const rows = [];
  let row = [], field = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') q = false;
      else field += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = "";
    } else field += c;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  const header = rows.shift() || [];
  return { header, rows: rows.filter(r => r.length > 1 || r[0] !== "") };
}

const isNum = v => v !== "" && !isNaN(Number(v));

function sameValue(a, b) {
  if (a === b) return true;
  if (isNum(a) && isNum(b)) return Math.abs(Number(a) - Number(b)) <= 1e-9 * Math.max(1, Math.abs(Number(a)));
  return false;
}

// Key each row by its first column (+ occurrence number for duplicates), compare cell by cell by column name.
function keyRows(t) {
  const seen = {};
  return t.rows.map(r => { const k = r[0]; seen[k] = (seen[k] || 0) + 1; return [k + "#" + seen[k], r]; });
}

function diffTables(cur, prev) {
  const out = { cells: new Map(), newRows: new Set(), removed: [], changedCells: 0, newCols: [] };
  if (!prev) return out;
  const pIdx = new Map(keyRows(prev));
  const pCol = new Map(prev.header.map((h, i) => [h, i]));
  out.newCols = cur.header.filter(h => !pCol.has(h));
  const curKeys = new Set();
  keyRows(cur).forEach(([k, r], ri) => {
    curKeys.add(k);
    const pr = pIdx.get(k);
    if (!pr) { out.newRows.add(ri); return; }
    cur.header.forEach((h, ci) => {
      if (!pCol.has(h)) return;
      const old = pr[pCol.get(h)] ?? "";
      if (!sameValue(r[ci] ?? "", old)) { out.cells.set(ri + ":" + ci, old); out.changedCells++; }
    });
  });
  for (const [k, r] of pIdx) if (!curKeys.has(k)) out.removed.push(r);
  return out;
}
