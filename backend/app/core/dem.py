"""Aquisição do Copernicus DEM GLO-30 (COG na AWS) ou do recorte de demonstração (offline)."""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.transform import Affine
from rasterio.windows import Window, from_bounds

from ..config import settings

DEM_META = {
    "product": "Copernicus DEM GLO-30 (Public)",
    "model_type": "DSM",  # modelo digital de SUPERFÍCIE
    "horizontal_crs": "EPSG:4326 (WGS 84)",
    "vertical_datum": "EGM2008 (EPSG:3855), altura ortométrica",
    "nominal_resolution": "1 arco-segundo (~30 m)",
    "vertical_accuracy_spec": "< 4 m (LE90, absoluta; especificação do produto)",
    "acquisition_period": "2010–2015 (missão TanDEM-X; WorldDEM)",
    "attribution": "Copernicus DEM © DLR e.V. 2010-2014 e © Airbus Defence and Space GmbH 2014-2018, "
                   "fornecido sob COPERNICUS pela União Europeia e ESA. Acessado via https://registry.opendata.aws/copernicus-dem.",
    "license": "Licença Copernicus DEM (uso gratuito; ver registry.opendata.aws/copernicus-dem)",
}


class CoverageError(ValueError):
    pass


@dataclass
class DemClip:
    array: np.ndarray  # float32, NaN onde não há dado
    transform: Affine
    crs: str
    meta: dict

    @property
    def res(self) -> tuple[float, float]:
        return abs(self.transform.a), abs(self.transform.e)


def tile_url(lat_floor: int, lon_floor: int) -> str:
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    name = f"Copernicus_DSM_COG_10_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"
    return f"{settings.dem_base_url}/{name}/{name}.tif"


def tiles_for_bbox(bbox) -> list[tuple[int, int]]:
    minx, miny, maxx, maxy = bbox
    return [(la, lo) for la in range(math.floor(miny), math.floor(maxy - 1e-12) + 1)
            for lo in range(math.floor(minx), math.floor(maxx - 1e-12) + 1)]


def _finish(arr, transform, crs, meta, nodata=None):
    a = arr.astype("float32")
    if nodata is not None:
        a[a == nodata] = np.nan
    a[~np.isfinite(a)] = np.nan
    return DemClip(a, transform, crs, meta)


def read_window(src, bbox):
    w0 = from_bounds(*bbox, transform=src.transform)
    c0, r0 = max(int(math.floor(w0.col_off + 1e-9)), 0), max(int(math.floor(w0.row_off + 1e-9)), 0)
    c1 = min(int(math.ceil(w0.col_off + w0.width - 1e-9)), src.width)
    r1 = min(int(math.ceil(w0.row_off + w0.height - 1e-9)), src.height)
    w = Window(c0, r0, c1 - c0, r1 - r0)
    return src.read(1, window=w, boundless=False), src.window_transform(w)


def fetch_demo(bbox) -> DemClip:
    path = settings.sample_dir / "demo_dem_glo30.tif"
    with rasterio.open(path) as src:
        b = src.bounds
        if bbox[0] < b.left or bbox[2] > b.right or bbox[1] < b.bottom or bbox[3] > b.top:
            raise CoverageError(
                f"Modo demonstração: o polígono (+margem) está fora do recorte de amostra "
                f"[{b.left:.3f}, {b.bottom:.3f}, {b.right:.3f}, {b.top:.3f}]. Use TSI_MODE=live para dados reais.")
        arr, tr = read_window(src, bbox)
        meta = {**DEM_META, **{k: v for k, v in src.tags().items() if k.startswith("TSI_")},
                "source": "sample_data/demo_dem_glo30.tif (recorte real do Copernicus DEM GLO-30)",
                "mode": "demo", "tiles": []}
        return _finish(arr, tr, "EPSG:4326", meta, src.nodata)


def fetch_live(bbox) -> DemClip:
    key = hashlib.sha1(repr([round(v, 6) for v in bbox]).encode()).hexdigest()[:16]
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    cache = settings.cache_dir / f"dem_{key}.tif"
    tiles = tiles_for_bbox(bbox)
    urls = [tile_url(*t) for t in tiles]
    if not cache.exists():
        srcs, windows = [], []
        try:
            for u in urls:
                try:
                    s = rasterio.open(u)
                except rasterio.errors.RasterioIOError as exc:
                    raise CoverageError(f"Tile do DEM indisponível ({u}): {exc}. Sem cobertura pública ou rede indisponível.") from exc
                srcs.append(s)
            if len(srcs) == 1:
                arr, tr = read_window(srcs[0], bbox)
            else:
                arr, tr = merge(srcs, bounds=bbox, nodata=np.nan, dtype="float32")
                arr = arr[0]
            with rasterio.open(cache, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1, dtype="float32",
                               crs="EPSG:4326", transform=tr, compress="deflate", nodata=np.nan) as dst:
                dst.write(arr.astype("float32"), 1)
        finally:
            for s in srcs:
                s.close()
    with rasterio.open(cache) as src:
        arr, tr = src.read(1), src.transform
    meta = {**DEM_META, "source": "; ".join(urls), "mode": "live", "tiles": urls,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    return _finish(arr, tr, "EPSG:4326", meta)


def fetch_dem(bbox, mode: str | None = None) -> DemClip:
    mode = mode or settings.mode
    return fetch_demo(bbox) if mode == "demo" else fetch_live(bbox)


def buffered_bbox(bbox, pixels: int = 3, res: float = 1 / 3600):
    d = pixels * res
    return (bbox[0] - d, bbox[1] - d, bbox[2] + d, bbox[3] + d)
