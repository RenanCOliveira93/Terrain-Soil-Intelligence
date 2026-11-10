# Terrain & Soil Intelligence

[Português](README.md) · [English](README.en.md)

A web platform for terrain and soil analysis of agricultural properties: from a drawn or imported boundary (GeoJSON, KML, zipped Shapefile) it computes area, perimeter, elevation, slope, aspect, hypsometry, contour lines and estimated soil attributes, with interactive maps, plot comparison, GeoTIFF/GeoJSON export and a PDF report covering methodology, sources and limitations.

![Slope and indicators](docs/screenshots/02_declividade_e_indicadores.png)

## Features

- Polygon drawing, editing and import, with geometry and CRS validation (repair with warning, rejection of UTM coordinates in GeoJSON, overlapping-plot detection).
- Area, perimeter, centroid and bounding box in SIRGAS 2000 / UTM, cross-checked geodesically on the ellipsoid.
- Copernicus DEM GLO-30 clipped to the polygon: elevation, slope (Horn gradient), aspect, hypsometry and contours with an interval policy consistent with the resolution.
- SoilGrids 2.0 (pH, organic carbon, clay, silt, sand) with a per-pixel 90% prediction interval.
- Zonal statistics per property and plot, with quality warnings (few pixels, plot smaller than a pixel).
- Asynchronous jobs with progress; offline demo mode using versioned real clips.
- GeoTIFF (DEM, slope, aspect), GeoJSON and PDF report export.

## Usage notes

- Copernicus DEM GLO-30 is a DSM (includes canopy and buildings) with ~30 m cells. It is not a topographic survey and must not be used to plan machinery paths.
- Contour lines are interpolated from the DSM, not field measurements.
- SoilGrids is a model prediction at 250 m with wide intervals (demo: clay 37.8% [5.8–79.9]); the application does not claim soil differences between plots.
- The application does not estimate compaction, fertility, fertiliser requirements, traffic safety or rollover risk.
- Demo-mode polygons are fictitious (drawn over real data).

## Architecture

```
Frontend (React + TypeScript + MapLibre GL JS)
   └─ /api ─ FastAPI backend ─ PostGIS (SQLite in demo mode)
                └─ Async jobs ─ Geospatial core (Shapely, GeoPandas, Rasterio, rasterstats)
                                 ├─ Copernicus DEM GLO-30 (COG, AWS Open Data)
                                 ├─ SoilGrids 2.0 (ISRIC)
                                 └─ sample_data/ (offline demo mode)
```

## Quick start (offline demo mode)

Requires Python 3.11 and Node.js.

```bash
make install                 # venv + Python dependencies + npm install
cp .env.example .env         # TSI_MODE=demo
make api                     # terminal 1: http://localhost:8000/docs
make web                     # terminal 2: http://localhost:5173
```

Select **Fazenda Demo (ilustrativa)** and run the analysis. For real data anywhere in Brazil (internet required) set `TSI_MODE=live`. Docker Compose (PostGIS) is described in the [technical guide](docs/GUIA_TECNICO.md#45-docker-compose-postgis).

## Repository layout

```
backend/app/      FastAPI API and geospatial core (core/)
frontend/src/     React + TypeScript + MapLibre
infra/            Dockerfiles, nginx, init.sql
tests/            unit, API and e2e/ (Playwright)
sample_data/      real clips (DEM, SoilGrids), fictitious polygons and invalid test files
notebooks/        terrain, real-DEM and SoilGrids-uncertainty validation
scripts/          sample data, notebooks, OpenAPI, infrastructure check
docs/             GUIA_TECNICO.md, openapi.json, screenshots/
```

## Tests

```bash
make test        # pytest + frontend typecheck and tests
make test-net    # tests that reach the remote sources
make e2e         # UI tests (Playwright/Chromium)
```

Scope, reference results and items outside validation (DEM accuracy against ground truth, PostGIS) are in section 8 of the [technical guide](docs/GUIA_TECNICO.md#8-testes-e-validação).

## Data and licences

Data: Copernicus DEM (Copernicus licence, cite the source) and SoilGrids (CC BY 4.0). Redistribution terms of the Copernicus clips were not legally reviewed; see [sample_data/ATTRIBUTION.md](sample_data/ATTRIBUTION.md).

## Documentation

[Technical guide](docs/GUIA_TECNICO.md) (in Portuguese): architecture, data sources, installation and reproduction, methodology, API, tests, limitations and licences. OpenAPI schema in [docs/openapi.json](docs/openapi.json).

## Licence

Code under GPL-3.0 ([LICENSE](LICENSE)).
