"""Validação de geometria, escolha de CRS projetado e métricas (área, perímetro, centroide, bbox)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from pyproj import CRS, Geod, Transformer
from shapely import force_2d
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union
from shapely.validation import explain_validity, make_valid

GEOD = Geod(ellps="WGS84")
SIRGAS_UTM_SOUTH = {18: 31978, 19: 31979, 20: 31980, 21: 31981, 22: 31982, 23: 31983, 24: 31984, 25: 31985}


@dataclass
class Issue:
    code: str
    severity: str  # "error" | "warning" | "info"
    message: str
    feature: str | None = None

    def asdict(self) -> dict:
        return {"code": self.code, "severity": self.severity, "message": self.message, "feature": self.feature}


@dataclass
class Validation:
    geometry: MultiPolygon | None
    issues: list[Issue] = field(default_factory=list)
    repaired: bool = False

    @property
    def ok(self) -> bool:
        return self.geometry is not None and not any(i.severity == "error" for i in self.issues)


def utm_epsg(lon: float, lat: float) -> int:
    """SIRGAS 2000 / UTM para o Brasil (zonas 18S–25S); WGS 84 / UTM no resto do mundo."""
    zone = int((lon + 180) // 6) + 1
    if lat < 0 and zone in SIRGAS_UTM_SOUTH and -80 <= lon <= -28:
        return SIRGAS_UTM_SOUTH[zone]
    return (32700 if lat < 0 else 32600) + zone


def to_multipolygon(g) -> MultiPolygon | None:
    if g is None or g.is_empty:
        return None
    if isinstance(g, Polygon):
        return MultiPolygon([g])
    if isinstance(g, MultiPolygon):
        return g
    polys = [p for p in getattr(g, "geoms", []) if isinstance(p, (Polygon, MultiPolygon))]
    flat = []
    for p in polys:
        flat.extend(p.geoms if isinstance(p, MultiPolygon) else [p])
    return MultiPolygon(flat) if flat else None


def validate_geometry(geom_geojson: dict, name: str | None = None, repair: bool = True, max_area_ha: float | None = None) -> Validation:
    """Valida um polígono em EPSG:4326 (lon, lat). Nunca altera em silêncio: repara só com `repair=True` e avisa."""
    issues: list[Issue] = []
    try:
        g = shape(geom_geojson)
    except Exception as exc:  # GeoJSON malformado
        return Validation(None, [Issue("GEOM_PARSE", "error", f"Geometria ilegível: {exc}", name)])
    if g.geom_type not in ("Polygon", "MultiPolygon"):
        return Validation(None, [Issue("GEOM_TYPE", "error", f"Esperado Polygon/MultiPolygon, recebido {g.geom_type}.", name)])
    if g.is_empty:
        return Validation(None, [Issue("GEOM_EMPTY", "error", "Geometria vazia.", name)])
    coords = np.asarray([c for p in ([g] if g.geom_type == "Polygon" else g.geoms) for c in p.exterior.coords])
    if coords.shape[1] > 2 and np.isfinite(coords[:, 2]).any():
        issues.append(Issue("GEOM_Z", "info", "Coordenada Z ignorada (a elevação vem do DEM, não da geometria).", name))
    if not np.isfinite(coords[:, :2]).all():
        return Validation(None, [Issue("GEOM_NAN", "error", "Coordenadas não finitas.", name)])
    x, y = coords[:, 0], coords[:, 1]
    if x.min() < -180 or x.max() > 180 or y.min() < -90 or y.max() > 90:
        return Validation(None, issues + [Issue(
            "CRS_RANGE", "error",
            "Coordenadas fora de [-180,180]/[-90,90]: provavelmente não estão em graus (EPSG:4326). "
            "Reenvie em lon/lat ou use Shapefile com .prj.", name)])
    g = force_2d(g)
    repaired = False
    if not g.is_valid:
        why = explain_validity(g)
        if repair:
            fixed = to_multipolygon(make_valid(g))
            if fixed is None or fixed.is_empty:
                return Validation(None, issues + [Issue("GEOM_INVALID", "error", f"Inválida e irreparável: {why}", name)])
            issues.append(Issue("GEOM_REPAIRED", "warning", f"Geometria inválida ({why}); reparada com make_valid — confira o resultado.", name))
            g, repaired = fixed, True
        else:
            return Validation(None, issues + [Issue("GEOM_INVALID", "error", f"Geometria inválida: {why}", name)])
    mp = to_multipolygon(g)
    if mp is None:
        return Validation(None, issues + [Issue("GEOM_EMPTY", "error", "Sem área após reparo.", name)])
    lon0, lat0 = mp.centroid.x, mp.centroid.y
    area_ha = GEOD.geometry_area_perimeter(mp)[0]
    area_ha = abs(area_ha) / 1e4
    if area_ha < 0.01:
        issues.append(Issue("AREA_TINY", "warning", f"Área muito pequena ({area_ha:.4f} ha).", name))
    if max_area_ha and area_ha > max_area_ha:
        issues.append(Issue("AREA_HUGE", "error", f"Área de {area_ha:.0f} ha excede o limite operacional de {max_area_ha:.0f} ha.", name))
    if len(mp.geoms) > 1:
        issues.append(Issue("GEOM_MULTI", "info", f"Geometria com {len(mp.geoms)} partes.", name))
    if any(len(p.interiors) for p in mp.geoms):
        issues.append(Issue("GEOM_HOLES", "info", "Geometria com buracos (áreas excluídas).", name))
    if (x.max() - x.min()) > 3.0:
        issues.append(Issue("UTM_SPAN", "warning", "Extensão E–O > 3°: a projeção UTM de uma zona distorce a área.", name))
    return Validation(mp, issues, repaired)


def check_plots(prop: MultiPolygon, plots: dict[str, MultiPolygon], tol_m2: float = 1.0) -> list[Issue]:
    """Talhões: sobreposição entre si e fora da propriedade (medidos em UTM)."""
    issues: list[Issue] = []
    crs = utm_epsg(prop.centroid.x, prop.centroid.y)
    tr = Transformer.from_crs(4326, crs, always_xy=True).transform
    P = shp_transform(tr, prop)
    U = {k: shp_transform(tr, v) for k, v in plots.items()}
    names = list(U)
    for i, a in enumerate(names):
        outside = U[a].difference(P).area
        if outside > tol_m2:
            issues.append(Issue("PLOT_OUTSIDE", "warning", f"{outside / 1e4:.2f} ha do talhão fora do perímetro da propriedade.", a))
        for b in names[i + 1:]:
            inter = U[a].intersection(U[b]).area
            if inter > tol_m2:
                issues.append(Issue("PLOT_OVERLAP", "warning", f"Talhões '{a}' e '{b}' se sobrepõem em {inter / 1e4:.2f} ha.", a))
    cover = unary_union(list(U.values())).intersection(P).area / P.area if U else 0
    if U:
        issues.append(Issue("PLOT_COVERAGE", "info", f"Talhões cobrem {cover * 100:.1f}% da propriedade.", None))
    return issues


def metrics(mp: MultiPolygon) -> dict:
    """Área/perímetro em UTM (SIRGAS 2000 no Brasil) e conferência geodésica no elipsoide WGS 84."""
    c = mp.centroid
    epsg = utm_epsg(c.x, c.y)
    tr = Transformer.from_crs(4326, epsg, always_xy=True).transform
    pu = shp_transform(tr, mp)
    geo_area = abs(GEOD.geometry_area_perimeter(mp)[0])
    geo_perim = sum(GEOD.geometry_area_perimeter(Polygon(p.exterior))[1] for p in mp.geoms) + sum(
        GEOD.geometry_area_perimeter(Polygon(r))[1] for p in mp.geoms for r in p.interiors)
    cu = pu.centroid
    inv = Transformer.from_crs(epsg, 4326, always_xy=True).transform
    clon, clat = inv(cu.x, cu.y)
    minx, miny, maxx, maxy = mp.bounds
    return {
        "crs_projected": f"EPSG:{epsg}",
        "crs_projected_name": CRS.from_epsg(epsg).name,
        "area_ha": pu.area / 1e4,
        "perimeter_m": pu.length,
        "area_ha_geodesic": geo_area / 1e4,
        "perimeter_m_geodesic": geo_perim,
        "area_diff_pct": (pu.area - geo_area) / geo_area * 100 if geo_area else 0.0,
        "centroid": {"lon": clon, "lat": clat},
        "bbox": [minx, miny, maxx, maxy],
        "n_parts": len(mp.geoms),
    }
