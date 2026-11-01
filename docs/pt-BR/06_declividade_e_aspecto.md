# 06 · Declividade e aspecto

## 1. Gradiente de Horn (3×3)
Para uma janela com células `a b c / d e f / g h i` (norte no topo):

```
dz/dx = ((c + 2f + i) − (a + 2d + g)) / (8·Δx)      (leste positivo)
dz/dy = ((a + 2b + c) − (g + 2h + i)) / (8·Δy)      (norte positivo)
declividade (°) = arctan( √( (dz/dx)² + (dz/dy)² ) )
declividade (%) = tan(declividade) × 100
aspecto = atan2(−dz/dx, −dz/dy) mod 360°            (azimute da DESCIDA, horário a partir do N)
```
Δx e Δy são em **metros e variam por linha** (`02_geodesia.md`). O centro da janela não entra no gradiente; por isso o código anula a declividade onde a própria elevação é `NaN`. Bordas viram `NaN`; o DEM é lido com margem de 3 pixels além do polígono.

## 2. Convenções
- **Aspecto = para onde a encosta *olha*** (direção de descida). Uma encosta que sobe para leste (aspecto 270°) "olha" para oeste.
- **Plano**: declividade < 1° → aspecto indefinido (`NaN`). Na propriedade de demonstração, 2,1% da área.
- **Rosa de aspecto**: porcentagem da área em cada oitante; a **direção média** usa média **circular** (a média aritmética de 350° e 10° daria 180°, absurdo) e o **comprimento resultante** R∈[0,1] diz quão concentrada é a orientação.

## 3. Classes de relevo (EMBRAPA/SiBCS)
| Classe | Declividade (%) | Demonstração (propriedade) |
|---|---|---|
| Plano | 0–3 | 5,7% |
| Suave ondulado | 3–8 | 24,8% |
| Ondulado | 8–20 | 60,6% |
| Forte ondulado | 20–45 | 8,8% |
| Montanhoso | 45–75 | 0,1% |
| Escarpado | > 75 | 0,0% |

São classes **descritivas** de relevo para levantamento de solos. **Não** são limiares de mecanização, de erosão nem de risco de tombamento, e o app não os usa como tal. Os rótulos são os da classificação de referência (Santos et al., SiBCS); o link de documentação oficial não foi verificado.

## 4. Verificação (notebook 01, executado)
- Planos inclinados exatos (1–100%, 8 aspectos): erro relativo máximo **0,002%**, erro de aspecto **≤ 0,005°**.
- Paraboloides: erro máximo **< 0,001°**.
- Isso valida a **aritmética**, não o DEM.

## 5. A resolução muda o número (dado real)
Agregando o DEM da região de amostra (média em blocos) e recalculando:

| Resolução | Decl. média (%) | P95 (%) | Área ≥ 20% |
|---|---|---|---|
| 30 m | 14,16 | 31,07 | 18,4% |
| 60 m | 12,13 | 25,79 | 11,3% |
| 90 m | 10,74 | 22,68 | 7,5% |
| 150 m | 8,69 | 18,70 | 4,2% |
| 300 m | 5,95 | 13,83 | 1,4% |

Moral: **a declividade de 30 m subestima a declividade local** (que varia dentro de 30 m) e não é comparável à de um DEM de outra resolução.

## 6. Ruído vertical (sensibilidade, não erro real)
Somando ruído independente por pixel: média 14,16% → 14,19 (σ=0,5 m) → 14,28 (1) → 14,62 (2) → **15,97% (σ=4 m)**. A classe "plano" (< 3%) quase não muda. O erro real do DEM é correlacionado no espaço e **desconhecido** aqui; o teste só dimensiona a sensibilidade.
