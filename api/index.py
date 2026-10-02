import os
import sys
from pathlib import Path

# Add project src to sys.path so the inferload package is importable on Vercel
root_dir = Path(__file__).resolve().parent.parent
src_dir = root_dir / "src"
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

from inferload.web import app
