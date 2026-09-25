#!/usr/bin/env python3
"""
pipeline.py

Pipeline reproducible completo para la localizacion optima de minimarkets en
Arequipa Metropolitana: construye la malla H3 con poblacion censal, reconstruye
la red historica de tiendas Mass, genera la matriz de features, entrena y valida
los modelos de prediccion y calcula el score y el ranking final de ubicaciones.
"""
import glob
import os
import re

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import xgboost as xgb
from bs4 import BeautifulSoup
from scipy.spatial import cKDTree
from shapely.geometry import Point, Polygon
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

np.random.seed(42)
DATA = "data"
OUT = "resultados"
UTM = 32719
RES = 9

UBIGEOS = {
    "040101": "AREQUIPA", "040102": "ALTO SELVA ALEGRE", "040103": "CAYMA",
    "040104": "CERRO COLORADO", "040105": "CHARACATO", "040107": "JACOBO HUNTER",
    "040109": "MARIANO MELGAR", "040110": "MIRAFLORES", "040112": "PAUCARPATA",
    "040116": "SABANDIA", "040117": "SACHACA", "040122": "SOCABAYA",
    "040123": "TIABAYA", "040124": "UCHUMAYO", "040126": "YANAHUARA",
    "040128": "YURA", "040129": "JLBR",
}


def construir_malla():
    print("[1] Malla H3 y poblacion censal")
    shp = glob.glob(f"{DATA}/inei/*Manzanas_Poblacion*.shp")[0]
    mz = gpd.read_file(shp)[
        ["UBIGEO", "ZONA", "MANZANA_ID", "T_TOTAL", "T_HOMBRES", "T_MUJERES", "geometry"]]
    mz["DIST"] = mz["UBIGEO"].map(UBIGEOS)
    mz = mz[mz["DIST"].notna()]
    mz = mz[mz.geometry.notna() & ~mz.geometry.is_empty].copy()
    for c in ("T_TOTAL", "T_HOMBRES", "T_MUJERES"):
        mz[c] = pd.to_numeric(mz[c], errors="coerce").fillna(0)
    print(f"    manzanas: {len(mz):,} | poblacion: {mz['T_TOTAL'].sum():,.0f}")

    cells = set()
    for g in mz.geometry:
        try:
            cells |= set(h3.polygon_to_cells(
                h3.LatLngPoly([(y, x) for x, y in g.exterior.coords]), RES))
        except Exception:
            pass
    cen = mz.to_crs(UTM).geometry.centroid.to_crs(4326)
    cells |= {h3.latlng_to_cell(p.y, p.x, RES) for p in cen}
    for g in mz.geometry:
        try:
            for x, y in list(g.exterior.coords)[::3]:
                cells.add(h3.latlng_to_cell(y, x, RES))
        except Exception:
            pass

    nucleo = set(cells)
    todos = set(cells)
    for c in nucleo:
        todos |= set(h3.grid_disk(c, 1))

    grid = gpd.GeoDataFrame(
        {"h3": sorted(todos)},
        geometry=[Polygon([(lng, lat) for lat, lng in h3.cell_to_boundary(c)])
                  for c in sorted(todos)], crs="EPSG:4326")
    grid["es_nucleo"] = grid["h3"].isin(nucleo)

    mzp = mz.to_crs(UTM)
    mzp["area_mz"] = mzp.area
    mzp = mzp[mzp["area_mz"] > 0]
    inter = gpd.overlay(
        mzp[["T_TOTAL", "T_HOMBRES", "T_MUJERES", "area_mz", "DIST", "geometry"]],
        grid.to_crs(UTM)[["h3", "geometry"]], how="intersection")
    inter["frac"] = inter.area / inter["area_mz"]
    for c in ("T_TOTAL", "T_HOMBRES", "T_MUJERES"):
        inter[c] = inter[c] * inter["frac"]

    agg = inter.groupby("h3").agg(pob_2017=("T_TOTAL", "sum"),
                                  pob_h=("T_HOMBRES", "sum"),
                                  pob_m=("T_MUJERES", "sum"),
                                  n_mz=("area_mz", "size")).reset_index()
    dom = (inter.groupby(["h3", "DIST"])["T_TOTAL"].sum().reset_index()
           .sort_values("T_TOTAL", ascending=False).drop_duplicates("h3")[["h3", "DIST"]])
    grid = grid.merge(agg, on="h3", how="left").merge(dom, on="h3", how="left")
    for c in ("pob_2017", "pob_h", "pob_m", "n_mz"):
        grid[c] = grid[c].fillna(0)
    grid["area_km2"] = grid.to_crs(UTM).area / 1e6
    grid["dens_hab_km2"] = grid["pob_2017"] / grid["area_km2"]

    print(f"    hexagonos: {len(grid):,} | poblacion repartida: {grid['pob_2017'].sum():,.0f}")
    grid.to_parquet(f"{OUT}/grid.parquet")
    return grid


def _num(v):
    if not v:
        return None
    m = re.search(r"-?\d+\.?\d*", str(v).replace(",", " "))
    return float(m.group()) if m else None


def _extraer_mass(path):
    soup = BeautifulSoup(open(path, encoding="utf-8", errors="ignore").read(), "lxml")
    rows = []
    for li in soup.find_all("li", attrs={"data-lat": True}):
        cod = li.find(class_="tienda-direccion")
        rows.append({"direccion": li.get("data-address"),
                     "distrito": li.get("data-distrito"),
                     "ciudad": li.get("data-ciudad"),
                     "lat": _num(li.get("data-lat")), "lng": _num(li.get("data-lng")),
                     "codigo": cod.get_text(strip=True) if cod else None})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df = df[df["ciudad"] == "AREQUIPA"].dropna(subset=["lat", "lng"])
    return df[df["lat"].between(-16.8, -16.0) & df["lng"].between(-72.0, -71.2)].copy()


def panel_mass():
    print("[2] Red historica de tiendas Mass")
    partes = []
    for f in sorted(glob.glob(f"{DATA}/mass/wayback/*.html")):
        anio = int(os.path.basename(f).split("_")[1][:4])
        d = _extraer_mass(f)
        if len(d):
            d["anio"] = anio
            partes.append(d)
            print(f"    snapshot {anio}: {len(d)} tiendas")
    act = _extraer_mass(f"{DATA}/mass/mass_ubicame.html")
    act["anio"] = 2026
    partes.append(act)
    print(f"    snapshot actual: {len(act)} tiendas")

    H = pd.concat(partes, ignore_index=True)
    H["codigo"] = (H["codigo"].astype(str).str.strip().str.upper()
                   .str.replace(r"\s+", " ", regex=True))
    H = H.drop_duplicates(["codigo", "anio"])
    H["h3"] = [h3.latlng_to_cell(r.lat, r.lng, RES) for r in H.itertuples()]
    H = H.merge(H.groupby("codigo")["anio"].min().rename("anio_apertura"), on="codigo")
    gpd.GeoDataFrame(H, geometry=[Point(r.lng, r.lat) for r in H.itertuples()],
                     crs="EPSG:4326").to_parquet(f"{OUT}/mass_panel.parquet")
    u = H.sort_values("anio").drop_duplicates("codigo", keep="last")
    print(f"    tiendas unicas: {H['codigo'].nunique()} | hexagonos: {H['h3'].nunique()}")
    print(f"    aperturas por anio:\n{u['anio_apertura'].value_counts().sort_index().to_string()}")
    return H


GRUPOS_POI = {
    "colegio": dict(amenity=["school", "college", "university"]),
    "salud":   dict(amenity=["pharmacy", "clinic", "hospital"]),
    "banco":   dict(amenity=["bank", "atm"]),
    "mercado": dict(amenity=["marketplace"]),
    "comida":  dict(amenity=["restaurant", "fast_food"]),
    "transp":  dict(amenity=["bus_station"], highway=["bus_stop"]),
    "culto":   dict(amenity=["place_of_worship"]),
    "grifo":   dict(amenity=["fuel"]),
    "panader": dict(shop=["bakery", "butcher", "greengrocer"]),
}


def features(grid, mass):
    print("[3] Ingenieria de features")
    poi = gpd.read_parquet(f"{DATA}/osm/poi_flujo.parquet")
    comp = gpd.read_parquet(f"{DATA}/osm/competencia.parquet")
    edges = gpd.read_parquet(f"{DATA}/osm/red_edges.parquet")
    nodes = gpd.read_parquet(f"{DATA}/osm/red_nodes.parquet")

    F = grid[["h3", "DIST", "pob_2017", "area_km2", "dens_hab_km2",
              "es_nucleo", "n_mz"]].copy()
    F["DIST"] = F["DIST"].fillna("SIN_DATO").astype(str)

    pob = dict(zip(grid["h3"], grid["pob_2017"]))
    for k in (1, 2, 3):
        F[f"pob_k{k}"] = [sum(pob.get(v, 0) for v in h3.grid_disk(c, k)) for c in F["h3"]]
    F["pob_k1_ext"] = F["pob_k1"] - F["pob_2017"]

    nodes["h3"] = [h3.latlng_to_cell(y, x, RES)
                   for y, x in zip(nodes.geometry.y, nodes.geometry.x)]
    F = F.merge(nodes.groupby("h3").size().rename("n_nodos").reset_index(),
                on="h3", how="left")
    nodes["_i"] = (pd.to_numeric(nodes["street_count"], errors="coerce") >= 3).astype(int)
    F = F.merge(nodes.groupby("h3")["_i"].sum().rename("n_intersec").reset_index(),
                on="h3", how="left")

    gp = grid.to_crs(UTM)
    ed = edges.to_crs(UTM)
    ed["len_m"] = pd.to_numeric(ed["length"], errors="coerce").fillna(ed.length)
    jn = gpd.sjoin(ed[["highway", "len_m", "geometry"]], gp[["h3", "geometry"]],
                   how="inner", predicate="intersects")
    F = F.merge(jn.groupby("h3")["len_m"].sum().rename("long_vial_m").reset_index(),
                on="h3", how="left")
    pr = jn[jn["highway"].str.contains("primary|secondary|trunk|tertiary", na=False)]
    F = F.merge(pr.groupby("h3")["len_m"].sum().rename("long_princ_m").reset_index(),
                on="h3", how="left")

    for nom, filt in GRUPOS_POI.items():
        m = pd.Series(False, index=poi.index)
        for col, vals in filt.items():
            if col in poi.columns:
                m |= poi[col].isin(vals)
        sub = poi[m]
        if len(sub) == 0:
            F[f"n_{nom}"] = 0
            continue
        j = gpd.sjoin(sub.to_crs(UTM)[["geometry"]], gp[["h3", "geometry"]],
                      how="inner", predicate="within")
        F = F.merge(j.groupby("h3").size().rename(f"n_{nom}").reset_index(),
                    on="h3", how="left")

    F = F.fillna({c: 0 for c in F.columns if c != "DIST"})
    nombres = list(GRUPOS_POI)
    for nom in nombres:
        d = dict(zip(F["h3"], F[f"n_{nom}"]))
        F[f"n_{nom}_k1"] = [sum(d.get(v, 0) for v in h3.grid_disk(c, 1)) for c in F["h3"]]
    F["n_poi_k1"] = F[[f"n_{n}_k1" for n in nombres]].sum(axis=1)

    comp["h3"] = [h3.latlng_to_cell(p.y, p.x, RES) for p in comp.geometry]
    F = F.merge(comp.groupby("h3").size().rename("n_comp_osm").reset_index(),
                on="h3", how="left").fillna({"n_comp_osm": 0})
    d = dict(zip(F["h3"], F["n_comp_osm"]))
    F["n_comp_osm_k1"] = [sum(d.get(v, 0) for v in h3.grid_disk(c, 1)) for c in F["h3"]]

    cen = gp.geometry.centroid
    XY = np.c_[cen.x, cen.y]
    mp = gpd.GeoDataFrame(mass, geometry=[Point(r.lng, r.lat) for r in mass.itertuples()],
                          crs="EPSG:4326").to_crs(UTM)
    for anio in (2024, 2025, 2026):
        sub = mp[mp["anio_apertura"] <= anio]
        if sub.empty:
            continue
        dist, _ = cKDTree(np.c_[sub.geometry.x, sub.geometry.y]).query(XY, k=1)
        F[f"d_mass_{anio}"] = dist
        F[f"mass_{anio}"] = F["h3"].isin(set(sub["h3"])).astype(int)
        dd = dict(zip(F["h3"], F[f"mass_{anio}"]))
        for k in (1, 2):
            F[f"mass_k{k}_{anio}"] = [sum(dd.get(v, 0) for v in h3.grid_disk(c, k))
                                      for c in F["h3"]]

    F["hab_por_comp_k1"] = F["pob_k1"] / (F["n_comp_osm_k1"] + 1)
    F["dens_intersec_km2"] = F["n_intersec"] / F["area_km2"]
    F["long_vial_km_km2"] = (F["long_vial_m"] / 1000) / F["area_km2"]
    F["pct_vial_princ"] = F["long_princ_m"] / (F["long_vial_m"] + 1)

    print(f"    matriz: {F.shape[0]:,} hexagonos x {F.shape[1]} columnas")
    F.to_parquet(f"{OUT}/features.parquet")
    return F


def modelos(F):
    print("[4] Entrenamiento y validacion")
    PRED = [c for c in F.columns
            if c not in ("h3", "DIST", "es_nucleo")
            and not c.startswith(("mass_", "d_mass_"))]
    X = F[PRED].replace([np.inf, -np.inf], 0).fillna(0).values

    def hacer_modelos(y):
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

    y24 = F["mass_2024"].values
    abrio = ((F["mass_2026"] == 1) & (F["mass_2024"] == 0)).astype(int).values
    viable = (F["pob_k1"] >= 1500).values
    cand = viable & (y24 == 0)
    print(f"    candidatos viables sin Mass en 2024: {cand.sum():,}")
    print(f"    aperturas reales 2025-26: {abrio[cand].sum()} "
          f"({100*abrio[cand].mean():.2f}%)")

    def evaluar(score, nombre):
        s, t = score[cand], abrio[cand]
        o = np.argsort(-s)
        n10 = max(int(0.10 * len(s)), 1)
        d = {"modelo": nombre, "PR_AUC": average_precision_score(t, s),
             "ROC_AUC": roc_auc_score(t, s)}
        for k in (10, 20, 50):
            d[f"P@{k}"] = t[o[:k]].sum() / k
            d[f"R@{k}"] = t[o[:k]].sum() / t.sum()
        d["Lift@10%"] = t[o[:n10]].mean() / t.mean()
        d["acierto@20"] = int(t[o[:20]].sum())
        return d

    res = [evaluar(F["dens_hab_km2"].values, "Baseline densidad"),
           evaluar(F["pob_k1"].values, "Baseline pob. k1"),
           evaluar(F["n_poi_k1"].values, "Baseline POIs k1")]
    M24 = hacer_modelos(y24)
    probs = {}
    for nom, (tipo, sc, m) in M24.items():
        p = m.predict_proba(sc.transform(X) if tipo == "s" else X)[:, 1]
        probs[nom] = p
        res.append(evaluar(p, {"LR": "Regresion logistica", "RF": "Random Forest",
                               "XGB": "XGBoost"}[nom]))
    ens = np.mean([pd.Series(p).rank(pct=True) for p in probs.values()], axis=0)
    res.append(evaluar(ens, "Ensamble (rank avg)"))
    R = pd.DataFrame(res)
    print("\n    --- Backtesting temporal ---")
    print(R[["modelo", "PR_AUC", "ROC_AUC", "P@20", "Lift@10%", "acierto@20"]]
          .round(3).to_string(index=False))
    R.to_csv(f"{OUT}/resultados_backtesting.csv", index=False)

    y = F["mass_2026"].values
    F["bloque"] = [h3.cell_to_parent(c, 6) for c in F["h3"]]
    pw = (y == 0).sum() / (y == 1).sum()
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

    print(f"\n    --- Validacion cruzada espacial ({F['bloque'].nunique()} bloques H3 r6) ---")
    oof["ENS"] = np.mean([pd.Series(v).rank(pct=True) for v in oof.values()], axis=0)
    cv = []
    for k, v in oof.items():
        cv.append({"modelo": k, "PR_AUC": average_precision_score(y, v),
                   "ROC_AUC": roc_auc_score(y, v)})
        print(f"    {k:4s}  PR-AUC {cv[-1]['PR_AUC']:.3f}   ROC-AUC {cv[-1]['ROC_AUC']:.3f}")
    pd.DataFrame(cv).to_csv(f"{OUT}/resultados_cv.csv", index=False)

    MF = hacer_modelos(y)
    F["p_potencial"] = np.mean(
        [pd.Series(m.predict_proba(sc.transform(X) if t == "s" else X)[:, 1]).rank(pct=True)
         for t, sc, m in MF.values()], axis=0)
    imp = pd.Series(MF["RF"][2].feature_importances_, index=PRED).sort_values(ascending=False)
    imp.rename_axis("variable").rename("importancia").to_csv(f"{OUT}/importancia_variables.csv")
    print("\n    Top 10 variables:")
    print("    " + imp.head(10).round(4).to_string().replace("\n", "\n    "))
    return F


def score(F, grid, gasto_mes=180, w_pot=0.45, pen_mass=0.60, radio=800, pob_min=1500):
    print("[5] Score y ranking")
    F["demanda_pot"] = F["pob_k1"] * gasto_mes
    F["oferta_k1"] = F["n_comp_osm_k1"] + F["mass_k1_2026"] * 3
    F["dem_residual"] = F["demanda_pot"] / (1 + F["oferta_k1"])
    F["dem_res_n"] = F["dem_residual"].rank(pct=True)
    F["riesgo_mass"] = np.clip(1 - F["d_mass_2026"] / radio, 0, 1)
    F["viable"] = (F["pob_k1"] >= pob_min) & (F["mass_2026"] == 0)
    F["SCORE"] = ((w_pot * F["p_potencial"] + (1 - w_pot) * F["dem_res_n"])
                  * (1 - pen_mass * F["riesgo_mass"]))
    F.loc[~F["viable"], "SCORE"] = 0.0

    out = F.merge(grid[["h3", "geometry"]], on="h3")
    out = gpd.GeoDataFrame(out, geometry="geometry", crs="EPSG:4326")
    cen = out.to_crs(UTM).geometry.centroid.to_crs(4326)
    out["lat"], out["lon"] = cen.y, cen.x
    out.to_parquet(f"{OUT}/resultado_final.parquet")

    top = out[out["viable"]].nlargest(20, "SCORE")
    print(f"\n    --- TOP 20 UBICACIONES ---")
    print(top[["DIST", "pob_k1", "n_comp_osm_k1", "d_mass_2026", "p_potencial",
               "SCORE", "lat", "lon"]].round(3).to_string(index=False))
    print(f"\n    Top-50 por distrito:")
    print("    " + out[out["viable"]].nlargest(50, "SCORE")["DIST"]
          .value_counts().to_string().replace("\n", "\n    "))
    return out


if __name__ == "__main__":
    grid = construir_malla()
    mass = panel_mass()
    F = features(grid, mass)
    F = modelos(F)
    out = score(F, grid)
    print("\n=== PIPELINE COMPLETO ===")
    print(f"  en {OUT}/: grid.parquet · features.parquet · resultado_final.parquet")
    print("  resultados_backtesting.csv · resultados_cv.csv · importancia_variables.csv")
