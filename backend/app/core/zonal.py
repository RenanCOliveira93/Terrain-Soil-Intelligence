"""Estatísticas zonais (rasterstats) para elevação, declividade, aspecto e solo.

Cada zona informa `n_pixels` e `quality_flags`: polígonos pequenos frente ao pixel (30 m no DEM, 250 m no
SoilGrids) têm estatísticas pouco representativas, e dizemos isso em vez de devolver números sem aviso.
"""
from __future__ import annotations

import numpy as np
from rasterio import features
from rasterstats import zonal_stats
from shapely.geometry import mapping

from . import soil as soilmod
from . import terrain

MIN_PIXELS_DEM = 30
MIN_PIXELS_SOIL = 4
BASIC = "count min max mean median std percentile_5 percentile_95"


def cell_mask(geom, transform, shape, all_touched=False) -> np.ndarray:
    """True dentro do polígono."""
    return features.geometry_mask([mapping(geom)], out_shape=shape, transform=transform,
                                  invert=True, all_touched=all_touched)


def _stats(geom, arr, transform, all_touched=False) -> dict:
    s = zonal_stats([mapping(geom)], arr, affine=transform, nodata=np.nan, stats=BASIC, all_touched=all_touched)[0]
    return {k: (None if v is None else float(v)) for k, v in s.items()}


def terrain_zone(geom, dem, slope, aspect, transform) -> dict:
    mask = cell_mask(geom, transform, dem.shape)
    flags = []
    if not (mask & np.isfinite(dem)).any():
        mask = cell_mask(geom, transform, dem.shape, all_touched=True)
        all_touched = True
        flags.append("Polígono menor que um pixel: usados pixels que tocam o polígono (all_touched).")
    else:
        all_touched = False
    e = _stats(geom, dem, transform, all_touched)
    sl = _stats(geom, slope, transform, all_touched)
    valid = mask & np.isfinite(dem)
    n = int(valid.sum())
    if n < MIN_PIXELS_DEM:
        flags.append(f"Apenas {n} pixels de 30 m: estatísticas de terreno pouco representativas.")
    sv = slope[valid & np.isfinite(slope)]
    av = aspect[valid]
    pct = terrain.slope_pct(sv)
    out = {
        "n_pixels": n,
        "elevation_m": {**e, "range": None if e["max"] is None else e["max"] - e["min"]},
        "slope_deg": sl,
        "slope_pct": {"mean": float(np.mean(pct)) if pct.size else None, "median": float(np.median(pct)) if pct.size else None,
                      "p95": float(np.percentile(pct, 95)) if pct.size else None,
                      "max": float(pct.max()) if pct.size else None},
        "slope_classes": terrain.slope_class_shares(sv),
        "aspect": terrain.aspect_summary(av, int(np.isfinite(dem[valid]).sum())),
        "hypsometry": terrain.hypsometry(dem[valid]),
        "quality_flags": flags,
    }
    return out


def _soil_stat(geom, grid, transform, shape):
    mask = cell_mask(geom, transform, shape)
    mode = "pixel_centers"
    if not (mask & np.isfinite(grid)).any():
        mask = cell_mask(geom, transform, shape, all_touched=True)
        mode = "all_touched"
    if not (mask & np.isfinite(grid)).any():
        c = geom.centroid
        col, row = ~transform * (c.x, c.y)
        r, cc = int(np.floor(row)), int(np.floor(col))
        if 0 <= r < shape[0] and 0 <= cc < shape[1] and np.isfinite(grid[r, cc]):
            m = np.zeros(shape, bool)
            m[r, cc] = True
            return m, "centroid_pixel"
        return mask, "none"
    return mask, mode


def soil_zone(geom, soil: dict, area_ha: float) -> dict:
    tr = soil["transform"]
    layers = soil["layers"]
    shape = next(iter(layers.values())).shape
    cell_ha = None
    out, flags = {}, []
    texture = {}
    for p in soil["props"]:
        info = soilmod.PROPERTIES[p]
        out[p] = {"label": info["label"], "unit": info["unit"], "depths": {}}
        for d in soil["depths"]:
            m, mode = _soil_stat(geom, layers[soilmod.layer_name(p, d, "mean")], tr, shape)
            rec = {"sampling": mode}
            sel = lambda stat: layers[soilmod.layer_name(p, d, stat)][m]  # noqa: E731
            means = sel("mean")
            ok = np.isfinite(means)
            rec["n_pixels"] = int(ok.sum())
            if ok.sum() == 0:
                rec["available"] = False
            else:
                q05, q50, q95 = sel("q05")[ok], sel("q50")[ok], sel("q95")[ok]
                rec.update({
                    "available": True,
                    "mean": float(means[ok].mean()),
                    "spatial_sd_of_pixel_means": float(means[ok].std()) if ok.sum() > 1 else None,
                    "q05_mean": float(q05.mean()), "q50_mean": float(q50.mean()), "q95_mean": float(q95.mean()),
                    "pi90_width_mean": float((q95 - q05).mean()),
                    "pi90_note": "média por pixel dos limites Q0.05/Q0.95 (predição por pixel; NÃO é IC da média da zona)",
                })
            out[p]["depths"][d] = rec
    for d in soil["depths"]:
        try:
            vals = [out[p]["depths"][d].get("mean") for p in ("clay", "silt", "sand")]
            if all(v is not None for v in vals):
                texture[d] = soilmod.texture_class(*vals)
        except KeyError:
            pass
    px_ha = abs(tr.a) * abs(tr.e) * (111320 ** 2) * np.cos(np.radians(geom.centroid.y)) / 1e4
    if area_ha < px_ha:
        flags.append(f"Zona de {area_ha:.1f} ha é menor que um pixel do SoilGrids (~{px_ha:.0f} ha): o valor é o do pixel que a contém, "
                     "não uma estatística da zona. Zonas vizinhas podem ter valores idênticos.")
    elif area_ha < MIN_PIXELS_SOIL * px_ha:
        flags.append(f"Zona cobre ~{area_ha / px_ha:.1f} pixels do SoilGrids: baixa representatividade.")
    return {"properties": out, "texture_class_of_means": texture, "soil_pixel_ha": float(px_ha), "quality_flags": flags}
