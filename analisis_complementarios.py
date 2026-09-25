#!/usr/bin/env python3
"""
analisis_complementarios.py

Analisis de robustez del modelo que complementan el Capitulo V. Parte de las
salidas de pipeline.py (resultados/features.parquet) y reutiliza exactamente
la misma configuracion de modelos, candidatos y metricas.

  1. Intervalos de confianza por bootstrap del backtesting y prueba de la
     diferencia entre el ensamble y las lineas base.
  2. Validacion cruzada espacial: media y desviacion estandar entre pliegues.
  3. Autocorrelacion espacial: I de Moran de la variable objetivo y de los
     residuos fuera de muestra.
  4. Multicolinealidad: factor de inflacion de la varianza (VIF).
  5. Area de aplicabilidad (Meyer y Pebesma, 2021) bajo validacion cruzada.
  6. Fuga temporal: repeticion del backtesting y de la validacion cruzada
     excluyendo de la capa de competencia de OpenStreetMap los locales de
     cadenas de conveniencia y los situados junto a una tienda de la cadena.
  7. Ventana de oportunidad: en cuantas de las ubicaciones que el score habria
     recomendado con la red de 2024 abrio despues una tienda de la cadena
     dentro del radio de amenaza.

Uso (desde la raiz del proyecto, tras ejecutar pipeline.py):
    python analisis_complementarios.py
"""
import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

np.random.seed(42)
DATA = "data"
OUT = "resultados"
UTM = 32719
B = 2000                       # replicas bootstrap
W_POT, PEN_MASS, RADIO = 0.344, 0.261, 750
CADENAS = r"\bMASS\b|TAMBO|OXXO|LISTO|REPSHOP|MINIMARKET MASS"

F = pd.read_parquet(f"{OUT}/features.parquet")
PRED = [c for c in F.columns if c not in ("h3", "DIST", "es_nucleo", "bloque")
        and not c.startswith(("mass_", "d_mass_"))]


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


def lift10(t, s):
    o = np.argsort(-s)
    n10 = max(int(0.10 * len(s)), 1)
    return t[o[:n10]].mean() / t.mean()


def metricas(t, s):
    o = np.argsort(-s)
    return {"PR_AUC": average_precision_score(t, s), "ROC_AUC": roc_auc_score(t, s),
            "Lift@10%": lift10(t, s), "acierto@20": int(t[o[:20]].sum())}


def backtesting(df):
    X = matriz(df)
    y24 = df["mass_2024"].values
    abrio = ((df["mass_2026"] == 1) & (df["mass_2024"] == 0)).astype(int).values
    cand = (df["pob_k1"] >= 1500).values & (y24 == 0)
    probs = predecir(hacer_modelos(X, y24), X)
    scores = {"Ensamble": ensamble(probs),
              "Baseline densidad": df["dens_hab_km2"].values,
              "Baseline pob. k1": df["pob_k1"].values}
    return cand, abrio, probs, scores


def cv_espacial(df):
    X = matriz(df)
    y = df["mass_2026"].values
    bloques = [h3.cell_to_parent(c, 6) for c in df["h3"]]
    oof = {k: np.zeros(len(df)) for k in ("LR", "RF", "XGB")}
    pliegues, folds = [], []
    for i, (tr, te) in enumerate(GroupKFold(n_splits=5).split(X, y, groups=bloques)):
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
    return y, oof, pd.DataFrame(pliegues), folds


# ═══════════════ 1. Bootstrap del backtesting ═══════════════
print("[1] Intervalos de confianza del backtesting (bootstrap, B = 2000)")
cand, abrio, probs, scores = backtesting(F)
t = abrio[cand]
S = {k: v[cand] for k, v in scores.items()}
rng = np.random.default_rng(42)
pos, neg = np.where(t == 1)[0], np.where(t == 0)[0]
reps = {k: [] for k in S}
difs = {"Lift@10%": {"Baseline densidad": [], "Baseline pob. k1": []},
        "PR_AUC": {"Baseline densidad": [], "Baseline pob. k1": []}}
for _ in range(B):
    # remuestreo estratificado: conserva las 39 aperturas en cada replica
    i = np.r_[rng.choice(pos, len(pos)), rng.choice(neg, len(neg))]
    tb = t[i]
    m = {k: metricas(tb, v[i]) for k, v in S.items()}
    for k in S:
        reps[k].append(m[k])
    for met in difs:
        for base in difs[met]:
            difs[met][base].append(m["Ensamble"][met] - m[base][met])

filas = []
for k in S:
    r = pd.DataFrame(reps[k])
    obs = metricas(t, S[k])
    for met in ("PR_AUC", "ROC_AUC", "Lift@10%"):
        lo, hi = np.percentile(r[met], [2.5, 97.5])
        filas.append({"modelo": k, "metrica": met, "valor": obs[met],
                      "IC95_inf": lo, "IC95_sup": hi})
IC = pd.DataFrame(filas)
IC.to_csv(f"{OUT}/analisis_ic_backtesting.csv", index=False)
print(IC.round(3).to_string(index=False))

filas = []
for met in difs:
    for base, v in difs[met].items():
        v = np.array(v)
        filas.append({"metrica": met, "comparacion": f"Ensamble - {base}",
                      "diferencia": metricas(t, S["Ensamble"])[met] - metricas(t, S[base])[met],
                      "IC95_inf": np.percentile(v, 2.5), "IC95_sup": np.percentile(v, 97.5),
                      "p_unilateral": (v <= 0).mean()})
DIF = pd.DataFrame(filas)
DIF.to_csv(f"{OUT}/analisis_diferencias_backtesting.csv", index=False)
print("\n" + DIF.round(3).to_string(index=False))

# ═══════════════ 2. Validacion cruzada por pliegue ═══════════════
print("\n[2] Validacion cruzada espacial por pliegue")
y26, oof, PL, folds = cv_espacial(F)
PL.to_csv(f"{OUT}/analisis_cv_pliegues.csv", index=False)
RES = PL.groupby("modelo")[["PR_AUC", "ROC_AUC"]].agg(["mean", "std"]).round(3)
print(RES.to_string())
print("    positivos por pliegue:", PL[PL.modelo == "ENS"]["n_pos"].tolist())

# ═══════════════ 3. I de Moran ═══════════════
print("\n[3] Autocorrelacion espacial (I de Moran, vecindad H3 k = 1)")
idx = {c: i for i, c in enumerate(F["h3"])}
vec = [[idx[v] for v in h3.grid_disk(c, 1) if v != c and v in idx] for c in F["h3"]]


def moran(z, perm=999):
    z = np.asarray(z, float) - np.mean(z)
    def I(zz):
        lag = np.array([zz[n].mean() if n else 0.0 for n in vec])
        return len(zz) * (zz * lag).sum() / ((zz ** 2).sum() * len(zz))
    obs = I(z)
    sims = np.array([I(rng.permutation(z)) for _ in range(perm)])
    return obs, (np.sum(sims >= obs) + 1) / (perm + 1)


filas = []
for nombre, z in (("Variable objetivo (tienda en 2026)", y26),
                  ("Residuos fuera de muestra de Random Forest", y26 - oof["RF"]),
                  ("Poblacion de la celda", F["pob_2017"].values)):
    i_obs, p = moran(z)
    filas.append({"variable": nombre, "I_Moran": i_obs, "p_valor": p})
MO = pd.DataFrame(filas)
MO.to_csv(f"{OUT}/analisis_moran.csv", index=False)
print(MO.round(4).to_string(index=False))

# ═══════════════ 4. VIF ═══════════════
print("\n[4] Multicolinealidad (VIF)")
Z = StandardScaler().fit_transform(matriz(F))


def calcular_vif(cols):
    Zc = Z[:, [PRED.index(c) for c in cols]]
    out = {}
    for j, c in enumerate(cols):
        A = np.c_[np.ones(len(Zc)), np.delete(Zc, j, axis=1)]
        beta, *_ = np.linalg.lstsq(A, Zc[:, j], rcond=None)
        ss = ((Zc[:, j] - Zc[:, j].mean()) ** 2).sum()
        r2 = 1 - ((Zc[:, j] - A @ beta) ** 2).sum() / ss
        out[c] = np.inf if r2 >= 1 - 1e-9 else 1 / (1 - r2)
    return out


# Identidades por construccion: n_poi_k1 es la suma de las nueve categorias en
# el anillo y pob_k1_ext = pob_k1 - pob_2017. Se calcula el VIF con los 37
# predictores y sin esas dos variables derivadas.
IDENT = ["n_poi_k1", "pob_k1_ext"]
v_all = calcular_vif(PRED)
v_red = calcular_vif([c for c in PRED if c not in IDENT])
VIF = pd.DataFrame({"variable": PRED, "VIF_37": [v_all[c] for c in PRED],
                    "VIF_sin_identidades": [v_red.get(c, np.nan) for c in PRED]})
VIF = VIF.sort_values("VIF_sin_identidades", ascending=False)
VIF.to_csv(f"{OUT}/analisis_vif.csv", index=False)
print(VIF.head(10).round(1).to_string(index=False))
print(f"    con 37 predictores: VIF infinito en {np.isinf(VIF.VIF_37).sum()} (identidades por construccion)")
print(f"    sin identidades: VIF > 10 en {(VIF.VIF_sin_identidades > 10).sum()} de {len(v_red)}, "
      f"VIF > 5 en {(VIF.VIF_sin_identidades > 5).sum()}")

# ═══════════════ 5. Area de aplicabilidad ═══════════════
print("\n[5] Area de aplicabilidad (Meyer y Pebesma, 2021)")
imp = pd.read_csv(f"{OUT}/importancia_variables.csv").set_index("variable")["importancia"]
Zw = Z * imp.reindex(PRED).fillna(0).values
from scipy.spatial import cKDTree
di = np.zeros(len(F))
dbar = []
for tr, te in folds:
    arbol = cKDTree(Zw[tr])
    d, _ = arbol.query(Zw[te], k=1)
    muestra = rng.choice(tr, min(len(tr), 1500), replace=False)
    dm = np.linalg.norm(Zw[muestra][:, None] - Zw[muestra][None], axis=2)
    dbar.append(dm[np.triu_indices(len(muestra), 1)].mean())
    di[te] = d / dbar[-1]
q1, q3 = np.percentile(di, [25, 75])
umbral = q3 + 1.5 * (q3 - q1)
dentro = di <= umbral
viables26 = (F["pob_k1"] >= 1500) & (F["mass_2026"] == 0)
AOA = pd.DataFrame([
    {"conjunto": "Todas las celdas", "n": len(F), "pct_dentro_AOA": dentro.mean()},
    {"conjunto": "Nucleo censado", "n": int(F.es_nucleo.sum()), "pct_dentro_AOA": dentro[F.es_nucleo == 1].mean()},
    {"conjunto": "Anillo de expansion", "n": int((F.es_nucleo == 0).sum()), "pct_dentro_AOA": dentro[F.es_nucleo == 0].mean()},
    {"conjunto": "Celdas viables del ranking", "n": int(viables26.sum()), "pct_dentro_AOA": dentro[viables26].mean()},
])
R = pd.read_parquet(f"{OUT}/resultado_final.parquet")
top50 = R[R["viable"]].nlargest(50, "SCORE")["h3"]
en_top = F["h3"].isin(top50).values
AOA.loc[len(AOA)] = {"conjunto": "Top-50 del ranking", "n": int(en_top.sum()),
                     "pct_dentro_AOA": dentro[en_top].mean()}
AOA.to_csv(f"{OUT}/analisis_aoa.csv", index=False)
print(f"    umbral DI = {umbral:.3f}")
print(AOA.round(3).to_string(index=False))

# ═══════════════ 6. Fuga temporal en la capa OSM ═══════════════
print("\n[6] Sensibilidad a la fuga temporal de la capa de competencia OSM")
C = gpd.read_parquet(f"{DATA}/osm/competencia.parquet")
Mp = gpd.read_parquet(f"{OUT}/mass_panel.parquet").drop_duplicates("codigo")
txt = C[["name", "brand", "operator"]].astype(str).agg(" ".join, axis=1).str.upper()
por_nombre = txt.str.contains(CADENAS, regex=True).values
cu, mu = C.to_crs(UTM), Mp.to_crs(UTM)
dist_mass = cu.geometry.apply(lambda p: mu.distance(p).min()).values
excluir = por_nombre | (dist_mass < 40)
print(f"    comercios OSM: {len(C)} | de cadena por nombre: {por_nombre.sum()} | "
      f"a < 40 m de una tienda de la cadena: {(dist_mass < 40).sum()} | excluidos: {excluir.sum()}")
Cl = C[~excluir].copy()
Cl["h3"] = [h3.latlng_to_cell(p.y, p.x, 9) for p in Cl.geometry]
G = F.drop(columns=["n_comp_osm", "n_comp_osm_k1", "hab_por_comp_k1"])
G = G.merge(Cl.groupby("h3").size().rename("n_comp_osm").reset_index(), on="h3",
            how="left").fillna({"n_comp_osm": 0})
d = dict(zip(G["h3"], G["n_comp_osm"]))
G["n_comp_osm_k1"] = [sum(d.get(v, 0) for v in h3.grid_disk(c, 1)) for c in G["h3"]]
G["hab_por_comp_k1"] = G["pob_k1"] / (G["n_comp_osm_k1"] + 1)
G = G[F.columns]

cand_l, abrio_l, probs_l, scores_l = backtesting(G)
_, oof_l, _, _ = cv_espacial(G)
filas = []
for nombre, ens_bt, o in (("Capa OSM original", scores["Ensamble"], oof),
                          ("Sin locales de cadena", scores_l["Ensamble"], oof_l)):
    m = metricas(abrio[cand], ens_bt[cand])
    filas.append({"escenario": nombre, "BT_PR_AUC": m["PR_AUC"], "BT_ROC_AUC": m["ROC_AUC"],
                  "BT_Lift@10%": m["Lift@10%"], "BT_aciertos@20": m["acierto@20"],
                  "CV_ROC_AUC_RF": roc_auc_score(y26, o["RF"]),
                  "CV_PR_AUC_ENS": average_precision_score(y26, o["ENS"]),
                  "CV_ROC_AUC_ENS": roc_auc_score(y26, o["ENS"])})
FU = pd.DataFrame(filas)
FU.to_csv(f"{OUT}/analisis_fuga_osm.csv", index=False)
print(FU.round(3).to_string(index=False))

# ═══════════════ 7. Ventana de oportunidad ═══════════════
print("\n[7] Ventana de oportunidad: aperturas de la cadena junto a las recomendaciones de 2024")
p24 = rango(ensamble(probs))
dem = F["pob_k1"] * 180 / (1 + F["n_comp_osm_k1"] + 3 * F["mass_k1_2024"])
dem_n = dem.rank(pct=True).values
riesgo = np.clip(1 - F["d_mass_2024"] / RADIO, 0, 1).values
viable24 = ((F["pob_k1"] >= 1500) & (F["mass_2024"] == 0)).values
score24 = np.where(viable24, (W_POT * p24 + (1 - W_POT) * dem_n) * (1 - PEN_MASS * riesgo), 0)
llego = ((F["d_mass_2026"] < RADIO) & (F["d_mass_2024"] >= RADIO)).values | \
        ((F["mass_k1_2026"] > F["mass_k1_2024"]).values)
o = np.argsort(-score24)
filas = []
for k in (10, 20, 50):
    sel = o[:k]
    filas.append({"conjunto": f"Top-{k} del score con la red de 2024",
                  "n": k, "pct_con_nueva_tienda_en_radio": llego[sel].mean(),
                  "pct_apertura_en_la_celda": abrio[sel].mean()})
filas.append({"conjunto": "Todas las celdas viables en 2024", "n": int(viable24.sum()),
              "pct_con_nueva_tienda_en_radio": llego[viable24].mean(),
              "pct_apertura_en_la_celda": abrio[viable24].mean()})
VO = pd.DataFrame(filas)
VO.to_csv(f"{OUT}/analisis_ventana_oportunidad.csv", index=False)
print(VO.round(3).to_string(index=False))

print("\n>> resultados/analisis_*.csv generados")
