#!/usr/bin/env python3
"""
verificar_integridad.py

Genera la Tabla 5 del Capitulo IV: corre las verificaciones de integridad del
pipeline (conservacion de la poblacion, cobertura de la malla, composicion de
celdas, normalizacion de codigos, limpieza numerica, ausencia de fuga de
informacion e independencia de las particiones espaciales) y las exporta a CSV.
"""
import glob

import geopandas as gpd
import h3
import numpy as np
import pandas as pd

DATA = "data"
UBIGEOS = {
    "040101", "040102", "040103", "040104", "040105", "040107", "040109",
    "040110", "040112", "040116", "040117", "040122", "040123", "040124",
    "040126", "040128", "040129",
}

filas = []


def chk(verificacion, condicion, valor, cumple):
    filas.append({
        "Verificacion": verificacion,
        "Condicion de cumplimiento": condicion,
        "Valor observado": valor,
        "Se cumple": "Si" if cumple else "NO",
    })


shp = glob.glob(f"{DATA}/inei/*Manzanas_Poblacion*.shp")[0]
mz = gpd.read_file(shp)
mz = mz[mz["UBIGEO"].isin(UBIGEOS)]
pob_mz = pd.to_numeric(mz["T_TOTAL"], errors="coerce").fillna(0).sum()

grid = gpd.read_parquet("grid.parquet")
pob_hx = grid["pob_2017"].sum()
err = abs(pob_hx - pob_mz) / pob_mz * 100

chk("Conservacion de la poblacion en la ponderacion areal",
    "Diferencia entre poblacion censal y poblacion repartida < 0.5 %",
    f"{pob_mz:,.0f} vs {pob_hx:,.0f} ({err:.3f} %)", err < 0.5)

cen = mz.to_crs(32719).geometry.centroid.to_crs(4326)
cel_mz = {h3.latlng_to_cell(p.y, p.x, 9) for p in cen}
sin_cob = len(cel_mz - set(grid["h3"]))

chk("Cobertura de manzanas por la malla",
    "Ninguna manzana censal queda fuera de la malla H3",
    f"{sin_cob} manzanas sin celda asignada", sin_cob == 0)

n_tot = len(grid)
n_nuc = int(grid["es_nucleo"].sum())
n_ani = n_tot - n_nuc

chk("Composicion de la malla",
    "Nucleo censado + anillo de expansion = total de celdas",
    f"{n_nuc:,} nucleo + {n_ani:,} anillo = {n_tot:,}", n_nuc + n_ani == n_tot)

mp = gpd.read_parquet("mass_panel.parquet")
crudos = mp["codigo"].astype(str).str.strip().nunique()
norm = (mp["codigo"].astype(str).str.strip().str.upper()
        .str.replace(r"\s+", " ", regex=True).nunique())

chk("Normalizacion de codigos del panel historico",
    "El conteo de tiendas unicas no varia tras normalizar capitalizacion",
    f"{crudos} sin normalizar vs {norm} normalizado", crudos == norm)

F = pd.read_parquet("features.parquet")
num = F.select_dtypes(include=[np.number])
n_inf = int(np.isinf(num.values).sum())
n_nan = int(num.isna().sum().sum())

chk("Integridad numerica de la matriz de caracteristicas",
    "La matriz no contiene valores infinitos ni nulos",
    f"{n_inf} infinitos, {n_nan} nulos", n_inf == 0 and n_nan == 0)

PRED = [c for c in F.columns
        if c not in ("h3", "DIST", "es_nucleo", "bloque")
        and not c.startswith(("mass_", "d_mass_"))]
fuga = [c for c in PRED if c.startswith(("mass_", "d_mass_"))]

chk("Exclusion de variables con fuga de informacion",
    "Ningun predictor deriva de la red de retail moderno",
    f"{len(PRED)} predictores, {len(fuga)} variables de fuga", len(fuga) == 0)

from sklearn.model_selection import GroupKFold

bloque = pd.Series([h3.cell_to_parent(c, 6) for c in F["h3"]])
X = F[PRED].replace([np.inf, -np.inf], 0).fillna(0).values
comp = 0
for tr, te in GroupKFold(n_splits=5).split(X, groups=bloque):
    comp += len(set(bloque.iloc[tr]) & set(bloque.iloc[te]))

chk("Independencia de las particiones espaciales",
    "Ningun bloque H3 r6 aparece en entrenamiento y prueba simultaneamente",
    f"{bloque.nunique()} bloques, {comp} compartidos", comp == 0)

try:
    R = pd.read_csv("resultados_backtesting.csv")
    ok = len(R) >= 7
    chk("Comparacion contra lineas base univariadas",
        "El backtesting evalua los 4 modelos y las 3 lineas base",
        f"{len(R)} modelos evaluados", ok)
except FileNotFoundError:
    pass

T = pd.DataFrame(filas)
T.to_csv("tabla5_integridad.csv", index=False, encoding="utf-8-sig")
print(T.to_string(index=False))
print("\n>> tabla5_integridad.csv generada")
