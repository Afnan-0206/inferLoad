import sys
from pathlib import Path

# Add project root and src directory to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from inferload.web import create_web_app

# Vercel's Python runtime detects this ASGI app
app = create_web_app()
