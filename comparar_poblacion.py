#!/usr/bin/env python3
"""
comparar_poblacion.py

Compara el modelo principal (poblacion actualizada al Censo 2025, carpeta
resultados/) con la corrida de comparacion que usa la poblacion del Censo 2017
sin actualizar (carpeta resultados/base_censo2017/): metricas de validacion,
backtesting sobre los candidatos comunes, estabilidad del ranking y
composicion territorial del Top-50.

Uso (desde la raiz del proyecto):
    python pipeline.py
    python pipeline.py --poblacion 2017 --salida resultados/base_censo2017
    python comparar_poblacion.py
"""
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.metrics import average_precision_score, roc_auc_score

ACT, BASE = "resultados", "resultados/base_censo2017"
NOMBRES = {ACT: "Poblacion actualizada (Censo 2025)", BASE: "Poblacion Censo 2017"}


def lift10(t, s):
    o = np.argsort(-s)
    n10 = max(int(0.10 * len(s)), 1)
    return t[o[:n10]].mean() / t.mean()


def metricas(t, s):
    o = np.argsort(-s)
    return {"ROC_AUC": roc_auc_score(t, s), "PR_AUC": average_precision_score(t, s),
            "Lift@10%": lift10(t, s), "aciertos@20": int(t[o[:20]].sum())}


filas = []
R, P, B = {}, {}, {}
for d in (BASE, ACT):
    R[d] = pd.read_parquet(f"{d}/resultado_final.parquet").set_index("h3")
    P[d] = pd.read_parquet(f"{d}/predicciones_backtesting.parquet").set_index("h3")
    bt = pd.read_csv(f"{d}/resultados_backtesting.csv").set_index("modelo")
    cv = pd.read_csv(f"{d}/resultados_cv.csv").set_index("modelo")
    e = bt.loc["Ensamble (rank avg)"]
    filas.append({
        "corrida": NOMBRES[d],
        "poblacion_malla": R[d]["pob_celda"].sum(),
        "celdas_viables": int(R[d]["viable"].sum()),
        "candidatos_backtesting": len(P[d]),
        "aperturas": int(P[d]["abrio"].sum()),
        "CV_ROC_AUC_ENS": cv.loc["ENS", "ROC_AUC"], "CV_PR_AUC_ENS": cv.loc["ENS", "PR_AUC"],
        "CV_ROC_AUC_RF": cv.loc["RF", "ROC_AUC"],
        "BT_ROC_AUC_ENS": e["ROC_AUC"], "BT_PR_AUC_ENS": e["PR_AUC"],
        "BT_Lift10_ENS": e["Lift@10%"], "BT_aciertos20_ENS": int(e["acierto@20"]),
        "BT_ROC_AUC_mejor_base": bt.loc[[i for i in bt.index if i.startswith("Baseline")], "ROC_AUC"].max(),
    })
T = pd.DataFrame(filas).set_index("corrida").T
print("=== Modelo principal frente a la poblacion 2017 ===")
print(T.to_string())
T.to_csv(f"{ACT}/comparacion_poblacion.csv", encoding="utf-8-sig")

# Backtesting sobre los candidatos comunes a ambas corridas (misma base de comparacion)
com = P[BASE].index.intersection(P[ACT].index)
filas = []
for d in (BASE, ACT):
    t = P[d].loc[com, "abrio"].values
    for col, nom in (("ENS", "Ensamble"), ("dens_hab_km2", "Baseline densidad"), ("pob_k1", "Baseline pob. k1")):
        filas.append({"corrida": NOMBRES[d], "modelo": nom, "candidatos_comunes": len(com),
                      "aperturas": int(t.sum()), **metricas(t, P[d].loc[com, col].values)})
C = pd.DataFrame(filas)
print(f"\n=== Backtesting sobre los {len(com)} candidatos comunes ===")
print(C.round(3).to_string(index=False))
C.to_csv(f"{ACT}/comparacion_poblacion_candidatos_comunes.csv", index=False, encoding="utf-8-sig")

# Estabilidad del ranking
s0, s1 = R[BASE]["SCORE"], R[ACT]["SCORE"].reindex(R[BASE].index)
v0, v1 = R[BASE]["viable"], R[ACT]["viable"].reindex(R[BASE].index)
ambos = v0 & v1
rho = stats.spearmanr(s0[ambos], s1[ambos]).statistic
top = {k: len(set(s0[v0].nlargest(k).index) & set(s1[v1].nlargest(k).index)) for k in (10, 20, 50)}
E = pd.DataFrame([{"celdas_viables_ambas": int(ambos.sum()), "spearman_score": rho,
                   **{f"top{k}_compartido": v for k, v in top.items()},
                   **{f"top{k}_compartido_pct": v / k for k, v in top.items()}}])
print(f"\n=== Ranking: Spearman {rho:.3f} | " + " | ".join(f"Top-{k} {v}/{k}" for k, v in top.items()))
E.to_csv(f"{ACT}/comparacion_poblacion_ranking.csv", index=False, encoding="utf-8-sig")

D = pd.DataFrame({NOMBRES[d]: R[d][R[d]["viable"]].nlargest(50, "SCORE")["DIST"].value_counts()
                  for d in (BASE, ACT)}).fillna(0).astype(int)
D = D.sort_values(NOMBRES[ACT], ascending=False)
print("\n=== Top-50 por distrito ===")
print(D.to_string())
D.to_csv(f"{ACT}/comparacion_poblacion_top50_distritos.csv", encoding="utf-8-sig")
