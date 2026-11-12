#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check --cache-dir /workspace/.cache/pip -r requirements.lock
.venv/bin/python -c 'from app.db import init; init()'
.venv/bin/python scripts/seed.py
.venv/bin/python scripts/export_excel.py
