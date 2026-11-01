import numpy as np
import pytest

from app.core import contours, terrain
from conftest import make_plane


@pytest.mark.parametrize("sx,sy,asp", [(0.10, 0, 270.0), (-0.10, 0, 90.0), (0, 0.10, 180.0), (0, -0.10, 0.0)])
def test_plano_inclinado_declividade_e_aspecto_exatos(sx, sy, asp):
    z, tr = make_plane(sx, sy)
    sl, a = terrain.slope_aspect(z, tr)
    inner = (slice(2, -2), slice(2, -2))
    assert np.nanmean(sl[inner]) == pytest.approx(np.degrees(np.arctan(0.10)), rel=2e-3)
    assert np.nanmax(np.abs(((a[inner] - asp + 180) % 360) - 180)) < 0.5


def test_diagonal_nordeste_sobe_logo_encosta_olha_para_sudoeste():
    z, tr = make_plane(0.05, 0.05)
    _, a = terrain.slope_aspect(z, tr)
    assert np.nanmean(a[3:-3, 3:-3]) == pytest.approx(225.0, abs=0.5)


def test_plano_horizontal_tem_aspecto_indefinido_e_hillshade_seno_da_altitude():
    z, tr = make_plane()
    sl, a = terrain.slope_aspect(z, tr)
    assert np.nanmax(sl[2:-2, 2:-2]) < 1e-3 and np.isnan(a[2:-2, 2:-2]).all()
    assert terrain.hillshade(z, tr)[3:-3, 3:-3].mean() == pytest.approx(np.sin(np.radians(45)), abs=1e-4)


def test_bordas_e_nan_viram_nan():
    z, tr = make_plane(0.1, 0)
    z[20, 20] = np.nan
    sl, _ = terrain.slope_aspect(z, tr)
    assert np.isnan(sl[0, :]).all() and np.isnan(sl[:, 0]).all()
    assert np.isnan(sl[19:22, 19:22]).all() and np.isfinite(sl[10, 10])


def test_tamanho_de_celula_em_metros_a_22s():
    _, tr = make_plane()
    dx, dy = terrain.cell_size_m(tr, 40)
    assert dx.mean() == pytest.approx(28.6, abs=0.2) and dy.mean() == pytest.approx(30.8, abs=0.2)


def test_dx_menor_perto_dos_polos():
    a, _ = terrain.meters_per_degree(np.array([0.0, 60.0]))
    assert a[1] == pytest.approx(a[0] / 2, rel=0.01)


def test_classes_de_declividade_somam_um_e_limites():
    pct = np.array([1, 3.01, 7.9, 8.01, 19.9, 20.01, 44, 45.01, 74, 75.01, 200.0])
    deg = np.degrees(np.arctan(pct / 100))
    sh = terrain.slope_class_shares(deg)
    assert sum(c["share"] for c in sh) == pytest.approx(1.0)
    assert [round(c["share"] * len(pct)) for c in sh] == [1, 2, 2, 2, 2, 2]


def test_aspecto_octantes_e_resumo_circular():
    a = np.array([350.0, 10.0, 355.0, 5.0])  # todos ~Norte: a média aritmética (180) seria absurda
    s = terrain.aspect_summary(a, 4)
    assert s["dominant"] == "N" and s["resultant_length"] > 0.99
    assert min(s["mean_dir_deg"], 360 - s["mean_dir_deg"]) < 1.0


def test_hipsometria_monotonica():
    h = terrain.hypsometry(np.random.default_rng(0).normal(800, 30, 5000))
    assert np.all(np.diff(h["elevation"]) >= 0) and h["area_above"][0] == 1 and h["area_above"][-1] == 0


def test_intervalo_de_curvas_politica():
    with pytest.raises(ValueError, match="mínimo"):
        contours.check_interval(4)
    assert contours.check_interval(7) and not contours.check_interval(10)
    assert contours.recommended_interval(40) == 10 and contours.recommended_interval(300) == 50


def test_curvas_de_plano_inclinado_sao_retas_nos_multiplos():
    z, tr = make_plane(0.0, 0.1)
    z = z + 3
    feats = contours.contour_features(z, tr, 10.0)
    levs = sorted({f["properties"]["elevation_m"] for f in feats})
    assert all(l % 10 == 0 for l in levs) and levs
    assert all(f["properties"]["kind"] == "derivada_do_DEM_GLO30_DSM" for f in feats)
    with pytest.raises(ValueError):
        contours.contour_features(z, tr, 2.0)
