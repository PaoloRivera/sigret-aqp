#!/usr/bin/env python3
"""
analisis_eleccion_modelo.py

Por que el sistema usa el ensamble y no Random Forest, XGBoost o la regresion
logistica (observacion 4 del jurado). Compara el ensamble con cada modelo y cada
baseline con pruebas formales y mide la estabilidad de los cuatro modelos.

1. Pruebas formales del ensamble frente a cada modelo y cada baseline
   - ROC-AUC: prueba de DeLong para curvas ROC correlacionadas (DeLong et al.,
     1988; algoritmo de Sun y Xu, 2014).
   - PR-AUC y lift en el decil superior: bootstrap pareado (los dos modelos que se
     comparan se evaluan en los mismos remuestreos).
       * Backtesting: se remuestrean las 1 486 celdas candidatas con los mismos
         1 000 remuestreos de analisis_complementarios.py (semilla 42), de modo que
         los IC frente a los baselines coinciden con los de la tabla de contrastacion.
       * Validacion espacial: se remuestrean los 52 bloques H3 r6, como en
         ic_validacion_espacial.py, porque las celdas vecinas no son independientes.
         Por la misma razon, ahi el ROC-AUC se prueba con DeLong (que supone celdas
         independientes) y tambien con el bootstrap por bloques.
   - p de Holm dentro de cada validacion, metrica y metodo (seis comparaciones).
2. Estabilidad
   a. Entre los cinco pliegues de la validacion espacial (analisis_cv_pliegues.csv):
      media, desviacion estandar, peor pliegue, puesto en cada pliegue, distancia al
      mejor modelo de cada pliegue y prueba de Friedman.
   b. Entre semillas: se repite el entrenamiento de pipeline.py con 20 semillas
      (1 a 20). La semilla cambia el azar de Random Forest (muestra y variables de
      cada arbol) y de XGBoost (submuestreo de filas y columnas); la regresion
      logistica no usa azar y da lo mismo con cualquier semilla.
   c. Top-50: se reentrenan los modelos finales 200 veces con las celdas
      remuestreadas con reemplazo (por separado las celdas con y sin tienda, para
      conservar 122 positivas) y se mide que parte del Top-50 original se conserva,
      tanto del Top-50 de cada modelo como del Top-50 del score de la aplicacion.

Regla de decision, fijada antes de correr el analisis. Se comparan en estabilidad
los modelos que cumplen la condicion de la hipotesis en la validacion espacial
(limite inferior del IC 95 % del ROC-AUC por encima de 0,85 en
ic_validacion_espacial.csv): Random Forest, XGBoost y el ensamble. El ensamble es
"el mas estable" si gana en al menos dos de estas tres medidas:
   (a) menor desviacion estandar del ROC-AUC entre los cinco pliegues;
   (b) menor desviacion estandar del lift en el decil superior del backtesting
       entre las 20 semillas (el lift es el criterio de contrastacion);
   (c) mayor parte media del Top-50 del score conservada en los 200 reentrenamientos.

Uso (desde la raiz del proyecto, despues de pipeline.py y analisis_complementarios.py):
    python analisis_eleccion_modelo.py                 # completo (unos 7 min en el equipo del Anexo H.1)
    python analisis_eleccion_modelo.py --rapido        # prueba: 2 semillas, 5 remuestreos
"""
import argparse
import time
import warnings

import h3
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.stats import friedmanchisquare, norm, rankdata, spearmanr
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
ap = argparse.ArgumentParser()
ap.add_argument("--semillas", type=int, default=20)
ap.add_argument("--remuestreos", type=int, default=200)
ap.add_argument("--rapido", action="store_true", help="2 semillas y 5 remuestreos")
args = ap.parse_args()
if args.rapido:
    args.semillas, args.remuestreos = 2, 5

OUT = "resultados"
B_PRUEBAS = 1000
SEMILLA_BASE = 42
SEMILLA_REMUESTREO = 2026
W_POT, PEN_MASS = 0.344, 0.261
MOD = ("LR", "RF", "XGB", "ENS")
NOM = {"LR": "Regresion logistica", "RF": "Random Forest", "XGB": "XGBoost",
       "ENS": "Ensamble", "dens": "Baseline densidad", "pob": "Baseline pob. k1",
       "poi": "Baseline POIs k1"}
CANDIDATOS = ("RF", "XGB", "ENS")
T0 = time.time()


def log(msg):
    print(f"[{time.time() - T0:6.0f} s] {msg}", flush=True)


# ─────────────────────────── datos (igual que pipeline.py) ───────────────────────────
F = pd.read_parquet(f"{OUT}/features.parquet")
F24 = pd.read_parquet(f"{OUT}/features_2024.parquet").set_index("h3").loc[F["h3"]]
PRED = [c for c in F.columns if c not in ("h3", "DIST", "es_nucleo", "bloque")
        and not c.startswith(("mass_", "d_mass_"))]
X = F[PRED].replace([np.inf, -np.inf], 0).fillna(0).values
X24 = F24[PRED].replace([np.inf, -np.inf], 0).fillna(0).values
y = F["mass_2026"].values
y24 = F["mass_2024"].values
abrio = ((F["mass_2026"] == 1) & (F["mass_2024"] == 0)).astype(int).values
cand = (F24["pob_k1"].values >= 1500) & (y24 == 0)
t = abrio[cand]
bloq = np.array([h3.cell_to_parent(c, 6) for c in F["h3"]])
PLIEGUES = list(GroupKFold(n_splits=5).split(X, y, groups=bloq))

R = pd.read_parquet(f"{OUT}/resultado_final.parquet",
                    columns=["h3", "viable", "dem_res_n", "riesgo_mass", "p_potencial", "SCORE"])
assert (R["h3"].values == F["h3"].values).all()
VIA = R["viable"].values.astype(bool)
IVIA = np.where(VIA)[0]
log(f"{len(F):,} celdas, {y.sum()} con tienda en 2026; backtesting: {cand.sum():,} "
    f"candidatos, {t.sum()} aperturas; {VIA.sum():,} celdas viables")


# ─────────────────────────── utilidades ───────────────────────────
def rango(p):
    return pd.Series(p).rank(pct=True).values


def ensamble(p):
    return np.mean([rango(p[k]) for k in ("LR", "RF", "XGB")], axis=0)


def metricas(tt, s):
    """Las mismas metricas y el mismo orden de desempate que pipeline.py."""
    o = np.argsort(-s)
    n10 = max(int(0.10 * len(s)), 1)
    return {"ROC_AUC": roc_auc_score(tt, s), "PR_AUC": average_precision_score(tt, s),
            "Lift@10%": tt[o[:n10]].mean() / tt.mean(), "aciertos@20": int(tt[o[:20]].sum())}


def ajustar(Xtr, ytr, semilla, pw=None, lr=True):
    pw = (ytr == 0).sum() / max((ytr == 1).sum(), 1) if pw is None else pw
    M = {}
    if lr:
        sc = StandardScaler().fit(Xtr)
        M["LR"] = (sc, LogisticRegression(max_iter=5000, class_weight="balanced", C=0.5)
                   .fit(sc.transform(Xtr), ytr))
    M["RF"] = (None, RandomForestClassifier(
        n_estimators=800, min_samples_leaf=5, max_features="sqrt",
        class_weight="balanced_subsample", n_jobs=-1, random_state=semilla).fit(Xtr, ytr))
    M["XGB"] = (None, xgb.XGBClassifier(
        n_estimators=400, max_depth=3, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.7, reg_lambda=3.0, min_child_weight=5,
        scale_pos_weight=pw, eval_metric="aucpr", random_state=semilla).fit(Xtr, ytr))
    return M


def predecir(M, Xte):
    return {k: m.predict_proba(Xte if sc is None else sc.transform(Xte))[:, 1]
            for k, (sc, m) in M.items()}


def score(pp):
    """Score de pipeline.score() con pp como perfil aprendido (p_potencial)."""
    s = (W_POT * pp + (1 - W_POT) * R["dem_res_n"].values) * (1 - PEN_MASS * R["riesgo_mass"].values)
    s[~VIA] = 0.0
    return s


def top50(v):
    """Indices de las 50 celdas viables con mayor v (empates por orden, como nlargest)."""
    return IVIA[np.argsort(-v[IVIA], kind="stable")[:50]]


def perfiles(p):
    """Perfil aprendido de cada modelo: rango percentil de su probabilidad; el del
    ensamble es el promedio de los tres rangos (p_potencial de pipeline.py)."""
    pp = {k: rango(p[k]) for k in ("LR", "RF", "XGB")}
    pp["ENS"] = ensamble(p)
    return pp


def delong(yt, s1, s2):
    """Prueba de DeLong para dos ROC-AUC correlacionados (Sun y Xu, 2014)."""
    pos, neg = yt == 1, yt == 0
    m, n = pos.sum(), neg.sum()
    v10, v01, auc = [], [], []
    for s in (s1, s2):
        tx, ty = rankdata(s[pos]), rankdata(s[neg])
        tz = rankdata(np.concatenate([s[pos], s[neg]]))
        auc.append((tz[:m].sum() - m * (m + 1) / 2) / (m * n))
        v10.append((tz[:m] - tx) / n)
        v01.append(1 - (tz[m:] - ty) / m)
    S = np.cov(np.vstack(v10)) / m + np.cov(np.vstack(v01)) / n
    d = auc[0] - auc[1]
    se = np.sqrt(max(S[0, 0] + S[1, 1] - 2 * S[0, 1], 1e-300))
    return d, d - 1.96 * se, d + 1.96 * se, 2 * norm.sf(abs(d / se))


def p_bootstrap(dif):
    """p bilateral del bootstrap pareado: dos veces la cola que cruza el cero."""
    dif = np.asarray(dif)
    return min(1.0, 2 * min((dif <= 0).mean(), (dif >= 0).mean()))


def holm(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    adj = np.maximum.accumulate((len(p) - np.arange(len(p))) * p[o])
    out = np.empty_like(p)
    out[o] = np.minimum(adj, 1)
    return out


def coincide(a, b, nombre):
    dif = np.max(np.abs(np.asarray(a, float) - np.asarray(b, float)))
    estado = "coincide" if dif < 1e-9 else "NO COINCIDE (otro sistema o version de librerias)"
    log(f"    control {nombre}: diferencia maxima {dif:.1e} -> {estado}")
    return dif < 1e-9


# ═══════════════════ 1. Pruebas formales ═══════════════════
log("[1] Pruebas formales del ensamble frente a cada modelo y cada baseline")
filas = []

# 1a. Backtesting temporal (predicciones oficiales de pipeline.py)
BT = pd.read_parquet(f"{OUT}/predicciones_backtesting.parquet")
assert (BT["h3"].values == F["h3"].values[cand]).all() and (BT["abrio"].values == t).all()
SB = {"ENS": BT["ENS"].values, "LR": BT["LR"].values, "RF": BT["RF"].values,
      "XGB": BT["XGB"].values, "dens": BT["dens_hab_km2"].values,
      "pob": BT["pob_k1"].values, "poi": BT["n_poi_k1"].values}
rng = np.random.default_rng(42)          # mismos remuestreos que analisis_complementarios.py
reps, n = [], len(t)
while len(reps) < B_PRUEBAS:
    i = rng.integers(0, n, n)
    if t[i].sum() == 0:
        continue
    reps.append({k: metricas(t[i], v[i]) for k, v in SB.items()})
OBS = {k: metricas(t, v) for k, v in SB.items()}
for k in ("LR", "RF", "XGB", "dens", "pob", "poi"):
    d, lo, hi, p = delong(t, SB["ENS"], SB[k])
    filas.append({"validacion": "backtesting", "metrica": "ROC_AUC", "metodo": "DeLong",
                  "comparacion": k, "ensamble": OBS["ENS"]["ROC_AUC"], "otro": OBS[k]["ROC_AUC"],
                  "diferencia": d, "IC95_inf": lo, "IC95_sup": hi, "p": p})
    for met in ("ROC_AUC", "PR_AUC", "Lift@10%"):
        dif = np.array([r["ENS"][met] - r[k][met] for r in reps])
        filas.append({"validacion": "backtesting", "metrica": met, "metodo": "bootstrap pareado",
                      "comparacion": k, "ensamble": OBS["ENS"][met], "otro": OBS[k][met],
                      "diferencia": OBS["ENS"][met] - OBS[k][met],
                      "IC95_inf": np.percentile(dif, 2.5), "IC95_sup": np.percentile(dif, 97.5),
                      "p": p_bootstrap(dif)})
# Control: los IC frente a los baselines deben ser los de analisis_complementarios.py
try:
    DIF = pd.read_csv(f"{OUT}/analisis_diferencias_backtesting.csv")
    eq = {"Ensamble - Baseline densidad": "dens", "Ensamble - Baseline pob. k1": "pob"}
    a, b = [], []
    for _, r in DIF.iterrows():
        f = next(x for x in filas if x["metodo"] == "bootstrap pareado" and x["metrica"] == r["metrica"]
                 and x["comparacion"] == eq[r["comparacion"]])
        a += [f["IC95_inf"], f["IC95_sup"]]
        b += [r["IC95_inf"], r["IC95_sup"]]
    coincide(a, b, "IC del backtesting frente a analisis_diferencias_backtesting.csv")
except FileNotFoundError:
    log("    (sin analisis_diferencias_backtesting.csv: corre antes analisis_complementarios.py)")

# 1b. Validacion cruzada espacial (predicciones fuera de pliegue de pipeline.py)
CV = pd.read_parquet(f"{OUT}/predicciones_cv.parquet")
assert (CV["h3"].values == F["h3"].values).all() and (CV["y"].values == y).all()
SC = {"ENS": CV["ENS"].values, "LR": CV["LR"].values, "RF": CV["RF"].values,
      "XGB": CV["XGB"].values, "dens": F["dens_hab_km2"].values,
      "pob": F["pob_k1"].values, "poi": F["n_poi_k1"].values}
rng = np.random.default_rng(42)          # mismo esquema que ic_validacion_espacial.py
ub = np.unique(bloq)
idx = {b: np.where(bloq == b)[0] for b in ub}
repc = []
for _ in range(B_PRUEBAS):
    s = np.concatenate([idx[b] for b in rng.choice(ub, len(ub))])
    if y[s].min() == y[s].max():
        continue
    repc.append({k: metricas(y[s], v[s]) for k, v in SC.items()})
OBSC = {k: metricas(y, v) for k, v in SC.items()}
for k in ("LR", "RF", "XGB", "dens", "pob", "poi"):
    d, lo, hi, p = delong(y, SC["ENS"], SC[k])
    filas.append({"validacion": "espacial", "metrica": "ROC_AUC", "metodo": "DeLong",
                  "comparacion": k, "ensamble": OBSC["ENS"]["ROC_AUC"], "otro": OBSC[k]["ROC_AUC"],
                  "diferencia": d, "IC95_inf": lo, "IC95_sup": hi, "p": p})
    for met in ("ROC_AUC", "PR_AUC", "Lift@10%"):
        dif = np.array([r["ENS"][met] - r[k][met] for r in repc])
        filas.append({"validacion": "espacial", "metrica": met,
                      "metodo": "bootstrap pareado por bloques", "comparacion": k,
                      "ensamble": OBSC["ENS"][met], "otro": OBSC[k][met],
                      "diferencia": OBSC["ENS"][met] - OBSC[k][met],
                      "IC95_inf": np.percentile(dif, 2.5), "IC95_sup": np.percentile(dif, 97.5),
                      "p": p_bootstrap(dif)})
PR = pd.DataFrame(filas)
PR["p_holm"] = PR.groupby(["validacion", "metrica", "metodo"])["p"].transform(holm)
PR["significativa"] = PR["p_holm"] < 0.05
PR["comparacion"] = "Ensamble - " + PR["comparacion"].map(NOM)
PR.to_csv(f"{OUT}/eleccion_pruebas.csv", index=False)
log(f"    remuestreos validos: backtesting {len(reps)}, espacial {len(repc)} (de {len(ub)} bloques)")
with pd.option_context("display.width", 200):
    print(PR.drop(columns=["significativa"]).round(4).to_string(index=False))

# ═══════════════════ 2a. Estabilidad entre pliegues ═══════════════════
log("[2a] Estabilidad entre los cinco pliegues de la validacion espacial")
PL = pd.read_csv(f"{OUT}/analisis_cv_pliegues.csv")
filas = []
for met in ("ROC_AUC", "PR_AUC"):
    W = PL.pivot(index="pliegue", columns="modelo", values=met)[list(MOD)]
    rk = W.rank(axis=1, ascending=False)
    gap = W.max(axis=1).values[:, None] - W.values
    fr = friedmanchisquare(*[W[k].values for k in MOD])
    for j, k in enumerate(MOD):
        filas.append({"metrica": met, "modelo": k, "media": W[k].mean(), "de": W[k].std(),
                      "cv_pct": 100 * W[k].std() / W[k].mean(), "minimo": W[k].min(),
                      "maximo": W[k].max(), "puesto_medio": rk[k].mean(),
                      "mejor_puesto": int(rk[k].min()), "peor_puesto": int(rk[k].max()),
                      "veces_ultimo": int((rk[k] == len(MOD)).sum()),
                      "distancia_media_al_mejor": gap[:, j].mean(),
                      "distancia_max_al_mejor": gap[:, j].max(),
                      "friedman_chi2": fr.statistic, "friedman_p": fr.pvalue})
EP = pd.DataFrame(filas)
EP.to_csv(f"{OUT}/eleccion_pliegues.csv", index=False)
print(EP.round(4).to_string(index=False))


# ═══════════════════ 2b. Estabilidad entre semillas ═══════════════════
def corrida(semilla, lr_cache):
    """Reproduce pipeline.modelos() con otra semilla. La regresion logistica no usa
    azar: se ajusta una sola vez y se reutiliza (lr_cache)."""
    nuevo = not lr_cache
    res = {}
    # backtesting: modelos entrenados con el estado al corte de 2024
    M = ajustar(X24, y24, semilla, lr=nuevo)
    p = predecir(M, X24)
    if nuevo:
        lr_cache["bt"] = p["LR"]
    p["LR"] = lr_cache["bt"]
    p["ENS"] = ensamble(p)
    res["bt"] = p
    # validacion cruzada espacial (scale_pos_weight global, como en pipeline.py)
    pw = (y == 0).sum() / (y == 1).sum()
    oof = {k: np.zeros(len(y)) for k in ("LR", "RF", "XGB")}
    if nuevo:
        lr_cache["cv"] = np.zeros(len(y))
    for tr, te in PLIEGUES:
        q = predecir(ajustar(X[tr], y[tr], semilla, pw=pw, lr=nuevo), X[te])
        if nuevo:
            lr_cache["cv"][te] = q["LR"]
        oof["RF"][te], oof["XGB"][te] = q["RF"], q["XGB"]
    oof["LR"] = lr_cache["cv"]
    oof["ENS"] = ensamble(oof)
    res["cv"] = oof
    # modelo final (todas las celdas, objetivo 2026): perfil y score
    M = ajustar(X, y, semilla, lr=nuevo)
    p = predecir(M, X)
    if nuevo:
        lr_cache["final"] = p["LR"]
    p["LR"] = lr_cache["final"]
    res["pp"] = perfiles(p)
    return res


def medir(res):
    fila = {}
    for k in MOD:
        mb = metricas(t, res["bt"][k][cand])
        mc = metricas(y, res["cv"][k])
        fila[k] = {"bt_ROC_AUC": mb["ROC_AUC"], "bt_PR_AUC": mb["PR_AUC"],
                   "bt_Lift@10%": mb["Lift@10%"], "bt_aciertos@20": mb["aciertos@20"],
                   "cv_ROC_AUC": mc["ROC_AUC"], "cv_PR_AUC": mc["PR_AUC"]}
        # ROC-AUC por pliegue (ensamble por rangos dentro del pliegue)
        pr = []
        for tr, te in PLIEGUES:
            v = (np.mean([rango(res["cv"][j][te]) for j in ("LR", "RF", "XGB")], axis=0)
                 if k == "ENS" else res["cv"][k][te])
            pr.append(roc_auc_score(y[te], v))
        fila[k]["cv_de_pliegues"] = np.std(pr, ddof=1)
    return fila


log(f"[2b] Semilla de referencia ({SEMILLA_BASE}) y control frente a pipeline.py")
LRC = {}
REF = corrida(SEMILLA_BASE, LRC)
ok = [coincide(REF["bt"][k][cand], BT[k].values, f"backtesting {k}") for k in MOD]
ok += [coincide(REF["cv"][k], CV[k].values, f"validacion espacial {k}") for k in MOD]
ok.append(coincide(REF["pp"]["ENS"], R["p_potencial"].values, "perfil del ensamble (p_potencial)"))
ok.append(coincide(score(REF["pp"]["ENS"]), R["SCORE"].values, "score de la aplicacion"))
REPRODUCE = all(ok)
TOP_REF = {k: {"modelo": top50(REF["pp"][k]), "score": top50(score(REF["pp"][k]))} for k in MOD}
TOP_REF_SET = {k: {tp: set(v) for tp, v in d.items()} for k, d in TOP_REF.items()}

log(f"[2b] {args.semillas} semillas (1 a {args.semillas})")
filas, filas_top = [], []
m42 = medir(REF)
for k in MOD:
    filas.append({"semilla": SEMILLA_BASE, "modelo": k, **m42[k]})
for s in range(1, args.semillas + 1):
    res = corrida(s, LRC)
    mm = medir(res)
    for k in MOD:
        filas.append({"semilla": s, "modelo": k, **mm[k]})
        for tp in ("modelo", "score"):
            T = set(top50(res["pp"][k] if tp == "modelo" else score(res["pp"][k])))
            filas_top.append({"semilla": s, "modelo": k, "top50": tp,
                              "conserva": len(T & TOP_REF_SET[k][tp]) / 50})
    log(f"    semilla {s:2d}: backtesting ROC-AUC "
        + " ".join(f"{k} {mm[k]['bt_ROC_AUC']:.3f}" for k in MOD))
SE = pd.DataFrame(filas)
SE.to_csv(f"{OUT}/eleccion_semillas.csv", index=False)
ST = pd.DataFrame(filas_top)
S20 = SE[SE["semilla"] != SEMILLA_BASE]
filas = []
for k in MOD:
    for met in [c for c in SE.columns if c not in ("semilla", "modelo")]:
        v = S20.loc[S20["modelo"] == k, met]
        filas.append({"modelo": k, "metrica": met, "valor_semilla42":
                      SE.loc[(SE["semilla"] == SEMILLA_BASE) & (SE["modelo"] == k), met].iloc[0],
                      "media": v.mean(), "de": v.std(), "minimo": v.min(), "maximo": v.max(),
                      "rango": v.max() - v.min()})
    for tp in ("modelo", "score"):
        v = ST.loc[(ST["modelo"] == k) & (ST["top50"] == tp), "conserva"]
        filas.append({"modelo": k, "metrica": f"top50_{tp}_conserva", "valor_semilla42": 1.0,
                      "media": v.mean(), "de": v.std(), "minimo": v.min(), "maximo": v.max(),
                      "rango": v.max() - v.min()})
SR = pd.DataFrame(filas)
# veces que cada modelo queda primero entre los cuatro en las 20 semillas (empates cuentan)
for met in [c for c in SE.columns if c not in ("semilla", "modelo", "cv_de_pliegues")]:
    W = S20.pivot(index="semilla", columns="modelo", values=met)
    mejor = W.eq(W.max(axis=1), axis=0).sum()
    for k in MOD:
        SR.loc[(SR["modelo"] == k) & (SR["metrica"] == met), "veces_mejor"] = int(mejor[k])
SR.to_csv(f"{OUT}/eleccion_semillas_resumen.csv", index=False)
print(SR.pivot(index="metrica", columns="modelo", values="de")[list(MOD)].round(4).to_string())

# ═══════════════════ 2c. Top-50 con 200 reentrenamientos ═══════════════════
log(f"[2c] Top-50 en {args.remuestreos} reentrenamientos con celdas remuestreadas")
rng = np.random.default_rng(SEMILLA_REMUESTREO)
ipos, ineg = np.where(y == 1)[0], np.where(y == 0)[0]
cuenta = {k: {tp: np.zeros(len(y), int) for tp in ("modelo", "score")} for k in MOD}
filas = []
for b in range(args.remuestreos):
    s = np.concatenate([rng.choice(ipos, len(ipos)), rng.choice(ineg, len(ineg))])
    pp = perfiles(predecir(ajustar(X[s], y[s], SEMILLA_BASE), X))
    for k in MOD:
        rho = spearmanr(pp[k][IVIA], REF["pp"][k][IVIA]).statistic
        for tp in ("modelo", "score"):
            T = top50(pp[k] if tp == "modelo" else score(pp[k]))
            cuenta[k][tp][T] += 1
            filas.append({"remuestreo": b + 1, "modelo": k, "top50": tp,
                          "conserva": len(set(T) & TOP_REF_SET[k][tp]) / 50, "spearman": rho})
    if (b + 1) % 20 == 0 or b + 1 == args.remuestreos:
        log(f"    {b + 1} reentrenamientos")
BO = pd.DataFrame(filas)
BO.to_csv(f"{OUT}/eleccion_top50_remuestreos.csv", index=False)
filas = []
for k in MOD:
    for tp in ("modelo", "score"):
        v = BO.loc[(BO["modelo"] == k) & (BO["top50"] == tp)]
        frec = cuenta[k][tp] / args.remuestreos
        filas.append({"modelo": k, "top50": tp, "conserva_media": v["conserva"].mean(),
                      "conserva_p05": v["conserva"].quantile(0.05),
                      "conserva_min": v["conserva"].min(),
                      "nucleo_90": int((frec >= 0.90).sum()),
                      "ref_en_90": int((frec[TOP_REF[k][tp]] >= 0.90).sum()),
                      "celdas_distintas": int((frec > 0).sum()),
                      "spearman_medio": v["spearman"].mean()})
TP = pd.DataFrame(filas)
TP.to_csv(f"{OUT}/eleccion_top50.csv", index=False)
print(TP.round(3).to_string(index=False))

# ═══════════════════ 3. Resumen y regla de decision ═══════════════════
def de_pliegues(k):
    return EP.query("metrica == 'ROC_AUC' and modelo == @k")["de"].iloc[0]


def de_semillas(k):
    return SR.query("metrica == 'bt_Lift@10%' and modelo == @k")["de"].iloc[0]


def conserva(k):
    return TP.query("top50 == 'score' and modelo == @k")["conserva_media"].iloc[0]


def mejores(f, signo):
    """Modelos con el mejor valor (signo -1: menor es mejor); los empates se listan juntos."""
    v = {k: signo * f(k) for k in CANDIDATOS}
    return [k for k in CANDIDATOS if v[k] >= max(v.values()) - 1e-12]


gana = {
    "(a) menor DE del ROC-AUC entre pliegues": mejores(de_pliegues, -1),
    "(b) menor DE del lift del backtesting entre semillas": mejores(de_semillas, -1),
    "(c) mayor parte del Top-50 del score conservada": mejores(conserva, 1),
}
victorias = sum("ENS" in v for v in gana.values())
veredicto = ("El ensamble ES el mas estable" if victorias >= 2 else
             "El ensamble NO es el mas estable") + f" (gana o empata en {victorias} de 3 medidas)."

L = ["# Eleccion del modelo: pruebas formales y estabilidad", "",
     f"Generado por analisis_eleccion_modelo.py ({args.semillas} semillas, "
     f"{args.remuestreos} reentrenamientos).", "",
     "Control de reproduccion frente a pipeline.py: "
     + ("todas las predicciones coinciden." if REPRODUCE else
        "**hay diferencias** (otro sistema operativo o versiones); las cifras no son las de la tesis."),
     "", "## Regla de decision", ""]
for med, ks in gana.items():
    L.append(f"- {med}: " + " y ".join(NOM[k] for k in ks) + (" (empate)" if len(ks) > 1 else ""))
L += ["", f"**{veredicto}**", "", "## Pruebas formales (p de Holm)", "",
      "| Validacion | Metrica | Metodo | Comparacion | Diferencia | IC 95 % | p | p Holm |",
      "|---|---|---|---|---|---|---|---|"]
for _, r in PR.iterrows():
    L.append(f"| {r['validacion']} | {r['metrica']} | {r['metodo']} | {r['comparacion']} | "
             f"{r['diferencia']:+.4f} | {r['IC95_inf']:+.4f} a {r['IC95_sup']:+.4f} | "
             f"{r['p']:.4f} | {r['p_holm']:.4f} |")
L += ["", "## Estabilidad entre pliegues", "",
      "| Metrica | Modelo | Media | DE | Minimo | Puesto medio | Peor puesto | Veces ultimo |",
      "|---|---|---|---|---|---|---|---|"]
for _, r in EP.iterrows():
    L.append(f"| {r['metrica']} | {NOM[r['modelo']]} | {r['media']:.4f} | {r['de']:.4f} | "
             f"{r['minimo']:.4f} | {r['puesto_medio']:.1f} | {r['peor_puesto']} | {r['veces_ultimo']} |")
L.append(f"\nFriedman: ROC-AUC p = {EP.query('metrica == \"ROC_AUC\"')['friedman_p'].iloc[0]:.3f}; "
         f"PR-AUC p = {EP.query('metrica == \"PR_AUC\"')['friedman_p'].iloc[0]:.3f}")
L += ["", f"## Estabilidad entre semillas (DE de {args.semillas} semillas)", "",
      "| Metrica | " + " | ".join(NOM[k] for k in MOD) + " |", "|---|" + "---|" * len(MOD)]
W = SR.pivot(index="metrica", columns="modelo", values="de")
M_ = SR.pivot(index="metrica", columns="modelo", values="media")
for met in W.index:
    L.append(f"| {met} | " + " | ".join(f"{M_.loc[met, k]:.4f} ± {W.loc[met, k]:.4f}" for k in MOD) + " |")
L += ["", f"## Top-50 en {args.remuestreos} reentrenamientos", "",
      "| Top-50 de | Modelo | Conserva (media) | Conserva (p5) | Nucleo >= 90 % | Spearman medio |",
      "|---|---|---|---|---|---|"]
for _, r in TP.iterrows():
    L.append(f"| {r['top50']} | {NOM[r['modelo']]} | {100 * r['conserva_media']:.1f} % | "
             f"{100 * r['conserva_p05']:.0f} % | {r['nucleo_90']} | {r['spearman_medio']:.3f} |")
open(f"{OUT}/RESUMEN_ELECCION_MODELO.md", "w", encoding="utf-8").write("\n".join(L) + "\n")
log(veredicto)
log("Listo: resultados/eleccion_*.csv y resultados/RESUMEN_ELECCION_MODELO.md")
