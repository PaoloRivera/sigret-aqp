#!/usr/bin/env python3
"""
analisis_significancia.py

Complemento de analisis_transferibilidad.py (responde a la revision del articulo):

  1. Significancia de las diferencias de ROC-AUC entre el ensamble y el mejor criterio
     univariado (Tabla 2 del articulo), con bootstrap por bloques espaciales: se remuestrean
     los 52 bloques H3 r6 con reemplazo, no las celdas, para respetar la autocorrelacion.
  2. Significancia de las diferencias entre el modelo propio y el de otro servicio en la
     matriz de transferencia (56 comparaciones; correccion de Holm).
  3. Umbral de viabilidad adaptado a cada servicio: en vez de fijar 1 500 habitantes para
     todos, se toma el percentil 10 de la poblacion alcanzable de las celdas donde el
     servicio existe (la demanda minima que el propio servicio revela). Se repite la
     evaluacion con ese umbral y con tres umbrales fijos (500, 1 500 y 3 000) como
     sensibilidad.

Uso (tras ejecutar analisis_transferibilidad.py, que guarda transfer_oof.parquet):
    python analisis_significancia.py
"""
import warnings

import numpy as np
import pandas as pd
from scipy.stats import rankdata

warnings.filterwarnings("ignore")
OUT = "resultados"
B = 2000
SEMILLA = 7
UMBRAL_FIJO = 1500
PERCENTIL_UMBRAL = 10

F = pd.read_parquet(f"{OUT}/features.parquet")
O = pd.read_parquet(f"{OUT}/transfer_oof.parquet")
assert (O["h3"].values == F["h3"].values).all()
nombres = [c.split("|", 1)[1] for c in O.columns if c.startswith("y|")]
Y = {n: O[f"y|{n}"].values for n in nombres}
POB = F["pob_k1"].values.astype(float)
BLOQ = O["bloque"].values
bloques = {b: np.where(BLOQ == b)[0] for b in np.unique(BLOQ)}
LLAVES = list(bloques)


def auc(y, s):
    n1 = int(y.sum())
    n0 = len(y) - n1
    if n1 < 3 or n0 < 3:
        return np.nan
    r = rankdata(s)
    return (r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def umbral_propio(n):
    return float(np.percentile(POB[Y[n] == 1], PERCENTIL_UMBRAL))


UMB = {n: umbral_propio(n) for n in nombres}
BASES = {"Densidad": F["dens_hab_km2"].values.astype(float), "Pob. alcanzable": POB}


def puntuaciones():
    S = {}
    for n in nombres:
        S[("ens", n)] = O[f"oof|{n}|completo"].values
        S[("estr", n)] = O[f"oof|{n}|estructural"].values
    return S


S = puntuaciones()


def mejor_base(n, mask):
    """Linea base univariada con mayor ROC-AUC en la muestra original (se fija antes de remuestrear)."""
    a = {k: auc(Y[n][mask], v[mask]) for k, v in BASES.items()}
    k = max(a, key=a.get)
    return k, a[k]


def percentil_ci(x):
    x = x[~np.isnan(x)]
    return np.percentile(x, 2.5), np.percentile(x, 97.5), 2 * min((x <= 0).mean(), (x >= 0).mean())


def holm(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    aj = np.empty_like(p)
    m = len(p)
    run = 0.0
    for i, j in enumerate(o):
        run = max(run, (m - i) * p[j])
        aj[j] = min(run, 1.0)
    return aj


def main():
    rng = np.random.default_rng(SEMILLA)
    sub = {
        "todas": np.ones(len(F), bool),
        "viables_1500": POB >= UMBRAL_FIJO,
    }
    for n in nombres:
        sub[f"propio|{n}"] = POB >= UMB[n]
    for t in (500, 3000):
        sub[f"fijo_{t}"] = POB >= t

    # ---- muestras bootstrap por bloques (los mismos indices para todas las comparaciones)
    reps = []
    for _ in range(B):
        sel = rng.choice(len(LLAVES), size=len(LLAVES), replace=True)
        reps.append(np.concatenate([bloques[LLAVES[i]] for i in sel]))

    def boot(f):
        return np.array([f(ix) for ix in reps])

    filas_t2, filas_mat, filas_viab = [], [], []

    # ---- 1. ensamble frente al mejor criterio univariado
    for n in nombres:
        for etiqueta, mask in (("todas", sub["todas"]), ("viables_1500", sub["viables_1500"]),
                               ("umbral_propio", sub[f"propio|{n}"])):
            kb, ab = mejor_base(n, mask)
            a_ens = auc(Y[n][mask], S[("ens", n)][mask])
            base = BASES[kb]

            def dif(ix, n=n, mask=mask, base=base):
                m = mask[ix]
                y = Y[n][ix][m]
                return auc(y, S[("ens", n)][ix][m]) - auc(y, base[ix][m])

            d = boot(dif)
            lo, hi, p = percentil_ci(d)
            filas_t2.append({"objetivo": n, "subconjunto": etiqueta, "celdas": int(mask.sum()),
                             "positivos": int(Y[n][mask].sum()), "roc_ensamble": a_ens,
                             "mejor_base": kb, "roc_base": ab, "diferencia": a_ens - ab,
                             "ic_inf": lo, "ic_sup": hi, "p": p})

    # ---- 2. matriz: modelo propio frente a modelo de otro servicio, por columna
    for etiqueta in ("todas", "viables_1500", "umbral_propio"):
        for b_ in nombres:
            mask = sub["todas"] if etiqueta == "todas" else (
                sub["viables_1500"] if etiqueta == "viables_1500" else sub[f"propio|{b_}"])
            propio = S[("estr", b_)]
            a_prop = auc(Y[b_][mask], propio[mask])
            for a_ in nombres:
                if a_ == b_:
                    continue
                otro = S[("estr", a_)]
                a_otro = auc(Y[b_][mask], otro[mask])

                def dif(ix, b_=b_, mask=mask, propio=propio, otro=otro):
                    m = mask[ix]
                    y = Y[b_][ix][m]
                    return auc(y, propio[ix][m]) - auc(y, otro[ix][m])

                d = boot(dif)
                lo, hi, p = percentil_ci(d)
                filas_mat.append({"subconjunto": etiqueta, "evaluado": b_, "entrenado_con": a_,
                                  "roc_propio": a_prop, "roc_otro": a_otro,
                                  "diferencia": a_prop - a_otro, "ic_inf": lo, "ic_sup": hi, "p": p})
        print(f"matriz {etiqueta}: listo")

    T2 = pd.DataFrame(filas_t2)
    M = pd.DataFrame(filas_mat)
    M["p_holm"] = np.nan
    for e in M["subconjunto"].unique():
        i = M["subconjunto"] == e
        M.loc[i, "p_holm"] = holm(M.loc[i, "p"].values)
    T2["p_holm"] = np.nan
    for e in T2["subconjunto"].unique():
        i = T2["subconjunto"] == e
        T2.loc[i, "p_holm"] = holm(T2.loc[i, "p"].values)
    T2.to_csv(f"{OUT}/signif_ensamble_vs_base.csv", index=False)
    M.to_csv(f"{OUT}/signif_matriz.csv", index=False)

    # ---- 3. viabilidad adaptada: umbrales y desempeno
    for n in nombres:
        fila = {"objetivo": n, "umbral_propio_hab": UMB[n]}
        for etiqueta, mask in (("propio", sub[f"propio|{n}"]), ("fijo_500", sub["fijo_500"]),
                               ("fijo_1500", sub["viables_1500"]), ("fijo_3000", sub["fijo_3000"])):
            kb, ab = mejor_base(n, mask)
            fila[f"celdas_{etiqueta}"] = int(mask.sum())
            fila[f"positivos_{etiqueta}"] = int(Y[n][mask].sum())
            fila[f"roc_ens_{etiqueta}"] = auc(Y[n][mask], S[("ens", n)][mask])
            fila[f"roc_base_{etiqueta}"] = ab
        filas_viab.append(fila)
    V = pd.DataFrame(filas_viab)
    V.to_csv(f"{OUT}/viabilidad_por_servicio.csv", index=False)

    # matriz de transferencia con la viabilidad propia de la columna
    Tp = pd.DataFrame(index=nombres, columns=nombres, dtype=float)
    for a_ in nombres:
        for b_ in nombres:
            mk = sub[f"propio|{b_}"]
            Tp.loc[a_, b_] = auc(Y[b_][mk], S[("estr", a_)][mk])
    Tp.to_csv(f"{OUT}/transfer_cruzada_umbral_propio.csv")

    pd.set_option("display.width", 250)
    print("\nUmbrales propios (P10 de pob_k1 en celdas con el servicio):")
    print(V[["objetivo", "umbral_propio_hab", "celdas_propio", "positivos_propio",
             "roc_ens_propio", "roc_base_propio", "roc_ens_fijo_500", "roc_ens_fijo_1500",
             "roc_ens_fijo_3000"]].round(3).to_string())
    print("\nEnsamble vs mejor base:")
    print(T2.round(3).to_string())
    for e in ("todas", "viables_1500", "umbral_propio"):
        x = M[M["subconjunto"] == e]
        n = len(x)
        mejor = ((x["ic_inf"] > 0)).sum()
        peor = ((x["ic_sup"] < 0)).sum()
        mejor_h = ((x["p_holm"] < 0.05) & (x["diferencia"] > 0)).sum()
        peor_h = ((x["p_holm"] < 0.05) & (x["diferencia"] < 0)).sum()
        print(f"matriz [{e}]: {n} comparaciones | propio mejor (IC95 sin 0): {mejor}, ajeno mejor: {peor} "
              f"| con Holm: propio mejor {mejor_h}, ajeno mejor {peor_h}")
    print("\nTransferencia con umbral propio (media fuera de la diagonal / diagonal / diag mejor):")
    v = Tp.values
    n = len(v)
    print(np.round(v[~np.eye(n, dtype=bool)].mean(), 3), np.round(np.diag(v).mean(), 3),
          sum(v[:, j].argmax() == j for j in range(n)))


if __name__ == "__main__":
    main()
