@echo off
echo Starting CertifAI Frontend on http://localhost:3000...
cd frontend
python -m http.server 3000
pause
