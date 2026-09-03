"""Orchestrator-specific conftest — no database or app dependencies needed."""

import sys
from pathlib import Path

# Ensure the app is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
