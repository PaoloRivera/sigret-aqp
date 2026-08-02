#!/usr/bin/env python3
"""
10_generar_json_app.py
Regenera los cuatro JSON que consume la aplicacion web a partir de las
salidas actuales del pipeline.

ESTE ES EL PASO QUE FALTABA: pipeline.py produce .parquet, pero la app web
sirve .json. Sin este script los JSON quedan congelados en la corrida que
se hizo a mano y la aplicacion muestra metricas distintas a las de la tesis.

Uso (desde la raiz del proyecto, tras ejecutar pipeline.py):
    python 10_generar_json_app.py

Salidas (se escriben en DESTINO, ver abajo):
    hexes.json         3,717 celdas x 24 columnas, formato de matriz
    mass.json          panel de tiendas con anio de apertura
    competencia.json   comercios de OpenStreetMap
    meta.json          backtesting, validacion cruzada, importancias, fuentes
"""
import json
import os
import sys

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

# ── Configuracion ────────────────────────────────────────────────────────
DESTINO = "vue/vue/javascript-version/public/data"
RECALCULAR_CV = True     # False = usa los valores de CV_FIJO (mas rapido)
CV_FIJO = [
    {"modelo": "Regresión logística", "pr_auc": 0.199, "roc_auc": 0.875},
    {"modelo": "Random Forest",       "pr_auc": 0.230, "roc_auc": 0.929},
    {"modelo": "XGBoost",             "pr_auc": 0.247, "roc_auc": 0.920},
    {"modelo": "Ensamble",            "pr_auc": 0.249, "roc_auc": 0.919},
]

COLS = ["h3", "dist", "lat", "lon", "pob_2017", "pob_k1", "pob_k2",
        "dens_hab_km2", "n_comp_osm_k1", "mass_k1_2026", "d_mass_2026",
        "n_poi_k1", "n_colegio_k1", "n_salud_k1", "n_mercado_k1",
        "n_comida_k1", "n_transp_k1", "n_banco_k1", "dens_intersec_km2",
        "long_princ_m", "p_potencial", "dem_res_n", "area_km2", "n_mz"]

ETIQUETAS = {
    "pob_2017": "Población del hexágono", "dens_hab_km2": "Densidad poblacional",
    "pob_k1": "Población a 500 m", "pob_k1_ext": "Población anillo externo",
    "pob_k2": "Población a 800 m", "pob_k3": "Población a 1.1 km",
    "n_poi_k1": "POIs de flujo (500 m)", "n_colegio_k1": "Colegios a 500 m",
    "n_mz": "N.º de manzanas", "dens_intersec_km2": "Densidad intersecciones",
    "long_princ_m": "Vías principales (m)", "pct_vial_princ": "% vía principal",
    "long_vial_m": "Longitud vial (m)", "n_intersec": "Intersecciones",
    "n_nodos": "Nodos viales", "area_km2": "Superficie",
    "n_comp_osm_k1": "Competencia a 500 m", "hab_por_comp_k1": "Hab. por competidor",
    "n_salud_k1": "Salud a 500 m", "n_banco_k1": "Bancos a 500 m",
    "n_mercado_k1": "Mercados a 500 m", "n_comida_k1": "Comida a 500 m",
    "n_transp_k1": "Transporte a 500 m", "long_vial_km_km2": "Densidad vial",
}

FUENTES = [
    {"n": "Censo Nacional INEI 2017", "t": "Manzanas con población",
     "v": "24,655 manzanas · 1,018,031 hab", "l": "Cartografía censal · uso público"},
    {"n": "OpenStreetMap", "t": "Competencia y puntos de interés",
     "v": "182 comercios · 3,072 POIs", "l": "ODbL · © colaboradores de OpenStreetMap"},
    {"n": "OpenStreetMap", "t": "Red vial caminable",
     "v": "Nodos y aristas", "l": "ODbL · © colaboradores de OpenStreetMap"},
    {"n": "Localizador público de la cadena", "t": "Red de retail moderno",
     "v": "136 tiendas nacionales", "l": "Sitio web público"},
    {"n": "Internet Archive", "t": "Versiones archivadas del localizador",
     "v": "4 snapshots anuales · 2023-2026", "l": "Público"},
]


def salir(msg):
    print(f"[!] {msg}")
    sys.exit(1)


for f in ("resultado_final.parquet", "features.parquet", "mass_panel.parquet",
          "resultados_backtesting.csv"):
    if not os.path.exists(f):
        salir(f"Falta {f}. Ejecuta primero: python pipeline.py")

os.makedirs(DESTINO, exist_ok=True)

# ═══════════════════════ 1. hexes.json ═══════════════════════
print("[1] hexes.json")
R = gpd.read_parquet("resultado_final.parquet")
R["DIST"] = R["DIST"].fillna("SIN_DATO").astype(str)
districts = sorted(R["DIST"].unique().tolist())
idx = {d: i for i, d in enumerate(districts)}

faltan = [c for c in COLS if c not in ("h3", "dist") and c not in R.columns]
if faltan:
    salir(f"Columnas ausentes en resultado_final.parquet: {faltan}")

rows = []
for r in R.itertuples():
    fila = [r.h3, idx[r.DIST]]
    for c in COLS[2:]:
        v = getattr(r, c)
        v = 0.0 if pd.isna(v) else float(v)
        fila.append(round(v, 5))
    rows.append(fila)

json.dump({"cols": COLS, "districts": districts, "rows": rows},
          open(f"{DESTINO}/hexes.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"    {len(rows):,} celdas · {len(COLS)} columnas · "
      f"{os.path.getsize(f'{DESTINO}/hexes.json')/1024:.0f} KB")

# ═══════════════════════ 2. mass.json ═══════════════════════
print("[2] mass.json")
M = gpd.read_parquet("mass_panel.parquet")
M = M.sort_values("anio").drop_duplicates("codigo", keep="first")
mass = [{"c": str(r.codigo), "d": str(getattr(r, "direccion", "") or ""),
         "dt": str(getattr(r, "distrito", "") or ""),
         "lat": round(float(r.lat), 5), "lon": round(float(r.lng), 5),
         "y": int(r.anio_apertura)} for r in M.itertuples()]
json.dump(mass, open(f"{DESTINO}/mass.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"    {len(mass)} tiendas")

# ═══════════════════════ 3. competencia.json ═══════════════════════
print("[3] competencia.json")
C = gpd.read_parquet("data/osm/competencia.parquet")
col_n = next((c for c in ("name", "nombre", "n") if c in C.columns), None)
col_s = next((c for c in ("shop", "tipo", "s") if c in C.columns), None)
comp = [{"n": str(r[col_n]) if col_n and pd.notna(r[col_n]) else "Sin nombre",
         "s": str(r[col_s]) if col_s and pd.notna(r[col_s]) else "shop",
         "lat": round(float(r.geometry.y), 5),
         "lon": round(float(r.geometry.x), 5)} for _, r in C.iterrows()]
json.dump(comp, open(f"{DESTINO}/competencia.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"    {len(comp)} comercios")

# ═══════════════════════ 4. meta.json ═══════════════════════
print("[4] meta.json")
B = pd.read_csv("resultados_backtesting.csv")
backtesting = [{"modelo": r["modelo"], "PR_AUC": round(r["PR_AUC"], 4),
                "ROC_AUC": round(r["ROC_AUC"], 4), "P@10": round(r["P@10"], 2),
                "P@20": round(r["P@20"], 2), "P@50": round(r["P@50"], 2),
                "R@50": round(r["R@50"], 4), "Lift@10%": round(r["Lift@10%"], 4),
                "acierto@20": int(r["acierto@20"])} for _, r in B.iterrows()]

F = pd.read_parquet("features.parquet")
PRED = [c for c in F.columns if c not in ("h3", "DIST", "es_nucleo", "bloque")
        and not c.startswith(("mass_", "d_mass_"))]
X = F[PRED].replace([np.inf, -np.inf], 0).fillna(0).values
y = F["mass_2026"].values
pw = (y == 0).sum() / max((y == 1).sum(), 1)

print("    entrenando Random Forest para importancias...")
rf = RandomForestClassifier(n_estimators=800, min_samples_leaf=5,
                            max_features="sqrt", class_weight="balanced_subsample",
                            n_jobs=-1, random_state=42).fit(X, y)
imp = pd.Series(rf.feature_importances_, index=PRED).sort_values(ascending=False)
importancias = [{"v": ETIQUETAS.get(k, k), "i": round(float(v), 4)}
                for k, v in imp.head(12).items()]
print("    top 3:", ", ".join(f"{d['v']} {d['i']:.4f}" for d in importancias[:3]))

if RECALCULAR_CV:
    print("    recalculando validación cruzada espacial (2-3 min)...")
    F["bloque"] = [h3.cell_to_parent(c, 6) for c in F["h3"]]
    oof = {k: np.zeros(len(F)) for k in ("LR", "RF", "XGB")}
    for tr, te in GroupKFold(n_splits=5).split(X, y, groups=F["bloque"]):
        sc = StandardScaler().fit(X[tr])
        oof["LR"][te] = LogisticRegression(max_iter=5000, class_weight="balanced", C=0.5)\
            .fit(sc.transform(X[tr]), y[tr]).predict_proba(sc.transform(X[te]))[:, 1]
        oof["RF"][te] = RandomForestClassifier(
            n_estimators=800, min_samples_leaf=5, max_features="sqrt",
            class_weight="balanced_subsample", n_jobs=-1, random_state=42)\
            .fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        oof["XGB"][te] = xgb.XGBClassifier(
            n_estimators=400, max_depth=3, learning_rate=0.05, subsample=0.8,
            colsample_bytree=0.7, reg_lambda=3.0, min_child_weight=5,
            scale_pos_weight=pw, eval_metric="aucpr", random_state=42)\
            .fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    eo = np.mean([pd.Series(v).rank(pct=True) for v in oof.values()], axis=0)
    nom = {"LR": "Regresión logística", "RF": "Random Forest", "XGB": "XGBoost"}
    cv = [{"modelo": nom[k], "pr_auc": round(average_precision_score(y, v), 3),
           "roc_auc": round(roc_auc_score(y, v), 3)} for k, v in oof.items()]
    cv.append({"modelo": "Ensamble",
               "pr_auc": round(average_precision_score(y, eo), 3),
               "roc_auc": round(roc_auc_score(y, eo), 3)})
else:
    cv = CV_FIJO
for c in cv:
    print(f"    {c['modelo']:22s} PR-AUC {c['pr_auc']:.3f}  ROC-AUC {c['roc_auc']:.3f}")

aperturas = M["anio_apertura"].value_counts().sort_index().to_dict()
aperturas = {str(int(k)): int(v) for k, v in aperturas.items()}

G = gpd.read_parquet("grid.parquet")
G["DIST"] = G["DIST"].fillna("SIN_DATO").astype(str)
pobd = (G[G["DIST"] != "SIN_DATO"].groupby("DIST")["pob_2017"].sum()
        .sort_values(ascending=False))
poblacion_distrito = [{"d": k, "p": int(round(v))} for k, v in pobd.items()]

json.dump({"backtesting": backtesting, "cv_espacial": cv,
           "importancias": importancias, "aperturas": aperturas,
           "poblacion_distrito": poblacion_distrito, "fuentes": FUENTES},
          open(f"{DESTINO}/meta.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print(f"    aperturas por año: {aperturas}")

total = sum(os.path.getsize(f"{DESTINO}/{f}") for f in
            ("hexes.json", "mass.json", "competencia.json", "meta.json"))
print(f"\n=== LISTO === {total/1024:.0f} KB en {DESTINO}")
print("Recarga la aplicación y verifica que /modelo muestre 3 aciertos y Lift 3.87")
