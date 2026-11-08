"""Make the producer modules importable as top-level modules (enrich, reader, main...)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "producer"))
