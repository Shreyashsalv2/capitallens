"""Local development server: the same API as production plus the dashboard in public/.

    python3 -m uvicorn scripts.dev_server:app --reload   (from the repo root)
    open http://127.0.0.1:8000
"""
import os
import sys

from fastapi.staticfiles import StaticFiles

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from api.index import app  # noqa: E402

app.mount("/", StaticFiles(directory=os.path.join(ROOT, "public"), html=True), name="public")
