import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.database import engine, Base
from app.routers import certificates
from app.services.certificate_generator import CertificateGenerator
from app.services.job_processor import resume_interrupted_jobs


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure database tables exist
    Base.metadata.create_all(bind=engine)
    # Ensure generated and templates directories exist
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    templates_dir = os.path.join(base_dir, "templates")
    generated_dir = os.path.join(base_dir, "generated")
    os.makedirs(generated_dir, exist_ok=True)
    os.makedirs(templates_dir, exist_ok=True)

    # 1. Startup validation: fail fast if ReportLab / template is broken
    CertificateGenerator.validate_template_at_startup(templates_dir)

    # 2. Crash recovery: resume any jobs interrupted if server restarted unexpectedly
    resume_interrupted_jobs()

    yield


app = FastAPI(
    title="Bulk Certificate Generator API",
    description="A high-performance FastAPI service for generating, managing, and verifying bulk PDF certificates with background processing.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(certificates.router)


@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint to verify service and database connectivity."""
    return {
        "status": "healthy",
        "service": "Bulk Certificate Generator",
        "version": "1.0.0",
    }


@app.get("/", response_class=HTMLResponse, tags=["Dashboard"])
def get_dashboard():
    """
    Interactive web console for Bulk Certificate Generation,
    file uploads, real-time job monitoring, and credential verification.
    """
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bulk Certificate Generator - Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Playfair+Display:ital,wght@0,600;0,700;1,600&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #090d16;
      --card-bg: rgba(17, 24, 39, 0.75);
      --card-border: rgba(255, 255, 255, 0.08);
      --primary: #3b82f6;
      --primary-hover: #2563eb;
      --gold: #f59e0b;
      --gold-hover: #d97706;
      --accent: #10b981;
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; }
    body {
      background: radial-gradient(circle at top right, #1e1b4b 0%, var(--bg) 60%);
      color: var(--text);
      min-height: 100vh;
      padding: 2rem 1rem;
    }
    .container { max-width: 1100px; margin: 0 auto; }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 2.5rem;
      flex-wrap: wrap;
      gap: 1rem;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 1.5rem;
    }
    .logo-badge {
      display: inline-flex;
      align-items: center;
      gap: 0.6rem;
      background: rgba(245, 158, 11, 0.15);
      border: 1px solid rgba(245, 158, 11, 0.3);
      padding: 0.35rem 0.85rem;
      border-radius: 9999px;
      font-size: 0.85rem;
      color: var(--gold);
      font-weight: 600;
      margin-bottom: 0.5rem;
    }
    h1 { font-size: 2.2rem; font-weight: 800; letter-spacing: -0.02em; }
    .nav-links a {
      color: var(--text-muted);
      text-decoration: none;
      margin-left: 1.25rem;
      font-size: 0.95rem;
      transition: color 0.2s;
    }
    .nav-links a:hover { color: #fff; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; }
    @media (max-width: 860px) { .grid { grid-template-columns: 1fr; } }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      backdrop-filter: blur(16px);
      border-radius: 16px;
      padding: 1.75rem;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.4);
    }
    .card-title {
      font-size: 1.25rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }
    .card-subtitle { font-size: 0.875rem; color: var(--text-muted); margin-bottom: 1.25rem; }
    .form-group { margin-bottom: 1rem; }
    label { display: block; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.35rem; color: #cbd5e1; }
    input, textarea, select {
      width: 100%;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 8px;
      padding: 0.75rem;
      color: #fff;
      font-size: 0.9rem;
      outline: none;
      transition: border-color 0.2s;
    }
    input:focus, textarea:focus { border-color: var(--primary); }
    button {
      cursor: pointer;
      font-weight: 600;
      padding: 0.75rem 1.25rem;
      border-radius: 8px;
      border: none;
      transition: all 0.2s ease;
      font-size: 0.9rem;
    }
    .btn-primary {
      background: linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);
      color: #fff;
      width: 100%;
      box-shadow: 0 4px 14px rgba(59, 130, 246, 0.35);
    }
    .btn-primary:hover { opacity: 0.95; transform: translateY(-1px); }
    .btn-gold {
      background: linear-gradient(135deg, #f59e0b 0%, #b45309 100%);
      color: #fff;
      box-shadow: 0 4px 14px rgba(245, 158, 11, 0.35);
    }
    .tab-bar { display: flex; gap: 0.5rem; margin-bottom: 1.25rem; }
    .tab-btn {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--card-border);
      color: var(--text-muted);
      padding: 0.5rem 1rem;
      border-radius: 8px;
    }
    .tab-btn.active {
      background: rgba(59, 130, 246, 0.2);
      border-color: rgba(59, 130, 246, 0.5);
      color: #fff;
    }
    .status-box {
      margin-top: 1.25rem;
      padding: 1rem;
      background: rgba(15, 23, 42, 0.9);
      border-radius: 8px;
      border: 1px solid var(--card-border);
      display: none;
    }
    .progress-bar-container {
      height: 8px;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 4px;
      overflow: hidden;
      margin: 0.75rem 0;
    }
    .progress-bar {
      height: 100%;
      background: linear-gradient(90deg, var(--primary), var(--accent));
      width: 0%;
      transition: width 0.3s ease;
    }
    .badge {
      display: inline-block;
      padding: 0.2rem 0.5rem;
      border-radius: 4px;
      font-size: 0.75rem;
      font-weight: 700;
      text-transform: uppercase;
    }
    .badge-completed { background: rgba(16, 185, 129, 0.2); color: #34d399; }
    .badge-processing { background: rgba(59, 130, 246, 0.2); color: #60a5fa; }
    .badge-failed { background: rgba(239, 68, 68, 0.2); color: #f87171; }
    .cert-item {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.6rem 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.05);
      font-size: 0.85rem;
    }
    .cert-item:last-child { border-bottom: none; }
    .download-link {
      color: var(--primary);
      text-decoration: none;
      font-weight: 600;
    }
    .download-link:hover { text-decoration: underline; }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <div>
        <div class="logo-badge">✦ High-Throughput PDF Engine</div>
        <h1>Bulk Certificate Generator</h1>
      </div>
      <div class="nav-links">
        <a href="/docs" target="_blank">Interactive API Docs (Swagger)</a>
        <a href="/redoc" target="_blank">ReDoc</a>
        <a href="/health" target="_blank">System Health</a>
      </div>
    </header>

    <div class="grid">
      <!-- Left Column: Generator Form -->
      <div class="card">
        <div class="card-title">Create Generation Job</div>
        <div class="card-subtitle">Generate bulk certificates via instant JSON input or CSV spreadsheet upload.</div>

        <div class="tab-bar">
          <button class="tab-btn active" id="tabJsonBtn" onclick="switchTab('json')">Direct Input</button>
          <button class="tab-btn" id="tabCsvBtn" onclick="switchTab('csv')">Upload CSV</button>
        </div>

        <div class="form-group">
          <label>Issuing Authority Name</label>
          <input type="text" id="issuerName" value="Academic Certification Authority">
        </div>

        <!-- JSON Mode Form -->
        <div id="jsonMode">
          <div class="form-group">
            <label>Recipients Data (JSON Format)</label>
            <textarea id="jsonRecipients" rows="8">[
  {
    "recipient_name": "Eleanor Vance",
    "recipient_email": "eleanor@example.com",
    "course_name": "Full Stack Cloud Architecture",
    "issue_date": "2025-06-15"
  },
  {
    "recipient_name": "Marcus Aurelius Reed",
    "recipient_email": "marcus@example.com",
    "course_name": "Advanced Python & Distributed Systems",
    "issue_date": "2025-06-15"
  },
  {
    "recipient_name": "Sophia Zhang",
    "recipient_email": "sophia@example.com",
    "course_name": "Applied Machine Learning & AI",
    "issue_date": "2025-06-15"
  }
]</textarea>
          </div>
          <button class="btn-primary" onclick="submitJsonJob()">Generate Certificates (JSON)</button>
        </div>

        <!-- CSV Mode Form -->
        <div id="csvMode" style="display: none;">
          <div class="form-group">
            <label>Upload CSV File (.csv)</label>
            <input type="file" id="csvFileInput" accept=".csv">
            <p style="font-size:0.75rem; color:var(--text-muted); margin-top:0.35rem;">
              Headers: <code>recipient_name, recipient_email, course_name, issue_date</code>
            </p>
          </div>
          <button class="btn-primary" onclick="submitCsvJob()">Upload &amp; Generate via CSV</button>
        </div>

        <!-- Status Progress Box -->
        <div id="statusBox" class="status-box">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <strong id="jobStatusTitle">Processing Job...</strong>
            <span id="jobStatusBadge" class="badge badge-processing">PROCESSING</span>
          </div>
          <div class="progress-bar-container">
            <div id="progressBar" class="progress-bar"></div>
          </div>
          <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-muted);">
            <span id="jobCountText">0 / 0 completed</span>
            <span id="jobPercentText">0%</span>
          </div>
          <div id="zipAction" style="margin-top: 1rem; display: none;">
            <a id="zipDownloadBtn" class="download-link" href="#" target="_blank" style="font-size: 0.95rem;">
              ⬇ Download Complete ZIP Archive
            </a>
          </div>
          <div id="certList" style="margin-top: 1rem; max-height: 180px; overflow-y: auto;"></div>
        </div>
      </div>

      <!-- Right Column: Verification & Live Check -->
      <div>
        <div class="card" style="margin-bottom: 1.5rem;">
          <div class="card-title">Certificate Verification</div>
          <div class="card-subtitle">Verify authenticity and integrity of any issued credential.</div>
          <div class="form-group">
            <label>Certificate Verification Code</label>
            <input type="text" id="verifyCodeInput" placeholder="e.g. CERT-A1B2-C3D4">
          </div>
          <button class="btn-gold" style="width:100%;" onclick="verifyCertificate()">Verify Credential</button>

          <div id="verifyResult" style="margin-top: 1rem; display: none; padding: 1rem; border-radius: 8px; background: rgba(15,23,42,0.8); border: 1px solid var(--card-border);"></div>
        </div>

        <div class="card">
          <div class="card-title">Recent Generation Jobs</div>
          <div class="card-subtitle">Real-time status of recent batch jobs</div>
          <div id="recentJobsList" style="max-height: 240px; overflow-y: auto;">
            <p style="font-size:0.85rem; color:var(--text-muted);">Loading recent jobs...</p>
          </div>
          <button onclick="loadRecentJobs()" style="margin-top: 0.75rem; background: rgba(255,255,255,0.08); color: #cbd5e1; width: 100%;">Refresh Jobs</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    function switchTab(mode) {
      document.getElementById('tabJsonBtn').classList.toggle('active', mode === 'json');
      document.getElementById('tabCsvBtn').classList.toggle('active', mode === 'csv');
      document.getElementById('jsonMode').style.display = mode === 'json' ? 'block' : 'none';
      document.getElementById('csvMode').style.display = mode === 'csv' ? 'block' : 'none';
    }

    let pollInterval = null;

    async function submitJsonJob() {
      const issuer = document.getElementById('issuerName').value;
      let recipients;
      try {
        recipients = JSON.parse(document.getElementById('jsonRecipients').value);
      } catch (e) {
        alert("Invalid JSON format in recipients textarea: " + e.message);
        return;
      }

      try {
        const res = await fetch('/api/certificates/generate', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            issuer_name: issuer,
            template_name: 'classic',
            recipients: recipients
          })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || JSON.stringify(data));
        startPollingJob(data.id);
      } catch (err) {
        alert("Failed to submit job: " + err.message);
      }
    }

    async function submitCsvJob() {
      const fileInput = document.getElementById('csvFileInput');
      if (!fileInput.files.length) {
        alert("Please select a .csv file first");
        return;
      }
      const formData = new FormData();
      formData.append('file', fileInput.files[0]);
      formData.append('issuer_name', document.getElementById('issuerName').value);
      formData.append('template_name', 'classic');

      try {
        const res = await fetch('/api/certificates/upload-csv', {
          method: 'POST',
          body: formData
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail?.message || data.detail || JSON.stringify(data));
        startPollingJob(data.id);
      } catch (err) {
        alert("Failed to upload CSV: " + err.message);
      }
    }

    function startPollingJob(jobId) {
      if (pollInterval) clearInterval(pollInterval);
      const statusBox = document.getElementById('statusBox');
      statusBox.style.display = 'block';

      pollJob(jobId);
      pollInterval = setInterval(() => pollJob(jobId), 1000);
    }

    async function pollJob(jobId) {
      try {
        const res = await fetch(`/api/certificates/jobs/${jobId}`);
        const data = await res.json();
        if (!res.ok) return;

        const percent = data.progress_percentage || 0;
        document.getElementById('progressBar').style.width = percent + '%';
        document.getElementById('jobPercentText').innerText = percent + '%';
        document.getElementById('jobCountText').innerText = `${data.processed_count} / ${data.total_count} processed`;

        const badge = document.getElementById('jobStatusBadge');
        badge.innerText = data.status;
        badge.className = 'badge badge-' + data.status.toLowerCase();

        if (data.status === 'COMPLETED' || data.status === 'FAILED') {
          clearInterval(pollInterval);
          if (data.download_zip_url) {
            document.getElementById('zipAction').style.display = 'block';
            document.getElementById('zipDownloadBtn').href = data.download_zip_url;
          }
          loadRecentJobs();
        }

        // Render certificates
        if (data.certificates && data.certificates.length) {
          const list = document.getElementById('certList');
          list.innerHTML = data.certificates.map(c => `
            <div class="cert-item">
              <div>
                <strong>${c.recipient_name}</strong>
                <div style="font-size:0.75rem; color:var(--text-muted);">${c.certificate_code}</div>
              </div>
              <div>
                ${c.download_url ? `<a class="download-link" href="${c.download_url}" target="_blank">Download PDF</a>` : '<span style="color:#ef4444;">Pending</span>'}
              </div>
            </div>
          `).join('');
        }
      } catch (e) {
        console.error(e);
      }
    }

    async function verifyCertificate() {
      const code = document.getElementById('verifyCodeInput').value.trim();
      if (!code) {
        alert("Please enter a certificate verification code.");
        return;
      }
      const box = document.getElementById('verifyResult');
      box.style.display = 'block';
      box.innerHTML = "Verifying...";

      try {
        const res = await fetch(`/api/certificates/verify/${encodeURIComponent(code)}`);
        const data = await res.json();

        if (data.is_valid) {
          box.innerHTML = `
            <div style="color:#34d399; font-weight:700; margin-bottom:0.5rem;">✔ Authentic & Valid Certificate</div>
            <div style="font-size:0.85rem; line-height:1.5;">
              <strong>Recipient:</strong> ${data.recipient_name}<br>
              <strong>Course:</strong> ${data.course_name}<br>
              <strong>Issuer:</strong> ${data.issuer_name}<br>
              <strong>Issue Date:</strong> ${data.issue_date}<br>
              <strong>Code:</strong> <code>${data.certificate_code}</code><br>
              ${data.download_url ? `<a class="download-link" href="${data.download_url}" target="_blank" style="display:inline-block; margin-top:0.5rem;">Download Official Certificate</a>` : ''}
            </div>
          `;
        } else {
          box.innerHTML = `
            <div style="color:#f87171; font-weight:700; margin-bottom:0.3rem;">✖ Verification Failed</div>
            <p style="font-size:0.85rem; color:var(--text-muted);">${data.error_message || 'Certificate code not found in official registry.'}</p>
          `;
        }
      } catch (err) {
        box.innerHTML = `<span style="color:#f87171;">Error checking verification: ${err.message}</span>`;
      }
    }

    async function loadRecentJobs() {
      try {
        const res = await fetch('/api/certificates/jobs?limit=5');
        const jobs = await res.json();
        const list = document.getElementById('recentJobsList');
        if (!jobs.length) {
          list.innerHTML = '<p style="font-size:0.85rem; color:var(--text-muted);">No jobs executed yet.</p>';
          return;
        }
        list.innerHTML = jobs.map(j => `
          <div class="cert-item" onclick="startPollingJob('${j.id}')" style="cursor:pointer;">
            <div>
              <strong>Job ${j.id.slice(0, 8)}...</strong>
              <div style="font-size:0.75rem; color:var(--text-muted);">${j.processed_count}/${j.total_count} processed</div>
            </div>
            <div>
              <span class="badge badge-${j.status.toLowerCase()}">${j.status}</span>
            </div>
          </div>
        `).join('');
      } catch (e) {
        console.error(e);
      }
    }

    window.addEventListener('DOMContentLoaded', loadRecentJobs);
  </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)
