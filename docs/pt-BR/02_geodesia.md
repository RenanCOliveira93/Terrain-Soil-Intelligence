# 02 · Geodésia: de onde vem a "altura" e a "área" que o app mostra

## 1. Três superfícies que não são a mesma
| Superfície | O que é | Onde aparece |
|---|---|---|
| **Terreno / superfície topográfica** | o chão (e, no DSM, o que está sobre ele) | o que queremos descrever |
| **Elipsoide** (WGS 84) | superfície matemática lisa que aproxima a Terra | latitude e longitude; altura **elipsoidal** (h) do GNSS bruto |
| **Geoide** (EGM2008) | superfície equipotencial do campo de gravidade, próxima ao nível médio do mar | altura **ortométrica** (H), a "altitude" usual |

A relação é **h ≈ H + N**, onde N é a **ondulação geoidal** (distância entre geoide e elipsoide). N varia de ponto a ponto e, no Sudeste do Brasil, é da ordem de alguns metros (**não calculamos o valor aqui**; para convertê-lo use um modelo geoidal oficial, como o MAPGEO do IBGE ou a grade EGM2008).

## 2. O que o Copernicus DEM GLO-30 usa
- Horizontal: **WGS 84 (EPSG:4326)**, graus.
- Vertical: **EGM2008 (EPSG:3855)**, ou seja, alturas **ortométricas** acima do geoide.
- Consequência prática: um ponto de GNSS com altura **elipsoidal** não pode ser comparado diretamente com o DEM; seria preciso subtrair N. Um valor "0 m" no DEM **não** é o nível médio do mar local.

> Fontes consultadas: página de coleção do Copernicus Data Space (exatidão e DSM), catálogo do Google Earth Engine (EGM2008/EPSG:3855) e uma página do EMD (WGS 84). O *Product Handbook* (i5.0) só pôde ser lido como índice; os números vêm dessas fontes secundárias. Veja `13_limitacoes_e_licencas.md`.

## 3. WGS 84 × SIRGAS 2000
O datum oficial brasileiro é o **SIRGAS 2000**. Para fins cartográficos de escala de propriedade, as diferenças horizontais entre WGS 84 e SIRGAS 2000 são da ordem de decímetros, **muito abaixo** da resolução de 30 m. Por isso o app mantém a entrada em WGS 84 (padrão do GeoJSON) e usa **SIRGAS 2000 / UTM** só para calcular áreas e perímetros no Brasil. Não fazemos transformação de datum com grade (não há ganho na escala do DEM).

## 4. Área: duas formas, uma conferência
- **UTM (primária):** projeta o polígono para a zona UTM do centroide (SIRGAS 2000 / UTM 18S–25S no Brasil) e mede em metros. A projeção distorce a escala em até ≈ 0,04% (fator 0,9996 no meridiano central até ≈ 1,0004 nas bordas), o que implica erro de área da ordem de 0,08% no pior caso.
- **Geodésica (conferência):** `pyproj.Geod` mede a área direto no elipsoide WGS 84.
- O app mostra as duas e a diferença. Na propriedade de demonstração: **332,86 ha (UTM)** × **332,85 ha (geodésica)**, diferença de **+0,003%**.
- Se a propriedade se estende por mais de 3° E–O, o app avisa (`UTM_SPAN`): uma única zona UTM deixa de ser adequada.

## 5. Tamanho da célula em metros
Um pixel de 1" não tem tamanho fixo: o comprimento de 1" de longitude diminui com cos(φ). A 22,2°S, a célula do DEM mede **≈ 28,6 m (E–O) × 30,8 m (N–S)** (medido, notebook 02). O app calcula dx(φ) e dy(φ) por linha com as séries padrão do elipsoide, em vez de supor 30 m × 30 m.
