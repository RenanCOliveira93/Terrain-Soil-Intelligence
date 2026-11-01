"""Derivados de terreno em grade geográfica (graus), com tamanho de célula em metros por linha.

Não reamostramos a elevação: o gradiente de Horn usa dx(φ) e dy(φ) reais. Isso evita
introduzir interpolação na superfície antes de calcular a declividade.
"""
from __future__ import annotations

import numpy as np
from rasterio.transform import Affine

# Classes de relevo por declividade (%): EMBRAPA/SiBCS. Referência de classificação, não de risco operacional.
SLOPE_CLASSES = [
    ("Plano", 0, 3), ("Suave ondulado", 3, 8), ("Ondulado", 8, 20),
    ("Forte ondulado", 20, 45), ("Montanhoso", 45, 75), ("Escarpado", 75, np.inf),
]
ASPECT_NAMES = ["N", "NE", "L", "SE", "S", "SO", "O", "NO"]
FLAT_SLOPE_DEG = 1.0  # abaixo disso o aspecto é considerado indefinido


def meters_per_degree(lat_deg):
    """(metros por grau de longitude, metros por grau de latitude) no elipsoide WGS 84 (série padrão)."""
    p = np.radians(lat_deg)
    m_lat = 111132.92 - 559.82 * np.cos(2 * p) + 1.175 * np.cos(4 * p) - 0.0023 * np.cos(6 * p)
    m_lon = 111412.84 * np.cos(p) - 93.5 * np.cos(3 * p) + 0.118 * np.cos(5 * p)
    return m_lon, m_lat


def cell_size_m(transform: Affine, nrows: int):
    lats = transform.f + transform.e * (np.arange(nrows) + 0.5)
    m_lon, m_lat = meters_per_degree(lats)
    return abs(transform.a) * m_lon, abs(transform.e) * m_lat  # arrays por linha


def gradients(dem: np.ndarray, transform: Affine):
    """dz/dx (leste+), dz/dy (norte+) por Horn (1981). Bordas e vizinhança com NaN viram NaN."""
    z = np.pad(dem.astype("float64"), 1, constant_values=np.nan)
    a, b, c = z[:-2, :-2], z[:-2, 1:-1], z[:-2, 2:]
    d, f = z[1:-1, :-2], z[1:-1, 2:]
    g, h, i = z[2:, :-2], z[2:, 1:-1], z[2:, 2:]
    dx, dy = cell_size_m(transform, dem.shape[0])
    dx, dy = dx[:, None], dy[:, None]
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * dx)
    dzdy = ((a + 2 * b + c) - (g + 2 * h + i)) / (8 * dy)
    return dzdx, dzdy


def slope_aspect(dem: np.ndarray, transform: Affine):
    """Declividade em graus e aspecto (azimute da DESCIDA, graus horários a partir do Norte; NaN = plano)."""
    dzdx, dzdy = gradients(dem, transform)
    slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
    slope = np.where(np.isfinite(dem), slope, np.nan)  # o centro do kernel de Horn não entra no gradiente
    aspect = np.degrees(np.arctan2(-dzdx, -dzdy)) % 360.0
    aspect = np.where(slope < FLAT_SLOPE_DEG, np.nan, aspect)
    aspect = np.where(np.isfinite(slope), aspect, np.nan)
    return slope.astype("float32"), aspect.astype("float32")


def slope_pct(slope_deg):
    return np.tan(np.radians(slope_deg)) * 100.0


def hillshade(dem, transform, azimuth=315.0, altitude=45.0):
    dzdx, dzdy = gradients(dem, transform)
    slope = np.arctan(np.hypot(dzdx, dzdy))
    asp = np.arctan2(-dzdx, -dzdy)  # azimute da descida (rad, a partir do Norte)
    az, alt = np.radians(azimuth), np.radians(altitude)
    hs = np.sin(alt) * np.cos(slope) + np.cos(alt) * np.sin(slope) * np.cos(az - asp)
    return np.clip(hs, 0, 1).astype("float32")


def slope_class_shares(slope_deg_values: np.ndarray) -> list[dict]:
    pct = slope_pct(slope_deg_values[np.isfinite(slope_deg_values)])
    n = max(pct.size, 1)
    return [{"class": nm, "min_pct": lo, "max_pct": None if np.isinf(hi) else hi,
             "share": float(((pct >= lo) & (pct < hi)).sum() / n)} for nm, lo, hi in SLOPE_CLASSES]


def aspect_summary(aspect_values: np.ndarray, n_total: int) -> dict:
    a = aspect_values[np.isfinite(aspect_values)]
    flat_share = 1 - a.size / max(n_total, 1)
    if a.size == 0:
        return {"flat_share": 1.0, "octants": {k: 0.0 for k in ASPECT_NAMES}, "mean_dir_deg": None, "resultant_length": None, "dominant": None}
    idx = (((a + 22.5) % 360) // 45).astype(int)
    shares = {k: float((idx == i).sum() / n_total) for i, k in enumerate(ASPECT_NAMES)}
    r = np.radians(a)
    C, S = np.cos(r).mean(), np.sin(r).mean()
    R = float(np.hypot(C, S))
    mean_dir = float(np.degrees(np.arctan2(S, C)) % 360)
    return {"flat_share": float(flat_share), "octants": shares, "mean_dir_deg": mean_dir,
            "resultant_length": R, "dominant": max(shares, key=shares.get)}


def hypsometry(elev: np.ndarray, n: int = 51) -> dict:
    """Curva hipsométrica: fração da área ACIMA de cada elevação (células com área ≈ constante)."""
    e = np.sort(elev[np.isfinite(elev)])
    if e.size == 0:
        return {"elevation": [], "area_above": [], "hist": {"edges": [], "counts": []}}
    q = np.linspace(0, 1, n)
    levels = np.quantile(e, q)
    counts, edges = np.histogram(e, bins=min(20, max(5, e.size // 50)))
    return {"elevation": levels.tolist(), "area_above": (1 - q).tolist(),
            "hist": {"edges": edges.tolist(), "counts": counts.tolist()}}
