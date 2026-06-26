#!/bin/bash
set -e

echo "=== Mykare Voice AI Backend ==="

if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and fill in your API keys."
    exit 1
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt

echo "Starting backend (API + Agent in one process)..."
python main.py
