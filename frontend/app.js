const API_BASE = window.location.port === "8000" ? "" : "http://127.0.0.1:8000";

let pollInterval = null;
let selectedCsvFile = null;

const sampleRecipients = [
  {
    recipient_name: "Eleanor Vance",
    recipient_email: "eleanor@example.com",
    course_name: "Full Stack Cloud Architecture",
    issue_date: "2025-06-15"
  },
  {
    recipient_name: "Marcus Aurelius Reed",
    recipient_email: "marcus@example.com",
    course_name: "Advanced Python & Distributed Systems",
    issue_date: "2025-06-15"
  },
  {
    recipient_name: "Dr. Sophia Lin-Zhang",
    recipient_email: "sophia@example.com",
    course_name: "Applied Machine Learning & Deep Neural Nets",
    issue_date: "2025-06-15"
  },
  {
    recipient_name: "Carlos Mendoza",
    recipient_email: "carlos@example.com",
    course_name: "Enterprise Microservices with FastAPI",
    issue_date: "2025-06-15"
  }
];

function init() {
  loadSampleData();
  checkBackendHealth();
  fetchRecentJobs();
  setInterval(checkBackendHealth, 10000);
}

function loadSampleData() {
  document.getElementById("jsonInput").value = JSON.stringify(sampleRecipients, null, 2);
}

function setTab(tab) {
  document.getElementById("tabJsonBtn").classList.toggle("active", tab === "json");
  document.getElementById("tabCsvBtn").classList.toggle("active", tab === "csv");
  document.getElementById("jsonSection").classList.toggle("active", tab === "json");
  document.getElementById("csvSection").classList.toggle("active", tab === "csv");
}

async function checkBackendHealth() {
  const statusEl = document.getElementById("backendStatus");
  const textEl = document.getElementById("backendStatusText");
  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      statusEl.className = "status-pill status-online";
      textEl.innerText = "API Connected (Port 8000)";
    } else {
      throw new Error("HTTP " + res.status);
    }
  } catch (e) {
    statusEl.className = "status-pill status-offline";
    textEl.innerText = "API Offline (Start backend)";
  }
}

async function submitJsonJob() {
  const jsonText = document.getElementById("jsonInput").value.trim();
  let recipients;
  try {
    recipients = JSON.parse(jsonText);
  } catch (err) {
    alert("Invalid JSON format in recipients list: " + err.message);
    return;
  }

  const issuer = document.getElementById("issuerNameInput").value.trim();
  const template = document.getElementById("templateSelect").value;
  const dedupe = document.getElementById("dedupeToggle").checked;

  const btn = document.getElementById("btnSubmitJson");
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/certificates/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        issuer_name: issuer,
        template_name: template,
        deduplicate_by_email: dedupe,
        recipients: recipients
      })
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail?.message || data.detail || JSON.stringify(data));
    }

    startMonitoringJob(data.id);
  } catch (err) {
    alert("Failed to submit job: " + err.message);
  } finally {
    btn.disabled = false;
  }
}

function handleCsvSelected(event) {
  const file = event.target.files[0];
  if (!file) return;
  selectedCsvFile = file;
  document.getElementById("csvFileName").innerText = `${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
  document.getElementById("csvFileInfo").style.display = "flex";
  document.getElementById("btnSubmitCsv").disabled = false;
}

function clearCsvFile(e) {
  e.stopPropagation();
  selectedCsvFile = null;
  document.getElementById("csvFileInput").value = "";
  document.getElementById("csvFileInfo").style.display = "none";
  document.getElementById("btnSubmitCsv").disabled = true;
}

async function submitCsvJob() {
  if (!selectedCsvFile) return;

  const formData = new FormData();
  formData.append("file", selectedCsvFile);
  formData.append("issuer_name", document.getElementById("issuerNameInput").value.trim());
  formData.append("template_name", document.getElementById("templateSelect").value);
  formData.append("deduplicate", document.getElementById("dedupeToggle").checked);

  const btn = document.getElementById("btnSubmitCsv");
  btn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/certificates/upload-file`, {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail?.message || data.detail || JSON.stringify(data));
    }

    startMonitoringJob(data.id);
  } catch (err) {
    alert("Failed to process CSV: " + err.message);
  } finally {
    btn.disabled = false;
  }
}

function startMonitoringJob(jobId) {
  if (pollInterval) clearInterval(pollInterval);
  document.getElementById("jobProgressHud").style.display = "block";
  document.getElementById("hudJobId").innerText = `Job ID: ${jobId.substring(0, 18)}...`;

  pollJob(jobId);
  pollInterval = setInterval(() => pollJob(jobId), 1500);
}

async function pollJob(jobId) {
  try {
    const res = await fetch(`${API_BASE}/api/certificates/jobs/${jobId}`);
    const data = await res.json();
    if (!res.ok) return;

    // Update HUD
    const pct = data.progress_percentage || 0;
    document.getElementById("hudProgressBar").style.width = pct + "%";
    document.getElementById("hudPercent").innerText = pct + "%";
    document.getElementById("hudTotal").innerText = data.total;
    document.getElementById("hudSuccess").innerText = data.successful;
    document.getElementById("hudFailed").innerText = data.failed;

    const badge = document.getElementById("hudBadge");
    badge.innerText = data.status;
    badge.className = `status-badge badge-${data.status.toLowerCase()}`;

    // Completion / Failure
    const isFinished = ["COMPLETED", "COMPLETED_WITH_ERRORS", "FAILED"].includes(data.status);
    if (isFinished) {
      clearInterval(pollInterval);
      if (data.download_zip_url) {
        document.getElementById("zipDownloadContainer").style.display = "block";
        document.getElementById("btnZipDownload").href = `${API_BASE}${data.download_zip_url}`;
      }
      fetchRecentJobs();
    }

    // Render certificates
    if (data.certificates && data.certificates.length) {
      const list = document.getElementById("hudCertificatesList");
      list.innerHTML = data.certificates.map(c => `
        <div class="cert-row">
          <div>
            <strong>${c.recipient_name}</strong>
            <div style="font-size:0.75rem; color:var(--text-muted);">${c.certificate_code} • ${c.course_name}</div>
          </div>
          <div>
            ${c.download_url ? `<a href="${API_BASE}${c.download_url}" target="_blank">Download PDF ↗</a>` : `<span style="color:var(--accent-red); font-size:0.8rem;">${c.error_message || 'Processing'}</span>`}
          </div>
        </div>
      `).join("");
    }
  } catch (err) {
    console.error("Polling error:", err);
  }
}

async function verifyCredential() {
  const code = document.getElementById("verifyCodeInput").value.trim();
  if (!code) {
    alert("Please enter a verification code");
    return;
  }

  const box = document.getElementById("verificationResultBox");
  box.style.display = "block";
  box.innerHTML = `<p class="muted-text">Verifying credential against registry...</p>`;

  try {
    const res = await fetch(`${API_BASE}/api/certificates/verify/${encodeURIComponent(code)}`);
    const data = await res.json();

    if (data.is_valid) {
      box.innerHTML = `
        <div style="color:var(--accent-green); font-weight:800; font-size:1.05rem; margin-bottom:0.6rem;">
          ✔ Authentic Credential
        </div>
        <div style="font-size:0.85rem; line-height:1.6;">
          <strong>Recipient:</strong> ${data.recipient_name}<br>
          <strong>Program:</strong> ${data.course_name}<br>
          <strong>Issuing Authority:</strong> ${data.issuer_name}<br>
          <strong>Issue Date:</strong> ${data.issue_date}<br>
          <strong>Registry ID:</strong> <code>${data.certificate_code}</code><br>
          ${data.download_url ? `<a href="${API_BASE}${data.download_url}" target="_blank" style="color:var(--primary); font-weight:700; display:inline-block; margin-top:0.6rem;">Download Official Certificate ↗</a>` : ''}
        </div>
      `;
    } else {
      box.innerHTML = `
        <div style="color:var(--accent-red); font-weight:800; font-size:1.05rem; margin-bottom:0.4rem;">
          ✖ Verification Failed
        </div>
        <p style="font-size:0.85rem; color:var(--text-muted);">${data.error_message || "Code was not found in official certificate records."}</p>
      `;
    }
  } catch (err) {
    box.innerHTML = `<span style="color:var(--accent-red);">Error connecting to verification server: ${err.message}</span>`;
  }
}

async function fetchRecentJobs() {
  try {
    const res = await fetch(`${API_BASE}/api/certificates/jobs?limit=6`);
    const jobs = await res.json();
    const list = document.getElementById("recentJobsList");

    if (!jobs || !jobs.length) {
      list.innerHTML = `<p class="muted-text">No jobs recorded yet.</p>`;
      return;
    }

    list.innerHTML = jobs.map(j => `
      <div class="job-item" onclick="startMonitoringJob('${j.id}')">
        <div>
          <strong style="font-size:0.85rem;">Job ${j.id.slice(0, 8)}...</strong>
          <div style="font-size:0.75rem; color:var(--text-muted);">
            ${j.successful} passed, ${j.failed} failed of ${j.total}
          </div>
        </div>
        <div>
          <span class="status-badge badge-${j.status.toLowerCase()}">${j.status}</span>
        </div>
      </div>
    `).join("");
  } catch (e) {
    console.error("Error fetching jobs:", e);
  }
}

window.addEventListener("DOMContentLoaded", init);
