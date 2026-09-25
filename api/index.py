import sys
from pathlib import Path

# Add project root directory to sys.path so app, smile_*, etc. resolve properly
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Import Flask WSGI app instance for Vercel Serverless Function runtime
from app import app
