const metrics = document.querySelector("#metrics");
const criteriaList = document.querySelector("#criteria-list");
const evidenceList = document.querySelector("#evidence-list");
const criterionSelect = document.querySelector("#criterion-select");
const uploadForm = document.querySelector("#upload-form");
const uploadStatus = document.querySelector("#upload-status");
const search = document.querySelector("#search");
const welcome = document.querySelector("#welcome");
let currentCriteria = [];

async function getJson(url) {
  const res = await fetch(url);
  const payload = await res.json();
  if (!res.ok) {
    const error = new Error(payload.error || `Request failed: ${res.status}`);
    error.payload = payload;
    throw error;
  }
  return payload;
}

function metric(number, label) {
  return `<div class="metric"><strong>${number}</strong><span>${label}</span></div>`;
}

async function loadDashboard() {
  const data = await getJson("/api/member/dashboard");
  currentCriteria = data.criteria;
  welcome.textContent = `Welcome ${data.client.display_name}.`;
  metrics.innerHTML = [
    metric(`${data.metrics.readiness_score}%`, "Readiness"),
    metric(data.metrics.evidence_count, "Evidence items"),
    metric(data.metrics.open_tasks, "Open tasks"),
    metric(data.metrics.criteria_started, "Criteria started"),
  ].join("");

  criterionSelect.innerHTML = data.criteria
    .map((item) => `<option value="${item.code}">${item.name}</option>`)
    .join("");

  criteriaList.innerHTML = data.criteria
    .map((item) => {
      const avg = Math.round(item.average_score || 0);
      return `
        <div class="criterion">
          <div>
            <h3>${item.name}</h3>
            <p>${item.evidence_count} evidence item(s)</p>
          </div>
          <div class="score">${avg}</div>
        </div>
      `;
    })
    .join("");
}

async function loadEvidence(query = "") {
  const items = await getJson(`/api/evidence${query ? `?q=${encodeURIComponent(query)}` : ""}`);
  const groups = currentCriteria.map((criterion) => ({
    ...criterion,
    files: items.filter((item) => item.criterion_code === criterion.code),
  }));
  const visibleGroups = query ? groups.filter((group) => group.files.length) : groups;
  evidenceList.innerHTML = visibleGroups.length
    ? visibleGroups.map((group) => `
      <section class="evidence-category">
        <div class="category-head">
          <h3>${group.name}</h3>
          <span class="badge">${group.files.length} file${group.files.length === 1 ? "" : "s"}</span>
        </div>
        <div class="category-files">
          ${group.files.length ? group.files.map(renderEvidence).join("") : `<p class="empty-state">No files uploaded in this category yet.</p>`}
        </div>
      </section>
    `).join("")
    : `<p>No evidence matched your search.</p>`;
}

function renderEvidence(item) {
  const href = item.drive_web_url || "#";
  return `
    <article class="evidence">
      <a class="file-link" href="${href}" target="_blank" rel="noreferrer">${item.file_name}</a>
      <button class="delete-button" data-delete-id="${item.id}" type="button">Delete</button>
    </article>
  `;
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  uploadStatus.className = "status-line";
  uploadStatus.textContent = "Uploading evidence...";
  const formData = new FormData(uploadForm);
  let payload;
  try {
    let res = await fetch("/api/evidence", { method: "POST", body: formData });
    payload = await res.json();
    if (res.status === 409 && payload.status === "duplicate") {
      const choice = window.prompt(
        `A file named "${payload.duplicate.file_name}" already exists in this category.\n\nType REPLACE to replace the current file.\nType COPY to keep both files.`,
        "COPY",
      );
      const normalized = (choice || "").trim().toLowerCase();
      if (!["replace", "copy"].includes(normalized)) {
        uploadStatus.className = "status-line error";
        uploadStatus.textContent = "Upload cancelled. Existing file was not changed.";
        return;
      }
      formData.set("duplicate_action", normalized);
      res = await fetch("/api/evidence", { method: "POST", body: formData });
      payload = await res.json();
    }
    if (!res.ok || payload.status === "failed") {
      uploadStatus.className = "status-line error";
      uploadStatus.textContent = "Upload failed. Please try again or contact Ascend support.";
      return;
    }
  } catch (error) {
    uploadStatus.className = "status-line error";
    uploadStatus.textContent = "Upload failed. Please try again or contact Ascend support.";
    return;
  }
  uploadStatus.className = "status-line success";
  uploadStatus.textContent = `Upload successful. Evidence ID: ${payload.evidence_id}`;
  uploadForm.reset();
  await loadDashboard();
  await loadEvidence();
});

search.addEventListener("input", async () => {
  await loadEvidence(search.value.trim());
});

evidenceList.addEventListener("click", async (event) => {
  const button = event.target.closest("[data-delete-id]");
  if (!button) return;
  const evidenceId = button.dataset.deleteId;
  const confirmed = window.confirm("Remove this file from your active evidence list?");
  if (!confirmed) return;
  button.disabled = true;
  button.textContent = "Removing...";
  try {
    const res = await fetch(`/api/evidence/${encodeURIComponent(evidenceId)}`, { method: "DELETE" });
    const payload = await res.json();
    if (!res.ok || payload.status === "failed") {
      window.alert("Could not remove the file. Please try again or contact Ascend support.");
      button.disabled = false;
      button.textContent = "Delete";
      return;
    }
    uploadStatus.className = "status-line success";
    uploadStatus.textContent = "File removed from active evidence.";
    await loadDashboard();
    await loadEvidence(search.value.trim());
  } catch (error) {
    window.alert("Could not remove the file. Please try again or contact Ascend support.");
    button.disabled = false;
    button.textContent = "Delete";
  }
});

loadDashboard().then(() => loadEvidence()).catch((err) => {
  document.body.innerHTML = `<main><h1>Startup error</h1><pre>${err.stack}</pre></main>`;
});
