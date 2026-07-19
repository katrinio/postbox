#!/usr/bin/env python3
"""
Start Postbox application (API + Web frontend)

Usage:
    python start.py

Press Ctrl+C to stop both services.
"""

import subprocess
import time
import sys
import os
import signal
from pathlib import Path

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")


def print_info(msg):
    print(f"{YELLOW}ℹ️  {msg}{RESET}")


def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")


def main():
    repo_root = Path(__file__).parent

    # Check dependencies
    try:
        subprocess.run(["poetry", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_error("poetry is not installed")
        sys.exit(1)

    try:
        subprocess.run(["npm", "--version"], capture_output=True, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print_error("npm is not installed")
        sys.exit(1)

    # Try to start PostgreSQL if not running (macOS only)
    try:
        result = subprocess.run(
            ["brew", "services", "list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if "postgresql" in result.stdout and "started" not in result.stdout:
            print_info("Starting PostgreSQL...")
            subprocess.run(
                ["brew", "services", "start", "postgresql@17"],
                capture_output=True,
                timeout=10,
            )
            time.sleep(2)
    except Exception:
        pass  # Ignore if brew not available or PostgreSQL not installed

    print(f"{GREEN}Starting Postbox application...{RESET}\n")

    # Start API
    print_info(f"Starting API on {GREEN}http://localhost:8000{RESET}")
    api_process = subprocess.Popen(
        ["poetry", "run", "postbox-api"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for API to be ready
    time.sleep(2)

    # Start Web
    print_info(f"Starting Web on {GREEN}http://localhost:3000{RESET}")
    web_dir = repo_root / "web"
    web_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=web_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    print(f"\n{GREEN}✨ Postbox is running!{RESET}\n")
    print(f"📖 Web:  {GREEN}http://localhost:3000{RESET}")
    print(f"🔌 API:  {GREEN}http://localhost:8000{RESET}\n")
    print(f"{YELLOW}Press Ctrl+C to stop both services{RESET}\n")

    def cleanup(signum, frame):
        print(f"\n{YELLOW}Stopping services...{RESET}")
        api_process.terminate()
        web_process.terminate()

        try:
            api_process.wait(timeout=5)
            web_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            api_process.kill()
            web_process.kill()

        print_success("Services stopped")
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

    # Wait for both processes
    try:
        api_process.wait()
        web_process.wait()
    except KeyboardInterrupt:
        cleanup(None, None)


if __name__ == "__main__":
    main()
