"""Put the shipped skill scripts on sys.path so tests can import them the way
the skill runs them (`python scripts/<name>.py`)."""
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "skill-scout" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
