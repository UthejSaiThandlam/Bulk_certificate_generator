#!/usr/bin/env python3
"""
CertifAI — Unified Runner Script
Allows running Backend, Frontend, Tests, or Both simultaneously with simple commands.
"""

import sys
import os
import subprocess
import argparse
import time

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, "backend")
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")


def run_backend(port=8000, reload=True):
    """Run FastAPI backend server."""
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "backend.app.main:app",
        "--port",
        str(port),
    ]
    if reload:
        cmd.append("--reload")
    print(f"\n🚀 Starting Backend API on http://127.0.0.1:{port}")
    print(f"📖 Swagger Documentation: http://127.0.0.1:{port}/docs\n")
    return subprocess.run(cmd, cwd=ROOT_DIR)


def run_frontend(port=3000):
    """Run lightweight HTTP frontend server."""
    cmd = [
        sys.executable,
        "-m",
        "http.server",
        str(port),
        "--directory",
        FRONTEND_DIR,
    ]
    print(f"\n🎨 Starting Frontend Dashboard on http://127.0.0.1:{port}\n")
    return subprocess.run(cmd, cwd=ROOT_DIR)


def run_tests():
    """Run complete pytest test suite."""
    cmd = [sys.executable, "-m", "pytest", "backend/tests", "-v"]
    print("\n🧪 Running Pytest Test Suite...\n")
    return subprocess.run(cmd, cwd=ROOT_DIR).returncode


def run_both(backend_port=8000, frontend_port=3000):
    """Run both Backend and Frontend concurrently."""
    print("=" * 65)
    print("🎓 CertifAI — Bulk Certificate Generator System")
    print("=" * 65)
    print(f"✔ Backend API:       http://127.0.0.1:{backend_port}")
    print(f"✔ Swagger API Docs:  http://127.0.0.1:{backend_port}/docs")
    print(f"✔ Frontend App:      http://127.0.0.1:{frontend_port}")
    print("=" * 65)
    print("Press Ctrl+C at any time to shut down both servers.\n")

    backend_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "backend.app.main:app",
            "--port",
            str(backend_port),
            "--reload",
        ],
        cwd=ROOT_DIR,
    )

    frontend_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "http.server",
            str(frontend_port),
            "--directory",
            FRONTEND_DIR,
        ],
        cwd=ROOT_DIR,
    )

    try:
        while True:
            time.sleep(1)
            if backend_proc.poll() is not None:
                print("Backend stopped.")
                break
            if frontend_proc.poll() is not None:
                print("Frontend stopped.")
                break
    except KeyboardInterrupt:
        print("\nShutting down servers...")
    finally:
        backend_proc.terminate()
        frontend_proc.terminate()
        try:
            backend_proc.wait(timeout=2)
            frontend_proc.wait(timeout=2)
        except Exception:
            backend_proc.kill()
            frontend_proc.kill()
        print("Servers stopped cleanly.")


def main():
    parser = argparse.ArgumentParser(description="CertifAI Server Runner")
    parser.add_argument(
        "service",
        nargs="?",
        default="both",
        choices=["both", "backend", "frontend", "test"],
        help="Service to start: 'both' (default), 'backend', 'frontend', or 'test'",
    )
    parser.add_argument("--backend-port", type=int, default=8000, help="Backend port (default: 8000)")
    parser.add_argument("--frontend-port", type=int, default=3000, help="Frontend port (default: 3000)")

    args = parser.parse_args()

    if args.service == "backend":
        run_backend(port=args.backend_port)
    elif args.service == "frontend":
        run_frontend(port=args.frontend_port)
    elif args.service == "test":
        sys.exit(run_tests())
    else:
        run_both(backend_port=args.backend_port, frontend_port=args.frontend_port)


if __name__ == "__main__":
    main()
