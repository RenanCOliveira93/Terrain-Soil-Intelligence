import os

import pytest
from sqlalchemy import text
from shapely.geometry import MultiPolygon, box

from app import store


def test_roundtrip_sqlite_e_cascata(tmp_path):
    store.init_db(f"sqlite:///{tmp_path}/t.db")
    g = MultiPolygon([box(-46.8, -22.2, -46.79, -22.19)])
    with store.session() as s:
        p = store.Property(name="a", geom=g, area_ha=1.0)
        p.plots.append(store.Plot(name="t", geom=g, area_ha=1.0))
        p.analyses.append(store.Analysis(params={"x": 1}))
        s.add(p)
        s.flush()
        pid = p.id
    with store.session() as s:
        p = s.get(store.Property, pid)
        assert p.geom.equals(g) and p.plots[0].geom.equals(g) and p.analyses[0].params == {"x": 1}
        s.delete(p)
    with store.session() as s:
        assert s.query(store.Plot).count() == 0 and s.query(store.Analysis).count() == 0
    store.init_db()


@pytest.mark.postgis
def test_postgis_roundtrip_e_indice_espacial():
    url = os.environ["TSI_TEST_DATABASE_URL"]
    eng = store.init_db(url)
    g = MultiPolygon([box(-46.8, -22.2, -46.79, -22.19)])
    with store.session() as s:
        p = store.Property(name="pg", geom=g, area_ha=1.0)
        s.add(p)
        s.flush()
        pid = p.id
    with store.session() as s:
        assert s.get(store.Property, pid).geom.equals_exact(g, 1e-9)
        n = s.execute(text("select count(*) from properties where ST_Intersects(geom, ST_MakeEnvelope(-46.9,-22.3,-46.7,-22.1,4326))")).scalar()
        assert n >= 1
    with eng.begin() as c:
        idx = c.exec_driver_sql("select indexdef from pg_indexes where tablename='properties'").fetchall()
    assert any("gist" in r[0].lower() for r in idx)
    with store.session() as s:
        s.delete(s.get(store.Property, pid))
