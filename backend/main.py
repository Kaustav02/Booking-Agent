"""
Single entry point for Mykare Voice AI backend.

Runs both services concurrently:
  • FastAPI REST API  — uvicorn on port 8000
  • LiveKit Agent Worker — subprocess (python agent.py start)

Usage:
    python main.py
"""

import asyncio
import subprocess
import sys
import os
from dotenv import load_dotenv

load_dotenv()

# Fix SSL cert verification on macOS with python.org installer
import certifi
os.environ.setdefault("SSL_CERT_FILE", certifi.where())
os.environ.setdefault("REQUESTS_CA_BUNDLE", certifi.where())

from logging_config import get_logger

log = get_logger(__name__)

import uvicorn
from api import app


async def run_api():
    config = uvicorn.Config(
        app,
        host=os.getenv("API_HOST", "0.0.0.0"),
        port=int(os.getenv("API_PORT", "8000")),
        log_config=None,
        access_log=False,
    )
    server = uvicorn.Server(config)
    log.info("FastAPI starting on http://%s:%s", config.host, config.port)
    await server.serve()


async def run_agent():
    log.info("Starting LiveKit agent worker subprocess...")
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "agent.py", "start",
        env=os.environ.copy(),
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
    log.info("Agent worker started | pid=%d", proc.pid)
    await proc.wait()
    log.warning("Agent worker exited | pid=%d returncode=%s", proc.pid, proc.returncode)


async def main():
    log.info("=" * 55)
    log.info("  Mykare Voice AI Backend")
    log.info("  API + Agent Worker starting...")
    log.info("=" * 55)

    try:
        await asyncio.gather(run_api(), run_agent())
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("Shutdown requested — goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
