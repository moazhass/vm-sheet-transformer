import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DEV_AUTH_BYPASS", "true")
os.environ.setdefault("SESSION_SECRET", "test-secret")
os.environ.setdefault("ALLOWED_EMAIL_DOMAINS", "devoteam.com")
