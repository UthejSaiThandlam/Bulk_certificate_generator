@echo off
echo Starting Bulk Certificate Generator Backend API on port 8000...
cd backend
python -m uvicorn app.main:app --reload --port 8000
pause
