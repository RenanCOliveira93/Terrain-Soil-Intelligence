# Dados de amostra (modo demonstração)

| Arquivo | Origem | Licença / termos |
|---|---|---|
| `demo_dem_glo30.tif` | **Copernicus DEM GLO-30** (tile `Copernicus_DSM_COG_10_S23_00_W047_00_DEM`, AWS Open Data), recorte (−46,84…−46,72; −22,26…−22,14), obtido em 31/10/2026 | Licença Copernicus. *Copernicus DEM © DLR e.V. 2010-2014 e © Airbus Defence and Space GmbH 2014-2018, fornecido sob COPERNICUS pela União Europeia e ESA; acessado via https://registry.opendata.aws/copernicus-dem.* Termos de redistribuição de recortes **não revisados**: confirme antes de publicar fora da organização. |
| `demo_soilgrids.tif` | **SoilGrids 2.0** (ISRIC), `files.isric.org/soilgrids/latest/data`, 5 atributos × 3 profundidades × (média, Q0.05, Q0.5, Q0.95), reamostrado por vizinho mais próximo para EPSG:4326 (0,0025°), valores convertidos (pH, g/kg, %) | **CC BY 4.0** — cite o ISRIC e Poggio et al. (2021). |
| `propriedade_demo.geojson/.kml`, `propriedade_demo_shp.zip` | **polígonos ilustrativos (fictícios)** de `scripts/make_sample_polygons.py` | do projeto |
| `invalido_*.geojson` | **sintéticos**, para testes de validação | do projeto |

Os polígonos **não representam uma propriedade real**. Regenerar: `python scripts/build_sample_data.py` (rede) e `python scripts/make_sample_polygons.py`.
