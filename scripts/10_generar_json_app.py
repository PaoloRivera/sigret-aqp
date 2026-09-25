#!/usr/bin/env python3
"""
10_generar_json_app.py
Regenera los cuatro JSON que consume la aplicacion web a partir de las
salidas actuales del pipeline.

ESTE ES EL PASO QUE FALTABA: pipeline.py produce .parquet, pero la app web
sirve .json. Sin este script los JSON quedan congelados en la corrida que
se hizo a mano y la aplicacion muestra metricas distintas a las de la tesis.

Uso (desde la raiz del proyecto, tras ejecutar pipeline.py):
    python scripts/10_generar_json_app.py

Salidas (se escriben en DESTINO, ver abajo):
    hexes.json         3,717 celdas x 25 columnas, formato de matriz
    mass.json          panel de tiendas con anio de apertura
    competencia.json   comercios de OpenStreetMap
    meta.json          backtesting, validacion cruzada, importancias, fuentes
"""
import json
import os
import sys

import glob
from datetime import date

import geopandas as gpd
import pandas as pd

# ── Configuracion ────────────────────────────────────────────────────────
RES = "resultados"
DESTINO = "app_web/public/data"

COLS = ["h3", "dist", "lat", "lon", "pob_2017", "pob_k1", "pob_k2",
        "dens_hab_km2", "n_comp_osm_k1", "mass_k1_2026", "d_mass_2026",
        "n_poi_k1", "n_colegio_k1", "n_salud_k1", "n_mercado_k1",
        "n_comida_k1", "n_transp_k1", "n_banco_k1", "dens_intersec_km2",
        "long_princ_m", "p_potencial", "dem_res_n", "area_km2", "n_mz", "mass_2026"]

# Coordenadas a 5 decimales (~1 m), indices a 4 y conteos, poblaciones y
# distancias a enteros, para mantener el JSON liviano
DECIMALES = {"lat": 5, "lon": 5, "p_potencial": 4, "dem_res_n": 4, "area_km2": 4}

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
     "v": "21,705 manzanas · 1,018,031 hab", "l": "Cartografía censal · uso público"},
    {"n": "OpenStreetMap", "t": "Competencia y puntos de interés",
     "v": "182 comercios · 3,072 POIs", "l": "ODbL · © colaboradores de OpenStreetMap"},
    {"n": "OpenStreetMap", "t": "Red vial caminable",
     "v": "Nodos y aristas", "l": "ODbL · © colaboradores de OpenStreetMap"},
    {"n": "Localizador público de la cadena", "t": "Red de retail moderno",
     "v": "127 tiendas con coordenadas", "l": "Sitio web público"},
    {"n": "Internet Archive", "t": "Versiones archivadas del localizador",
     "v": "4 snapshots · 2024-2026", "l": "Público"},
]


def salir(msg):
    print(f"[!] {msg}")
    sys.exit(1)


for f in ("resultado_final.parquet", "mass_panel.parquet", "resultados_backtesting.csv",
          "resultados_cv.csv", "importancia_variables.csv"):
    if not os.path.exists(f"{RES}/{f}"):
        salir(f"Falta {RES}/{f}. Ejecuta primero: python pipeline.py")

os.makedirs(DESTINO, exist_ok=True)

# ═══════════════════════ 1. hexes.json ═══════════════════════
print("[1] hexes.json")
R = gpd.read_parquet(f"{RES}/resultado_final.parquet")
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
        fila.append(round(v, DECIMALES.get(c, 0)))
    rows.append(fila)

json.dump({"cols": COLS, "districts": districts, "rows": rows},
          open(f"{DESTINO}/hexes.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"    {len(rows):,} celdas · {len(COLS)} columnas · "
      f"{os.path.getsize(f'{DESTINO}/hexes.json')/1024:.0f} KB")

# ═══════════════════════ 2. mass.json ═══════════════════════
print("[2] mass.json")
M = gpd.read_parquet(f"{RES}/mass_panel.parquet")
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
B = pd.read_csv(f"{RES}/resultados_backtesting.csv")
backtesting = [{"modelo": r["modelo"], "PR_AUC": round(r["PR_AUC"], 4),
                "ROC_AUC": round(r["ROC_AUC"], 4), "P@10": round(r["P@10"], 2),
                "P@20": round(r["P@20"], 2), "P@50": round(r["P@50"], 2),
                "R@50": round(r["R@50"], 4), "Lift@10%": round(r["Lift@10%"], 4),
                "acierto@20": int(r["acierto@20"])} for _, r in B.iterrows()]

# Validacion cruzada e importancias: las mismas que calculo pipeline.py
NOM_CV = {"LR": "Regresión logística", "RF": "Random Forest",
          "XGB": "XGBoost", "ENS": "Ensamble"}
cv = [{"modelo": NOM_CV[r["modelo"]], "pr_auc": round(r["PR_AUC"], 3),
       "roc_auc": round(r["ROC_AUC"], 3)}
      for _, r in pd.read_csv(f"{RES}/resultados_cv.csv").iterrows()]
for c in cv:
    print(f"    {c['modelo']:22s} PR-AUC {c['pr_auc']:.3f}  ROC-AUC {c['roc_auc']:.3f}")

I = pd.read_csv(f"{RES}/importancia_variables.csv").head(12)
importancias = [{"v": ETIQUETAS.get(r.variable, r.variable), "i": round(float(r.importancia), 4)}
                for r in I.itertuples()]
print("    top 3:", ", ".join(f"{d['v']} {d['i']:.4f}" for d in importancias[:3]))

aperturas = M["anio_apertura"].value_counts().sort_index().to_dict()
aperturas = {str(int(k)): int(v) for k, v in aperturas.items()}

# Poblacion censal por distrito (total de manzanas por UBIGEO)
UBIGEOS = {
    "040101": "AREQUIPA", "040102": "ALTO SELVA ALEGRE", "040103": "CAYMA",
    "040104": "CERRO COLORADO", "040105": "CHARACATO", "040107": "JACOBO HUNTER",
    "040109": "MARIANO MELGAR", "040110": "MIRAFLORES", "040112": "PAUCARPATA",
    "040116": "SABANDIA", "040117": "SACHACA", "040122": "SOCABAYA",
    "040123": "TIABAYA", "040124": "UCHUMAYO", "040126": "YANAHUARA",
    "040128": "YURA", "040129": "JLBR",
}
mz = gpd.read_file(glob.glob("data/inei/*Manzanas_Poblacion*.dbf")[0], ignore_geometry=True)
pobd = (mz.groupby(mz["UBIGEO"].map(UBIGEOS))["T_TOTAL"].sum()
        .sort_values(ascending=False))
poblacion_distrito = [{"d": k, "p": int(round(v))} for k, v in pobd.items()]

# Tasa base de la validacion cruzada: celdas con tienda en 2026
F = pd.read_parquet(f"{RES}/features.parquet", columns=["mass_2026"])
tasa_base_cv = round(float((F["mass_2026"] > 0).mean()), 4)

json.dump({"generado": date.today().isoformat(), "backtesting": backtesting, "cv_espacial": cv, "tasa_base_cv": tasa_base_cv,
           "importancias": importancias, "aperturas": aperturas,
           "poblacion_distrito": poblacion_distrito, "fuentes": FUENTES},
          open(f"{DESTINO}/meta.json", "w", encoding="utf-8"),
          ensure_ascii=False, separators=(",", ":"))
print(f"    aperturas por año: {aperturas}")

total = sum(os.path.getsize(f"{DESTINO}/{f}") for f in
            ("hexes.json", "mass.json", "competencia.json", "meta.json"))
print(f"\n=== LISTO === {total/1024:.0f} KB en {DESTINO}")
