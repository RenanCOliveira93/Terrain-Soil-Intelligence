import numpy as np
import pytest
import rasterio
from shapely.geometry import box

from app.core import dem as demmod
from app.core import soil, terrain, zonal
from app.config import settings
from conftest import make_plane


def _grid():
    z, tr = make_plane(0.05, 0.02, n=60)
    sl, a = terrain.slope_aspect(z, tr)
    return z, sl, a, tr


def test_rasterstats_bate_com_media_por_mascara_propria():
    z, sl, a, tr = _grid()
    poly = box(tr.c + 15 * tr.a, tr.f + 45 * tr.e, tr.c + 45 * tr.a, tr.f + 15 * tr.e)
    zs = zonal.terrain_zone(poly, z, sl, a, tr)
    m = zonal.cell_mask(poly, tr, z.shape)
    assert zs["n_pixels"] == int((m & np.isfinite(z)).sum()) == 900
    assert zs["elevation_m"]["mean"] == pytest.approx(float(z[m].mean()), rel=1e-6)
    assert zs["slope_deg"]["mean"] == pytest.approx(float(sl[m].mean()), rel=1e-5)
    assert sum(c["share"] for c in zs["slope_classes"]) == pytest.approx(1.0)
    assert zs["quality_flags"] == []


def test_poligono_menor_que_pixel_gera_aviso():
    z, sl, a, tr = _grid()
    c = (tr.c + 30.2 * tr.a, tr.f + 30.2 * tr.e)
    tiny = box(c[0], c[1] - 0.1 * abs(tr.e), c[0] + 0.1 * tr.a, c[1])
    zs = zonal.terrain_zone(tiny, z, sl, a, tr)
    assert zs["n_pixels"] >= 1 and any("menor que um pixel" in f for f in zs["quality_flags"])


def test_poligono_fora_do_dem_nao_inventa_numeros():
    z, sl, a, tr = _grid()
    far = box(tr.c + 1, tr.f - 1, tr.c + 1.001, tr.f - 0.999)
    zs = zonal.terrain_zone(far, z, sl, a, tr)
    assert zs["n_pixels"] == 0 and zs["elevation_m"]["mean"] is None


def test_fatores_de_conversao_e_soma_da_textura_nas_amostras():
    d = soil.fetch_demo((-46.79, -22.21, -46.77, -22.19))
    L = d["layers"]
    clay, silt, sand = (np.nanmean(L[soil.layer_name(p, "0-5cm", "mean")]) for p in ("clay", "silt", "sand"))
    assert clay + silt + sand == pytest.approx(100, abs=1.0)  # composicional: soma ≈ 100%
    ph = np.nanmean(L[soil.layer_name("phh2o", "0-5cm", "mean")])
    assert 3.5 < ph < 8.5
    for p in soil.PROPERTIES:
        for dpt in d["depths"]:
            q05, q50, q95 = (L[soil.layer_name(p, dpt, s)] for s in ("q05", "q50", "q95"))
            ok = np.isfinite(q05) & np.isfinite(q95)
            assert (q05[ok] <= q50[ok] + 1e-6).all() and (q50[ok] <= q95[ok] + 1e-6).all()


def test_nodata_vira_nan_e_nunca_zero():
    d = soil.fetch_demo((-46.84, -22.26, -46.72, -22.14))
    for a in d["layers"].values():
        assert not np.isin(a, [-32768, 65535, -3276.8]).any()


def test_demo_fora_da_cobertura_levanta_erro_claro():
    with pytest.raises(demmod.CoverageError, match="fora do recorte"):
        demmod.fetch_demo((10.0, 10.0, 10.1, 10.1))
    with pytest.raises(ValueError, match="fora do recorte"):
        soil.fetch_demo((10.0, 10.0, 10.1, 10.1))


@pytest.mark.parametrize("c,s,a,esperado", [
    (5, 5, 90, "Areia"), (50, 10, 40, "Argila"), (20, 40, 40, "Franco"), (10, 85, 5, "Silte"),
    (35, 30, 35, "Franco argiloso"), (15, 15, 70, "Franco arenoso"), (60, 10, 30, "Argila")])
def test_classe_textural_usda(c, s, a, esperado):
    assert soil.texture_class(c, s, a) == esperado


def test_textura_normaliza_e_trata_nan():
    assert soil.texture_class(np.nan, 1, 1) is None
    assert soil.texture_class(35 * 1.01, 30 * 1.01, 35 * 1.01) == soil.texture_class(35, 30, 35)


def test_metadados_do_dem_declaram_dsm_datum_e_licenca():
    m = demmod.DEM_META
    assert m["model_type"] == "DSM" and "EGM2008" in m["vertical_datum"] and "4 m" in m["vertical_accuracy_spec"]
    assert "COPERNICUS" in m["attribution"]


def test_url_dos_tiles():
    assert demmod.tile_url(-23, -47).endswith("Copernicus_DSM_COG_10_S23_00_W047_00_DEM/Copernicus_DSM_COG_10_S23_00_W047_00_DEM.tif")
    assert demmod.tiles_for_bbox((-46.84, -22.26, -46.72, -22.14)) == [(-23, -47)]
    assert len(demmod.tiles_for_bbox((-47.1, -22.5, -46.9, -22.4))) == 2  # cruza o meridiano -47


@pytest.mark.network
def test_dem_ao_vivo_igual_a_amostra_versionada():
    import os
    bbox = (-46.80, -22.22, -46.76, -22.18)
    live = demmod.fetch_live(bbox)
    with rasterio.open(settings.sample_dir / "demo_dem_glo30.tif") as s:
        from app.core.dem import read_window
        arr, tr = read_window(s, bbox)
    assert live.array.shape == arr.shape
    assert np.allclose(live.array, arr, equal_nan=True)


@pytest.mark.network
def test_soilgrids_ao_vivo_igual_a_amostra():
    bbox = (-46.79, -22.21, -46.77, -22.19)
    live = soil.fetch_live(bbox, props=["clay"], depths=["0-5cm"])
    demo = soil.fetch_demo(bbox)
    # mesma grade de 0,0025°: compara todos os pixels, tratando nodata (NaN) como igual a NaN
    tr = live["transform"]
    n = 0
    for stat in ("mean", "q05", "q95"):
        a = live["layers"][soil.layer_name("clay", "0-5cm", stat)]
        b = demo["layers"][soil.layer_name("clay", "0-5cm", stat)]
        for r in range(a.shape[0]):
            for c in range(a.shape[1]):
                x, y = tr * (c + 0.5, r + 0.5)
                col, row = ~demo["transform"] * (x, y)
                bv = b[int(row), int(col)]
                assert (np.isnan(a[r, c]) and np.isnan(bv)) or a[r, c] == pytest.approx(bv, abs=1e-4)
                n += 1
    assert n > 100
