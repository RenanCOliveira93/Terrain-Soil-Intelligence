"""Configuração por variáveis de ambiente (veja .env.example)."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TSI_", env_file=str(ROOT / ".env"), extra="ignore")

    # "demo" lê só de sample_data/ (offline); "live" baixa DEM e SoilGrids.
    mode: str = "demo"
    database_url: str = f"sqlite:///{ROOT / 'data' / 'tsi.db'}"
    data_dir: Path = ROOT / "data"
    sample_dir: Path = ROOT / "sample_data"
    dem_base_url: str = "https://copernicus-dem-30m.s3.amazonaws.com"
    soilgrids_base_url: str = "https://files.isric.org/soilgrids/latest/data"
    max_area_ha: float = 20000.0  # proteção de recursos, não limite científico
    max_upload_mb: int = 20
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    job_workers: int = 2

    @property
    def analyses_dir(self) -> Path:
        return self.data_dir / "analyses"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"


settings = Settings()
