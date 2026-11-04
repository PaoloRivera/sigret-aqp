#!/usr/bin/env python3
"""
ic_validacion_espacial.py — IC 95 % del ROC-AUC de la validacion cruzada espacial
mediante bootstrap por bloques H3 r6 (1 000 remuestreos de los 52 bloques).
Uso (desde la raiz del repo, despues de pipeline.py):  python ic_validacion_espacial.py
"""
import warnings
import h3, numpy as np, pandas as pd, xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler
warnings.filterwarnings("ignore"); np.random.seed(42)
RES = "resultados"; B = 1000

F = pd.read_parquet(f"{RES}/features.parquet")
PRED = [c for c in F.columns if c not in ("h3", "DIST", "es_nucleo", "bloque")
        and not c.startswith(("mass_", "d_mass_"))]
X = F[PRED].replace([np.inf, -np.inf], 0).fillna(0).values
y = F["mass_2026"].values
bloq = np.array([h3.cell_to_parent(c, 6) for c in F["h3"]])

oof = {k: np.zeros(len(F)) for k in ("LR", "RF", "XGB")}
for tr, te in GroupKFold(n_splits=5).split(X, y, groups=bloq):
    pw = (y[tr] == 0).sum() / (y[tr] == 1).sum()
    sc = StandardScaler().fit(X[tr])
    oof["LR"][te] = LogisticRegression(max_iter=5000, class_weight="balanced", C=0.5)\
        .fit(sc.transform(X[tr]), y[tr]).predict_proba(sc.transform(X[te]))[:, 1]
    oof["RF"][te] = RandomForestClassifier(n_estimators=800, min_samples_leaf=5, max_features="sqrt",
        class_weight="balanced_subsample", n_jobs=-1, random_state=42)\
        .fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    oof["XGB"][te] = xgb.XGBClassifier(n_estimators=400, max_depth=3, learning_rate=0.05, subsample=0.8,
        colsample_bytree=0.7, reg_lambda=3.0, min_child_weight=5, scale_pos_weight=pw,
        eval_metric="aucpr", random_state=42).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
oof["ENS"] = np.mean([pd.Series(oof[k]).rank(pct=True) for k in ("LR", "RF", "XGB")], axis=0)

rng = np.random.default_rng(42)
ub = np.unique(bloq); idx = {b: np.where(bloq == b)[0] for b in ub}
bs = {k: [] for k in oof}
for _ in range(B):
    s = np.concatenate([idx[b] for b in rng.choice(ub, len(ub))])
    if y[s].min() == y[s].max():
        continue
    for k in oof:
        bs[k].append(roc_auc_score(y[s], oof[k][s]))

filas = []
for k in ("LR", "RF", "XGB", "ENS"):
    lo, hi = np.percentile(bs[k], [2.5, 97.5])
    filas.append({"modelo": k, "ROC_AUC": roc_auc_score(y, oof[k]), "IC95_inf": lo, "IC95_sup": hi,
                  "IC_supera_0.85": lo > 0.85})
T = pd.DataFrame(filas)
print(f"Bloques: {len(ub)} | remuestreos validos: {len(bs['ENS'])}")
print(T.round(3).to_string(index=False))
T.to_csv(f"{RES}/ic_validacion_espacial.csv", index=False)
