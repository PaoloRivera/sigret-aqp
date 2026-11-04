#!/usr/bin/env python3
"""
poblacion_actualizada.py

Actualiza la poblacion de cada celda H3 desde el Censo 2017 (manzanas) hasta
el Censo 2025 y la reconstruye al corte del backtesting (31-12-2024).

Metodo (reparto dasimetrico del crecimiento):
  1. Crecimiento de cada distrito: G_d = poblacion censada 2025 - poblacion
     censada 2017 (INEI, 2018 e INEI, 2026).
  2. Edificaciones detectadas por satelite (Google Open Buildings 2.5D
     Temporal; Sirko et al., 2023), capas de 2017 y 2023: se suman por celda
     H3 r9 en todo el territorio de cada distrito, no solo dentro de la malla.
  3. El crecimiento de cada distrito se reparte entre sus celdas en
     proporcion a las edificaciones nuevas (2023 - 2017, sin valores
     negativos):  pob_2025 = pob_2017 + G_d * dB_celda / dB_distrito.
     Si el distrito perdio poblacion (G_d < 0), cada celda se reduce en la
     misma proporcion que el distrito: pob_2025 = pob_2017 * P2025_d / P2017_d.
  4. Poblacion al corte del backtesting (31-12-2024): interpolacion lineal
     entre las fechas censales (22-10-2017 y el punto medio del
     empadronamiento 2025, 19-09-2025).
  5. Validacion del indicador: (a) se reparte la poblacion 2017 de cada
     distrito segun las edificaciones de 2017 y se compara con la poblacion
     censal por manzanas de cada celda; (b) se compara, entre distritos, el
     crecimiento censal 2017-2025 con las edificaciones nuevas.

Entradas:
  data/edificaciones/ob_temporal_aqp_50m.tif   raster exportado de Earth Engine
      (bandas cnt_, area_, vol_ de 2017 y 2023; script en data/edificaciones/
      exportar_open_buildings.js). Se resume una sola vez en
      data/edificaciones/edificaciones_h3.csv, que es lo que usa el pipeline.
  data/inei/limites_distritales_aqp.geojson    limites distritales (INEI)
  data/inei/poblacion_censada_distritos.csv    poblacion censada 2017 y 2025

Salidas (resultados/):
  poblacion_celdas.parquet       pob_2017, pob_2024, pob_2025 por celda
  poblacion_distritos.csv        crecimiento y reparto por distrito
  validacion_edificaciones.csv   ajuste del indicador con el censo 2017

Uso (desde la raiz del proyecto; pipeline.py lo llama automaticamente):
    python poblacion_actualizada.py
"""
import glob
import os
from datetime import date

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
from scipy import stats

DATA = "data"
RES = 9
UTM = 32719
RASTER = f"{DATA}/edificaciones/ob_temporal_aqp_50m.tif"
RESUMEN = f"{DATA}/edificaciones/edificaciones_h3.csv"
LIMITES = f"{DATA}/inei/limites_distritales_aqp.geojson"
CENSOS = f"{DATA}/inei/poblacion_censada_distritos.csv"
BANDAS = ["cnt_2017", "area_2017", "vol_2017", "cnt_2023", "area_2023", "vol_2023"]
# El raster exportado guarda, en cada pixel de 50 m, el valor medio por pixel de
# 4 m (comprobado contra sumas a 4 m con reduceRegion en Earth Engine); por eso
# se multiplica por (50/4)^2 para obtener totales por pixel de 50 m.
FACTOR_50M = (50 / 4) ** 2

# Fechas censales: 22-10-2017 y punto medio del empadronamiento 2025
# (agosto a noviembre de 2025). Corte del backtesting: 31-12-2024.
F_2017, F_2025, F_CORTE = date(2017, 10, 22), date(2025, 9, 19), date(2024, 12, 31)
FRAC_CORTE = (F_CORTE - F_2017).days / (F_2025 - F_2017).days

UBIGEO_A_DIST = {
    "040101": "AREQUIPA", "040102": "ALTO SELVA ALEGRE", "040103": "CAYMA",
    "040104": "CERRO COLORADO", "040105": "CHARACATO", "040107": "JACOBO HUNTER",
    "040109": "MARIANO MELGAR", "040110": "MIRAFLORES", "040112": "PAUCARPATA",
    "040116": "SABANDIA", "040117": "SACHACA", "040122": "SOCABAYA",
    "040123": "TIABAYA", "040124": "UCHUMAYO", "040126": "YANAHUARA",
    "040128": "YURA", "040129": "JLBR",
}
# Indicadores candidatos para repartir la poblacion. La banda area_ sale
# redondeada a enteros en el exportado y no se usa como indicador.
PROXIES = {"cnt": "Numero de edificaciones", "vol": "Volumen construido"}


def edificaciones_por_celda():
    """Suma por celda H3 r9 de cada banda del raster (se guarda en RESUMEN)."""
    if os.path.exists(RESUMEN):
        return pd.read_csv(RESUMEN, index_col="h3")
    import rasterio
    from pyproj import Transformer
    partes = []
    for a in sorted(glob.glob(RASTER.replace(".tif", "*.tif"))):
        with rasterio.open(a) as r:
            nombres = list(r.descriptions) if all(r.descriptions) else BANDAS[:r.count]
            A = np.nan_to_num(r.read().astype("float64"), nan=0.0)
            filas, cols = np.nonzero(A.sum(axis=0) > 0)
            xs, ys = rasterio.transform.xy(r.transform, filas, cols, offset="center")
            lon, lat = Transformer.from_crs(r.crs, "EPSG:4326", always_xy=True).transform(
                np.asarray(xs), np.asarray(ys))
            df = pd.DataFrame({n: A[i, filas, cols] * FACTOR_50M for i, n in enumerate(nombres)})
            df["h3"] = [h3.latlng_to_cell(la, lo, RES) for la, lo in zip(lat, lon)]
            partes.append(df)
    if not partes:
        raise SystemExit(f"No se encontro {RASTER} ni {RESUMEN}")
    E = pd.concat(partes).groupby("h3")[BANDAS].sum()
    E.round(3).to_csv(RESUMEN)
    return pd.read_csv(RESUMEN, index_col="h3")


def distrito_inei(celdas):
    """Distrito INEI que contiene el centro de cada celda (o el mas cercano a < 2 km)."""
    lim = gpd.read_file(LIMITES)
    lim["DIST"] = lim["IDDIST"].map(UBIGEO_A_DIST)
    ll = [h3.cell_to_latlng(c) for c in celdas]
    pts = gpd.GeoDataFrame({"h3": list(celdas)},
                           geometry=gpd.points_from_xy([x[1] for x in ll], [x[0] for x in ll]),
                           crs=4326).to_crs(UTM)
    j = gpd.sjoin_nearest(pts, lim.to_crs(UTM)[["DIST", "geometry"]], how="left",
                          max_distance=2000).drop_duplicates("h3")
    return j.set_index("h3")["DIST"]


def calcular(grid, proxy=None, verbose=True):
    """grid: salida de construir_malla() (h3, DIST, pob_2017).
    Devuelve (celdas, distritos, validacion)."""
    cen = pd.read_csv(CENSOS, dtype={"ubigeo": str})
    cen["DIST"] = cen["ubigeo"].map(UBIGEO_A_DIST)
    cen = cen.set_index("DIST")

    E = edificaciones_por_celda()
    g = grid.set_index("h3")
    todas = sorted(set(g.index) | set(E.index))
    D = pd.DataFrame(index=pd.Index(todas, name="h3")).join(E).fillna(0.0)
    D["en_malla"] = D.index.isin(g.index)
    D["pob_2017"] = g["pob_2017"].reindex(D.index).fillna(0.0)
    # Distrito: el de las manzanas censales de la celda; si no tiene, el limite INEI
    D["DIST"] = g["DIST"].reindex(D.index)
    sin = D["DIST"].isna()
    D.loc[sin, "DIST"] = distrito_inei(D.index[sin]).reindex(D.index[sin])
    D = D[D["DIST"].isin(cen.index)].copy()

    # ── Validacion (a): el indicador reproduce la poblacion 2017 de cada celda ──
    M = D[D["en_malla"]]
    obs = M["pob_2017"].values
    filas = []
    for clave, nombre in PROXIES.items():
        b = M[f"{clave}_2017"]
        pred = (M.groupby("DIST")["pob_2017"].transform("sum") * b
                / M.groupby("DIST")[f"{clave}_2017"].transform("sum")).fillna(0).values
        filas.append({"indicador": nombre, "clave": clave,
                      "R2_reparto_2017": 1 - ((obs - pred) ** 2).sum() / ((obs - obs.mean()) ** 2).sum(),
                      "spearman_celdas": stats.spearmanr(obs, b).statistic,
                      "error_abs_medio": np.abs(obs - pred).mean(),
                      "pob_media_celda": obs.mean()})
    V = pd.DataFrame(filas)
    if proxy is None:
        proxy = V.loc[V["R2_reparto_2017"].idxmax(), "clave"]
    c17, c23 = f"{proxy}_2017", f"{proxy}_2023"
    V["elegido"] = V["clave"] == proxy

    # ── Reparto del crecimiento 2017-2025 ──
    D["dB"] = np.maximum(D[c23] - D[c17], 0.0)
    G = cen["pob_2025_censada"] - cen["pob_2017_censada"]
    D["share"] = (D["dB"] / D["DIST"].map(D.groupby("DIST")["dB"].sum())).fillna(0.0)
    D["pob_2025"] = np.where(D["DIST"].map(G) > 0,
                             D["pob_2017"] + D["DIST"].map(G) * D["share"],
                             D["pob_2017"] * D["DIST"].map(cen["pob_2025_censada"] / cen["pob_2017_censada"]))
    D["pob_2024"] = D["pob_2017"] + FRAC_CORTE * (D["pob_2025"] - D["pob_2017"])

    # ── Resumen por distrito ──
    mal = D[D["en_malla"]].groupby("DIST")
    R = pd.DataFrame({"pob_2017_censada": cen["pob_2017_censada"],
                      "pob_2025_censada": cen["pob_2025_censada"]})
    R["crecimiento"] = G
    R["crec_pct"] = 100 * G / cen["pob_2017_censada"]
    R["edif_2017"] = D.groupby("DIST")[c17].sum()
    R["edif_nuevas"] = D.groupby("DIST")["dB"].sum()
    R["pct_edif_nuevas_en_malla"] = 100 * mal["dB"].sum() / R["edif_nuevas"]
    R["hab_nuevos_por_edif_nueva"] = np.where(G > 0, G / R["edif_nuevas"], np.nan)
    R["pob_2017_malla"] = mal["pob_2017"].sum()
    R["pob_2024_malla"] = mal["pob_2024"].sum()
    R["pob_2025_malla"] = mal["pob_2025"].sum()
    R = R.fillna({c: 0 for c in R.columns if c != "hab_nuevos_por_edif_nueva"})
    R.index.name = "distrito"

    # ── Validacion (b): crecimiento censal frente a edificaciones nuevas, por distrito ──
    cr = R[R["crecimiento"] > 0]
    V["spearman_distritos_crec_vs_edif_nuevas"] = stats.spearmanr(cr["crecimiento"], cr["edif_nuevas"]).statistic
    V["pearson_distritos_crec_vs_edif_nuevas"] = stats.pearsonr(cr["crecimiento"], cr["edif_nuevas"]).statistic
    V["n_distritos_crecen"] = len(cr)

    C = D.reset_index()[["h3", "DIST", "en_malla", "pob_2017", "pob_2024", "pob_2025",
                         c17, c23, "dB"]]
    if verbose:
        e = V[V["elegido"]].iloc[0]
        print(f"    indicador: {PROXIES[proxy]} | R2 reparto 2017 = {e['R2_reparto_2017']:.3f}"
              f" | Spearman celdas = {e['spearman_celdas']:.3f}"
              f" | Spearman distritos = {e['spearman_distritos_crec_vs_edif_nuevas']:.3f}")
        m = C[C["en_malla"]]
        print(f"    fraccion al corte 2024 = {FRAC_CORTE:.3f} | malla: 2017 {m['pob_2017'].sum():,.0f}"
              f" -> 2024 {m['pob_2024'].sum():,.0f} -> 2025 {m['pob_2025'].sum():,.0f}"
              f" | fuera de la malla 2025: {C.loc[~C['en_malla'], 'pob_2025'].sum():,.0f}")
    return C, R, V


if __name__ == "__main__":
    grid = pd.read_parquet("resultados/grid.parquet")
    C, R, V = calcular(grid)
    C.to_parquet("resultados/poblacion_celdas.parquet")
    R.to_csv("resultados/poblacion_distritos.csv", encoding="utf-8-sig")
    V.to_csv("resultados/validacion_edificaciones.csv", index=False)
    pd.set_option("display.width", 220)
    print(V.round(3).to_string(index=False))
    print(R.round(1).to_string())
