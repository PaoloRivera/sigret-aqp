#!/usr/bin/env python3
"""
analisis_complementarios.py

Analisis de robustez que complementan el Capitulo V. Parte de las salidas de
pipeline.py y reutiliza exactamente la misma configuracion de modelos,
candidatos y metricas.

  1. Fuga temporal: backtesting con tres versiones de los predictores OSM
     (estado 2026 sin filtrar la cadena, estado 2026 filtrado y estado al
     31-12-2024 filtrado, que es la corrida oficial).
  2. Intervalos de confianza por bootstrap (1 000 remuestreos de las celdas
     candidatas) del backtesting y de la diferencia ensamble - linea base.
  3. Validacion cruzada espacial: media y desviacion estandar entre pliegues.
  4. Autocorrelacion espacial: I de Moran (esda) de la variable objetivo y de
     los residuos fuera de muestra, bajo validacion aleatoria y espacial.
  5. Multicolinealidad: factor de inflacion de la varianza (statsmodels).
  6. Area de aplicabilidad (Meyer y Pebesma, 2021) bajo validacion cruzada.
  7. Tasa de entrada de la cadena: en cuantas de las celdas mejor puntuadas
     con el estado de 2024 abrio despues una tienda de la cadena a menos del
     radio de amenaza.

Uso (desde la raiz del proyecto, tras ejecutar pipeline.py):
    python analisis_complementarios.py
"""
import warnings

import esda
import geopandas as gpd
import h3
import libpysal
import numpy as np
import pandas as pd
import xgboost as xgb
from scipy.spatial import cKDTree
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold, StratifiedKFold
from sklearn.preprocessing import StandardScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor


warnings.filterwarnings("ignore")
np.random.seed(42)
DATA = "data"
OUT = "resultados"
UTM = 32719
B = 1000
W_POT, PEN_MASS, RADIO = 0.344, 0.261, 750

F = pd.read_parquet(f"{OUT}/features.parquet")
F24 = pd.read_parquet(f"{OUT}/features_2024.parquet").set_index("h3").loc[F["h3"]].reset_index()
PRED = [c for c in F.columns if c not in ("h3", "DIST", "es_nucleo", "bloque")
        and not c.startswith(("mass_", "d_mass_"))]
rng = np.random.default_rng(42)


def matriz(df):
    return df[PRED].replace([np.inf, -np.inf], 0).fillna(0).values


def hacer_modelos(X, y):
    pw = (y == 0).sum() / max((y == 1).sum(), 1)
    sc = StandardScaler().fit(X)
    return {
        "LR": ("s", sc, LogisticRegression(max_iter=5000, class_weight="balanced",
                                           C=0.5).fit(sc.transform(X), y)),
        "RF": ("r", None, RandomForestClassifier(
            n_estimators=800, min_samples_leaf=5, max_features="sqrt",
            class_weight="balanced_subsample", n_jobs=-1, random_state=42).fit(X, y)),
        "XGB": ("r", None, xgb.XGBClassifier(
            n_estimators=400, max_depth=3, learning_rate=0.05, subsample=0.8,
            colsample_bytree=0.7, reg_lambda=3.0, min_child_weight=5,
            scale_pos_weight=pw, eval_metric="aucpr", random_state=42).fit(X, y)),
    }


def predecir(M, X):
    return {k: m.predict_proba(sc.transform(X) if t == "s" else X)[:, 1]
            for k, (t, sc, m) in M.items()}


def rango(p):
    return pd.Series(p).rank(pct=True).values


def ensamble(probs):
    return np.mean([rango(p) for p in probs.values()], axis=0)


def metricas(t, s):
    o = np.argsort(-s)
    n10 = max(int(0.10 * len(s)), 1)
    return {"PR_AUC": average_precision_score(t, s), "ROC_AUC": roc_auc_score(t, s),
            "Lift@10%": t[o[:n10]].mean() / t.mean(), "acierto@20": int(t[o[:20]].sum())}


y24 = F["mass_2024"].values
abrio = ((F["mass_2026"] == 1) & (F["mass_2024"] == 0)).astype(int).values
cand = (F["pob_k1"] >= 1500).values & (y24 == 0)
t = abrio[cand]


def backtesting(P):
    """P: matriz de predictores (DataFrame alineado con F)."""
    X = matriz(P)
    probs = predecir(hacer_modelos(X, y24), X)
    return {"Ensamble": ensamble(probs),
            "Baseline densidad": P["dens_hab_km2"].values,
            "Baseline pob. k1": P["pob_k1"].values,
            "Baseline POIs k1": P["n_poi_k1"].values}


def cv(P, divisor):
    X = matriz(P)
    y = P["mass_2026"].values
    oof = {k: np.zeros(len(P)) for k in ("LR", "RF", "XGB")}
    pliegues, folds = [], []
    for i, (tr, te) in enumerate(divisor):
        p = predecir(hacer_modelos(X[tr], y[tr]), X[te])
        for k in oof:
            oof[k][te] = p[k]
        p["ENS"] = ensamble(p)
        for k, v in p.items():
            pliegues.append({"pliegue": i + 1, "modelo": k, "n_pos": int(y[te].sum()),
                             "PR_AUC": average_precision_score(y[te], v),
                             "ROC_AUC": roc_auc_score(y[te], v)})
        folds.append((tr, te))
    oof["ENS"] = ensamble(oof)
    return oof, pd.DataFrame(pliegues), folds


bloques = [h3.cell_to_parent(c, 6) for c in F["h3"]]
y26 = F["mass_2026"].values


def cv_espacial(P):
    return cv(P, GroupKFold(n_splits=5).split(matriz(P), y26, groups=bloques))


# ═══════════════ 1. Fuga temporal ═══════════════
print("[1] Fuga temporal: backtesting con tres versiones de los predictores OSM")
mass = gpd.read_parquet(f"{OUT}/mass_panel.parquet")
Craw = gpd.read_parquet(f"{DATA}/osm/competencia.parquet")
Craw["h3"] = [h3.latlng_to_cell(p.y, p.x, 9) for p in Craw.geometry]
G = F.drop(columns=["n_comp_osm", "n_comp_osm_k1", "hab_por_comp_k1"]).merge(
    Craw.groupby("h3").size().rename("n_comp_osm").reset_index(), on="h3",
    how="left").fillna({"n_comp_osm": 0})
d = dict(zip(G["h3"], G["n_comp_osm"]))
G["n_comp_osm_k1"] = [sum(d.get(v, 0) for v in h3.grid_disk(c, 1)) for c in G["h3"]]
G["hab_por_comp_k1"] = G["pob_k1"] / (G["n_comp_osm_k1"] + 1)
G = G[F.columns]

escenarios = {"OSM 2026 sin filtrar la cadena": G,
              "OSM 2026 sin locales de la cadena": F,
              "OSM al 31-12-2024 sin locales de la cadena (oficial)": F24}
filas, scores_oficial = [], None
for nombre, P in escenarios.items():
    sc = backtesting(P)
    m = metricas(t, sc["Ensamble"][cand])
    filas.append({"escenario": nombre, "PR_AUC": m["PR_AUC"], "ROC_AUC": m["ROC_AUC"],
                  "Lift@10%": m["Lift@10%"], "aciertos@20": m["acierto@20"]})
    scores_oficial = sc
FU = pd.DataFrame(filas)
FU.to_csv(f"{OUT}/analisis_fuga_osm.csv", index=False)
print(FU.round(3).to_string(index=False))

# ═══════════════ 2. Bootstrap ═══════════════
print(f"\n[2] Intervalos de confianza del backtesting oficial (bootstrap, B = {B})")
S = {k: v[cand] for k, v in scores_oficial.items()}
reps = {k: [] for k in S}
n = len(t)
while len(reps["Ensamble"]) < B:
    i = rng.integers(0, n, n)
    if t[i].sum() == 0:
        continue
    for k, v in S.items():
        reps[k].append(metricas(t[i], v[i]))
filas = []
for k in S:
    r, obs = pd.DataFrame(reps[k]), metricas(t, S[k])
    for met in ("ROC_AUC", "PR_AUC", "Lift@10%"):
        lo, hi = np.percentile(r[met], [2.5, 97.5])
        filas.append({"modelo": k, "metrica": met, "valor": obs[met], "IC95_inf": lo, "IC95_sup": hi})
IC = pd.DataFrame(filas)
IC.to_csv(f"{OUT}/analisis_ic_backtesting.csv", index=False)
print(IC.round(3).to_string(index=False))

filas = []
base_ref = {met: max((b for b in S if b != "Ensamble"), key=lambda b: metricas(t, S[b])[met])
            for met in ("ROC_AUC", "PR_AUC", "Lift@10%")}
for met, base in base_ref.items():
    for b in ("Baseline densidad", base):
        dif = np.array([e[met] - x[met] for e, x in zip(reps["Ensamble"], reps[b])])
        filas.append({"metrica": met, "comparacion": f"Ensamble - {b}",
                      "mejor_baseline": b == base,
                      "diferencia": metricas(t, S["Ensamble"])[met] - metricas(t, S[b])[met],
                      "IC95_inf": np.percentile(dif, 2.5), "IC95_sup": np.percentile(dif, 97.5),
                      "incluye_cero": np.percentile(dif, 2.5) <= 0 <= np.percentile(dif, 97.5)})
DIF = pd.DataFrame(filas).drop_duplicates(["metrica", "comparacion"])
DIF.to_csv(f"{OUT}/analisis_diferencias_backtesting.csv", index=False)
print("\n" + DIF.round(3).to_string(index=False))

# ═══════════════ 3. Validacion cruzada por pliegue ═══════════════
print("\n[3] Validacion cruzada espacial por pliegue")
oof, PL, folds = cv_espacial(F)
PL.to_csv(f"{OUT}/analisis_cv_pliegues.csv", index=False)
print(PL.groupby("modelo")[["PR_AUC", "ROC_AUC"]].agg(["mean", "std"]).round(3).to_string())
print("    positivos por pliegue:", PL[PL.modelo == "ENS"]["n_pos"].tolist())

# ═══════════════ 4. I de Moran ═══════════════
print("\n[4] I de Moran (esda; vecindad H3 de orden 1, pesos estandarizados por fila)")
idx = {c: i for i, c in enumerate(F["h3"])}
vecinos = {i: [idx[v] for v in h3.grid_disk(c, 1) if v != c and v in idx]
           for c, i in idx.items()}
Wm = libpysal.weights.W(vecinos, silence_warnings=True)
Wm.transform = "r"
oof_rand, _, _ = cv(F, StratifiedKFold(5, shuffle=True, random_state=42).split(matriz(F), y26))
filas = []
for nombre, z in (("Variable objetivo (tienda de la cadena en 2026)", y26),
                  ("Residuos RF, validacion aleatoria", y26 - oof_rand["RF"]),
                  ("Residuos RF, validacion espacial en bloques", y26 - oof["RF"]),
                  ("Poblacion de la celda", F["pob_2017"].values)):
    mi = esda.Moran(z.astype(float), Wm, permutations=999)
    filas.append({"variable": nombre, "I_Moran": mi.I, "p_valor": mi.p_sim, "z": mi.z_sim})
MO = pd.DataFrame(filas)
MO.to_csv(f"{OUT}/analisis_moran.csv", index=False)
print(MO.round(4).to_string(index=False))
m_rand = {"ROC_AUC_RF": roc_auc_score(y26, oof_rand["RF"]), "ROC_AUC_ENS": roc_auc_score(y26, oof_rand["ENS"]),
          "PR_AUC_ENS": average_precision_score(y26, oof_rand["ENS"])}
m_esp = {"ROC_AUC_RF": roc_auc_score(y26, oof["RF"]), "ROC_AUC_ENS": roc_auc_score(y26, oof["ENS"]),
         "PR_AUC_ENS": average_precision_score(y26, oof["ENS"])}
CMP = pd.DataFrame([dict(particion="Aleatoria (5 pliegues estratificados)", **m_rand),
                    dict(particion="Espacial (52 bloques H3 r6)", **m_esp)])
CMP.to_csv(f"{OUT}/analisis_cv_aleatoria_vs_espacial.csv", index=False)
print("\n" + CMP.round(3).to_string(index=False))

# ═══════════════ 5. VIF ═══════════════
print("\n[5] Multicolinealidad (VIF, statsmodels)")
Z = StandardScaler().fit_transform(matriz(F))
Zc = np.c_[np.ones(len(Z)), Z]
# n_poi_k1 es la suma exacta de las nueve categorias del anillo y pob_k1_ext =
# pob_k1 - pob_2017: identidades por construccion con VIF infinito. Se reporta
# ademas el VIF sin esas dos variables.
IDENT = ["n_poi_k1", "pob_k1_ext"]
red = [c for c in PRED if c not in IDENT]
Zr = np.c_[np.ones(len(Z)), Z[:, [PRED.index(c) for c in red]]]
v_red = {c: variance_inflation_factor(Zr, j + 1) for j, c in enumerate(red)}
VIF = pd.DataFrame({"variable": PRED,
                    "VIF_37": [variance_inflation_factor(Zc, j + 1) for j in range(len(PRED))],
                    "VIF_sin_identidades": [v_red.get(c, np.nan) for c in PRED]})
VIF["VIF_37"] = VIF["VIF_37"].where(VIF["VIF_37"] < 1e6, np.inf)
VIF = VIF.sort_values("VIF_sin_identidades", ascending=False)
VIF.to_csv(f"{OUT}/analisis_vif.csv", index=False)
print(VIF.head(12).round(1).to_string(index=False))
print(f"    37 predictores: VIF infinito en {np.isinf(VIF.VIF_37).sum()} (identidades por construccion)")
print(f"    sin identidades ({len(red)}): VIF > 10 en {(VIF.VIF_sin_identidades > 10).sum()}, "
      f"VIF > 5 en {(VIF.VIF_sin_identidades > 5).sum()}")

# ═══════════════ 6. Area de aplicabilidad ═══════════════
print("\n[6] Area de aplicabilidad (Meyer y Pebesma, 2021)")
imp = pd.read_csv(f"{OUT}/importancia_variables.csv").set_index("variable")["importancia"]
Zw = Z * imp.reindex(PRED).fillna(0).values
di = np.zeros(len(F))
for tr, te in folds:
    dmin, _ = cKDTree(Zw[tr]).query(Zw[te], k=1)
    muestra = rng.choice(tr, min(len(tr), 1500), replace=False)
    dm = np.linalg.norm(Zw[muestra][:, None] - Zw[muestra][None], axis=2)
    di[te] = dmin / dm[np.triu_indices(len(muestra), 1)].mean()
q1, q3 = np.percentile(di, [25, 75])
dentro = di <= q3 + 1.5 * (q3 - q1)
R = pd.read_parquet(f"{OUT}/resultado_final.parquet")
top50 = F["h3"].isin(R[R["viable"]].nlargest(50, "SCORE")["h3"]).values
viables = R.set_index("h3").loc[F["h3"], "viable"].values
AOA = pd.DataFrame([
    {"conjunto": "Todas las celdas", "n": len(F), "pct_dentro_AOA": dentro.mean()},
    {"conjunto": "Nucleo censado", "n": int(F.es_nucleo.sum()), "pct_dentro_AOA": dentro[F.es_nucleo == 1].mean()},
    {"conjunto": "Anillo de expansion", "n": int((F.es_nucleo == 0).sum()), "pct_dentro_AOA": dentro[F.es_nucleo == 0].mean()},
    {"conjunto": "Celdas viables del ranking", "n": int(viables.sum()), "pct_dentro_AOA": dentro[viables].mean()},
    {"conjunto": "Top-50 del ranking", "n": int(top50.sum()), "pct_dentro_AOA": dentro[top50].mean()},
])
AOA.to_csv(f"{OUT}/analisis_aoa.csv", index=False)
print(AOA.round(3).to_string(index=False))

# ═══════════════ 7. Tasa de entrada de la cadena ═══════════════
print("\n[7] Tasa de entrada de la cadena junto a las celdas mejor puntuadas en 2024")
p24 = rango(scores_oficial["Ensamble"])
dem_n = (F24["pob_k1"] * 180 / (1 + F24["n_comp_osm_k1"] + 3 * F["mass_k1_2024"])).rank(pct=True).values
riesgo = np.clip(1 - F["d_mass_2024"] / RADIO, 0, 1).values
viable24 = ((F["pob_k1"] >= 1500) & (F["mass_2024"] == 0)).values
score24 = np.where(viable24, (W_POT * p24 + (1 - W_POT) * dem_n) * (1 - PEN_MASS * riesgo), 0)
panel = mass.drop_duplicates("codigo")
nuevas = panel[panel["anio_apertura"] >= 2025].to_crs(UTM)
cen = gpd.GeoSeries(gpd.points_from_xy(R.set_index("h3").loc[F["h3"], "lon"],
                                       R.set_index("h3").loc[F["h3"], "lat"]), crs=4326).to_crs(UTM)
d_nueva, _ = cKDTree(np.c_[nuevas.geometry.x, nuevas.geometry.y]).query(np.c_[cen.x, cen.y], k=1)
entro = d_nueva < RADIO
o = np.argsort(-score24)
filas = [{"conjunto": f"Top-{k} con el estado de 2024", "n": k,
          "celdas_con_apertura_a_menos_de_750m": int(entro[o[:k]].sum()),
          "tasa_entrada": entro[o[:k]].mean(), "apertura_en_la_propia_celda": int(abrio[o[:k]].sum())}
         for k in (10, 20, 50)]
filas.append({"conjunto": "Todas las celdas viables en 2024", "n": int(viable24.sum()),
              "celdas_con_apertura_a_menos_de_750m": int(entro[viable24].sum()),
              "tasa_entrada": entro[viable24].mean(), "apertura_en_la_propia_celda": int(abrio[viable24].sum())})
VO = pd.DataFrame(filas)
VO.to_csv(f"{OUT}/analisis_tasa_entrada_cadena.csv", index=False)
print(VO.round(3).to_string(index=False))

print("\n>> resultados/analisis_*.csv generados")
