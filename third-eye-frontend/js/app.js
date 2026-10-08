const API_BASE_URL = localStorage.getItem("thirdEyeApiBase") || "http://127.0.0.1:8000";

const state = {
  apiOnline: false,
  currentCase: JSON.parse(localStorage.getItem("thirdEyeCurrentCase") || "null"),
  witnesses: [],
  reconstruction: null,
  history: [],
  editingWitnessId: null,
  modalMode: null,
  zoom: 1
};

const $ = (id) => document.getElementById(id);

function escapeHtml(value = "") {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function saveCaseLocal() {
  localStorage.setItem("thirdEyeCurrentCase", JSON.stringify(state.currentCase));
}

function showToast(message, type = "info") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.textContent = message;
  $("toastContainer").appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

function setApiStatus(online) {
  state.apiOnline = online;
  $("apiDot").className = `status-dot ${online ? "online" : "offline"}`;
  $("apiStatusText").textContent = online ? "API ONLINE" : "API OFFLINE";
  $("sideApiStatus").textContent = online ? "ONLINE" : "OFFLINE";
  $("sideApiStatus").className = `pill ${online ? "pill-success" : "pill-danger"}`;
  $("statApi").textContent = online ? "ONLINE" : "OFFLINE";
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {})
    }
  });

  let data = null;
  try { data = await response.json(); } catch (_) {}

  if (!response.ok) {
    const detail = data?.detail || `HTTP ${response.status}`;
    throw new Error(detail);
  }
  return data;
}

const api = {
  health: () => request("/"),
  getCases: () => request("/cases"),
  createCase: (caseName) => request("/cases", {
    method: "POST",
    body: JSON.stringify({ case_name: caseName })
  }),
  getWitnesses: (caseId) => request(`/cases/${encodeURIComponent(caseId)}/witnesses`),
  addWitness: (caseId, statement) => request(`/cases/${encodeURIComponent(caseId)}/witnesses`, {
    method: "POST",
    body: JSON.stringify({ statement })
  }),
  updateWitness: (witnessId, statement) => request(`/witnesses/${encodeURIComponent(witnessId)}`, {
    method: "PUT",
    body: JSON.stringify({ statement })
  }),
  generateReconstruction: (caseId) => request(`/cases/${encodeURIComponent(caseId)}/reconstruction`, {
    method: "POST"
  }),
  getCurrentReconstruction: (caseId) => request(`/cases/${encodeURIComponent(caseId)}/reconstruction`),
  getHistory: (caseId) => request(`/cases/${encodeURIComponent(caseId)}/reconstruction/history`)
};

function navigate(view) {
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.classList.toggle("active", btn.dataset.view === view);
  });

  document.querySelectorAll(".view").forEach(section => {
    section.classList.toggle("active", section.id === `view-${view}`);
  });

  if (view === "case") refreshCaseView();
  if (view === "witnesses") loadWitnesses();
  if (view === "reconstruction") refreshReconstructionView();
  if (view === "history") loadHistory();
  if (view === "report") refreshReport();
}

function openModal(mode, witness = null) {
  state.modalMode = mode;
  state.editingWitnessId = witness?.id || null;
  $("modal").classList.remove("hidden");

  const isCase = mode === "case";
  $("modalEyebrow").textContent = isCase ? "CASE MANAGEMENT" : "TESTIMONY COLLECTION";
  $("modalTitle").textContent = isCase ? "Create New Case" : (witness ? "Edit Witness Statement" : "Add Witness");
  $("caseNameLabel").classList.toggle("hidden", !isCase);
  $("caseNameInput").classList.toggle("hidden", !isCase);
  $("statementLabel").classList.toggle("hidden", isCase);
  $("statementInput").classList.toggle("hidden", isCase);

  $("caseNameInput").value = "";
  $("statementInput").value = witness?.statement || "";
  $("charCount").textContent = $("statementInput").value.length;

  setTimeout(() => (isCase ? $("caseNameInput") : $("statementInput")).focus(), 30);
}

function closeModal() {
  $("modal").classList.add("hidden");
  state.modalMode = null;
  state.editingWitnessId = null;
}

async function saveModal() {
  try {
    if (state.modalMode === "case") {
      const name = $("caseNameInput").value.trim();
      if (!name) return showToast("Case name cannot be empty.", "error");

      const result = await api.createCase(name);
      state.currentCase = result;
      saveCaseLocal();
      await loadCases();
      closeModal();
      showToast("Case created successfully.", "success");
      await loadCaseData();
      navigate("case");
      return;
    }

    if (!state.currentCase?.id) {
      closeModal();
      return showToast("Create a case before adding witness statements.", "error");
    }

    const statement = $("statementInput").value.trim();
    if (!statement) return showToast("Witness statement cannot be empty.", "error");

    if (state.editingWitnessId) {
      await api.updateWitness(state.editingWitnessId, statement);
      showToast("Witness statement updated.", "success");
    } else {
      await api.addWitness(state.currentCase.id, statement);
      showToast("Witness statement added.", "success");
    }

    closeModal();
    await loadWitnesses();
  } catch (error) {
    showToast(error.message, "error");
  }
}

async function loadCases() {
  try {
    const data = await api.getCases();
    const cases = data?.cases || [];
    renderCaseSelector(cases);

    const savedId = state.currentCase?.id;
    const savedCase = cases.find(c => String(c.id) === String(savedId));

    if (savedCase) {
      state.currentCase = savedCase;
      saveCaseLocal();
      await loadCaseData();
      updateStats();
      refreshCaseView();
      return;
    }

    if (cases.length) {
      state.currentCase = cases[0];
      saveCaseLocal();
      await loadCaseData();
      showToast(`Loaded existing case: ${cases[0].case_name}`, "success");
    } else {
      state.currentCase = null;
      saveCaseLocal();
    }

    updateStats();
    refreshCaseView();
  } catch (error) {
    showToast(`Could not load cases: ${error.message}`, "error");
  }
}

function renderCaseSelector(cases) {
  const select = $("caseSelect");
  if (!select) return;

  select.innerHTML = `<option value="">SELECT CASE</option>`;

  cases.forEach(c => {
    const option = document.createElement("option");
    option.value = c.id;
    option.textContent = c.case_name || c.id;
    select.appendChild(option);
  });

  if (state.currentCase?.id) {
    select.value = state.currentCase.id;
  }
}

async function selectCase(caseId) {
  if (!caseId) {
    state.currentCase = null;
    state.witnesses = [];
    state.reconstruction = null;
    state.history = [];
    saveCaseLocal();
    refreshAllViews();
    return;
  }

  try {
    const select = $("caseSelect");
    const selectedOption = select?.options[select.selectedIndex];
    state.currentCase = {
      id: caseId,
      case_name: selectedOption?.textContent || caseId
    };

    saveCaseLocal();
    await loadCaseData();
    refreshAllViews();
    showToast(`Case loaded: ${state.currentCase.case_name}`, "success");
  } catch (error) {
    showToast(`Could not load case: ${error.message}`, "error");
  }
}

function refreshAllViews() {
  updateStats();
  refreshCaseView();
  renderWitnesses();
  renderCompactWitnesses();
  renderReconstruction();
  renderHistory();
  refreshReport();
}

async function loadWitnesses() {
  if (!state.currentCase?.id) {
    state.witnesses = [];
    renderWitnesses();
    return;
  }
  try {
    const data = await api.getWitnesses(state.currentCase.id);
    state.witnesses = data.witnesses || [];
    renderWitnesses();
    renderCompactWitnesses();
    updateStats();
  } catch (error) {
    showToast(`Could not load witnesses: ${error.message}`, "error");
  }
}

function renderWitnesses() {
  const container = $("witnessList");
  if (!state.currentCase?.id) {
    container.innerHTML = `<div class="empty-panel">NO CASE SELECTED<br><small>Create a case before recording testimony.</small></div>`;
    return;
  }
  if (!state.witnesses.length) {
    container.innerHTML = `<div class="empty-panel">NO WITNESS STATEMENTS<br><small>Add the first witness statement to begin.</small></div>`;
    return;
  }

  container.innerHTML = state.witnesses.map((w, i) => `
    <article class="witness-card">
      <div class="witness-top">
        <span class="witness-id">WITNESS #${escapeHtml(w.id ?? i + 1)}</span>
        <span class="witness-date">${escapeHtml(formatDate(w.created_at))}</span>
      </div>
      <div class="witness-statement">${escapeHtml(w.statement)}</div>
      <div class="witness-actions">
        <button class="ghost-btn edit-witness" data-id="${escapeHtml(w.id)}">Edit Statement</button>
      </div>
    </article>
  `).join("");

  document.querySelectorAll(".edit-witness").forEach(btn => {
    btn.addEventListener("click", () => {
      const witness = state.witnesses.find(w => String(w.id) === String(btn.dataset.id));
      if (witness) openModal("witness", witness);
    });
  });
}

function renderCompactWitnesses() {
  const el = $("reconWitnesses");
  if (!state.witnesses.length) {
    el.innerHTML = `<div class="empty-panel">No witness statements.</div>`;
    return;
  }
  el.innerHTML = state.witnesses.map((w, i) => `
    <div class="compact-witness">
      <b>WITNESS #${escapeHtml(w.id ?? i + 1)}</b>
      <p>${escapeHtml(w.statement)}</p>
    </div>
  `).join("");
}

async function loadReconstruction() {
  if (!state.currentCase?.id) {
    state.reconstruction = null;
    return;
  }
  try {
    const data = await api.getCurrentReconstruction(state.currentCase.id);
    state.reconstruction = data?.reconstruction ?? data ?? null;
    renderReconstruction();
    updateStats();
  } catch (error) {
    showToast(`Could not load reconstruction: ${error.message}`, "error");
  }
}

async function loadHistory() {
  if (!state.currentCase?.id) {
    state.history = [];
    renderHistory();
    return;
  }
  try {
    const data = await api.getHistory(state.currentCase.id);
    state.history = data.versions || [];
    renderHistory();
  } catch (error) {
    showToast(`Could not load history: ${error.message}`, "error");
  }
}

async function loadCaseData() {
  await loadWitnesses();
  await loadReconstruction();
  await loadHistory();
  updateStats();
}

function formatDate(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return d.toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
}

function updateStats() {
  const c = state.currentCase;

  const caseSelect = $("caseSelect");
  if (caseSelect) {
    caseSelect.value = c?.id || "";
  }

  $("statCase").textContent = c?.id ? "ACTIVE" : "—";
  $("statWitnesses").textContent = state.witnesses.length;

  const v = state.reconstruction?.version_number ?? state.reconstruction?.version;
  $("statVersion").textContent = v ? `V${v}` : "—";

  $("caseIdField").textContent = c?.id || "—";
  $("caseNameField").textContent = c?.case_name || "—";
  $("caseWitnessCount").textContent = state.witnesses.length;
  $("caseVersion").textContent = v ? `V${v}` : "—";
}

function refreshCaseView() {
  const c = state.currentCase;
  $("caseTitle").textContent = c?.case_name || "No Case";
  $("caseMeta").textContent = c?.id ? `Case ID ${c.id}` : "Create a case to begin the reconstruction workflow.";
  $("caseStatus").textContent = c ? "ACTIVE" : "STANDBY";
  $("caseStatus").className = `badge ${c ? "badge-success" : "badge-neutral"}`;
  $("dashCaseTitle").textContent = c?.case_name || "No case selected";
  $("dashCaseBadge").textContent = c ? "ACTIVE" : "STANDBY";
  $("dashCaseBadge").className = `badge ${c ? "badge-success" : "badge-neutral"}`;
  const img = state.reconstruction?.image_url;
  $("casePreview").innerHTML = img
    ? `<img src="${escapeHtml(img)}" alt="Current forensic reconstruction" style="max-width:100%;max-height:270px;object-fit:contain">`
    : "NO RECONSTRUCTION AVAILABLE";
  $("casePreview").classList.toggle("empty-preview", !img);
  updateStats();
}

function refreshReconstructionView() {
  renderCompactWitnesses();
  renderReconstruction();
}

function renderVersionSelector() {
  const select = $("versionSelect");
  if (!select) return;

  const versions = [...state.history].sort((a, b) => Number(a.version_number) - Number(b.version_number));
  const currentVersion = state.reconstruction?.version_number ?? state.reconstruction?.version;

  select.innerHTML = versions.length
    ? versions.map(v => `<option value="${escapeHtml(v.version_number)}">V${escapeHtml(v.version_number)}${Number(v.version_number) === Number(currentVersion) ? " — CURRENT VIEW" : ""}</option>`).join("")
    : `<option value="">NO VERSIONS</option>`;

  if (currentVersion && versions.some(v => Number(v.version_number) === Number(currentVersion))) {
    select.value = String(currentVersion);
  }
}

function viewVersion(versionNumber) {
  const version = state.history.find(v => String(v.version_number) === String(versionNumber));
  if (!version) return;

  state.reconstruction = version;
  state.zoom = 1;
  renderReconstruction();
  refreshReport();
}

function renderReconstruction() {
  const r = state.reconstruction;
  const version = r?.version_number ?? r?.version;
  $("viewerVersion").textContent = version ? `V${version}` : "V—";
  $("reconSubtitle").textContent = version
    ? `Version V${version} is the latest reconstruction returned by the backend.`
    : "No reconstruction generated.";

  $("consolidatedText").textContent = r?.consolidated_description || "No analysis available.";
  $("changeText").textContent = r?.change_instruction || "No visual change.";
  $("generationId").textContent = r?.generation_id || "—";
  $("storagePath").textContent = r?.storage_path || "—";
  $("sourceImage").textContent = r?.source_image_url || "None";
  $("imageResolution").textContent = r?.image_url ? "Generated image" : "—";

  renderVersionSelector();

  const viewer = $("imageViewer");
  if (r?.image_url) {
    viewer.innerHTML = `<img id="mainReconImage" src="${escapeHtml(r.image_url)}" alt="Forensic reconstruction V${escapeHtml(version)}">`;
    applyZoom();
  } else {
    viewer.innerHTML = `
      <div class="empty-viewer">
        <div class="crosshair">＋</div>
        <b>NO RECONSTRUCTION</b>
        <span>Generate a case reconstruction to populate the viewer.</span>
      </div>`;
  }
}

function renderHistory() {
  const container = $("historyList");
  if (!state.currentCase?.id) {
    container.innerHTML = `<div class="empty-panel">NO CASE SELECTED</div>`;
    return;
  }
  if (!state.history.length) {
    container.innerHTML = `<div class="empty-panel">NO SAVED VERSIONS<br><small>Generate a reconstruction to create V1.</small></div>`;
    return;
  }

  renderVersionSelector();

  container.innerHTML = [...state.history].reverse().map(v => `
    <article class="history-card">
      <div class="history-thumb">
        ${v.image_url ? `<img src="${escapeHtml(v.image_url)}" alt="Version ${escapeHtml(v.version_number)}">` : `<span>NO IMAGE</span>`}
      </div>
      <div>
        <div class="history-version">VERSION V${escapeHtml(v.version_number)}</div>
        <div class="history-source">SAVED RECONSTRUCTION</div>
      </div>
      <div>
        <div class="history-desc">${escapeHtml(v.consolidated_description || "No description available.")}</div>
        <div class="history-source">${v.source_image_url ? "SOURCE IMAGE AVAILABLE" : "INITIAL VERSION"}</div>
      </div>
      <div class="history-actions">
        <button class="ghost-btn view-version" data-version="${escapeHtml(v.version_number)}">View</button>
      </div>
    </article>
  `).join("");

  document.querySelectorAll(".view-version").forEach(btn => {
    btn.addEventListener("click", () => {
      const version = state.history.find(v => String(v.version_number) === String(btn.dataset.version));
      if (!version) return;
      state.reconstruction = version;
      renderReconstruction();
      navigate("reconstruction");
    });
  });
}

function refreshReport() {
  const c = state.currentCase;
  const r = state.reconstruction;
  $("reportCaseId").textContent = c?.id || "—";
  $("reportCaseName").textContent = c?.case_name || "—";
  $("reportVersion").textContent = r ? `V${r.version_number ?? r.version ?? "—"}` : "—";
  $("reportWitnesses").innerHTML = state.witnesses.length
    ? state.witnesses.map((w, i) => `<p><b>Witness #${escapeHtml(w.id ?? i + 1)}:</b> ${escapeHtml(w.statement)}</p>`).join("")
    : "No witnesses.";
  $("reportDescription").textContent = r?.consolidated_description || "No reconstruction.";
  $("reportChange").textContent = r?.change_instruction || "No visual change.";
  if (r?.image_url) {
    $("reportImage").src = r.image_url;
    $("reportImage").hidden = false;
  } else {
    $("reportImage").hidden = true;
  }
}

function applyZoom() {
  const img = $("mainReconImage");
  if (img) img.style.transform = `scale(${state.zoom})`;
}

async function generateReconstruction() {
  if (!state.currentCase?.id) {
    showToast("Create a case first.", "error");
    navigate("dashboard");
    return;
  }
  if (!state.witnesses.length) {
    showToast("No witness statements found.", "error");
    navigate("witnesses");
    return;
  }

  $("processingOverlay").classList.remove("hidden");
  $("generateBtn").disabled = true;
  $("caseGenerateBtn").disabled = true;
  setProcessingStep(1);

  const timers = [
    setTimeout(() => setProcessingStep(2), 500),
    setTimeout(() => setProcessingStep(3), 1300),
    setTimeout(() => setProcessingStep(4), 2200)
  ];

  try {
    const result = await api.generateReconstruction(state.currentCase.id);
    timers.forEach(clearTimeout);
    setProcessingStep(5);
    await new Promise(r => setTimeout(r, 450));
    state.reconstruction = result;
    await loadHistory();
    renderReconstruction();
    refreshCaseView();
    refreshReport();
    showToast(`Reconstruction V${result.version} generated successfully.`, "success");
  } catch (error) {
    timers.forEach(clearTimeout);
    showToast(error.message, "error");
  } finally {
    $("processingOverlay").classList.add("hidden");
    $("generateBtn").disabled = false;
    $("caseGenerateBtn").disabled = false;
  }
}

function setProcessingStep(n) {
  document.querySelectorAll(".processing-step").forEach(step => {
    const index = Number(step.dataset.step);
    step.classList.toggle("active", index === n);
    step.classList.toggle("done", index < n);
  });
}

async function checkApi() {
  try {
    await api.health();
    setApiStatus(true);
  } catch (_) {
    setApiStatus(false);
  }
}

$("caseSelect")?.addEventListener("change", async (event) => {
  await selectCase(event.target.value);
});

document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => navigate(btn.dataset.view));
});

$("newCaseBtn").addEventListener("click", () => openModal("case"));
$("addWitnessBtn").addEventListener("click", () => openModal("witness"));
$("dashAddWitness").addEventListener("click", () => {
  if (!state.currentCase) return openModal("case");
  openModal("witness");
});
$("dashGenerate").addEventListener("click", generateReconstruction);
$("dashHistory").addEventListener("click", () => navigate("history"));
$("caseGenerateBtn").addEventListener("click", generateReconstruction);
$("generateBtn").addEventListener("click", generateReconstruction);
$("refreshWitnessesBtn").addEventListener("click", loadWitnesses);
$("refreshHistoryBtn").addEventListener("click", loadHistory);
$("versionSelect")?.addEventListener("change", (event) => {
  if (event.target.value) viewVersion(event.target.value);
});
$("caseOpenReconstruction").addEventListener("click", () => navigate("reconstruction"));
$("refreshApiBtn").addEventListener("click", checkApi);
$("printReportBtn").addEventListener("click", () => window.print());

$("closeModal").addEventListener("click", closeModal);
$("cancelModal").addEventListener("click", closeModal);
$("saveModal").addEventListener("click", saveModal);

$("statementInput").addEventListener("input", () => {
  $("charCount").textContent = $("statementInput").value.length;
});

$("modal").addEventListener("click", (e) => {
  if (e.target === $("modal")) closeModal();
});

$("zoomIn").addEventListener("click", () => {
  state.zoom = Math.min(2.5, +(state.zoom + 0.1).toFixed(1));
  applyZoom();
});
$("zoomOut").addEventListener("click", () => {
  state.zoom = Math.max(.5, +(state.zoom - 0.1).toFixed(1));
  applyZoom();
});
$("zoomReset").addEventListener("click", () => {
  state.zoom = 1;
  applyZoom();
});
$("fullscreenBtn").addEventListener("click", () => {
  $("imageViewer").requestFullscreen?.();
});

async function init() {
  await checkApi();

  if (state.apiOnline) {
    await loadCases();
  }

  refreshAllViews();
}

init();
