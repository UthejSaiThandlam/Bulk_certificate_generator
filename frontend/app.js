/**
 * CertifAI Enterprise Dashboard Engine
 * Multi-page routing, live worker polling, cryptographic verification, and instant previews.
 */

const API_BASE = window.location.port === "8000"
  ? ""
  : `${window.location.protocol}//${window.location.hostname || "localhost"}:8000`;

// ── State Management ──
let activePage = "studio";
let currentJobId = null;
let pollInterval = null;
let pollFailureCount = 0;
let selectedCsvFile = null;
let cachedCertificates = [];
let modalSelectedCode = null;

// ── Sample Recipient Datasets ──
const sampleRecipients5 = [
  {
    recipient_name: "Carol White",
    recipient_email: "carol.white@techinstitute.edu",
    course_name: "Data Structures & Algorithms",
    issue_date: "10 April 2025"
  },
  {
    recipient_name: "Dr. Arthur Pendelton",
    recipient_email: "arthur.pendelton@academic.org",
    course_name: "Advanced Distributed Systems & High Performance Python",
    issue_date: "10 April 2025"
  },
  {
    recipient_name: "Prof. Evelyn Vance",
    recipient_email: "evelyn.vance@techinstitute.edu",
    course_name: "Enterprise Machine Learning & Neural Networks",
    issue_date: "10 April 2025"
  },
  {
    recipient_name: "Marcus Aurelius Reed",
    recipient_email: "marcus.reed@domain.com",
    course_name: "Full-Stack Cloud Native Microservices",
    issue_date: "10 April 2025"
  },
  {
    recipient_name: "Dr. Sophia Lin-Zhang",
    recipient_email: "sophia.lin@research.ai",
    course_name: "Applied Transformer Architectures & LLM Engineering",
    issue_date: "10 April 2025"
  }
];

const sampleRecipients20 = [
  ...sampleRecipients5,
  { recipient_name: "David Kim", recipient_email: "david.kim@example.com", course_name: "Data Structures & Algorithms", issue_date: "10 April 2025" },
  { recipient_name: "Elena Rostova", recipient_email: "elena.r@example.com", course_name: "Cloud Architecture & Kubernetes", issue_date: "10 April 2025" },
  { recipient_name: "Amara Okafor", recipient_email: "amara.o@example.com", course_name: "Data Engineering with Apache Spark", issue_date: "10 April 2025" },
  { recipient_name: "Liam O'Connor", recipient_email: "liam.oc@example.com", course_name: "Applied Cybersecurity & Cryptography", issue_date: "10 April 2025" },
  { recipient_name: "Priya Sharma", recipient_email: "priya.s@example.com", course_name: "Full-Stack Cloud Native Microservices", issue_date: "10 April 2025" },
  { recipient_name: "Gabriel Santos", recipient_email: "gabriel.s@example.com", course_name: "Advanced Distributed Systems", issue_date: "10 April 2025" },
  { recipient_name: "Zoe Chen", recipient_email: "zoe.chen@example.com", course_name: "Applied Transformer Architectures", issue_date: "10 April 2025" },
  { recipient_name: "Mohamed Al-Fassi", recipient_email: "mohamed.a@example.com", course_name: "High-Performance Computing with C++ & Python", issue_date: "10 April 2025" },
  { recipient_name: "Hannah Schmidt", recipient_email: "hannah.s@example.com", course_name: "Data Structures & Algorithms", issue_date: "10 April 2025" },
  { recipient_name: "Lucas Silva", recipient_email: "lucas.s@example.com", course_name: "Enterprise Machine Learning", issue_date: "10 April 2025" },
  { recipient_name: "Ananya Patel", recipient_email: "ananya.p@example.com", course_name: "Cloud Architecture & Kubernetes", issue_date: "10 April 2025" },
  { recipient_name: "Kenji Sato", recipient_email: "kenji.s@example.com", course_name: "Applied Cybersecurity & Cryptography", issue_date: "10 April 2025" },
  { recipient_name: "Nadia Benali", recipient_email: "nadia.b@example.com", course_name: "Full-Stack Cloud Native Microservices", issue_date: "10 April 2025" },
  { recipient_name: "Mateo Rossi", recipient_email: "mateo.r@example.com", course_name: "Data Engineering with Apache Spark", issue_date: "10 April 2025" },
  { recipient_name: "Fatima Zahra", recipient_email: "fatima.z@example.com", course_name: "Applied Transformer Architectures", issue_date: "10 April 2025" }
];

// ── Utility: Safe XSS Escaping ──
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

// ── Multi-Page Navigation ──
function navigateToPage(pageId) {
  activePage = pageId;

  // Update navbar buttons
  document.querySelectorAll(".nav-page-btn").forEach(btn => {
    btn.classList.remove("active");
  });
  const activeNavBtn = document.getElementById(`navBtn${capitalize(pageId)}`);
  if (activeNavBtn) activeNavBtn.classList.add("active");

  // Update page views
  document.querySelectorAll(".page-view").forEach(page => {
    page.classList.remove("active");
  });
  const targetPage = document.getElementById(`page${capitalize(pageId)}`);
  if (targetPage) targetPage.classList.add("active");

  // Contextual actions
  if (pageId === "registry") {
    fetchRecentJobs();
  }
}

function capitalize(s) {
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// ── API Docs Modal ──
function openDocsModal(path, label) {
  const modal = document.getElementById("docsModal");
  const iframe = document.getElementById("docsIframe");
  const title = document.getElementById("docsModalTitle");
  if (!modal || !iframe) return;

  title.textContent = label ? `API Documentation — ${label}` : "Interactive API Documentation";
  iframe.src = API_BASE + path;
  modal.style.display = "flex";
  document.body.style.overflow = "hidden";

  // Set active tab pill
  document.querySelectorAll(".tab-pill").forEach(p => p.classList.remove("active"));
  if (path.includes("swagger") || path === "/docs") {
    document.getElementById("docsSwaggerTab")?.classList.add("active");
  } else {
    document.getElementById("docsRedocTab")?.classList.add("active");
  }
}

function switchDocsTab(path, label) {
  openDocsModal(path, label);
}

function closeDocsModal() {
  const modal = document.getElementById("docsModal");
  const iframe = document.getElementById("docsIframe");
  if (modal) modal.style.display = "none";
  if (iframe) iframe.src = "";
  document.body.style.overflow = "";
}

// ── Certificate Detail Modal ──
function openPreviewModal(cert) {
  const modal = document.getElementById("certPreviewModal");
  if (!modal) return;

  modalSelectedCode = cert.certificate_code || null;
  document.getElementById("previewRecipientName").textContent = cert.recipient_name || "Certificate Details";
  document.getElementById("previewCode").textContent = cert.certificate_code || "N/A";
  document.getElementById("previewCourse").textContent = cert.course_name || "N/A";
  document.getElementById("previewEmail").textContent = cert.recipient_email || "N/A";
  document.getElementById("previewIssuer").textContent = cert.issuer_name || "TECH INSTITUTE";
  document.getElementById("previewDate").textContent = cert.issue_date || "N/A";

  const statusBadge = document.getElementById("previewStatusBadge");
  statusBadge.className = `status-badge ${cert.status === "SUCCESS" ? "badge-completed" : "badge-failed"}`;
  statusBadge.textContent = cert.status || "UNKNOWN";

  const errBox = document.getElementById("previewErrorContainer");
  const errText = document.getElementById("previewErrorMsg");
  if (cert.error_message && cert.status !== "SUCCESS") {
    errBox.style.display = "flex";
    errText.textContent = cert.error_message;
  } else {
    errBox.style.display = "none";
  }

  const dlBtn = document.getElementById("previewDownloadBtn");
  if (cert.status === "SUCCESS" && cert.download_url) {
    dlBtn.style.display = "inline-flex";
    dlBtn.href = cert.download_url.startsWith("http") ? cert.download_url : API_BASE + cert.download_url;
  } else {
    dlBtn.style.display = "none";
  }

  const verifyBtn = document.getElementById("previewVerifyDirectBtn");
  verifyBtn.style.display = cert.certificate_code ? "inline-flex" : "none";

  modal.style.display = "flex";
}

function closePreviewModal() {
  const modal = document.getElementById("certPreviewModal");
  if (modal) modal.style.display = "none";
}

function verifyFromModal() {
  if (!modalSelectedCode) return;
  closePreviewModal();
  document.getElementById("verifyCodeInput").value = modalSelectedCode;
  navigateToPage("verify");
  verifyCredential();
}

// ── Ingestion Tabs (JSON vs File) ──
function setTab(tabName) {
  document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

  if (tabName === "json") {
    document.getElementById("tabJsonBtn")?.classList.add("active");
    document.getElementById("jsonSection")?.classList.add("active");
  } else {
    document.getElementById("tabCsvBtn")?.classList.add("active");
    document.getElementById("csvSection")?.classList.add("active");
  }
}

// ── Sample Data Loaders ──
function loadSampleData() {
  const jsonBox = document.getElementById("jsonInput");
  if (!jsonBox) return;
  jsonBox.value = JSON.stringify(sampleRecipients5, null, 2);
  updateJsonRowEstimate();
}

function loadLargeSampleData() {
  const jsonBox = document.getElementById("jsonInput");
  if (!jsonBox) return;
  jsonBox.value = JSON.stringify(sampleRecipients20, null, 2);
  updateJsonRowEstimate();
}

function formatJsonInput() {
  const jsonBox = document.getElementById("jsonInput");
  if (!jsonBox) return;
  try {
    const parsed = JSON.parse(jsonBox.value);
    jsonBox.value = JSON.stringify(parsed, null, 2);
    updateJsonRowEstimate();
  } catch (err) {
    alert("Invalid JSON format: " + err.message);
  }
}

function updateJsonRowEstimate() {
  const jsonBox = document.getElementById("jsonInput");
  const estEl = document.getElementById("jsonRowEstimate");
  if (!jsonBox || !estEl) return;
  try {
    const data = JSON.parse(jsonBox.value.trim() || "[]");
    const count = Array.isArray(data) ? data.length : 1;
    estEl.textContent = `${count} record${count === 1 ? "" : "s"} ready for generation`;
  } catch {
    estEl.textContent = "Formatting / parsing error";
  }
}

// ── Template Selection Handlers ──
const templateDescriptions = {
  classic: {
    name: "Royal Navy & Gold (Classic)",
    desc: "Tech Institute signature design. Sharp angled navy polygons with gold trim stripes, classical Greek pillar crest, live verification QR code, italic script recipient name, and center gold medallion seal.",
    swatches: ["#0B1E36", "#C8A84B", "#FCFBF7"]
  },
  midnight_dark: {
    name: "Midnight Luxury Dark",
    desc: "Dramatic deep navy-black canvas with luminous gold typography, gold foil corner highlights, glowing border accents, and high-contrast dark-mode QR code.",
    swatches: ["#091322", "#D4AF37", "#F6E7B9"]
  },
  vintage_crest: {
    name: "Vintage Crest Parchment",
    desc: "Warm ivory background with ornamental vintage guilloche borders, traditional academic typography, and gold insignia seal.",
    swatches: ["#F9F7F1", "#9B7A2E", "#0B1E36"]
  },
  minimal_gold: {
    name: "Minimalist Modern Gold",
    desc: "Clean editorial aesthetic with ample whitespace, refined hairline gold accents, modern typography, and crisp minimal emblem.",
    swatches: ["#FFFFFF", "#C8A84B", "#1A202C"]
  }
};

function onTemplateChanged(val) {
  const info = templateDescriptions[val] || templateDescriptions.classic;
  const nameEl = document.getElementById("sidebarTplName");
  const descEl = document.getElementById("sidebarTplDesc");
  if (nameEl) nameEl.textContent = info.name;
  if (descEl) descEl.textContent = info.desc;
}

function selectTemplateAndGo(tplName) {
  const select = document.getElementById("templateSelect");
  if (select) {
    select.value = tplName;
    onTemplateChanged(tplName);
  }
  navigateToPage("studio");
}

// ── Drag & Drop File Upload Handlers ──
function initDragAndDrop() {
  const dropzone = document.getElementById("dropzone");
  if (!dropzone) return;

  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.add("dragover");
    }, false);
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, (e) => {
      e.preventDefault();
      e.stopPropagation();
      dropzone.classList.remove("dragover");
    }, false);
  });

  dropzone.addEventListener("drop", (e) => {
    const dt = e.dataTransfer;
    const files = dt.files;
    if (files.length > 0) {
      applySelectedFile(files[0]);
    }
  }, false);
}

function handleCsvSelected(event) {
  if (event.target.files && event.target.files.length > 0) {
    applySelectedFile(event.target.files[0]);
  }
}

function applySelectedFile(file) {
  selectedCsvFile = file;
  const infoBadge = document.getElementById("csvFileInfo");
  const fileName = document.getElementById("csvFileName");
  const fileSize = document.getElementById("csvFileSize");
  const submitBtn = document.getElementById("btnSubmitCsv");

  if (fileName) fileName.textContent = file.name;
  if (fileSize) fileSize.textContent = `${(file.size / 1024).toFixed(1)} KB`;
  if (infoBadge) infoBadge.style.display = "flex";
  if (submitBtn) submitBtn.disabled = false;
}

function clearCsvFile(event) {
  if (event) event.stopPropagation();
  selectedCsvFile = null;
  const fileInput = document.getElementById("csvFileInput");
  if (fileInput) fileInput.value = "";
  const infoBadge = document.getElementById("csvFileInfo");
  const submitBtn = document.getElementById("btnSubmitCsv");
  if (infoBadge) infoBadge.style.display = "none";
  if (submitBtn) submitBtn.disabled = true;
}

function formatApiErrorMessage(err) {
  if (!err) return "Unknown server error";
  if (typeof err === "string") return err;
  if (typeof err.detail === "string") return err.detail;
  if (Array.isArray(err.detail)) {
    return err.detail.map(d => `${d.loc ? d.loc.slice(1).join('.') + ': ' : ''}${d.msg}`).join(", ");
  }
  if (typeof err.detail === "object" && err.detail !== null) {
    return JSON.stringify(err.detail);
  }
  if (err.message) return err.message;
  return JSON.stringify(err);
}

// ── Job Submission: JSON Payload ──
async function submitJsonJob() {
  const jsonBox = document.getElementById("jsonInput");
  const submitBtn = document.getElementById("btnSubmitJson");
  const issuer = document.getElementById("issuerNameInput")?.value || "TECH INSTITUTE";
  const template = document.getElementById("templateSelect")?.value || "classic";
  const dedupe = document.getElementById("dedupeToggle")?.checked ?? true;
  const rawKey = document.getElementById("idempotencyKeyInput")?.value.trim() || null;

  let recipients = [];
  try {
    recipients = JSON.parse(jsonBox.value.trim());
    if (!Array.isArray(recipients) || recipients.length === 0) {
      alert("Please provide an array with at least 1 recipient object.");
      return;
    }
  } catch (err) {
    alert("Invalid JSON format: " + err.message);
    return;
  }

  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span>⏳ Dispatching Job...</span>`;

  try {
    const payload = {
      recipients: recipients,
      template_name: template,
      issuer_name: issuer,
      idempotency_key: rawKey || `BATCH-${Date.now()}`,
      deduplicate_by_email: dedupe,
      deduplicate: dedupe
    };

    const res = await fetch(`${API_BASE}/api/certificates/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(formatApiErrorMessage(err));
    }

    const job = await res.json();
    launchLiveJobMonitoring(job.id);
  } catch (err) {
    alert(`Error starting batch: ${err.message}`);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<span class="btn-icon">⚡</span> Run Bulk Generation Job`;
  }
}

// ── Job Submission: File Upload ──
async function submitCsvJob() {
  if (!selectedCsvFile) return;

  const submitBtn = document.getElementById("btnSubmitCsv");
  const issuer = document.getElementById("issuerNameInput")?.value || "TECH INSTITUTE";
  const template = document.getElementById("templateSelect")?.value || "classic";
  const dedupe = document.getElementById("dedupeToggle")?.checked ?? true;
  const rawKey = document.getElementById("idempotencyKeyInput")?.value.trim() || null;

  submitBtn.disabled = true;
  submitBtn.innerHTML = `<span>⏳ Uploading &amp; Parsing File...</span>`;

  try {
    const formData = new FormData();
    formData.append("file", selectedCsvFile);
    formData.append("template_name", template);
    formData.append("issuer_name", issuer);
    formData.append("deduplicate", dedupe.toString());
    if (rawKey) formData.append("idempotency_key", rawKey);

    const res = await fetch(`${API_BASE}/api/certificates/upload-file`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(formatApiErrorMessage(err));
    }

    const job = await res.json();
    clearCsvFile();
    launchLiveJobMonitoring(job.id);
  } catch (err) {
    alert(`Error processing file: ${err.message}`);
  } finally {
    submitBtn.disabled = false;
    submitBtn.innerHTML = `<span class="btn-icon">⚡</span> Ingest File &amp; Generate Certificates`;
  }
}

// ── Live Worker Monitoring & Polling ──
function launchLiveJobMonitoring(jobId) {
  currentJobId = jobId;
  pollFailureCount = 0;

  // Navigate to Live Monitor view
  navigateToPage("monitor");

  const emptyState = document.getElementById("monitorEmptyState");
  const hud = document.getElementById("jobProgressHud");
  if (emptyState) emptyState.style.display = "none";
  if (hud) hud.style.display = "flex";

  const activeIndicator = document.getElementById("activeJobIndicator");
  if (activeIndicator) activeIndicator.style.display = "inline-block";

  // Reset Progress HUD
  document.getElementById("hudJobId").textContent = jobId;
  document.getElementById("hudProgressBar").style.width = "0%";
  document.getElementById("hudPercent").textContent = "0%";
  document.getElementById("hudTotal").textContent = "0";
  document.getElementById("hudSuccess").textContent = "0";
  document.getElementById("hudFailed").textContent = "0";
  document.getElementById("hudStatusSummary").textContent = "Queueing...";
  document.getElementById("zipDownloadContainer").style.display = "none";

  if (pollInterval) clearInterval(pollInterval);
  fetchJobStatus();
  pollInterval = setInterval(fetchJobStatus, 800);
}

async function fetchJobStatus() {
  if (!currentJobId) return;

  try {
    const res = await fetch(`${API_BASE}/api/certificates/jobs/${currentJobId}`);
    if (!res.ok) {
      pollFailureCount++;
      if (pollFailureCount > 6) {
        clearInterval(pollInterval);
      }
      return;
    }

    const job = await res.json();
    pollFailureCount = 0;
    updateMonitorHUD(job);

    if (job.status === "COMPLETED" || job.status === "COMPLETED_WITH_ERRORS" || job.status === "FAILED") {
      clearInterval(pollInterval);
      const activeIndicator = document.getElementById("activeJobIndicator");
      if (activeIndicator) activeIndicator.style.display = "none";
    }
  } catch {
    pollFailureCount++;
    if (pollFailureCount > 6) clearInterval(pollInterval);
  }
}

function updateMonitorHUD(job) {
  document.getElementById("hudJobId").textContent = job.id;
  document.getElementById("hudTemplateBadge").textContent = `Template: ${job.template_name || 'classic'}`;

  const pct = job.progress_percentage || 0;
  document.getElementById("hudProgressBar").style.width = `${pct}%`;
  document.getElementById("hudPercent").textContent = `${pct}%`;

  document.getElementById("hudTotal").textContent = job.total;
  document.getElementById("hudSuccess").textContent = job.successful;
  document.getElementById("hudFailed").textContent = job.failed;

  const badge = document.getElementById("hudBadge");
  const summary = document.getElementById("hudStatusSummary");

  if (job.status === "COMPLETED") {
    badge.className = "status-badge badge-completed";
    badge.textContent = "COMPLETED";
    summary.textContent = "Finished 100%";
  } else if (job.status === "COMPLETED_WITH_ERRORS") {
    badge.className = "status-badge badge-failed";
    badge.textContent = "WITH ERRORS";
    summary.textContent = "Partially Completed";
  } else if (job.status === "FAILED") {
    badge.className = "status-badge badge-failed";
    badge.textContent = "FAILED";
    summary.textContent = "Batch Aborted";
  } else {
    badge.className = "status-badge badge-processing";
    badge.textContent = "PROCESSING";
    summary.textContent = "Generating...";
  }

  // ZIP Download link
  const zipContainer = document.getElementById("zipDownloadContainer");
  const zipBtn = document.getElementById("btnZipDownload");
  if (job.download_zip_url) {
    zipContainer.style.display = "flex";
    zipBtn.href = job.download_zip_url.startsWith("http") ? job.download_zip_url : API_BASE + job.download_zip_url;
  } else {
    zipContainer.style.display = "none";
  }

  // Render Certificates List
  cachedCertificates = job.certificates || [];
  renderCertificatesList(cachedCertificates);
}

function renderCertificatesList(certs) {
  const container = document.getElementById("hudCertificatesList");
  if (!container) return;

  if (!certs || certs.length === 0) {
    container.innerHTML = `<p class="muted-text" style="padding:1rem; text-align:center;">No certificate records generated yet.</p>`;
    return;
  }

  container.innerHTML = certs.map(c => {
    const isSuccess = c.status === "SUCCESS";
    const statusPill = isSuccess
      ? `<span class="badge-pill" style="color:var(--accent-green); border-color:rgba(16,185,129,0.3);">SUCCESS</span>`
      : `<span class="badge-pill" style="color:var(--accent-red); border-color:rgba(239,68,68,0.3);">FAILED</span>`;

    const downloadLink = (isSuccess && c.download_url)
      ? `<a href="${c.download_url.startsWith('http') ? c.download_url : API_BASE + c.download_url}" target="_blank" class="btn btn-sm btn-primary" title="Download PDF"><span>📥 PDF</span></a>`
      : "";

    return `
      <div class="cert-row-card">
        <div class="cert-main-info">
          <div class="cert-row-top">
            <span class="cert-name">${escapeHtml(c.recipient_name || 'Invalid Entry')}</span>
            ${c.certificate_code ? `<span class="cert-code">${escapeHtml(c.certificate_code)}</span>` : ''}
            ${statusPill}
          </div>
          <span class="cert-meta">${escapeHtml(c.course_name || 'N/A')} • ${escapeHtml(c.recipient_email || 'No email')}</span>
          ${c.error_message ? `<span class="cert-meta" style="color:var(--accent-red);">⚠️ ${escapeHtml(c.error_message)}</span>` : ''}
        </div>
        <div class="cert-row-actions">
          ${downloadLink}
          <button class="btn btn-sm btn-secondary" onclick='openPreviewModal(${JSON.stringify(c).replace(/'/g, "&apos;")})'>
            <span>👁️ Details</span>
          </button>
        </div>
      </div>
    `;
  }).join("");
}

function filterCertificatesList(query) {
  const q = query.toLowerCase().trim();
  if (!q) {
    renderCertificatesList(cachedCertificates);
    return;
  }
  const filtered = cachedCertificates.filter(c =>
    (c.recipient_name && c.recipient_name.toLowerCase().includes(q)) ||
    (c.recipient_email && c.recipient_email.toLowerCase().includes(q)) ||
    (c.course_name && c.course_name.toLowerCase().includes(q)) ||
    (c.certificate_code && c.certificate_code.toLowerCase().includes(q))
  );
  renderCertificatesList(filtered);
}

// ── Credential Verification ──
async function quickVerify() {
  const code = document.getElementById("quickVerifyInput")?.value.trim();
  if (!code) return;

  const resultBox = document.getElementById("quickVerifyResult");
  resultBox.style.display = "block";
  resultBox.innerHTML = `<span class="muted-text">Verifying with registry...</span>`;

  try {
    const res = await fetch(`${API_BASE}/api/certificates/verify/${encodeURIComponent(code)}`);
    const data = await res.json();

    if (data.is_valid) {
      resultBox.innerHTML = `
        <div style="color:var(--accent-green); font-weight:700; margin-bottom:0.25rem;">✓ Valid Certificate</div>
        <div style="font-size:0.8rem; color:#fff;">${escapeHtml(data.recipient_name)}</div>
        <div style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(data.course_name)}</div>
        ${data.download_url ? `<a href="${data.download_url.startsWith('http') ? data.download_url : API_BASE + data.download_url}" target="_blank" class="btn btn-sm btn-primary" style="margin-top:0.5rem;">📥 Download Official PDF</a>` : ''}
      `;
    } else {
      resultBox.innerHTML = `
        <div style="color:var(--accent-red); font-weight:700;">✕ Invalid Credential</div>
        <div style="font-size:0.75rem; color:var(--text-muted);">${escapeHtml(data.error_message || 'Certificate code not found.')}</div>
      `;
    }
  } catch (err) {
    resultBox.innerHTML = `<span style="color:var(--accent-red);">Verification error: ${err.message}</span>`;
  }
}

async function verifyCredential() {
  const code = document.getElementById("verifyCodeInput")?.value.trim();
  if (!code) {
    alert("Please enter a certificate verification code.");
    return;
  }

  const resultBox = document.getElementById("verificationResultBox");
  resultBox.style.display = "block";
  resultBox.innerHTML = `
    <div class="empty-state">
      <div class="empty-icon">🔍</div>
      <p class="muted-text">Querying cryptographic ledger and database index...</p>
    </div>
  `;

  try {
    const res = await fetch(`${API_BASE}/api/certificates/verify/${encodeURIComponent(code)}`);
    const data = await res.json();

    if (data.is_valid) {
      resultBox.innerHTML = `
        <div class="verify-card-result verified">
          <div class="verify-header">
            <div class="verify-badge-icon">🛡️</div>
            <div class="verify-title-group">
              <h3 style="color:var(--accent-green);">Authentic &amp; Verified Credential</h3>
              <p>Cryptographic hash and registry index matched successfully.</p>
            </div>
          </div>
          <div class="verify-details-grid">
            <div class="verify-detail-item">
              <span class="verify-detail-label">Recipient Name</span>
              <span class="verify-detail-val name-script">${escapeHtml(data.recipient_name || 'N/A')}</span>
            </div>
            <div class="verify-detail-item">
              <span class="verify-detail-label">Verification Code</span>
              <span class="verify-detail-val code-highlight">${escapeHtml(data.certificate_code)}</span>
            </div>
            <div class="verify-detail-item">
              <span class="verify-detail-label">Course / Program</span>
              <span class="verify-detail-val">${escapeHtml(data.course_name || 'N/A')}</span>
            </div>
            <div class="verify-detail-item">
              <span class="verify-detail-label">Issuing Authority</span>
              <span class="verify-detail-val">${escapeHtml(data.issuer_name || 'TECH INSTITUTE')}</span>
            </div>
            <div class="verify-detail-item">
              <span class="verify-detail-label">Date of Issue</span>
              <span class="verify-detail-val">${escapeHtml(data.issue_date || 'N/A')}</span>
            </div>
            <div class="verify-detail-item">
              <span class="verify-detail-label">Timestamp Verified</span>
              <span class="verify-detail-val">${new Date(data.verification_timestamp).toLocaleString()}</span>
            </div>
          </div>
          <div class="verify-actions">
            ${data.download_url ? `<a href="${data.download_url.startsWith('http') ? data.download_url : API_BASE + data.download_url}" target="_blank" class="btn btn-primary btn-lg"><span>📥 Download Authentic PDF</span></a>` : ''}
            <button class="btn btn-secondary btn-lg" onclick="navigateToPage('studio')">⚡ Generate Another Batch</button>
          </div>
        </div>
      `;
    } else {
      resultBox.innerHTML = `
        <div class="verify-card-result unverified">
          <div class="verify-header">
            <div class="verify-badge-icon">❌</div>
            <div class="verify-title-group">
              <h3 style="color:var(--accent-red);">Certificate Code Not Authenticated</h3>
              <p>${escapeHtml(data.error_message || 'The specified credential could not be verified in the registry.')}</p>
            </div>
          </div>
          <p style="font-size:0.85rem; color:var(--text-muted); margin-bottom:1rem;">
            Please ensure you have entered the exact uppercase code formatted as <code>CERT-XXXX-XXXX</code>.
          </p>
          <button class="btn btn-secondary" onclick="document.getElementById('verifyCodeInput').focus()">Try Again</button>
        </div>
      `;
    }
  } catch (err) {
    resultBox.innerHTML = `
      <div class="error-notice">
        <span>Verification request failed: ${escapeHtml(err.message)}</span>
      </div>
    `;
  }
}

// ── Job Registry History ──
async function fetchRecentJobs() {
  const list = document.getElementById("recentJobsList");
  if (!list) return;

  try {
    const res = await fetch(`${API_BASE}/api/certificates/jobs?limit=25`);
    if (!res.ok) throw new Error("Failed to fetch jobs");
    const jobs = await res.json();

    const statsJobCount = document.getElementById("statsJobCount");
    if (statsJobCount) statsJobCount.textContent = `${jobs.length} Job${jobs.length === 1 ? '' : 's'}`;

    if (jobs.length === 0) {
      list.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">📋</div>
          <p class="muted-text">No generation jobs recorded yet. Launch your first batch from the Studio.</p>
          <button class="btn btn-primary" onclick="navigateToPage('studio')" style="margin-top:0.75rem;">⚡ Go to Studio</button>
        </div>
      `;
      return;
    }

    list.innerHTML = jobs.map(j => {
      const isDone = j.status === "COMPLETED";
      const statusClass = isDone ? "badge-completed" : (j.status === "PROCESSING" ? "badge-processing" : "badge-failed");
      const zipBtn = (j.download_zip_url)
        ? `<a href="${j.download_zip_url.startsWith('http') ? j.download_zip_url : API_BASE + j.download_zip_url}" target="_blank" class="btn btn-sm btn-accent" title="Download ZIP"><span>📦 ZIP</span></a>`
        : "";

      return `
        <div class="job-history-row">
          <div class="job-row-main">
            <span class="status-badge ${statusClass}">${j.status}</span>
            <div>
              <div class="job-row-id">${escapeHtml(j.id)}</div>
              <div class="job-row-meta">
                ${new Date(j.created_at).toLocaleString()} • ${j.successful}/${j.total} Successful • Template: <strong>${escapeHtml(j.template_name || 'classic')}</strong>
              </div>
            </div>
          </div>
          <div class="job-row-actions">
            ${zipBtn}
            <button class="btn btn-sm btn-secondary" onclick="launchLiveJobMonitoring('${j.id}')">
              <span>📊 Inspect Job</span>
            </button>
          </div>
        </div>
      `;
    }).join("");
  } catch {
    list.innerHTML = `<p class="muted-text" style="padding:1rem;">Failed to load job registry.</p>`;
  }
}

// ── Health Check ──
async function checkBackendHealth() {
  const pill = document.getElementById("backendStatus");
  const text = document.getElementById("backendStatusText");
  const engineVal = document.getElementById("engineStatusVal");

  try {
    const res = await fetch(`${API_BASE}/health`);
    if (res.ok) {
      const data = await res.json();
      pill.className = "status-pill status-online";
      text.textContent = "API Ready";
      if (engineVal) engineVal.textContent = `${data.service} (${data.database})`;
    } else {
      pill.className = "status-pill status-offline";
      text.textContent = "Degraded";
    }
  } catch {
    pill.className = "status-pill status-offline";
    text.textContent = "Disconnected";
  }
}

// ── Keyboard Shortcuts ──
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeDocsModal();
    closePreviewModal();
  }
});

// ── Initialization ──
document.addEventListener("DOMContentLoaded", () => {
  initDragAndDrop();
  loadSampleData();
  checkBackendHealth();
  setInterval(checkBackendHealth, 15000);
  fetchRecentJobs();
});
