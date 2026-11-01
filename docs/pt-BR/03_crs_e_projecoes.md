# 03 · CRS e projeções

## 1. O que é um CRS
Um *Coordinate Reference System* diz como números viram pontos na Terra: o **datum** (modelo da forma da Terra), o **sistema de coordenadas** (graus ou metros) e, se for projetado, a **projeção**.

| CRS | Unidade | Uso no projeto |
|---|---|---|
| **EPSG:4326** (WGS 84) | graus (lon, lat) | armazenamento, API, GeoJSON, MapLibre, grade do DEM |
| **EPSG:3857** (Web Mercator) | metros (distorcidos) | só a exibição do mapa; **nunca** para medir |
| **SIRGAS 2000 / UTM** (EPSG:31978–31985, zonas 18S–25S) | metros | área e perímetro no Brasil |
| **WGS 84 / UTM** (EPSG:326xx/327xx) | metros | área e perímetro fora do Brasil |

## 2. Escolha automática da zona UTM
`utm_epsg(lon, lat)`: zona = ⌊(lon+180)/6⌋+1. No Brasil (lon entre −80° e −28°, hemisfério sul, zonas 18–25) usa SIRGAS 2000; senão, WGS 84. Exemplos testados: (−46,78; −22,2) → **EPSG:31983** (23S); (−51; −22) → 31982; (10; 45) → 32632.

## 3. Por que nunca medir em graus nem em Web Mercator
- Em graus, 0,01° de longitude a 22°S vale ≈ 1031 m, mas 0,01° de latitude ≈ 1106 m.
- Em Web Mercator a área é inflada por 1/cos²(φ): ≈ 17% a 22°S. Um app que mede no mapa exibido erra a área.

## 4. Armadilhas de entrada (todas tratadas e testadas)
| Situação | Comportamento do app |
|---|---|
| GeoJSON com coordenadas em UTM (metros) | recusado (`CRS_RANGE`): valores fora de ±180/±90 |
| GeoJSON com membro `crs` ≠ WGS 84 | recusado: RFC 7946 exige lon/lat WGS 84 |
| Shapefile em UTM com `.prj` | **reprojetado** para EPSG:4326 e a nota é exibida |
| Shapefile sem `.prj` | recusado: CRS desconhecido não deve ser adivinhado |
| Ordem lat/lon trocada | **não detectável com segurança** se os valores couberem em ±90: confira no mapa |
| KML | sempre WGS 84 (lon, lat, alt); altitude ignorada |

> A ordem **lon, lat** (x, y) é a do GeoJSON e do Shapely. Muitas ferramentas de GPS e planilhas usam lat, lon.

## 5. Reprojeção de raster
O DEM **não é reprojetado**: mantemos a grade geográfica original e ajustamos dx/dy por latitude. Reprojetar elevação exigiria reamostrar (interpolar), o que mistura erro de interpolação com o dado. O SoilGrids, esse sim, está em *Interrupted Goode Homolosine* e é reamostrado para EPSG:4326 com **vizinho mais próximo** (não altera valores; ver `08_propriedades_do_solo.md`).
