// script.js — Lumora frontend logic

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const browseBtn = document.getElementById("browseBtn");
const uploadStatus = document.getElementById("uploadStatus");
const progressWrap = document.getElementById("progressWrap");
const progressBar = document.getElementById("progressBar");
const uploadSection = document.getElementById("upload-section");
const dashboard = document.getElementById("dashboard");
const loadingOverlay = document.getElementById("loadingOverlay");
const newUploadBtn = document.getElementById("newUploadBtn");
const downloadReportBtn = document.getElementById("downloadReportBtn");
const downloadCleanBtn = document.getElementById("downloadCleanBtn");
const cleanDropdown = document.getElementById("cleanDropdown");

let currentSessionId = null;

browseBtn.addEventListener("click", () => fileInput.click());
dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) {
    handleFile(e.dataTransfer.files[0]);
  }
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) handleFile(fileInput.files[0]);
});

function handleFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  uploadStatus.textContent = `Uploading "${file.name}"...`;
  progressWrap.style.display = "block";
  progressBar.style.width = "10%";

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload");

  xhr.upload.addEventListener("progress", (e) => {
    if (e.lengthComputable) {
      const pct = Math.min(90, (e.loaded / e.total) * 90);
      progressBar.style.width = pct + "%";
    }
  });

  xhr.onload = () => {
    progressBar.style.width = "100%";
    if (xhr.status === 200) {
      const data = JSON.parse(xhr.responseText);
      currentSessionId = data.session_id;
      renderDashboard(data);
      uploadStatus.textContent = "";
      progressWrap.style.display = "none";
    } else {
      let msg = "Upload failed.";
      try { msg = JSON.parse(xhr.responseText).error || msg; } catch (e2) {}
      uploadStatus.textContent = "❌ " + msg;
      progressWrap.style.display = "none";
    }
    loadingOverlay.style.display = "none";
  };

  xhr.onerror = () => {
    uploadStatus.textContent = "❌ Network error during upload.";
    progressWrap.style.display = "none";
    loadingOverlay.style.display = "none";
  };

  loadingOverlay.style.display = "flex";
  xhr.send(formData);
}

function renderDashboard(data) {
  uploadSection.style.display = "none";
  dashboard.style.display = "block";

  document.getElementById("datasetName").textContent = data.dataset_name;
  const [r0, c0] = data.clean_report.original_shape;
  const [r1, c1] = data.clean_report.cleaned_shape;
  document.getElementById("shapeInfo").textContent =
    `${r0.toLocaleString()} → ${r1.toLocaleString()} rows  •  ${c1} columns after cleaning`;

  // Cleaning summary cards
  const cardsRow = document.getElementById("cleaningCards");
  const filledCount = Object.keys(data.clean_report.missing_values_filled || {}).length;
  cardsRow.innerHTML = `
    <div class="info-card"><div class="label">Rows (cleaned)</div><div class="value">${r1.toLocaleString()}</div></div>
    <div class="info-card"><div class="label">Columns</div><div class="value">${c1}</div></div>
    <div class="info-card"><div class="label">Duplicates removed</div><div class="value">${data.clean_report.duplicates_removed}</div></div>
    <div class="info-card"><div class="label">Columns with missing data fixed</div><div class="value">${filledCount}</div></div>
  `;

  // Insights
  const insightsList = document.getElementById("insightsList");
  insightsList.innerHTML = data.insights.map(i => `<li>${escapeHtml(i)}</li>`).join("");

  // Numeric stats table
  const numTable = document.getElementById("numericStatsTable");
  numTable.innerHTML = buildTable(data.stats.numeric);

  // Categorical stats table
  const catTable = document.getElementById("catStatsTable");
  catTable.innerHTML = buildTable(data.stats.categorical);

  // Univariate charts
  const uniGrid = document.getElementById("univariateGrid");
  uniGrid.innerHTML = data.uni_charts.map(chartCard).join("");

  // Bivariate charts
  const biGrid = document.getElementById("bivariateGrid");
  biGrid.innerHTML = data.bi_charts.map(chartCard).join("");

  // Preview table
  const previewTable = document.getElementById("previewTable");
  previewTable.innerHTML = buildPreviewTable(data.preview_cols, data.preview_rows);
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
  html += "</tbody>";
  return html;
}

function buildPreviewTable(cols, rows) {
  let html = "<thead><tr>" + cols.map(c => `<th>${escapeHtml(c)}</th>`).join("") + "</tr></thead><tbody>";
  rows.forEach(row => {
    html += "<tr>" + cols.map(c => `<td>${escapeHtml(String(row[c]))}</td>`).join("") + "</tr>";
  });
  html += "</tbody>";
  return html;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

newUploadBtn.addEventListener("click", () => {
  dashboard.style.display = "none";
  uploadSection.style.display = "block";
  fileInput.value = "";
  currentSessionId = null;
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
    const fmt = a.dataset.fmt;
    window.location.href = `/api/download/cleaned/${currentSessionId}/${fmt}`;
  });
});
