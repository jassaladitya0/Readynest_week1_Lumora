// script.js — Lumora frontend logic (async polling version)

const dropzone       = document.getElementById("dropzone");
const fileInput      = document.getElementById("fileInput");
const browseBtn      = document.getElementById("browseBtn");
const uploadStatus   = document.getElementById("uploadStatus");
const progressWrap   = document.getElementById("progressWrap");
const progressBar    = document.getElementById("progressBar");
const uploadSection  = document.getElementById("upload-section");
const dashboard      = document.getElementById("dashboard");
const loadingOverlay = document.getElementById("loadingOverlay");
const loadingText    = document.getElementById("loadingText");
const newUploadBtn   = document.getElementById("newUploadBtn");
const downloadReportBtn = document.getElementById("downloadReportBtn");
const downloadCleanBtn  = document.getElementById("downloadCleanBtn");
const cleanDropdown     = document.getElementById("cleanDropdown");

let currentSessionId = null;
let pollInterval     = null;

// ── File picker / drag-drop ──────────────────────────────────────────────────

browseBtn.addEventListener("click", (e) => { e.stopPropagation(); fileInput.click(); });
dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("click", (e) => e.stopPropagation());

dropzone.addEventListener("dragover", (e) => { e.preventDefault(); dropzone.classList.add("dragover"); });
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleFile(fileInput.files[0]);
});

// ── Upload → immediate 202 → poll status ────────────────────────────────────

function handleFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  uploadStatus.textContent = `Uploading "${file.name}"…`;
  progressWrap.style.display = "block";
  progressBar.style.width = "5%";
  loadingOverlay.style.display = "flex";
  loadingText.textContent = "Uploading your dataset…";

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");

  xhr.upload.addEventListener("progress", (e) => {
    if (e.lengthComputable) {
      const pct = Math.min(30, (e.loaded / e.total) * 30);
      progressBar.style.width = pct + "%";
    }
  });

  xhr.onload = () => {
    if (xhr.status === 202) {
      const { session_id } = JSON.parse(xhr.responseText);
      currentSessionId = session_id;
      uploadStatus.textContent = "File uploaded. Processing…";
      loadingText.textContent = "Cleaning & analysing your dataset…";
      progressBar.style.width = "35%";
      startPolling(session_id);
    } else {
      let msg = "Upload failed.";
      try { msg = JSON.parse(xhr.responseText).error || msg; } catch (_) {}
      showError(msg);
    }
  };

  xhr.onerror = () => showError("Network error during upload. Please try again.");

  xhr.send(formData);
}

// ── Polling ──────────────────────────────────────────────────────────────────

const POLL_MESSAGES = [
  "Cleaning & analysing your dataset…",
  "Generating visualisations…",
  "Computing statistics…",
  "Almost there…",
];
let pollMsgIdx = 0;

function startPolling(session_id) {
  let dots = 35;
  pollMsgIdx = 0;

  pollInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/status/${session_id}`);
      const json = await res.json();

      if (json.status === "done") {
        clearInterval(pollInterval);
        progressBar.style.width = "100%";
        loadingText.textContent = "Done!";
        setTimeout(() => {
          loadingOverlay.style.display = "none";
          progressWrap.style.display = "none";
          uploadStatus.textContent = "";
          renderDashboard(json.data);
        }, 400);

      } else if (json.status === "error") {
        clearInterval(pollInterval);
        showError(json.error || "Processing failed. Please try again.");

      } else {
        // still processing — animate progress bar and rotate messages
        dots = Math.min(90, dots + 3);
        progressBar.style.width = dots + "%";
        loadingText.textContent = POLL_MESSAGES[pollMsgIdx % POLL_MESSAGES.length];
        pollMsgIdx++;
      }
    } catch (err) {
      // Network glitch — keep polling
      console.warn("Poll error (will retry):", err);
    }
  }, 2000);
}

function showError(msg) {
  if (pollInterval) clearInterval(pollInterval);
  uploadStatus.textContent = "❌ " + msg;
  progressWrap.style.display = "none";
  loadingOverlay.style.display = "none";
  fileInput.value = "";
}

// ── Dashboard rendering ──────────────────────────────────────────────────────

function renderDashboard(data) {
  uploadSection.style.display = "none";
  dashboard.style.display = "block";

  document.getElementById("datasetName").textContent = data.dataset_name;
  const [r0, c0] = data.clean_report.original_shape;
  const [r1, c1] = data.clean_report.cleaned_shape;
  document.getElementById("shapeInfo").textContent =
    `${r0.toLocaleString()} → ${r1.toLocaleString()} rows  •  ${c1} columns after cleaning`;

  // Cleaning cards
  const cardsRow   = document.getElementById("cleaningCards");
  const filledCount = Object.keys(data.clean_report.missing_values_filled || {}).length;
  cardsRow.innerHTML = `
    <div class="info-card"><div class="label">Rows (cleaned)</div><div class="value">${r1.toLocaleString()}</div></div>
    <div class="info-card"><div class="label">Columns</div><div class="value">${c1}</div></div>
    <div class="info-card"><div class="label">Duplicates removed</div><div class="value">${data.clean_report.duplicates_removed}</div></div>
    <div class="info-card"><div class="label">Columns fixed</div><div class="value">${filledCount}</div></div>
  `;

  // Insights
  document.getElementById("insightsList").innerHTML =
    data.insights.map(i => `<li>${escapeHtml(i)}</li>`).join("");

  // Stats tables
  document.getElementById("numericStatsTable").innerHTML = buildTable(data.stats.numeric);
  document.getElementById("catStatsTable").innerHTML     = buildTable(data.stats.categorical);

  // Charts
  document.getElementById("univariateGrid").innerHTML = data.uni_charts.map(chartCard).join("");
  document.getElementById("bivariateGrid").innerHTML  = data.bi_charts.map(chartCard).join("");

  // Preview
  document.getElementById("previewTable").innerHTML =
    buildPreviewTable(data.preview_cols, data.preview_rows);
}

function chartCard(chart) {
  return `<div class="chart-card">
    <img src="data:image/png;base64,${chart.img}" alt="${escapeHtml(chart.title)}">
    <div class="chart-title">${escapeHtml(chart.title)}</div>
  </div>`;
}

function buildTable(rows) {
  if (!rows || rows.length === 0) return "<tr><td>No data</td></tr>";
  const cols = Object.keys(rows[0]);
  let html = "<thead><tr>" + cols.map(c => `<th>${escapeHtml(c)}</th>`).join("") + "</tr></thead><tbody>";
  rows.forEach(row => {
    html += "<tr>" + cols.map(c => `<td>${escapeHtml(String(row[c]))}</td>`).join("") + "</tr>";
  });
  return html + "</tbody>";
}

function buildPreviewTable(cols, rows) {
  let html = "<thead><tr>" + cols.map(c => `<th>${escapeHtml(c)}</th>`).join("") + "</tr></thead><tbody>";
  rows.forEach(row => {
    html += "<tr>" + cols.map(c => `<td>${escapeHtml(String(row[c]))}</td>`).join("") + "</tr>";
  });
  return html + "</tbody>";
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// ── Button actions ───────────────────────────────────────────────────────────

newUploadBtn.addEventListener("click", () => {
  if (pollInterval) clearInterval(pollInterval);
  dashboard.style.display = "none";
  uploadSection.style.display = "block";
  fileInput.value = "";
  currentSessionId = null;
  uploadStatus.textContent = "";
});

downloadReportBtn.addEventListener("click", () => {
  if (!currentSessionId) return;
  window.location.href = `/api/download/report/${currentSessionId}`;
});

downloadCleanBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  cleanDropdown.classList.toggle("show");
});

document.addEventListener("click", () => cleanDropdown.classList.remove("show"));

cleanDropdown.querySelectorAll("a").forEach(a => {
  a.addEventListener("click", (e) => {
    e.preventDefault();
    if (!currentSessionId) return;
    window.location.href = `/api/download/cleaned/${currentSessionId}/${a.dataset.fmt}`;
  });
});
