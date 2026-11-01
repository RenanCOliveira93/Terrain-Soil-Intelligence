"""Curvas de nível derivadas do DEM. São INTERPOLAÇÕES de um modelo de superfície, não medidas de campo."""
from __future__ import annotations

import numpy as np
from contourpy import contour_generator
from shapely.geometry import LineString, mapping
from shapely.ops import unary_union

MIN_INTERVAL_M = 5.0  # ~ 1,25 × a exatidão vertical especificada (4 m LE90): abaixo disso as linhas são ruído
WARN_INTERVAL_M = 10.0


def recommended_interval(relief_m: float) -> float:
    """Maior entre 10 m e o intervalo 'bonito' que gera ~10 curvas."""
    target = max(relief_m / 10.0, WARN_INTERVAL_M)
    for step in (10, 20, 25, 50, 100, 200, 250, 500):
        if step >= target:
            return float(step)
    return 500.0


def check_interval(interval_m: float) -> list[str]:
    if interval_m < MIN_INTERVAL_M:
        raise ValueError(
            f"Intervalo {interval_m:g} m incoerente com o DEM GLO-30 (exatidão vertical especificada < 4 m LE90, "
            f"célula ~30 m): mínimo {MIN_INTERVAL_M:g} m.")
    if interval_m < WARN_INTERVAL_M:
        return [f"Intervalo de {interval_m:g} m é menor que 10 m: as curvas refletem em parte o ruído do DEM."]
    return []


def contour_features(dem: np.ndarray, transform, interval_m: float, clip=None) -> list[dict]:
    check_interval(interval_m)
    z = np.ma.masked_invalid(dem)
    if z.count() == 0:
        return []
    lo = np.floor(np.nanmin(dem) / interval_m) * interval_m
    hi = np.ceil(np.nanmax(dem) / interval_m) * interval_m
    levels = np.arange(lo, hi + interval_m, interval_m)
    gen = contour_generator(z=z, name="serial")
    feats = []
    clip_geom = unary_union(clip) if clip is not None else None
    for lev in levels:
        for line in gen.lines(float(lev)):
            if len(line) < 2:
                continue
            xs = transform.c + transform.a * (line[:, 0] + 0.5)
            ys = transform.f + transform.e * (line[:, 1] + 0.5)
            g = LineString(np.column_stack([xs, ys]))
            if clip_geom is not None:
                g = g.intersection(clip_geom)
                if g.is_empty:
                    continue
            feats.append({"type": "Feature", "geometry": mapping(g),
                          "properties": {"elevation_m": float(lev), "interval_m": float(interval_m),
                                         "kind": "derivada_do_DEM_GLO30_DSM"}})
    return feats
