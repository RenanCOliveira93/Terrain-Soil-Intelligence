# 04 · Raster e vetor

## 1. Dois modelos de dados
- **Vetor:** geometrias exatas (ponto, linha, polígono) com coordenadas. A propriedade e os talhões são vetores.
- **Raster:** grade regular de células com um valor cada. O DEM (30 m) e o SoilGrids (250 m) são rasters.

O trabalho do app é **cruzar** os dois: dizer quais células pertencem a cada polígono e resumir os valores.

## 2. Pixel é uma área, não um ponto
Um pixel de 30 m representa o valor numa **área** de ≈ 29 × 31 m. A fonte do Copernicus marca `AREA_OR_POINT=Point`, mas os limites dos tiles estão deslocados em meio pixel de graus inteiros (−48,000139°), compatível com centro do pixel em graus inteiros. Usamos a geotransformação do arquivo como está; **pode haver uma ambiguidade de até meio pixel (~15 m)** que não verificamos.

## 3. Quais células estão "dentro"
`rasterio.features.geometry_mask`: por padrão, uma célula entra se seu **centro** está no polígono (`all_touched=False`). Para o DEM em polígonos de dezenas de hectares isso é bom: na propriedade de 332,86 ha, 3775 pixels × 0,0881 ha = 332,60 ha (**razão 0,999**).

### Polígonos pequenos
No **talhão D (1,78 ha)** sobram 16 pixels (1,41 ha, razão **0,79**): o recorte "perde" 21% da área. O app:
1. tenta `all_touched=True` se nenhum centro cair dentro;
2. informa `n_pixels` e **avisa** quando há menos de 30 pixels (`quality_flags`).

No SoilGrids (250 m ≈ 6–7 ha) a situação é mais forte: uma zona < 1 pixel recebe **o valor do pixel que a contém** (`centroid_pixel`), e zonas vizinhas podem ter valores idênticos. O app avisa isso e a comparação entre zonas marca "valores idênticos".

## 4. Estatísticas zonais
Usamos `rasterstats.zonal_stats` sobre a matriz e a geotransformação (mín., máx., média, mediana, desvio, P5, P95), mais:
- distribuição por **classe de declividade** (fatias de área);
- **aspecto**: oitantes, direção média circular e comprimento resultante;
- **hipsometria**: quantis da elevação.
Os testes comparam `rasterstats` com uma média independente por máscara (resultados idênticos).

## 5. Valores ausentes (nodata)
- DEM: sem lacunas na amostra; qualquer NaN vira `NaN` e propaga para a declividade vizinha (um pixel sem dado também fica sem declividade).
- SoilGrids: **int16 com nodata −32768**, mas as camadas de incerteza são **uint16 com 65535**. Sempre lemos o nodata do próprio arquivo: confundir os dois transforma "sem dado" em "valor 65535" e estraga qualquer média (erro real que quase ocorreu na exploração). Ainda assim, ≈ 9% dos pixels do recorte são nodata (máscara do ISRIC).

## 6. COG e leitura remota
O Copernicus DEM está em **Cloud Optimized GeoTIFF**: abrimos o arquivo remoto e lemos só a **janela** da propriedade (HTTP range). O resultado é guardado em `data/cache/` por hash da caixa envolvente.
