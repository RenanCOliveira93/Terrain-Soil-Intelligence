import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_tmp = tempfile.mkdtemp(prefix="tsi_tests_")
os.environ.setdefault("TSI_MODE", "demo")
os.environ["TSI_DATA_DIR"] = _tmp
os.environ["TSI_DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
sys.path.insert(0, str(ROOT / "backend"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402

SAMPLE = ROOT / "sample_data"


def pytest_configure(config):
    config.addinivalue_line("markers", "network: usa a internet (defina TSI_RUN_NETWORK=1)")
    config.addinivalue_line("markers", "postgis: exige PostGIS (defina TSI_TEST_DATABASE_URL)")


def pytest_collection_modifyitems(config, items):
    for it in items:
        if "network" in it.keywords and os.environ.get("TSI_RUN_NETWORK") != "1":
            it.add_marker(pytest.mark.skip(reason="TSI_RUN_NETWORK!=1"))
        if "postgis" in it.keywords and not os.environ.get("TSI_TEST_DATABASE_URL"):
            it.add_marker(pytest.mark.skip(reason="TSI_TEST_DATABASE_URL ausente (PostGIS não testado)"))


@pytest.fixture(scope="session")
def demo_geojson():
    return json.loads((SAMPLE / "propriedade_demo.geojson").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def demo_parts(demo_geojson):
    prop = [f for f in demo_geojson["features"] if f["properties"]["kind"] == "property"][0]["geometry"]
    plots = [{"name": f["properties"]["name"], "geometry": f["geometry"]} for f in demo_geojson["features"] if f["properties"]["kind"] == "plot"]
    return prop, plots


def make_plane(sx=0.0, sy=0.0, n=40, lat0=-22.2, lon0=-46.8, res=1 / 3600):
    """DEM sintético com gradiente exato em metros: sx (leste+), sy (norte+), em m/m."""
    from app.core.terrain import cell_size_m
    tr = from_origin(lon0, lat0 + n * res / 2, res, res)
    dx, dy = cell_size_m(tr, n)
    j = np.arange(n)[None, :]
    i = np.arange(n)[:, None]
    z = 500 + sx * j * dx[:, None] - sy * i * dy.mean()
    return z.astype("float32"), tr
