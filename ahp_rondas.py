#!/usr/bin/env python3
"""
ahp_rondas.py — Consistencia por ronda y sensibilidad de los pesos AHP a los
expertos que requirieron segunda ronda.
Entrada: data/panel/matrices_ahp_rondas.csv con columnas
    experto, ronda, criterio_a, criterio_b, valor
(una fila por comparacion; ronda = 1 o 2; valor > 1 si criterio_a pesa mas)
Uso (despues de pipeline.py):  python ahp_rondas.py
"""
import numpy as np, pandas as pd
from scipy import stats
CLAVES = ["C1", "C2", "C3", "C4"]; RI = 0.90
# Radio declarado por experto (Tabla 14 / Anexo E)
RADIOS = {"E01": 800, "E02": 600, "E03": 1000, "E04": 800, "E05": 700,
          "E06": 800, "E07": 500, "E08": 600, "E09": 1000, "E10": 700}

def pesos_cr(sub):
    idx = {c: i for i, c in enumerate(CLAVES)}; A = np.ones((4, 4))
    for r in sub.itertuples():
        i, j = idx[r.criterio_a], idx[r.criterio_b]; A[i, j] = float(r.valor); A[j, i] = 1 / float(r.valor)
    val, vec = np.linalg.eig(A); k = int(np.argmax(val.real))
    w = np.abs(vec[:, k].real); w /= w.sum(); lmax = val.real[k]
    return w, lmax, (lmax - 4) / 3 / RI

D = pd.read_csv("data/panel/matrices_ahp_rondas.csv")
filas, finales = [], {}
for (e, rd), sub in D.groupby(["experto", "ronda"]):
    w, l, cr = pesos_cr(sub)
    filas.append({"experto": e, "ronda": rd, "lambda_max": l, "CR": cr, **dict(zip(CLAVES, w))})
C = pd.DataFrame(filas)
print("=== Consistencia por experto y ronda ===")
print(C.round(3).to_string(index=False))
ult = C.sort_values("ronda").groupby("experto").tail(1).set_index("experto")
ult = ult[ult["CR"] < 0.10]                      # solo matrices finales consistentes
dos = sorted(C.loc[C["ronda"] == 2, "experto"].unique())

def agregar(expertos):
    Wm = ult.loc[expertos, CLAVES].values
    g = np.exp(np.log(Wm).mean(0)); g /= g.sum()
    return g, g[1] / (g[0] + g[1] + g[2]), g[3], float(np.median([RADIOS[e] for e in expertos]))

R = pd.read_parquet("resultados/resultado_final.parquet")
def score(w, pen, rad):
    r = np.clip(1 - R["d_mass_2026"] / rad, 0, 1)
    s = (w * R["p_potencial"] + (1 - w) * R["dem_res_n"]) * (1 - pen * r)
    return s.where(R["viable"], 0.0)

todos = sorted(ult.index); sin2 = [e for e in todos if e not in dos]
g0, w0, p0, r0 = agregar(todos); s0 = score(w0, p0, r0)
print(f"\nExpertos con segunda ronda: {dos}")
for nombre, ex in (("Panel (matrices finales validas)", todos), ("Sin segunda ronda", sin2)):
    g, w, p, rad = agregar(ex)
    print(f"\n{nombre} (n = {len(ex)}): C1 {g[0]:.3f} | C2 {g[1]:.3f} | C3 {g[2]:.3f} | C4 {g[3]:.3f}"
          f" -> w = {w:.3f}; pen = {p:.3f}; radio mediano = {rad:.0f} m")
    for rr in sorted({r0, rad}):
        s1 = score(w, p, rr); v = R["viable"]
        rho = stats.spearmanr(s0[v], s1[v]).statistic
        tk = "  ".join(f"Top-{k} {len(set(s0[v].nlargest(k).index) & set(s1[v].nlargest(k).index)) / k:.0%}"
                       for k in (10, 20, 50))
        print(f"   radio {rr:.0f} m: Spearman {rho:.3f} | {tk}")
