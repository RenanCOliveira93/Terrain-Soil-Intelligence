import io
import json
import zipfile

import pytest

from app.core import io as gio

S = "sample_data/"


def _read(name):
    return open(S + name, "rb").read()


def test_geojson_demo():
    imp = gio.read_any("x.geojson", _read("propriedade_demo.geojson"))
    assert len(imp.features) == 5 and imp.source_crs == "EPSG:4326"


def test_kml_demo_equivale_ao_geojson():
    a = gio.read_any("x.kml", _read("propriedade_demo.kml"))
    b = gio.read_any("x.geojson", _read("propriedade_demo.geojson"))
    assert [f["name"] for f in a.features] == [f["name"] for f in b.features]
    from shapely.geometry import shape
    assert shape(a.features[0]["geometry"]).symmetric_difference(shape(b.features[0]["geometry"])).area < 1e-8


def test_shapefile_zip_utm_e_reprojetado_para_4326():
    imp = gio.read_any("x.zip", _read("propriedade_demo_shp.zip"))
    assert "31983" in imp.source_crs and any("Reprojetado" in n for n in imp.notes)
    from shapely.geometry import shape
    g0 = shape(imp.features[0]["geometry"])
    assert -46.80 < g0.centroid.x < -46.77 and -22.21 < g0.centroid.y < -22.19  # voltou para graus
    assert imp.features[0]["name"] == "Fazenda Demo (ilustrativa)"


def test_zip_sem_prj_e_recusado():
    src = zipfile.ZipFile(io.BytesIO(_read("propriedade_demo_shp.zip")))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for n in src.namelist():
            if not n.endswith(".prj"):
                z.writestr(n, src.read(n))
    with pytest.raises(gio.ImportError_, match="prj"):
        gio.read_any("x.zip", buf.getvalue())


def test_zip_sem_shp_ou_incompleto():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("a.txt", "x")
    with pytest.raises(gio.ImportError_, match="shp"):
        gio.read_any("x.zip", buf.getvalue())
    buf2 = io.BytesIO()
    with zipfile.ZipFile(buf2, "w") as z:
        z.writestr("a.shp", b"x")
    with pytest.raises(gio.ImportError_, match="Faltam"):
        gio.read_any("x.zip", buf2.getvalue())


def test_geojson_com_crs_projetado_e_recusado():
    obj = {"type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::31983"}}, "features": []}
    with pytest.raises(gio.ImportError_, match="CRS"):
        gio.read_geojson(json.dumps(obj).encode())


def test_formatos_invalidos():
    for bad in (("x.geojson", b"{nao json"), ("x.kml", b"<kml"), ("x.gpkg", b"")):
        with pytest.raises(gio.ImportError_):
            gio.read_any(*bad)


def test_kml_xxe_nao_resolve_entidades():
    evil = b'<?xml version="1.0"?><!DOCTYPE k [<!ENTITY x SYSTEM "file:///etc/passwd">]><kml><Placemark><name>&x;</name></Placemark></kml>'
    with pytest.raises(gio.ImportError_):
        gio.read_kml(evil)


def test_kml_com_comentarios_e_buracos():
    kml = b"""<?xml version="1.0"?><kml xmlns="http://www.opengis.net/kml/2.2"><!-- c --><Document><Placemark><!-- x --><name>P</name>
    <Polygon><outerBoundaryIs><LinearRing><coordinates>-46.8,-22.2,0 -46.79,-22.2,0 -46.79,-22.19,0 -46.8,-22.19,0 -46.8,-22.2,0</coordinates></LinearRing></outerBoundaryIs>
    <innerBoundaryIs><LinearRing><coordinates>-46.797,-22.197,0 -46.795,-22.197,0 -46.795,-22.195,0 -46.797,-22.195,0 -46.797,-22.197,0</coordinates></LinearRing></innerBoundaryIs></Polygon></Placemark></Document></kml>"""
    imp = gio.read_kml(kml)
    from shapely.geometry import shape
    assert imp.features[0]["name"] == "P" and len(shape(imp.features[0]["geometry"]).interiors) == 1
