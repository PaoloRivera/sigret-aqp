# Eleccion del modelo: pruebas formales y estabilidad

Generado por analisis_eleccion_modelo.py (20 semillas, 200 reentrenamientos).

Control de reproduccion frente a pipeline.py: todas las predicciones coinciden.

## Regla de decision

- (a) menor DE del ROC-AUC entre pliegues: Random Forest
- (b) menor DE del lift del backtesting entre semillas: Ensamble
- (c) mayor parte del Top-50 del score conservada: Ensamble

**El ensamble ES el mas estable (gana o empata en 2 de 3 medidas).**

## Pruebas formales (p de Holm)

| Validacion | Metrica | Metodo | Comparacion | Diferencia | IC 95 % | p | p Holm |
|---|---|---|---|---|---|---|---|
| backtesting | ROC_AUC | DeLong | Ensamble - Regresion logistica | +0.0143 | -0.0175 a +0.0461 | 0.3776 | 1.0000 |
| backtesting | ROC_AUC | bootstrap pareado | Ensamble - Regresion logistica | +0.0143 | -0.0198 a +0.0451 | 0.4140 | 1.0000 |
| backtesting | PR_AUC | bootstrap pareado | Ensamble - Regresion logistica | +0.0218 | -0.0107 a +0.0718 | 0.1900 | 0.7900 |
| backtesting | Lift@10% | bootstrap pareado | Ensamble - Regresion logistica | +0.7723 | -1.2188 a +2.3433 | 0.6740 | 1.0000 |
| backtesting | ROC_AUC | DeLong | Ensamble - Random Forest | +0.0060 | -0.0135 a +0.0255 | 0.5452 | 1.0000 |
| backtesting | ROC_AUC | bootstrap pareado | Ensamble - Random Forest | +0.0060 | -0.0125 a +0.0249 | 0.5400 | 1.0000 |
| backtesting | PR_AUC | bootstrap pareado | Ensamble - Random Forest | +0.0178 | -0.0068 a +0.0650 | 0.1580 | 0.7900 |
| backtesting | Lift@10% | bootstrap pareado | Ensamble - Random Forest | +0.2574 | -0.7176 a +1.1960 | 0.8580 | 1.0000 |
| backtesting | ROC_AUC | DeLong | Ensamble - XGBoost | +0.0229 | -0.0018 a +0.0476 | 0.0694 | 0.3471 |
| backtesting | ROC_AUC | bootstrap pareado | Ensamble - XGBoost | +0.0229 | -0.0004 a +0.0495 | 0.0560 | 0.2800 |
| backtesting | PR_AUC | bootstrap pareado | Ensamble - XGBoost | +0.0090 | -0.0321 a +0.0537 | 0.6280 | 1.0000 |
| backtesting | Lift@10% | bootstrap pareado | Ensamble - XGBoost | +0.2574 | +0.0000 a +1.1156 | 0.5260 | 1.0000 |
| backtesting | ROC_AUC | DeLong | Ensamble - Baseline densidad | +0.0185 | -0.0289 a +0.0659 | 0.4439 | 1.0000 |
| backtesting | ROC_AUC | bootstrap pareado | Ensamble - Baseline densidad | +0.0185 | -0.0320 a +0.0656 | 0.4380 | 1.0000 |
| backtesting | PR_AUC | bootstrap pareado | Ensamble - Baseline densidad | +0.0271 | -0.0497 a +0.1022 | 0.4120 | 1.0000 |
| backtesting | Lift@10% | bootstrap pareado | Ensamble - Baseline densidad | +1.5447 | -0.6478 a +3.6734 | 0.1860 | 0.9720 |
| backtesting | ROC_AUC | DeLong | Ensamble - Baseline pob. k1 | +0.0408 | -0.0197 a +0.1013 | 0.1862 | 0.7450 |
| backtesting | ROC_AUC | bootstrap pareado | Ensamble - Baseline pob. k1 | +0.0408 | -0.0205 a +0.0996 | 0.1960 | 0.7840 |
| backtesting | PR_AUC | bootstrap pareado | Ensamble - Baseline pob. k1 | +0.0127 | -0.0804 a +0.0930 | 0.7280 | 1.0000 |
| backtesting | Lift@10% | bootstrap pareado | Ensamble - Baseline pob. k1 | +1.2872 | -0.7729 a +3.1707 | 0.2980 | 1.0000 |
| backtesting | ROC_AUC | DeLong | Ensamble - Baseline POIs k1 | +0.1030 | +0.0376 a +0.1683 | 0.0020 | 0.0121 |
| backtesting | ROC_AUC | bootstrap pareado | Ensamble - Baseline POIs k1 | +0.1030 | +0.0396 a +0.1723 | 0.0060 | 0.0360 |
| backtesting | PR_AUC | bootstrap pareado | Ensamble - Baseline POIs k1 | +0.0505 | -0.0059 a +0.1283 | 0.0700 | 0.4200 |
| backtesting | Lift@10% | bootstrap pareado | Ensamble - Baseline POIs k1 | +1.5447 | -0.4898 a +3.5437 | 0.1620 | 0.9720 |
| espacial | ROC_AUC | DeLong | Ensamble - Regresion logistica | +0.0535 | +0.0249 a +0.0822 | 0.0003 | 0.0015 |
| espacial | ROC_AUC | bootstrap pareado por bloques | Ensamble - Regresion logistica | +0.0535 | +0.0039 a +0.0874 | 0.0040 | 0.0240 |
| espacial | PR_AUC | bootstrap pareado por bloques | Ensamble - Regresion logistica | +0.0531 | +0.0078 a +0.0684 | 0.0280 | 0.0960 |
| espacial | Lift@10% | bootstrap pareado por bloques | Ensamble - Regresion logistica | +0.3285 | -0.4620 a +1.0891 | 0.3700 | 1.0000 |
| espacial | ROC_AUC | DeLong | Ensamble - Random Forest | -0.0144 | -0.0269 a -0.0020 | 0.0226 | 0.1132 |
| espacial | ROC_AUC | bootstrap pareado por bloques | Ensamble - Random Forest | -0.0144 | -0.0283 a +0.0040 | 0.6180 | 1.0000 |
| espacial | PR_AUC | bootstrap pareado por bloques | Ensamble - Random Forest | +0.0240 | +0.0004 a +0.0513 | 0.0460 | 0.0960 |
| espacial | Lift@10% | bootstrap pareado por bloques | Ensamble - Random Forest | -0.0821 | -0.7225 a +0.6352 | 1.0000 | 1.0000 |
| espacial | ROC_AUC | DeLong | Ensamble - XGBoost | -0.0043 | -0.0179 a +0.0094 | 0.5387 | 1.0000 |
| espacial | ROC_AUC | bootstrap pareado por bloques | Ensamble - XGBoost | -0.0043 | -0.0153 a +0.0103 | 0.7100 | 1.0000 |
| espacial | PR_AUC | bootstrap pareado por bloques | Ensamble - XGBoost | +0.0032 | -0.0202 a +0.0425 | 0.8000 | 0.8000 |
| espacial | Lift@10% | bootstrap pareado por bloques | Ensamble - XGBoost | +0.1642 | -0.4546 a +0.9766 | 0.8960 | 1.0000 |
| espacial | ROC_AUC | DeLong | Ensamble - Baseline densidad | -0.0048 | -0.0191 a +0.0095 | 0.5102 | 1.0000 |
| espacial | ROC_AUC | bootstrap pareado por bloques | Ensamble - Baseline densidad | -0.0048 | -0.0225 a +0.0239 | 0.8280 | 1.0000 |
| espacial | PR_AUC | bootstrap pareado por bloques | Ensamble - Baseline densidad | +0.0564 | +0.0050 a +0.0845 | 0.0240 | 0.0960 |
| espacial | Lift@10% | bootstrap pareado por bloques | Ensamble - Baseline densidad | +0.0000 | -0.6261 a +1.1390 | 0.9940 | 1.0000 |
| espacial | ROC_AUC | DeLong | Ensamble - Baseline pob. k1 | +0.0079 | -0.0089 a +0.0247 | 0.3573 | 1.0000 |
| espacial | ROC_AUC | bootstrap pareado por bloques | Ensamble - Baseline pob. k1 | +0.0079 | -0.0157 a +0.0428 | 0.5380 | 1.0000 |
| espacial | PR_AUC | bootstrap pareado por bloques | Ensamble - Baseline pob. k1 | +0.0573 | +0.0226 a +0.1321 | 0.0000 | 0.0000 |
| espacial | Lift@10% | bootstrap pareado por bloques | Ensamble - Baseline pob. k1 | +0.8212 | -0.3817 a +2.4285 | 0.2880 | 1.0000 |
| espacial | ROC_AUC | DeLong | Ensamble - Baseline POIs k1 | +0.0131 | -0.0077 a +0.0339 | 0.2171 | 0.8683 |
| espacial | ROC_AUC | bootstrap pareado por bloques | Ensamble - Baseline POIs k1 | +0.0131 | -0.0006 a +0.0428 | 0.0640 | 0.3200 |
| espacial | PR_AUC | bootstrap pareado por bloques | Ensamble - Baseline POIs k1 | +0.0880 | +0.0417 a +0.1173 | 0.0000 | 0.0000 |
| espacial | Lift@10% | bootstrap pareado por bloques | Ensamble - Baseline POIs k1 | +0.9033 | +0.1019 a +2.0856 | 0.0440 | 0.2640 |

## Estabilidad entre pliegues

| Metrica | Modelo | Media | DE | Minimo | Puesto medio | Peor puesto | Veces ultimo |
|---|---|---|---|---|---|---|---|
| ROC_AUC | Regresion logistica | 0.9001 | 0.0864 | 0.7471 | 3.2 | 4 | 3 |
| ROC_AUC | Random Forest | 0.9278 | 0.0419 | 0.8578 | 1.8 | 3 | 0 |
| ROC_AUC | XGBoost | 0.9208 | 0.0460 | 0.8436 | 2.8 | 4 | 2 |
| ROC_AUC | Ensamble | 0.9257 | 0.0507 | 0.8383 | 2.2 | 3 | 0 |
| PR_AUC | Regresion logistica | 0.2369 | 0.0547 | 0.1535 | 3.0 | 4 | 2 |
| PR_AUC | Random Forest | 0.2268 | 0.0459 | 0.1920 | 2.6 | 4 | 2 |
| PR_AUC | XGBoost | 0.2508 | 0.0699 | 0.1301 | 2.4 | 4 | 1 |
| PR_AUC | Ensamble | 0.2598 | 0.0496 | 0.1842 | 2.0 | 3 | 0 |

Friedman: ROC-AUC p = 0.323; PR-AUC p = 0.668

## Estabilidad entre semillas (DE de 20 semillas)

| Metrica | Regresion logistica | Random Forest | XGBoost | Ensamble |
|---|---|---|---|---|
| bt_Lift@10% | 3.6043 ± 0.0000 | 4.3380 ± 0.3156 | 4.0291 ± 0.3571 | 4.4668 ± 0.2677 |
| bt_PR_AUC | 0.0888 ± 0.0000 | 0.0978 ± 0.0027 | 0.1010 ± 0.0065 | 0.1104 ± 0.0036 |
| bt_ROC_AUC | 0.8166 ± 0.0000 | 0.8301 ± 0.0025 | 0.8118 ± 0.0058 | 0.8338 ± 0.0023 |
| bt_aciertos@20 | 1.0000 ± 0.0000 | 1.9500 ± 0.3940 | 2.9000 ± 0.7182 | 2.9500 ± 0.2236 |
| cv_PR_AUC | 0.2083 ± 0.0000 | 0.2414 ± 0.0024 | 0.2577 ± 0.0082 | 0.2665 ± 0.0031 |
| cv_ROC_AUC | 0.8636 ± 0.0000 | 0.9317 ± 0.0006 | 0.9232 ± 0.0011 | 0.9174 ± 0.0004 |
| cv_de_pliegues | 0.0864 ± 0.0000 | 0.0410 ± 0.0008 | 0.0451 ± 0.0014 | 0.0504 ± 0.0005 |
| top50_modelo_conserva | 1.0000 ± 0.0000 | 0.9080 ± 0.0136 | 0.8400 ± 0.0275 | 0.9070 ± 0.0262 |
| top50_score_conserva | 1.0000 ± 0.0000 | 0.9560 ± 0.0167 | 0.9060 ± 0.0206 | 0.9330 ± 0.0218 |

## Top-50 en 200 reentrenamientos

| Top-50 de | Modelo | Conserva (media) | Conserva (p5) | Nucleo >= 90 % | Spearman medio |
|---|---|---|---|---|---|
| modelo | Regresion logistica | 65.6 % | 54 % | 7 | 0.944 |
| score | Regresion logistica | 89.0 % | 82 % | 32 | 0.944 |
| modelo | Random Forest | 55.2 % | 44 % | 0 | 0.954 |
| score | Random Forest | 80.4 % | 76 % | 22 | 0.954 |
| modelo | XGBoost | 49.1 % | 38 % | 0 | 0.936 |
| score | XGBoost | 76.2 % | 70 % | 22 | 0.936 |
| modelo | Ensamble | 59.0 % | 46 % | 2 | 0.960 |
| score | Ensamble | 81.8 % | 76 % | 27 | 0.960 |
