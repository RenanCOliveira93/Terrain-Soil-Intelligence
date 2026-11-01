"""Exporta o OpenAPI para docs/openapi.json."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["TSI_DATA_DIR"] = tempfile.mkdtemp()
sys.path.insert(0, str(ROOT / "backend"))
from app.main import app  # noqa: E402

(ROOT / "docs" / "openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
print("paths:", len(app.openapi()["paths"]))
