"""Camadas raster em PNG (RGBA) e definições de legenda. Fora do polígono: transparente."""
from __future__ import annotations

import io

import matplotlib
import numpy as np
from matplotlib import colormaps
from matplotlib.colors import to_rgb
from PIL import Image

from . import soil as soilmod
from . import terrain

matplotlib.use("Agg")

SLOPE_COLORS = ["#2e7d32", "#9ccc65", "#ffee58", "#fb8c00", "#e53935", "#6a1b9a"]
ASPECT_COLORS = {"N": "#1e88e5", "NE": "#00acc1", "L": "#43a047", "SE": "#c0ca33",
                 "S": "#fdd835", "SO": "#fb8c00", "O": "#e53935", "NO": "#8e24aa", "Plano": "#bdbdbd"}
# Faixas FIXAS para solo: autoescala faria diferenças pequenas parecerem grandes.
SOIL_RANGES = {"phh2o": (4.0, 8.0, "RdYlBu_r"), "soc": (0.0, 60.0, "YlGn"), "clay": (0.0, 100.0, "YlOrBr"),
               "silt": (0.0, 100.0, "PuBu"), "sand": (0.0, 100.0, "YlOrRd")}
PI_MAX = {"phh2o": 4.0, "soc": 80.0, "clay": 80.0, "silt": 60.0, "sand": 80.0}


def _rgba(rgb, mask):
    out = np.zeros(rgb.shape[:2] + (4,), np.uint8)
    out[..., :3] = rgb
    out[..., 3] = np.where(mask, 255, 0)
    return out


def _png(rgba) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG", optimize=True)
    return buf.getvalue()


def continuous(arr, mask, vmin, vmax, cmap):
    t = np.clip((arr - vmin) / (vmax - vmin if vmax > vmin else 1), 0, 1)
    rgb = (colormaps[cmap](np.nan_to_num(t))[..., :3] * 255).astype(np.uint8)
    return _rgba(rgb, mask & np.isfinite(arr))


def legend_continuous(vmin, vmax, cmap, unit, n=6):
    cm = colormaps[cmap]
    return {"type": "continuous", "unit": unit, "min": float(vmin), "max": float(vmax),
            "stops": ["#%02x%02x%02x" % tuple((np.array(cm(i / (n - 1))[:3]) * 255).astype(int)) for i in range(n)]}


def slope_rgba(slope_deg, mask):
    pct = terrain.slope_pct(slope_deg)
    rgb = np.zeros(slope_deg.shape + (3,), np.uint8)
    for (nm, lo, hi), col in zip(terrain.SLOPE_CLASSES, SLOPE_COLORS):
        sel = (pct >= lo) & (pct < hi)
        rgb[sel] = (np.array(to_rgb(col)) * 255).astype(np.uint8)
    return _rgba(rgb, mask & np.isfinite(slope_deg))


def legend_slope():
    return {"type": "categorical", "unit": "% (classes EMBRAPA/SiBCS)", "classes": [
        {"label": f"{nm} ({lo:g}–{'∞' if np.isinf(hi) else format(hi, 'g')}%)", "color": c}
        for (nm, lo, hi), c in zip(terrain.SLOPE_CLASSES, SLOPE_COLORS)]}


def aspect_rgba(aspect, mask, dem):
    rgb = np.zeros(aspect.shape + (3,), np.uint8)
    flat = np.isnan(aspect) & np.isfinite(dem)
    rgb[flat] = (np.array(to_rgb(ASPECT_COLORS["Plano"])) * 255).astype(np.uint8)
    idx = np.where(np.isfinite(aspect), (((np.nan_to_num(aspect) + 22.5) % 360) // 45).astype(int), -1)
    for i, k in enumerate(terrain.ASPECT_NAMES):
        rgb[idx == i] = (np.array(to_rgb(ASPECT_COLORS[k])) * 255).astype(np.uint8)
    return _rgba(rgb, mask & np.isfinite(dem))


def legend_aspect():
    return {"type": "categorical", "unit": "azimute da descida", "classes": [{"label": k, "color": v} for k, v in ASPECT_COLORS.items()]}


def hillshade_rgba(hs, mask):
    g = (np.nan_to_num(hs) * 255).astype(np.uint8)
    return _rgba(np.stack([g, g, g], -1), mask & np.isfinite(hs))


def soil_spec(prop, depth, kind):
    lo, hi, cm = SOIL_RANGES[prop]
    info = soilmod.PROPERTIES[prop]
    if kind == "mean":
        return {"vmin": lo, "vmax": hi, "cmap": cm, "unit": info["unit"], "label": f"{info['label']} {depth} (média predita)"}
    return {"vmin": 0.0, "vmax": PI_MAX[prop], "cmap": "magma_r", "unit": info["unit"],
            "label": f"{info['label']} {depth}: largura do intervalo 90% (Q0.95−Q0.05)"}
