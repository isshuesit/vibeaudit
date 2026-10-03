const API_BASE = ""; // same origin - FastAPI serves this file too

// ---------- Optional companion event surface ----------
// Lightweight pub/sub so ambient add-ons (see bug.js) can observe meaningful
// events without touching audit logic. Completely inert if nothing listens.
const VibeBugBus = {
  _l: {},
  on(evt, fn) { (this._l[evt] = this._l[evt] || []).push(fn); },
  emit(evt, detail) {
    (this._l[evt] || []).forEach((fn) => { try { fn(detail); } catch (_) {} });
  },
};
window.VibeBugBus = VibeBugBus;

// ---------- Tabs ----------

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => {
      t.classList.remove("active");
      t.setAttribute("aria-selected", "false");
    });
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    tab.setAttribute("aria-selected", "true");
    document.getElementById(`panel-${tab.dataset.tab}`).classList.add("active");
    if (tab.dataset.tab === "leaderboard") loadLeaderboard();
    VibeBugBus.emit("view:change", { view: tab.dataset.tab });
  });
});

// ---------- Network error overlay ----------

const noiseOverlay = document.getElementById("noise-overlay");
const noiseDetail = document.getElementById("noise-detail");

function showNetworkError(detail) {
  noiseDetail.textContent = detail || "Target unreachable.";
  noiseOverlay.hidden = false;
}

document.getElementById("noise-dismiss").addEventListener("click", () => {
  noiseOverlay.hidden = true;
});

async function apiPost(path, body) {
  let resp;
  try {
    resp = await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    showNetworkError("Could not reach the VibeAudit backend. Is the server running?");
    throw err;
  }
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    showNetworkError(`Backend returned ${resp.status}. ${text}`.slice(0, 160));
    throw new Error(`HTTP ${resp.status}`);
  }
  return resp.json();
}

async function apiGet(path) {
  let resp;
  try {
    resp = await fetch(API_BASE + path);
  } catch (err) {
    showNetworkError("Could not reach the VibeAudit backend. Is the server running?");
    throw err;
  }
  if (!resp.ok) {
    showNetworkError(`Backend returned ${resp.status}.`);
    throw new Error(`HTTP ${resp.status}`);
  }
  return resp.json();
}

// ---------- Single audit ----------

const singleUrlInput = document.getElementById("single-url");
const singleRunBtn = document.getElementById("single-run");
const singleStatus = document.getElementById("single-status");
const singleWrap = document.getElementById("single-wrap");
const singleIntro = document.getElementById("single-intro");
const singleResult = document.getElementById("single-result");
const spcIndicators = document.getElementById("spc-indicators");
const utstSubtotal = document.getElementById("utst-subtotal");
const utstLog = document.getElementById("utst-log");
const singleNotes = document.getElementById("single-notes");

const tsgaNumber = document.getElementById("tsga-number");
const tsgaBand = document.getElementById("tsga-band");
const tsgaDesc = document.getElementById("tsga-desc");
const tsgaUtstN = document.getElementById("tsga-utst-n");
const tsgaSpcN = document.getElementById("tsga-spc-n");
const tsgaGap = document.getElementById("tsga-gap");
const hriRange = document.getElementById("hri-range");
const hriValue = document.getElementById("hri-value");
const hriClear = document.getElementById("hri-clear");
const tsgaBanner = document.getElementById("tsga-banner");

let lastResult = null; // most recent successful audit, for HRI recompute + export

function indicatorRow(label, on) {
  const div = document.createElement("div");
  div.className = "indicator";
  div.innerHTML =
    `<span class="indicator-box ${on ? "on" : ""}" aria-hidden="true"></span>` +
    `<span class="indicator-label">${escapeHtml(label)}</span>` +
    `<span class="indicator-state">${on ? "Yes" : "No"}</span>`;
  return div;
}

const BAND_CLASS = { Low: "band-low", Moderate: "band-moderate", High: "band-high", Severe: "band-severe" };

function renderTsga(tsga, hriAssessed) {
  tsgaBanner.classList.remove("band-low", "band-moderate", "band-high", "band-severe");
  if (!tsga) {
    tsgaNumber.textContent = "—";
    tsgaBand.textContent = "No score";
    tsgaDesc.textContent = "";
    return;
  }
  tsgaBanner.classList.add(BAND_CLASS[tsga.band_label] || "band-low");
  tsgaNumber.textContent = (tsga.tsga_base >= 0 ? "+" : "") + tsga.tsga_base.toFixed(2);
  tsgaBand.textContent = tsga.band_label.toUpperCase();
  tsgaUtstN.textContent = tsga.utst_normalized.toFixed(2);
  tsgaSpcN.textContent = tsga.spc_normalized.toFixed(2);
  tsgaGap.textContent = (tsga.gap >= 0 ? "+" : "") + tsga.gap.toFixed(2);
  const hriNote = hriAssessed
    ? `HRI ${tsga.hri_normalized.toFixed(2)} applied.`
    : "HRI not assessed — multiplier held at 1.";
  tsgaDesc.textContent = `${tsga.band_description} ${hriNote}`;
}

function renderSingleResult(result) {
  singleWrap.hidden = false;
  if (singleIntro) singleIntro.hidden = true;
  singleNotes.textContent = (result.notes || []).join("  ·  ");

  if (!result.fetch_ok) {
    spcIndicators.innerHTML = "";
    utstLog.innerHTML = `<div class="log-empty">Fetch failed — ${escapeHtml(result.fetch_error || "unknown error")}</div>`;
    utstSubtotal.textContent = "—";
    renderTsga(null);
    return;
  }

  spcIndicators.innerHTML = "";
  spcIndicators.appendChild(indicatorRow("HTTPS", result.spc.https));
  spcIndicators.appendChild(indicatorRow("Privacy policy link", result.spc.privacy_policy_link_found));
  const present = result.spc.security_headers_present;
  const headerLabel = `Security headers (${present.length}/${result.spc.security_headers_checked.length})`;
  spcIndicators.appendChild(indicatorRow(headerLabel, present.length > 0));
  if (present.length) {
    const list = document.createElement("div");
    list.className = "header-sublist";
    list.textContent = present.join(", ");
    spcIndicators.appendChild(list);
  }

  if (result.likely_blank_page) {
    const warn = document.createElement("div");
    warn.className = "blank-warn";
    warn.textContent = "Likely JS-rendered or blank — no visible text was found without executing JavaScript. This is a finding, not a fetch error.";
    spcIndicators.appendChild(warn);
  }

  utstSubtotal.textContent = result.utst.automated_subtotal;
  utstLog.innerHTML = "";
  if (result.utst.hits.length === 0) {
    utstLog.innerHTML = `<div class="log-empty">No automated trust-inflation patterns detected.</div>`;
  } else {
    result.utst.hits.forEach((hit) => {
      const div = document.createElement("div");
      div.className = "log-entry";
      div.innerHTML = `<span class="weight">+${hit.trust_weight}</span> ${escapeHtml(hit.pattern)} <span class="cat">${escapeHtml(hit.category)}</span><span class="evidence">"${escapeHtml(hit.evidence)}"</span>`;
      utstLog.appendChild(div);
    });
  }

  const assessed = result.tsga && result.tsga.hri_source === "manual";
  if (assessed) {
    hriRange.value = Math.round(result.tsga.hri_normalized * 100);
    hriValue.textContent = result.tsga.hri_normalized.toFixed(2);
  } else {
    hriRange.value = 0;
    hriValue.textContent = "Not assessed";
  }
  renderTsga(result.tsga, assessed);
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

singleRunBtn.addEventListener("click", async () => {
  const url = singleUrlInput.value.trim();
  if (!url) return;
  singleStatus.textContent = "Fetching target…";
  singleWrap.hidden = true;
  singleRunBtn.disabled = true;
  VibeBugBus.emit("audit:start", { url });
  try {
    const result = await apiPost("/api/audit", { url });
    lastResult = result;
    singleStatus.textContent = `Audited ${new Date(result.audited_at).toLocaleTimeString()}`;
    renderSingleResult(result);
    VibeBugBus.emit("audit:complete", result);
  } catch (e) {
    singleStatus.textContent = "Audit failed.";
    VibeBugBus.emit("audit:error", { url });
  } finally {
    singleRunBtn.disabled = false;
  }
});

// ---------- HRI recompute (no re-fetch) ----------

let hriTimer = null;
function scheduleHriRecompute() {
  if (hriTimer) clearTimeout(hriTimer);
  hriTimer = setTimeout(recomputeHri, 180);
}

async function recomputeHri() {
  if (!lastResult || !lastResult.tsga) return;
  const hri = Number(hriRange.value) / 100;
  hriValue.textContent = hri.toFixed(2);
  try {
    const tsga = await apiPost("/api/tsga", {
      utst_raw: lastResult.tsga.utst_raw,
      spc_raw: lastResult.tsga.spc_raw,
      hri,
    });
    lastResult.tsga = tsga;
    renderTsga(tsga, true);
    VibeBugBus.emit("hri:change", { hri });
  } catch (e) {
    /* overlay already shown */
  }
}

hriRange.addEventListener("input", () => {
  hriValue.textContent = (Number(hriRange.value) / 100).toFixed(2);
});
hriRange.addEventListener("change", scheduleHriRecompute);

hriClear.addEventListener("click", async () => {
  if (!lastResult || !lastResult.tsga) return;
  hriRange.value = 0;
  hriValue.textContent = "Not assessed";
  try {
    const tsga = await apiPost("/api/tsga", {
      utst_raw: lastResult.tsga.utst_raw,
      spc_raw: lastResult.tsga.spc_raw,
      hri: null,
    });
    lastResult.tsga = tsga;
    renderTsga(tsga, false);
    VibeBugBus.emit("hri:clear", {});
  } catch (e) {
    /* overlay already shown */
  }
});

// ---------- Export single result ----------

document.getElementById("single-copy").addEventListener("click", async () => {
  if (!lastResult) return;
  try {
    await navigator.clipboard.writeText(JSON.stringify(lastResult, null, 2));
    singleStatus.textContent = "Copied JSON to clipboard.";
  } catch (e) {
    singleStatus.textContent = "Clipboard blocked — use Download JSON.";
  }
});

document.getElementById("single-download").addEventListener("click", () => {
  if (!lastResult) return;
  const name = (lastResult.app_name || "audit").replace(/[^a-z0-9._-]+/gi, "_");
  downloadText(`${name}.json`, JSON.stringify(lastResult, null, 2), "application/json");
});

function downloadText(filename, text, mime) {
  const blob = new Blob([text], { type: mime || "text/plain" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

singleUrlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") singleRunBtn.click();
});

// ---------- Batch audit ----------

const batchInput = document.getElementById("batch-input");
const batchRunBtn = document.getElementById("batch-run");
const batchProgress = document.getElementById("batch-progress");
const batchTable = document.getElementById("batch-table");
const batchTbody = document.getElementById("batch-tbody");
const batchSummary = document.getElementById("batch-summary");
const batchActions = document.getElementById("batch-actions");

let lastBatch = null; // { results, summary }

function parseBatchInput(raw) {
  return raw
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parts = line.split(",").map((p) => p.trim());
      if (parts.length >= 2) return { app_name: parts[0], url: parts.slice(1).join(",") };
      return { app_name: null, url: parts[0] };
    });
}

function bandCell(label) {
  if (!label) return `<td class="cell-no">—</td>`;
  return `<td><span class="band-chip ${BAND_CLASS[label] || "band-low"}">${label}</span></td>`;
}

function batchRow(r, idx) {
  const tr = document.createElement("tr");
  if (!r.fetch_ok) {
    tr.className = "batch-fail";
    tr.innerHTML =
      `<td>${escapeHtml(r.app_name || r.url || "?")}</td>` +
      `<td colspan="6" class="cell-fail">${escapeHtml(r.fetch_error || "failed")}</td>` +
      `<td class="cell-no">Failed</td>`;
    return [tr, null];
  }
  const spc = r.spc || {};
  const utst = r.utst || {};
  const tsga = r.tsga || {};
  const hdrs = `${(spc.security_headers_present || []).length}/${(spc.security_headers_checked || []).length}`;
  const status = r.likely_blank_page ? `<span class="cell-fail">Blank?</span>` : `<span class="cell-yes">OK</span>`;
  tr.className = "batch-ok";
  tr.innerHTML = `
    <td>${escapeHtml(r.app_name || r.url)}</td>
    <td class="${spc.https ? "cell-yes" : "cell-no"}">${spc.https ? "Yes" : "No"}</td>
    <td class="${spc.privacy_policy_link_found ? "cell-yes" : "cell-no"}">${spc.privacy_policy_link_found ? "Yes" : "No"}</td>
    <td>${hdrs}</td>
    <td>${utst.automated_subtotal ?? "—"}</td>
    <td>${tsga.gap != null ? (tsga.gap >= 0 ? "+" : "") + tsga.gap.toFixed(2) : "—"}</td>
    ${bandCell(tsga.band_label)}
    <td>${status}</td>`;

  const detail = document.createElement("tr");
  detail.className = "batch-detail";
  detail.hidden = true;
  const hits = (utst.hits || [])
    .map((h) => `<li><span class="weight">+${h.trust_weight}</span> ${escapeHtml(h.pattern)} — <span class="evidence">"${escapeHtml(h.evidence)}"</span></li>`)
    .join("");
  const notes = (r.notes || []).map((n) => `<div class="muted-note">${escapeHtml(n)}</div>`).join("");
  detail.innerHTML = `<td colspan="8">
      <div class="batch-detail-body">
        <div><b>${escapeHtml(r.final_url || r.url)}</b></div>
        ${hits ? `<ul class="hit-list">${hits}</ul>` : `<div class="muted-note">No automated patterns matched.</div>`}
        ${notes}
      </div></td>`;
  tr.addEventListener("click", () => { detail.hidden = !detail.hidden; });
  return [tr, detail];
}

function renderBatchSummary(s) {
  if (!s) { batchSummary.hidden = true; return; }
  const bands = Object.entries(s.bands || {}).map(([k, v]) => `${k}: ${v}`).join("  ·  ") || "—";
  batchSummary.hidden = false;
  batchSummary.innerHTML = `
    <span><b>${s.ok}</b>/${s.total} ok</span>
    <span><b>${s.failed}</b> failed</span>
    <span><b>${s.blank}</b> blank</span>
    <span>avg gap <b>${s.avg_gap ?? "—"}</b></span>
    <span>max gap <b>${s.max_gap ?? "—"}</b></span>
    <span class="muted-note">${bands}</span>`;
}

batchRunBtn.addEventListener("click", async () => {
  const entries = parseBatchInput(batchInput.value);
  if (entries.length === 0) return;

  batchProgress.textContent = `Running ${entries.length} audit${entries.length === 1 ? "" : "s"}…`;
  batchRunBtn.disabled = true;
  batchTable.hidden = false;
  batchTbody.innerHTML = "";
  batchActions.hidden = true;
  batchSummary.hidden = true;
  VibeBugBus.emit("batch:start", { count: entries.length });

  try {
    const data = await apiPost("/api/audit/batch", { entries });
    lastBatch = data;
    (data.results || []).forEach((r, i) => {
      const [row, detail] = batchRow(r, i);
      batchTbody.appendChild(row);
      if (detail) batchTbody.appendChild(detail);
    });
    renderBatchSummary(data.summary);
    batchActions.hidden = false;
    batchProgress.textContent = `${(data.results || []).length} audited`;
    VibeBugBus.emit("batch:complete", { ...(data.summary || {}), count: entries.length });
  } catch (e) {
    batchProgress.textContent = "Batch failed.";
    VibeBugBus.emit("audit:error", { batch: true });
  } finally {
    batchRunBtn.disabled = false;
  }
});

// ---------- Batch exports (client-side) ----------

function batchToCsv(results) {
  const cols = ["app_name", "url", "final_url", "fetch_ok", "fetch_error", "https",
    "privacy_policy_link_found", "security_headers_present", "utst_automated_subtotal",
    "utst_patterns_hit", "tsga_gap", "tsga_base", "tsga_band", "likely_blank_page"];
  const esc = (v) => {
    const s = v == null ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const rows = results.map((r) => {
    const spc = r.spc || {}, utst = r.utst || {}, tsga = r.tsga || {};
    return [
      r.app_name, r.url, r.final_url || "", r.fetch_ok, r.fetch_error || "",
      spc.https ?? "", spc.privacy_policy_link_found ?? "",
      (spc.security_headers_present || []).join("; "),
      utst.automated_subtotal ?? "",
      (utst.hits || []).map((h) => h.pattern).join("; "),
      tsga.gap ?? "", tsga.tsga_base ?? "", tsga.band_label || "",
      r.likely_blank_page ?? "",
    ].map(esc).join(",");
  });
  return [cols.join(","), ...rows].join("\n");
}

function batchToMarkdown(data) {
  const s = data.summary || {};
  const lines = [
    "# VibeAudit batch report", "",
    `_${new Date().toISOString()}_`, "",
    "## Summary", "",
    `- Targets: **${s.total}** (${s.ok} ok, ${s.failed} failed, ${s.blank} blank)`,
    `- Average gap: **${s.avg_gap ?? "n/a"}** (max ${s.max_gap ?? "n/a"})`,
    "", "## Results", "",
    "| App | URL | HTTPS | Privacy | UTST | Gap | Band | Status |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
  ];
  (data.results || []).forEach((r) => {
    const spc = r.spc || {}, utst = r.utst || {}, tsga = r.tsga || {};
    const cell = (v) => String(v == null ? "" : v).replace(/\|/g, "\\|");
    lines.push("| " + [
      cell(r.app_name), cell(r.final_url || r.url),
      r.fetch_ok ? (spc.https ? "yes" : "no") : "-",
      r.fetch_ok ? (spc.privacy_policy_link_found ? "yes" : "no") : "-",
      r.fetch_ok ? (utst.automated_subtotal ?? "-") : "-",
      tsga.gap != null ? tsga.gap.toFixed(2) : "-",
      tsga.band_label || "-",
      r.fetch_ok ? (r.likely_blank_page ? "blank?" : "ok") : (r.fetch_error || "failed"),
    ].map(cell).join(" | ") + " |");
  });
  return lines.join("\n");
}

document.getElementById("batch-csv").addEventListener("click", () => {
  if (lastBatch) downloadText("vibeaudit-batch.csv", batchToCsv(lastBatch.results || []), "text/csv");
});
document.getElementById("batch-json").addEventListener("click", () => {
  if (lastBatch) downloadText("vibeaudit-batch.json", JSON.stringify(lastBatch, null, 2), "application/json");
});
document.getElementById("batch-md").addEventListener("click", () => {
  if (lastBatch) downloadText("vibeaudit-batch.md", batchToMarkdown(lastBatch), "text/markdown");
});

// ---------- Leaderboard ----------

const leaderboardTbody = document.getElementById("leaderboard-tbody");
const leaderboardSort = document.getElementById("leaderboard-sort");
const leaderboardCount = document.getElementById("leaderboard-count");

async function loadLeaderboard() {
  const sort = leaderboardSort.value || "rank";
  try {
    const { entries, count } = await apiGet(`/api/leaderboard?sort=${encodeURIComponent(sort)}`);
    leaderboardCount.textContent = count ?? entries.length;
    leaderboardTbody.innerHTML = "";
    VibeBugBus.emit("leaderboard:loaded", { count: entries.length, sort });
    if (!entries.length) {
      leaderboardTbody.innerHTML = `<tr><td colspan="9" class="cell-fail">No audits recorded yet.</td></tr>`;
      return;
    }
    entries.forEach((e, i) => {
      const tr = document.createElement("tr");
      const spc = e.spc || {};
      const utst = e.utst || {};
      const tsga = e.tsga || {};
      tr.innerHTML = `
        <td>${i + 1}</td>
        <td>${escapeHtml(e.app_name || e.url || "?")}</td>
        <td>${tsga.tsga_base != null ? (tsga.tsga_base >= 0 ? "+" : "") + tsga.tsga_base.toFixed(2) : "—"}</td>
        ${bandCell(tsga.band_label)}
        <td>${e.gap_signal ?? "—"}</td>
        <td>${utst.automated_subtotal ?? "—"}</td>
        <td class="${spc.https ? "cell-yes" : "cell-no"}">${spc.https ? "Yes" : "No"}</td>
        <td class="${spc.privacy_policy_link_found ? "cell-yes" : "cell-no"}">${spc.privacy_policy_link_found ? "Yes" : "No"}</td>
        <td>${e.audited_at ? new Date(e.audited_at).toLocaleString() : "—"}</td>`;
      leaderboardTbody.appendChild(tr);
    });
  } catch (e) {
    // network error already surfaced via overlay
  }
}

leaderboardSort.addEventListener("change", () => {
  VibeBugBus.emit("leaderboard:sort", { sort: leaderboardSort.value });
  loadLeaderboard();
});
document.getElementById("leaderboard-refresh").addEventListener("click", () => {
  VibeBugBus.emit("leaderboard:refresh", {});
  loadLeaderboard();
});
document.getElementById("leaderboard-clear").addEventListener("click", async () => {
  if (!confirm("Clear all leaderboard history? This cannot be undone.")) return;
  try {
    await fetch(API_BASE + "/api/leaderboard", { method: "DELETE" });
    loadLeaderboard();
  } catch (e) {
    showNetworkError("Could not reach the backend to clear history.");
  }
});
