"""Make producer/, functions/fraud_alert/ and analysis/ importable as top-level modules (enrich, main, alerts...)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for folder in ("producer", "functions/fraud_alert", "analysis"):
    sys.path.insert(0, str(ROOT / folder))
