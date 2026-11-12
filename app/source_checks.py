"""Dated access observations for references that are not live integrations."""
import json
from pathlib import Path


def reference_checks():
    path=Path(__file__).resolve().parents[1]/'samples'/'source_access_checks.json'
    return json.loads(path.read_text()) if path.exists() else []
