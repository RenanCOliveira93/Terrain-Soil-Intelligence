"""Importação de perímetros: GeoJSON, KML e Shapefile (ZIP). Saída sempre em EPSG:4326 (lon, lat)."""
from __future__ import annotations

import io
import json
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
from lxml import etree
from shapely.geometry import MultiPolygon, Polygon, mapping

MAX_ZIP_UNCOMPRESSED = 200 * 1024 * 1024


class ImportError_(ValueError):
    pass


@dataclass
class Imported:
    features: list[dict]  # {"name": str, "geometry": geojson, "properties": dict}
    source_crs: str
    notes: list[str] = field(default_factory=list)


def _name(props: dict, i: int) -> str:
    for k in ("name", "nome", "NAME", "Name", "NOME", "talhao", "TALHAO", "id", "ID"):
        if props.get(k) not in (None, ""):
            return str(props[k])
    return f"feição {i + 1}"


def read_geojson(raw: bytes) -> Imported:
    try:
        obj = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise ImportError_(f"GeoJSON inválido: {exc}") from exc
    notes = []
    crs = (obj.get("crs") or {}).get("properties", {}).get("name") if isinstance(obj, dict) else None
    if crs and "4326" not in crs and "CRS84" not in crs.upper():
        raise ImportError_(
            f"GeoJSON declara CRS '{crs}'. A especificação RFC 7946 exige WGS 84 (lon/lat); "
            "reprojete antes ou envie um Shapefile com .prj.")
    if crs:
        notes.append("Membro 'crs' obsoleto presente; tratado como WGS 84.")
    t = obj.get("type")
    if t == "FeatureCollection":
        feats = obj["features"]
    elif t == "Feature":
        feats = [obj]
    elif t in ("Polygon", "MultiPolygon"):
        feats = [{"type": "Feature", "geometry": obj, "properties": {}}]
    else:
        raise ImportError_(f"Tipo GeoJSON não suportado: {t}")
    out = []
    for i, f in enumerate(feats):
        if not f.get("geometry"):
            notes.append(f"Feição {i + 1} sem geometria ignorada.")
            continue
        props = f.get("properties") or {}
        out.append({"name": _name(props, i), "geometry": f["geometry"], "properties": props})
    return Imported(out, "EPSG:4326", notes)


def _coords(text: str) -> list[tuple[float, float]]:
    pts = []
    for tok in text.split():
        p = tok.split(",")
        if len(p) >= 2:
            pts.append((float(p[0]), float(p[1])))
    return pts


def read_kml(raw: bytes) -> Imported:
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)
        root = etree.fromstring(raw, parser)
    except Exception as exc:
        raise ImportError_(f"KML inválido: {exc}") from exc
    out, notes = [], []
    els = lambda node: (n for n in node.iter() if isinstance(n.tag, str))  # ignora comentários e instruções  # noqa: E731
    for i, pm in enumerate(n for n in els(root) if etree.QName(n).localname == "Placemark"):
        nm = next((c.text for c in pm if isinstance(c.tag, str) and etree.QName(c).localname == "name" and c.text), None)
        polys = []
        for poly in (n for n in els(pm) if etree.QName(n).localname == "Polygon"):
            outer, holes = None, []
            for b in els(poly):
                ln = etree.QName(b).localname
                if ln in ("outerBoundaryIs", "innerBoundaryIs"):
                    c = next((x for x in els(b) if etree.QName(x).localname == "coordinates"), None)
                    if c is not None and c.text:
                        ring = _coords(c.text)
                        (holes.append(ring) if ln == "innerBoundaryIs" else None)
                        if ln == "outerBoundaryIs":
                            outer = ring
            if outer and len(outer) >= 4:
                polys.append(Polygon(outer, holes))
        if not polys:
            notes.append(f"Placemark '{nm or i + 1}' sem polígono ignorado.")
            continue
        g = polys[0] if len(polys) == 1 else MultiPolygon(polys)
        out.append({"name": nm or f"feição {i + 1}", "geometry": mapping(g), "properties": {}})
    if not out:
        raise ImportError_("Nenhum polígono encontrado no KML.")
    return Imported(out, "EPSG:4326", notes + ["KML é sempre WGS 84 (lon, lat)."])


def read_shapefile_zip(raw: bytes) -> Imported:
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise ImportError_("ZIP inválido.") from exc
    names = zf.namelist()
    if sum(i.file_size for i in zf.infolist()) > MAX_ZIP_UNCOMPRESSED:
        raise ImportError_("ZIP descompactado grande demais.")
    shps = [n for n in names if n.lower().endswith(".shp") and not n.startswith("__MACOSX")]
    if not shps:
        raise ImportError_("O ZIP não contém arquivo .shp.")
    base = shps[0][:-4]
    need = {".shp", ".shx", ".dbf"}
    have = {Path(n).suffix.lower() for n in names if n[:-4] == base}
    if not need <= have:
        raise ImportError_(f"Faltam componentes do Shapefile: {sorted(need - have)}.")
    notes = []
    with tempfile.TemporaryDirectory() as td:
        for n in names:
            if n[:-4] == base:  # só os componentes do shapefile escolhido; evita path traversal
                (Path(td) / ("s" + Path(n).suffix.lower())).write_bytes(zf.read(n))
        gdf = gpd.read_file(Path(td) / "s.shp")
    if gdf.crs is None:
        if ".prj" not in have and ".PRJ" not in have:
            raise ImportError_("Shapefile sem .prj: não é possível saber o CRS. Inclua o .prj no ZIP.")
        raise ImportError_("CRS do .prj não reconhecido.")
    src = gdf.crs.to_string()
    if gdf.crs.to_epsg() != 4326:
        notes.append(f"Reprojetado de {src} para EPSG:4326.")
        gdf = gdf.to_crs(4326)
    out = []
    for i, row in gdf.iterrows():
        if row.geometry is None or row.geometry.is_empty:
            notes.append(f"Registro {i + 1} sem geometria ignorado.")
            continue
        props = {k: (v if isinstance(v, (str, int, float, bool)) or v is None else str(v)) for k, v in row.items() if k != "geometry"}
        out.append({"name": _name(props, i), "geometry": mapping(row.geometry), "properties": props})
    return Imported(out, src, notes)


def read_any(filename: str, raw: bytes) -> Imported:
    ext = Path(filename).suffix.lower()
    if ext in (".geojson", ".json"):
        return read_geojson(raw)
    if ext == ".kml":
        return read_kml(raw)
    if ext == ".zip":
        return read_shapefile_zip(raw)
    raise ImportError_(f"Formato '{ext}' não suportado. Use .geojson, .kml ou .zip (Shapefile).")
