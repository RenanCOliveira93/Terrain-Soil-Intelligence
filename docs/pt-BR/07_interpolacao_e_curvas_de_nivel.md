# 07 · Interpolação e curvas de nível

## 1. Toda curva de nível é uma interpolação
Um DEM só tem um valor por célula. Para traçar a curva de 840 m, o algoritmo (marching squares, `contourpy`) **interpola linearmente** entre centros de células vizinhas para achar onde a superfície cruza 840 m. A linha resultante é uma **inferência** sobre o modelo, não uma medida de campo. O app rotula as curvas como `derivada_do_DEM_GLO30_DSM`, mostra o aviso "interpoladas" na camada e inclui o aviso no GeoJSON exportado.

## 2. Intervalo coerente com a resolução
Uma curva de cota *h* tem posição horizontal incerta em ≈ **σᵥ / tan(β)**, onde σᵥ é o erro vertical e β a declividade. Para σᵥ = 4 m (a especificação) e a distribuição de declividade da região de amostra (P10/P50/P90 = 5,6 / 12,3 / 25,1%):

| σᵥ | P10 (suave) | mediana | P90 (íngreme) |
|---|---|---|---|
| 1 m | 18 m | 8 m | 4 m |
| 2 m | 36 m | 16 m | 8 m |
| **4 m** | **72 m** | **32 m** | **16 m** |

Com 4 m, a incerteza horizontal na declividade mediana (≈ 32 m) já é **um pixel**. Política do app:

| Intervalo pedido | Comportamento |
|---|---|
| < 5 m | **recusado** (HTTP 422): abaixo disso as linhas são ruído |
| 5 a < 10 m | aceito com **aviso** |
| ≥ 10 m | aceito |
| em branco | automático: o maior entre 10 m e um intervalo "redondo" que gera ≈ 10 curvas (10, 20, 25, 50, 100…) |

Na propriedade de demonstração (relevo de 80 m) o automático dá **10 m**.

## 3. Outras interpolações do projeto
| Onde | Método | Efeito sobre os valores |
|---|---|---|
| DEM → declividade | nenhuma (sem reamostragem) | — |
| SoilGrids (Goode → 4326) | **vizinho mais próximo** | não cria valores novos, mas desloca até meio pixel (~125 m) |
| Rasters de camada (PNG) | MapLibre `raster-resampling: nearest` | pixels visíveis, sem suavização enganosa |
| Curvas de nível | linear entre centros | ver acima |

O app **não** faz krigagem nem suavização de solo: interpolar um produto de 250 m para parecer detalhado seria falsa precisão.

## 4. O que não fazer
- Usar as curvas para demarcar terraços ou projetar drenagem.
- Reduzir o intervalo para "ficar mais bonito".
- Tratar a distância entre curvas como medida de campo.
