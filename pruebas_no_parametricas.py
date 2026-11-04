#!/usr/bin/env python3
"""
pruebas_no_parametricas.py — Shapiro-Wilk, Wilcoxon de una muestra (unilateral),
IC 95 % bootstrap y Kruskal-Wallis para SUS y TAM (n = 15).
Entrada: data/encuestas/respuestas.csv con columnas
    participante, perfil, SUS, u1..u6, f1..f6, i1..i3
(SUS = puntaje 0-100 ya calculado; u = utilidad, f = facilidad, i = intencion; Likert 1-5)
Uso:  python pruebas_no_parametricas.py
"""
import numpy as np, pandas as pd
from scipy import stats
D = pd.read_csv("data/encuestas/respuestas.csv")
D["Utilidad"] = D[[f"u{i}" for i in range(1, 7)]].mean(axis=1)
D["Facilidad"] = D[[f"f{i}" for i in range(1, 7)]].mean(axis=1)
D["Intencion"] = D[[f"i{i}" for i in range(1, 4)]].mean(axis=1)
D["TAM_global"] = D[[f"u{i}" for i in range(1, 7)] + [f"f{i}" for i in range(1, 7)]
                    + [f"i{i}" for i in range(1, 4)]].mean(axis=1)
rng = np.random.default_rng(42)

def prueba(x, mu0):
    x = np.asarray(x, float)
    sw = stats.shapiro(x)
    d = x - mu0; dd = d[d != 0]
    r = stats.rankdata(np.abs(dd)); wp, wm = r[dd > 0].sum(), r[dd < 0].sum()
    p = stats.wilcoxon(d, alternative="greater", zero_method="wilcox").pvalue
    bm = [rng.choice(x, len(x)).mean() for _ in range(10000)]
    lo, hi = np.percentile(bm, [2.5, 97.5])
    t = stats.ttest_1samp(x, mu0)
    return {"media": x.mean(), "mediana": np.median(x), "IC95_boot_inf": lo, "IC95_boot_sup": hi,
            "Shapiro_W": sw.statistic, "Shapiro_p": sw.pvalue, "ref": mu0, "n_efectivo": len(dd),
            "W_mas": wp, "W_menos": wm, "Wilcoxon_p_unilateral": p, "r_rangos": (wp - wm) / (wp + wm),
            "t_comparativo": t.statistic, "t_p_bilateral": t.pvalue}

filas = [dict(variable="SUS", **prueba(D["SUS"], 68)), dict(variable="SUS", **prueba(D["SUS"], 75))]
for v in ("Utilidad", "Facilidad", "Intencion", "TAM_global"):
    filas.append(dict(variable=v, **prueba(D[v], 4.0)))
T = pd.DataFrame(filas)
pd.set_option("display.width", 250)
print(T.round(4).to_string(index=False))
T.to_csv("resultados/pruebas_no_parametricas.csv", index=False)

print("\n=== Kruskal-Wallis por perfil ===")
for v in ("SUS", "TAM_global"):
    g = [grp[v].values for _, grp in D.groupby("perfil")]
    k = stats.kruskal(*g)
    print(f"{v}: H = {k.statistic:.3f}; gl = {len(g) - 1}; p = {k.pvalue:.3f}")
