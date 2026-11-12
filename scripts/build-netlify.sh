#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 -m venv .venv-netlify
.venv-netlify/bin/python -m pip install --disable-pip-version-check --no-cache-dir -r requirements.lock
.venv-netlify/bin/python scripts/build_static.py
