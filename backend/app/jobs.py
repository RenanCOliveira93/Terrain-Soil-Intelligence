"""Jobs assíncronos: executor de threads + progresso persistido na tabela `analyses`."""
from __future__ import annotations

import logging
import traceback
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from shapely.geometry import mapping

from . import store
from .config import settings
from .core import analysis as an

log = logging.getLogger("tsi.jobs")
_pool: ThreadPoolExecutor | None = None


def pool() -> ThreadPoolExecutor:
    global _pool
    if _pool is None:
        _pool = ThreadPoolExecutor(settings.job_workers, thread_name_prefix="tsi-job")
    return _pool


def _update(aid: str, **kw):
    with store.session() as s:
        a = s.get(store.Analysis, aid)
        for k, v in kw.items():
            setattr(a, k, v)


def _run(aid: str):
    try:
        with store.session() as s:
            a = s.get(store.Analysis, aid)
            p = a.property
            prop_geom = mapping(p.geom)
            plots = [{"name": pl.name, "geometry": mapping(pl.geom)} for pl in p.plots]
            params, name, mode = dict(a.params or {}), p.name, a.mode
        _update(aid, status="running", stage="Iniciando", progress=0.01)

        def progress(f, msg):
            _update(aid, progress=float(f), stage=msg)

        res = an.run_analysis(prop_geom, plots, params, settings.analyses_dir / aid, progress, mode, name)
        z = res["zones"]["property"]
        summary = {"area_ha": res["metrics"]["property"]["area_ha"], "elevation_mean_m": z["elevation_m"]["mean"],
                   "slope_mean_pct": z["slope_pct"]["mean"], "n_warnings": len(res["warnings"])}
        from .core import report
        report.build_pdf(settings.analyses_dir / aid, res)
        _update(aid, status="done", progress=1.0, stage="Concluído", summary=summary,
                finished_at=datetime.now(timezone.utc))
    except Exception as exc:
        log.error("job %s falhou: %s\n%s", aid, exc, traceback.format_exc())
        _update(aid, status="failed", stage="Falhou", error=str(exc), finished_at=datetime.now(timezone.utc))


def submit(aid: str):
    return pool().submit(_run, aid)
