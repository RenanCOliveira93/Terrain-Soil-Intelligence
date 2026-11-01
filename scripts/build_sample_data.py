"""Gera sample_data/ a partir das fontes reais (precisa de internet). Roda uma vez; o resultado é versionado."""
import sys
from pathlib import Path

import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import os
os.environ["TSI_MODE"] = "live"
from app.config import settings  # noqa: E402
from app.core import dem, soil  # noqa: E402

# Região: entorno de Espírito Santo do Pinhal (SP), relevo ondulado típico de cafeicultura de montanha.
BBOX = (-46.84, -22.26, -46.72, -22.14)
out = ROOT / "sample_data"
out.mkdir(exist_ok=True)
settings.data_dir = ROOT / "data"

clip = dem.fetch_live(BBOX)
with rasterio.open(out / "demo_dem_glo30.tif", "w", driver="GTiff", height=clip.array.shape[0], width=clip.array.shape[1],
                   count=1, dtype="float32", crs="EPSG:4326", transform=clip.transform, compress="deflate", nodata=np.nan) as d:
    d.write(clip.array, 1)
    d.update_tags(TSI_SOURCE="Copernicus DEM GLO-30 via AWS Open Data", TSI_TILES=";".join(clip.meta["tiles"]),
                  TSI_RETRIEVED_AT=clip.meta["retrieved_at"], TSI_BBOX=str(BBOX))
print("DEM", clip.array.shape, np.nanmin(clip.array), np.nanmax(clip.array))

s = soil.fetch_live(BBOX, depths=soil.DEPTHS[:3])
names = list(s["layers"])
with rasterio.open(out / "demo_soilgrids.tif", "w", driver="GTiff", height=s["layers"][names[0]].shape[0],
                   width=s["layers"][names[0]].shape[1], count=len(names), dtype="float32", crs="EPSG:4326",
                   transform=s["transform"], compress="deflate", nodata=np.nan) as d:
    for i, n in enumerate(names, 1):
        d.write(s["layers"][n], i)
        d.set_band_description(i, n)
    d.update_tags(TSI_SOURCE="SoilGrids 2.0 (ISRIC) files.isric.org", TSI_LICENSE="CC BY 4.0",
                  TSI_UNITS="valores já convertidos: pH, g/kg (soc), % (clay/silt/sand)")
print("SOIL", len(names), "bandas", s["layers"][names[0]].shape)
