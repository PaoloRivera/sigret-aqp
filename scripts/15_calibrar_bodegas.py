#!/usr/bin/env python3
"""
15_calibrar_bodegas.py

Procesa el conteo de campo de bodegas (opcional) y recalibra la ecuacion 1 del
simulador economico. No cambia el modelo predictivo ni el score: la ecuacion 1
solo interviene en el simulador.

Entradas
  data/campo/muestra_campo.csv               muestra de scripts/14_muestra_campo.py
  exportacion de KoboToolbox (--kobo)        XLS o CSV con "XML values and headers"
  data/campo/kobo/revision_registros.csv     opcional: columnas _uuid,tipo_final
                                             (bodega, minimarket, abarrotes, cadena,
                                             mercado o excluir) para resolver los
                                             registros "dudoso" y los duplicados
  resultados/resultado_final.parquet, poblacion_celdas.parquet, competencia_2026.parquet

Regla fijada antes del conteo para elegir la forma de la ecuacion 1
  1. Modelo de conteo: bodegas ~ log(poblacion de la celda) + zona de expansion.
     Poisson, o binomial negativa si hay sobredispersion (razon de
     verosimilitud, p < 0,05).
  2. Si el IC 95 % de la elasticidad incluye 1, las bodegas son proporcionales
     a la poblacion y la ecuacion 1 se mantiene (N = P / h):
       2a. si el IC 95 % de la diferencia de bodegas por 1 000 habitantes entre
           zonas de expansion y consolidadas excluye 0, se usa un h por zona;
       2b. si no, un solo h para toda el area.
  3. Si lo excluye, la ecuacion 1 pasa a N = exp(b0 + b2 * zona) * P^b1,
     aplicada a cada celda y sumada en el area de captacion.
  h se estima con un estimador de razon separado por estrato, ponderado por la
  poblacion de cada estrato; su IC 95 % sale de un bootstrap estratificado que
  remuestrea n - 1 celdas por estrato (Rao y Wu, 1988).

Salidas (resultados/campo/; ninguna lleva puntos ni fotos)
  conteo_por_celda.csv            conteos por celda (se publica)
  estimacion_h.csv                h e IC 95 % por dominio y sensibilidades
  modelos_conteo.csv              comparacion de modelos (AIC y error dejando una celda fuera)
  cobertura_osm.csv               que parte de las bodegas reales registra OpenStreetMap
  simulador_recalibrado.csv       ventas y recuperacion entre celdas: v7 frente a campo
  anexo_j_campo.csv               tabla del Anexo J con el h de campo
  score_vs_campo.csv              score frente a bodegas reales (observacion 2)
  bodegas_k1_calibradas.parquet   bodegas estimadas por area de captacion (aplicacion web)
  h_calibrado.json                forma elegida de la ecuacion 1 y sus parametros
  RESUMEN_CAMPO.md                valores para los marcadores [..] de la tesis
  figuras/campo_bodegas_poblacion.png
  data/campo/kobo/posibles_duplicados.csv (solo con --kobo; queda fuera del repositorio)

Uso, desde la raiz del proyecto:
    python scripts/15_calibrar_bodegas.py --kobo data/campo/kobo/conteo_bodegas.xlsx
    python scripts/15_calibrar_bodegas.py --conteos resultados/campo/conteo_por_celda.csv
La segunda forma reproduce todo a partir de los conteos publicados, sin los puntos.
"""
import argparse
import json
import os
import sys
from datetime import date

import geopandas as gpd
import h3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import optimize, sparse, stats
from scipy.spatial import cKDTree
from scipy.special import gammaln
from shapely.geometry import Polygon

SEMILLA, B, B_SIM = 42, 4000, 1000
RADIO_OSM_M = 30              # un comercio de OSM y uno de campo son el mismo si distan <= 30 m
RADIO_DUP_M = 5               # posibles duplicados para revisar con las fotos
PRECISION_MAX_M = 15          # GPS por encima de esto se marca como impreciso
UMBRAL_EXPANSION = 0.20       # igual que scripts/14_muestra_campo.py
H_V7 = 120                    # valor por defecto de la version 7
S_B, S_C = 45, 175            # m2 de una bodega y de una tienda de la cadena (ecuacion 3)
G_PC, S0, MARGEN, INV = 180, 100, 0.22, 160000
UTM, RES_H3 = "EPSG:32719", 9
INDEP = ["bodega", "minimarket", "abarrotes", "dudoso"]
TIPOS = ["bodega", "minimarket", "abarrotes", "cadena", "mercado", "dudoso"]
ORDEN = [f"{d}-{z}" for d in ("baja", "media", "alta") for z in ("consolidada", "expansion")]
OUT, FIG = "resultados/campo", "figuras"
PETROL, NARANJA, GRIS = "#0E7C86", "#D9822B", "#8A8A8A"


def aviso(msg):
    print(f"  [!] {msg}")


def salir(msg):
    print(f"[x] {msg}")
    sys.exit(1)


def num(x, d=0):
    """Numero con espacio de miles y coma decimal, como en la tesis."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "—"
    s = f"{x:,.{d}f}".replace(",", " ").replace(".", ",")
    return s


ap = argparse.ArgumentParser(description="Conteo de campo de bodegas")
fuente = ap.add_mutually_exclusive_group(required=True)
fuente.add_argument("--kobo", help="exportacion de KoboToolbox (.xlsx o .csv)")
fuente.add_argument("--conteos", help="conteo_por_celda.csv ya procesado")
ap.add_argument("--revision", default="data/campo/kobo/revision_registros.csv")
args = ap.parse_args()
os.makedirs(OUT, exist_ok=True)
os.makedirs(FIG, exist_ok=True)

# ── Muestra y capas del pipeline ────────────────────────────────────────────
M = pd.read_csv("data/campo/muestra_campo.csv", encoding="utf-8-sig")
M["densidad"] = M["estrato"].str.split("-").str[0]
M["zona"] = M["estrato"].str.split("-").str[1]
P_E = M.drop_duplicates("estrato").set_index("estrato")["pob_estrato"].reindex(ORDEN).astype(float)
N_E = M.drop_duplicates("estrato").set_index("estrato")["N_estrato"].reindex(ORDEN)

R = pd.read_parquet("resultados/resultado_final.parquet",
                    columns=["h3", "DIST", "pob_celda", "pob_k1", "n_comp_osm_k1", "mass_k1_2026",
                             "viable", "SCORE", "p_potencial"])
# Poblacion y crecimiento de edificaciones de todas las celdas, incluidas las
# vecinas que quedan fuera de la malla (entran en los anillos de las celdas del borde)
CP = pd.read_parquet("resultados/poblacion_celdas.parquet", columns=["h3", "pob_2025", "cnt_2017", "dB"]).fillna(0.0)
crec = np.where(CP["cnt_2017"] > 0, CP["dB"] / CP["cnt_2017"].clip(lower=1e-9),
                np.where(CP["dB"] > 0, np.inf, 0.0))
CP["expansion"] = (crec >= UMBRAL_EXPANSION).astype(int)
COMP = gpd.read_parquet("resultados/competencia_2026.parquet")
COMP["h3"] = [h3.latlng_to_cell(p.y, p.x, RES_H3) for p in COMP.geometry]


# ── 1. Exportacion de KoboToolbox -> conteo por celda ───────────────────────
def hexagono(c):
    return Polygon([(lon, lat) for lat, lon in h3.cell_to_boundary(c)])


def leer_kobo(ruta):
    if not os.path.exists(ruta):
        salir(f"No existe {ruta}")
    if ruta.lower().endswith((".xlsx", ".xls")):
        K = pd.read_excel(ruta, sheet_name=0, dtype=str)
    else:
        K = pd.read_csv(ruta, sep=None, engine="python", dtype=str, encoding="utf-8-sig")
    K.columns = [str(c).strip() for c in K.columns]
    falta = [c for c in ("celda", "tipo_registro") if c not in K.columns]
    if falta:
        salir(f"Faltan las columnas {falta}. Exporta en XLS con 'XML values and headers'.")
    K = K.fillna("").astype(str).apply(lambda s: s.str.strip())
    K["celda"] = K["celda"].str.upper()
    K["tipo_registro"] = K["tipo_registro"].str.lower()
    if not K["tipo_registro"].isin(["establecimiento", "cierre", ""]).all():
        salir("tipo_registro trae etiquetas en lugar de valores: exporta con 'XML values and headers'.")
    if "_uuid" not in K.columns:
        K["_uuid"] = [f"fila{i + 2}" for i in range(len(K))]
    for c in ("registrador", "tipo_est", "cadena", "acceso", "en_vivienda", "nombre", "puestos",
              "recorrido_completo", "minutos", "cerradas", "ubicacion"):
        if c not in K.columns:
            K[c] = ""
    otras = sorted(set(K["celda"]) - set(M["id"]) - {""})
    if otras:
        aviso(f"Celdas que no estan en la muestra (se ignoran): {otras}")
    return K[K["celda"].isin(M["id"])].copy()


def coordenadas(E):
    """Latitud, longitud y precision del geopoint 'ubicacion'."""
    col = {k: next((c for c in E.columns if c.lower().endswith(k) and "ubicacion" in c.lower()), None)
           for k in ("latitude", "longitude", "precision")}
    if col["latitude"] and col["longitude"]:
        la = pd.to_numeric(E[col["latitude"]], errors="coerce")
        lo = pd.to_numeric(E[col["longitude"]], errors="coerce")
        pr = pd.to_numeric(E[col["precision"]], errors="coerce") if col["precision"] else np.nan
    else:
        p = E["ubicacion"].str.split(expand=True).reindex(columns=range(4))
        la, lo, pr = (pd.to_numeric(p[i], errors="coerce") for i in (0, 1, 3))
    return la, lo, pr


def emparejar(xy_a, xy_b, radio):
    """Empareja uno a uno por cercania (pares mas cercanos primero)."""
    ma, mb = np.zeros(len(xy_a), bool), np.zeros(len(xy_b), bool)
    if len(xy_a) == 0 or len(xy_b) == 0:
        return ma, mb
    pares = cKDTree(xy_a).sparse_distance_matrix(cKDTree(xy_b), radio, output_type="ndarray")
    orden = np.argsort(pares["v"], kind="stable")
    for i, j in zip(pares["i"][orden], pares["j"][orden]):
        if not ma[i] and not mb[j]:
            ma[i] = mb[j] = True
    return ma, mb


def conteo_desde_kobo(ruta):
    K = leer_kobo(ruta)
    E = K[K["tipo_registro"] == "establecimiento"].copy()
    E["tipo_est"] = E["tipo_est"].str.lower()
    if os.path.exists(args.revision):
        rv = pd.read_csv(args.revision, dtype=str).fillna("")
        rv = dict(zip(rv["_uuid"].str.strip(), rv["tipo_final"].str.strip().str.lower()))
        E["tipo_est"] = [rv.get(u, t) for u, t in zip(E["_uuid"], E["tipo_est"])]
        E = E[E["tipo_est"] != "excluir"]
        print(f"  revision aplicada: {len(rv)} registros de {args.revision}")
    raros = sorted(set(E["tipo_est"]) - set(TIPOS))
    if raros:
        salir(f"tipo_est desconocido: {raros}")
    E["lat"], E["lon"], E["precision"] = coordenadas(E)
    sin_gps = E["lat"].isna() | E["lon"].isna()
    if sin_gps.any():
        aviso(f"{int(sin_gps.sum())} establecimientos sin GPS (se excluyen)")
    E = E[~sin_gps].copy()
    E["h3_gps"] = [h3.latlng_to_cell(a, b, RES_H3) for a, b in zip(E["lat"], E["lon"])]
    E["celda_gps"] = E["h3_gps"].map(dict(zip(M["h3"], M["id"])))
    fuera = E["celda_gps"].isna()
    if fuera.any():
        aviso(f"{int(fuera.sum())} establecimientos con GPS fuera de toda celda de la muestra (se excluyen)")
    imprecisos = int((E["precision"] > PRECISION_MAX_M).sum())
    if imprecisos:
        aviso(f"{imprecisos} establecimientos con precision GPS peor que {PRECISION_MAX_M} m (se cuentan)")
    E = gpd.GeoDataFrame(E, geometry=gpd.points_from_xy(E["lon"], E["lat"]), crs="EPSG:4326").to_crs(UTM)

    # Posibles duplicados: mismo tipo a menos de 5 m dentro de la misma celda
    dup = []
    for cid, g in E[~E["celda_gps"].isna()].groupby("celda_gps"):
        xy = np.c_[g.geometry.x, g.geometry.y]
        for i, j in cKDTree(xy).query_pairs(RADIO_DUP_M):
            a, b = g.iloc[i], g.iloc[j]
            if a["tipo_est"] == b["tipo_est"]:
                dup.append({"celda": cid, "uuid_a": a["_uuid"], "uuid_b": b["_uuid"], "tipo": a["tipo_est"],
                            "distancia_m": round(float(np.hypot(*(xy[i] - xy[j]))), 1),
                            "registrador_a": a["registrador"], "registrador_b": b["registrador"],
                            "nombre_a": a["nombre"], "nombre_b": b["nombre"]})
    if dup:
        os.makedirs("data/campo/kobo", exist_ok=True)
        pd.DataFrame(dup).to_csv("data/campo/kobo/posibles_duplicados.csv", index=False, encoding="utf-8-sig")
        aviso(f"{len(dup)} pares de posibles duplicados en data/campo/kobo/posibles_duplicados.csv: "
              "revisalos con las fotos y anota 'excluir' en revision_registros.csv")

    # OpenStreetMap frente a campo: comercios dentro de las celdas visitadas o a
    # menos de 30 m de su borde (un punto de campo puede caer al otro lado)
    visitadas = M[M["id"].isin(K["celda"])]
    hexs = gpd.GeoSeries([hexagono(c) for c in visitadas["h3"]], crs="EPSG:4326").to_crs(UTM)
    O = COMP.to_crs(UTM)
    O = O[O.intersects(hexs.union_all().buffer(RADIO_OSM_M))].copy()
    E_ok = E[~E["celda_gps"].isna()]
    m_e, m_o = emparejar(np.c_[E_ok.geometry.x, E_ok.geometry.y], np.c_[O.geometry.x, O.geometry.y], RADIO_OSM_M)
    E_ok = E_ok.assign(en_osm=m_e)
    O = O.assign(confirmado=m_o)

    filas = []
    for _, c in M.iterrows():
        reg = K[K["celda"] == c["id"]]
        ci = reg[reg["tipo_registro"] == "cierre"]
        if reg.empty:
            estado = "no visitada"
        elif ci.empty:
            estado = "sin cierre"
        elif (ci["recorrido_completo"].str.lower() == "no").any():
            estado = "incompleta"
        else:
            estado = "completa"
        e = E_ok[E_ok["celda_gps"] == c["id"]]
        ind = e[e["tipo_est"].isin(INDEP)]
        cuenta = e["tipo_est"].value_counts()
        filas.append({
            "id": c["id"], "estado": estado,
            "minutos": pd.to_numeric(ci["minutos"], errors="coerce").sum(),
            "cerradas": pd.to_numeric(ci["cerradas"], errors="coerce").sum(),
            **{t: int(cuenta.get(t, 0)) for t in TIPOS},
            "n_indep": len(ind),
            "puestos_mercado": int(pd.to_numeric(e.loc[e["tipo_est"] == "mercado", "puestos"],
                                                 errors="coerce").fillna(0).sum()),
            "en_vivienda": int((ind["en_vivienda"].str.lower() == "si").sum()),
            "por_ventana": int((ind["acceso"].str.lower() == "ventana").sum()),
            "fuera_de_celda": int(((E["celda"] == c["id"]) & E["celda_gps"].isna()).sum()),
            "osm_celda": int((O["h3"] == c["h3"]).sum()),
            "osm_confirmados": int((O["confirmado"] & (O["h3"] == c["h3"])).sum()),
            "indep_en_osm": int(ind["en_osm"].sum()),
        })
    T = M[["id", "rol", "estrato", "densidad", "zona", "h3", "DIST", "pob_celda", "N_estrato",
           "pob_estrato"]].merge(pd.DataFrame(filas), on="id")
    return T


if args.kobo:
    print(f"[1] Exportacion de KoboToolbox: {args.kobo}")
    T = conteo_desde_kobo(args.kobo)
    T.to_csv(f"{OUT}/conteo_por_celda.csv", index=False, encoding="utf-8-sig")
else:
    print(f"[1] Conteos por celda: {args.conteos}")
    T = pd.read_csv(args.conteos, encoding="utf-8-sig")
    if "densidad" not in T.columns:
        T["densidad"] = T["estrato"].str.split("-").str[0]
        T["zona"] = T["estrato"].str.split("-").str[1]

print(T["estado"].value_counts().to_string())
A = T[T["estado"] == "completa"].copy().reset_index(drop=True)
A["y"] = A["n_indep"]
por_e = A.groupby("estrato").size().reindex(ORDEN, fill_value=0)
if (por_e == 0).any():
    salir(f"Estratos sin ninguna celda completa: {list(por_e[por_e == 0].index)}")
if (por_e == 1).any():
    aviso(f"Estratos con una sola celda completa (sin varianza propia): {list(por_e[por_e == 1].index)}")
reemplazos = int(((A["rol"] == "reserva")).sum())
print(f"  celdas completas: {len(A)} (de ellas {reemplazos} reservas) · establecimientos "
      f"independientes: {int(A['y'].sum())} · cadenas: {int(A['cadena'].sum())}")

# ── 2. Habitantes por bodega (estimador de razon separado) ──────────────────
DOM = {"Total": ORDEN,
       "Consolidada": [e for e in ORDEN if e.endswith("consolidada")],
       "Expansión": [e for e in ORDEN if e.endswith("expansion")],
       "Densidad baja": [e for e in ORDEN if e.startswith("baja")],
       "Densidad media": [e for e in ORDEN if e.startswith("media")],
       "Densidad alta": [e for e in ORDEN if e.startswith("alta")],
       **{e: [e] for e in ORDEN}}


def sumas(df, col):
    s = df.groupby("estrato")[[col, "pob_celda"]].sum().reindex(ORDEN)
    return s[col].to_numpy(float), s["pob_celda"].to_numpy(float)


def h_dominios(num_e, pob_e):
    """h de cada dominio a partir de las sumas por estrato (bodegas, poblacion)."""
    r = np.divide(num_e, pob_e, out=np.zeros_like(num_e), where=pob_e > 0)
    out = {}
    for d, es in DOM.items():
        idx = [ORDEN.index(e) for e in es]
        tot = (P_E.to_numpy()[idx] * r[..., idx]).sum(axis=-1)
        out[d] = np.divide(P_E.to_numpy()[idx].sum(), tot, out=np.full_like(tot, np.inf), where=tot > 0)
    return out


# Remuestreo de celdas por estrato (n - 1 con reposicion), comun a todas las razones
rng = np.random.default_rng(SEMILLA)
IDX = {e: [rng.integers(0, len(A[A["estrato"] == e]), max(len(A[A["estrato"] == e]) - 1, 1))
           for _ in range(B)] for e in ORDEN}


def boot_sumas(col):
    nb, pb = np.empty((B, 6)), np.empty((B, 6))
    for j, e in enumerate(ORDEN):
        g = A[A["estrato"] == e]
        yv, pv = g[col].to_numpy(float), g["pob_celda"].to_numpy(float)
        for b, ix in enumerate(IDX[e]):
            nb[b, j], pb[b, j] = yv[ix].sum(), pv[ix].sum()
    return nb, pb


def ic(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return (np.percentile(x, 2.5), np.percentile(x, 97.5)) if len(x) else (np.nan, np.nan)


A["y_sin_dudosos"] = A["y"] - A["dudoso"]
A["y_con_cerradas"] = A["y"] + A["cerradas"].fillna(0)
A["y_con_mercados"] = A["y"] + A["puestos_mercado"]
filas = []
H, HB = {}, {}
for col, etq in (("y", "Principal: abiertas, con dudosas"), ("y_sin_dudosos", "Sin las dudosas"),
                 ("y_con_cerradas", "Con las cerradas identificables"),
                 ("y_con_mercados", "Con los puestos de mercado")):
    est = h_dominios(*sumas(A, col))
    bt = h_dominios(*boot_sumas(col))
    if col == "y":
        H, HB = est, bt
    for d in (DOM if col == "y" else ["Total"]):
        lo, hi = ic(bt[d])
        n_d = int(A["estrato"].isin(DOM[d]).sum())
        filas.append({"variante": etq, "dominio": d, "celdas": n_d,
                      "bodegas": int(A.loc[A["estrato"].isin(DOM[d]), col].sum()),
                      "h": float(est[d]), "h_ic_inf": lo, "h_ic_sup": hi,
                      "bodegas_por_1000": 1000 / float(est[d]),
                      "por_1000_ic_inf": 1000 / hi, "por_1000_ic_sup": 1000 / lo})
EH = pd.DataFrame(filas)
EH.round(3).to_csv(f"{OUT}/estimacion_h.csv", index=False, encoding="utf-8-sig")
h_tot, (h_lo, h_hi) = float(H["Total"]), ic(HB["Total"])
dif = 1000 / HB["Expansión"] - 1000 / HB["Consolidada"]
dif_est = 1000 / H["Expansión"] - 1000 / H["Consolidada"]
dif_lo, dif_hi = ic(dif)
print(f"[2] h = {h_tot:.1f} hab./bodega (IC 95 %: {h_lo:.1f}-{h_hi:.1f}); "
      f"v7 usaba {H_V7}: {'dentro' if h_lo <= H_V7 <= h_hi else 'fuera'} del IC")
print(EH[EH["variante"].str.startswith("Principal")][["dominio", "celdas", "bodegas", "h", "h_ic_inf",
                                                      "h_ic_sup"]].round(1).to_string(index=False))
print(f"    expansion - consolidada: {dif_est:+.2f} bodegas por 1 000 hab (IC 95 %: {dif_lo:+.2f} a {dif_hi:+.2f})")

# ── 3. Modelos de conteo ────────────────────────────────────────────────────
A["log_pob"] = np.log(A["pob_celda"])
A["expansion"] = (A["zona"] == "expansion").astype(int)
po = smf.poisson("y ~ log_pob + expansion", A).fit(disp=0)
try:
    nb = smf.negativebinomial("y ~ log_pob + expansion", A).fit(disp=0, maxiter=500)
    nb_ok = bool(nb.mle_retvals.get("converged", False)) and np.isfinite(nb.llf)
except Exception:
    nb_ok = False
lr = 2 * (nb.llf - po.llf) if nb_ok else 0.0
p_lr = 0.5 * stats.chi2.sf(lr, 1) if lr > 0 else 1.0
USA_NB = nb_ok and p_lr < 0.05
FAMILIA = "binomial negativa" if USA_NB else "Poisson"
print(f"[3] Sobredispersion: LR = {lr:.2f}, p = {p_lr:.4f} -> familia {FAMILIA}")


def ll_nb(y, mu, alpha):
    a = 1 / alpha
    return float(np.sum(gammaln(y + a) - gammaln(a) - gammaln(y + 1)
                        + a * np.log(a / (a + mu)) + y * np.log(mu / (a + mu))))


def ll(y, mu):
    """Log-verosimilitud de una media dada, en la familia elegida (alpha por MV)."""
    mu = np.clip(mu, 1e-9, None)
    if not USA_NB:
        return float(stats.poisson.logpmf(y, mu).sum()), 0
    r = optimize.minimize_scalar(lambda la: -ll_nb(y, mu, np.exp(la)), bounds=(-12, 4), method="bounded")
    return -float(r.fun), 1


def ajustar(formula, df, offset=None):
    f = smf.negativebinomial if USA_NB else smf.poisson
    return f(formula, df, offset=offset).fit(disp=0, maxiter=500)


y = A["y"].to_numpy(float)
modelos = {
    "h fijo = 120 (v7)": dict(formula=None, k=0),
    "Un h para toda el área": dict(formula="y ~ 1", offset=True, k=1),
    "Un h por tipo de zona": dict(formula="y ~ expansion", offset=True, k=2),
    "Elasticidad (log población + zona)": dict(formula="y ~ log_pob + expansion", offset=False, k=3),
}
filas, AJ = [], {}
for nom, spec in modelos.items():
    if spec["formula"] is None:
        mu = A["pob_celda"].to_numpy() / H_V7
        L, extra = ll(y, mu)
        k = extra
    else:
        fit = ajustar(spec["formula"], A, offset=A["log_pob"] if spec["offset"] else None)
        AJ[nom] = fit
        mu = fit.predict(A, offset=A["log_pob"] if spec["offset"] else None) if spec["offset"] \
            else fit.predict(A)
        L, k = float(fit.llf), spec["k"] + (1 if USA_NB else 0)
    # Error absoluto medio dejando una celda fuera
    err = []
    for i in range(len(A)):
        tr, te = A.drop(index=i), A.iloc[[i]]
        if spec["formula"] is None:
            p = te["pob_celda"].to_numpy() / H_V7
        else:
            f = ajustar(spec["formula"], tr, offset=tr["log_pob"] if spec["offset"] else None)
            p = f.predict(te, offset=te["log_pob"]) if spec["offset"] else f.predict(te)
        err.append(abs(float(np.asarray(p)[0]) - float(te["y"].iloc[0])))
    filas.append({"modelo": nom, "familia": FAMILIA, "parametros": k, "log_verosimilitud": L,
                  "AIC": 2 * k - 2 * L, "error_abs_medio_loo": float(np.mean(err))})
MC = pd.DataFrame(filas)
fe = AJ["Elasticidad (log población + zona)"]
b1, (b1_lo, b1_hi) = float(fe.params["log_pob"]), map(float, fe.conf_int().loc["log_pob"])
b2, (b2_lo, b2_hi) = float(fe.params["expansion"]), map(float, fe.conf_int().loc["expansion"])
MC["elasticidad"] = [np.nan, np.nan, np.nan, b1]
MC["elasticidad_ic"] = ["", "", "", f"{b1_lo:.3f} a {b1_hi:.3f}"]
MC.round(4).to_csv(f"{OUT}/modelos_conteo.csv", index=False, encoding="utf-8-sig")
print(MC[["modelo", "parametros", "AIC", "error_abs_medio_loo"]].round(2).to_string(index=False))
print(f"    elasticidad = {b1:.3f} (IC 95 %: {b1_lo:.3f}-{b1_hi:.3f}); "
      f"zona de expansion = {b2:+.3f} (IC 95 %: {b2_lo:+.3f} a {b2_hi:+.3f})")

# Regla de decision fijada antes del conteo
if b1_lo <= 1 <= b1_hi:
    VARIANTE = "zona" if (dif_lo > 0 or dif_hi < 0) else "global"
else:
    VARIANTE = "elasticidad"
TEXTO_VAR = {"global": "A: un solo h para toda el área",
             "zona": "B: un h por tipo de zona",
             "elasticidad": "C: ecuación de elasticidad"}[VARIANTE]
print(f"    Forma elegida de la ecuacion 1 -> variante {TEXTO_VAR}")

# ── 4. Bodegas estimadas en el area de captacion de cada celda ──────────────
# Matriz de anillos: fila = celda de la malla, columna = celda (de la malla o
# vecina) dentro de su area de captacion (H3 k = 1)
ix = {c: j for j, c in enumerate(CP["h3"])}
fil, colu = [], []
for i, c in enumerate(R["h3"]):
    for v in h3.grid_disk(c, 1):
        j = ix.get(v)
        if j is not None:
            fil.append(i)
            colu.append(j)
ANILLO = sparse.csr_matrix((np.ones(len(fil)), (fil, colu)), shape=(len(R), len(CP)))
pob = CP["pob_2025"].to_numpy(float)
dif_pk1 = np.abs(ANILLO @ pob - R["pob_k1"].to_numpy(float)).max()
if dif_pk1 > 1:
    aviso(f"La suma de poblacion en el anillo difiere de pob_k1 hasta en {dif_pk1:.1f} hab "
          "(¿resultado_final.parquet no es la corrida con la poblacion 2025?)")
expc = CP["expansion"].to_numpy()
pob_cons, pob_exp = ANILLO @ (pob * (expc == 0)), ANILLO @ (pob * (expc == 1))


def bod_k1(h_g=None, h_c=None, h_e=None, par=None):
    if VARIANTE == "global" or h_g is not None:
        return R["pob_k1"].to_numpy(float) / (h_g if h_g is not None else h_tot)
    if VARIANTE == "zona":
        return pob_cons / h_c + pob_exp / h_e
    b0_, b1_, b2_ = par
    mu = np.where(pob > 0, np.exp(b0_ + b2_ * expc) * np.power(np.clip(pob, 1e-9, None), b1_), 0.0)
    return ANILLO @ mu


PAR = (float(fe.params["Intercept"]), b1, b2)
if VARIANTE == "global":
    BOD = bod_k1(h_g=h_tot)
elif VARIANTE == "zona":
    BOD = bod_k1(h_c=float(H["Consolidada"]), h_e=float(H["Expansión"]))
else:
    BOD = bod_k1(par=PAR)
Uni = R["viable"] & (R["pob_celda"] >= 100)
h_equiv = float(R.loc[Uni, "pob_k1"].sum() / BOD[Uni.to_numpy()].sum())
pd.DataFrame({"h3": R["h3"], "bod_k1": np.round(BOD, 3)}).to_parquet(f"{OUT}/bodegas_k1_calibradas.parquet")


# ── 5. Simulador recalibrado ────────────────────────────────────────────────
def huff(P, Nest, Nosm, K):
    N = np.maximum(Nosm, Nest)
    Arv = N * S_B + K * S_C
    C = S0 / (S0 + Arv)
    V = C * P * G_PC
    Bm = MARGEN * V
    return N, Arv, C, V, Bm, INV / Bm


Vb = R["viable"].to_numpy()
P1, NO, KM = (R[c].to_numpy(float) for c in ("pob_k1", "n_comp_osm_k1", "mass_k1_2026"))
top = R[R["viable"]].nlargest(10, "SCORE")
jh = top[top["DIST"] == "JACOBO HUNTER"].head(1)
jh = top.head(1) if jh.empty else jh
J = int(R.index.get_loc(jh.index[0]))


def resumen(nom, Nest, f_pob=1.0):
    N, Arv, C, V, Bm, PR = huff(P1 * f_pob, Nest, NO, KM)
    v, p = V[Vb], PR[Vb]
    return {"escenario": nom, "celdas_viables": int(Vb.sum()),
            "osm_supera_estimacion": int((NO[Vb] > Nest[Vb]).sum()),
            "ventas_min": v.min(), "ventas_p5": np.percentile(v, 5), "ventas_mediana": np.median(v),
            "ventas_p95": np.percentile(v, 95), "ventas_max": v.max(), "ventas_cv_%": 100 * v.std() / v.mean(),
            "recup_min": p.min(), "recup_p5": np.percentile(p, 5), "recup_mediana": np.median(p),
            "recup_p95": np.percentile(p, 95), "recup_max": p.max(),
            "JH_bodegas": N[J], "JH_atractividad_m2": Arv[J], "JH_cuota_%": 100 * C[J], "JH_ventas": V[J],
            "JH_margen": Bm[J], "JH_recuperacion": PR[J]}


Nv7 = P1 / H_V7
S = [resumen("v7: h = 120", Nv7), resumen(f"Campo: variante {TEXTO_VAR}", BOD)]
# IC 95 % de las cifras del simulador con el modelo elegido
sim = []
rs = np.random.default_rng(SEMILLA)
if VARIANTE == "elasticidad":
    draws = rs.multivariate_normal(fe.params[["Intercept", "log_pob", "expansion"]].to_numpy(),
                                   fe.cov_params().loc[["Intercept", "log_pob", "expansion"],
                                                       ["Intercept", "log_pob", "expansion"]].to_numpy(), B_SIM)
for b in range(B_SIM):
    if VARIANTE == "global":
        Ne = bod_k1(h_g=float(HB["Total"][b]))
    elif VARIANTE == "zona":
        Ne = bod_k1(h_c=float(HB["Consolidada"][b]), h_e=float(HB["Expansión"][b]))
    else:
        Ne = bod_k1(par=tuple(draws[b]))
    _, _, _, V, _, PR = huff(P1, Ne, NO, KM)
    sim.append((np.median(V[Vb]), np.median(PR[Vb]), V[J], PR[J]))
sim = np.array(sim)
IC_SIM = {k: ic(sim[:, i]) for i, k in enumerate(("ventas_mediana", "recup_mediana", "JH_ventas", "JH_recuperacion"))}
S.append(resumen("Campo con +15 % de población", BOD * (1.15 ** (b1 if VARIANTE == "elasticidad" else 1)), 1.15))
SR = pd.DataFrame(S)
for k, (lo, hi) in IC_SIM.items():
    SR.loc[1, f"{k}_ic_inf"], SR.loc[1, f"{k}_ic_sup"] = lo, hi
SR.round(3).to_csv(f"{OUT}/simulador_recalibrado.csv", index=False, encoding="utf-8-sig")
print("[5] Simulador (celdas viables)")
print(SR[["escenario", "ventas_min", "ventas_mediana", "ventas_max", "ventas_cv_%", "recup_min",
          "recup_mediana", "recup_max", "JH_ventas", "JH_recuperacion"]].round(1).to_string(index=False))

# Tabla del Anexo J con el h de campo
filas = []


def fila_j(etq, Nest):
    N, Arv, C, V, Bm, PR = huff(P1, Nest, NO, KM)
    return {"h": etq, "bodegas_JH": N[J], "cuota_JH_%": 100 * C[J], "ventas_JH": V[J], "margen_JH": Bm[J],
            "recuperacion_JH": PR[J], "recuperacion_mediana_viables": np.median(PR[Vb])}


for hh in (60, 90, 120, 150, 200):
    filas.append(fila_j(str(hh), P1 / hh))
if VARIANTE == "global":
    filas += [fila_j(f"{h_tot:.0f} (campo)", P1 / h_tot), fila_j(f"{h_lo:.0f} (IC inferior)", P1 / h_lo),
              fila_j(f"{h_hi:.0f} (IC superior)", P1 / h_hi)]
elif VARIANTE == "zona":
    hc, he = float(H["Consolidada"]), float(H["Expansión"])
    filas.append(fila_j(f"{hc:.0f} consolidada / {he:.0f} expansión (campo)", BOD))
else:
    filas.append(fila_j(f"Elasticidad {b1:.2f} (campo)", BOD))
AJT = pd.DataFrame(filas)
AJT.round(3).to_csv(f"{OUT}/anexo_j_campo.csv", index=False, encoding="utf-8-sig")

# ── 6. Cobertura de OpenStreetMap ───────────────────────────────────────────
filas = []
for d in ("Total", "Consolidada", "Expansión", "Densidad baja", "Densidad media", "Densidad alta"):
    g = A[A["estrato"].isin(DOM[d])]
    filas.append({"dominio": d, "celdas": len(g), "indep_campo": int(g["y"].sum()),
                  "indep_en_osm": int(g["indep_en_osm"].sum()),
                  "cobertura_%": 100 * g["indep_en_osm"].sum() / max(g["y"].sum(), 1),
                  "osm_en_celdas": int(g["osm_celda"].sum()), "osm_confirmados": int(g["osm_confirmados"].sum())})
CO = pd.DataFrame(filas)
nb_, pb_ = sumas(A, "y")
ne_, _ = sumas(A, "indep_en_osm")
rr = np.divide(nb_, pb_, out=np.zeros(6), where=pb_ > 0)
cov_e = np.divide(ne_, nb_, out=np.zeros(6), where=nb_ > 0)
cob_strat = 100 * (P_E.to_numpy() * rr * cov_e).sum() / (P_E.to_numpy() * rr).sum()
bn, bp = boot_sumas("y")
be, _ = boot_sumas("indep_en_osm")
rb = np.divide(bn, bp, out=np.zeros_like(bn), where=bp > 0)
cb = np.divide(be, bn, out=np.zeros_like(be), where=bn > 0)
cob_lo, cob_hi = ic(100 * (P_E.to_numpy() * rb * cb).sum(axis=1) / (P_E.to_numpy() * rb).sum(axis=1))
T_univ = float((P_E.to_numpy() * rr).sum())
osm_univ = int(COMP["h3"].isin(set(R.loc[Uni, "h3"])).sum())
rho_osm, p_osm = stats.spearmanr(A["osm_celda"], A["y"]) if A["osm_celda"].nunique() > 1 else (np.nan, np.nan)
CO["cobertura_estratificada_%"] = [cob_strat] + [np.nan] * (len(CO) - 1)
CO["cobertura_ic_inf"] = [cob_lo] + [np.nan] * (len(CO) - 1)
CO["cobertura_ic_sup"] = [cob_hi] + [np.nan] * (len(CO) - 1)
CO.round(3).to_csv(f"{OUT}/cobertura_osm.csv", index=False, encoding="utf-8-sig")
print(f"[6] OSM registra {cob_strat:.1f} % de las bodegas independientes (IC 95 %: {cob_lo:.1f}-{cob_hi:.1f}); "
      f"en las {int(Uni.sum())} celdas del universo hay unas {T_univ:,.0f} y OSM tiene {osm_univ}")

# ── 7. Score frente a bodegas reales (observacion 2) ────────────────────────
Sv = A.merge(R[["h3", "SCORE", "p_potencial"]], on="h3", how="left")
Sv["por_1000"] = 1000 * Sv["y"] / Sv["pob_celda"]
umbral = R.loc[R["viable"], "SCORE"].quantile(0.9)
Sv["decil_superior"] = Sv["SCORE"] >= umbral
filas = []
for x in ("SCORE", "p_potencial"):
    for yy in ("y", "por_1000"):
        rho, p = stats.spearmanr(Sv[x], Sv[yy])
        filas.append({"prueba": f"Spearman {x} vs {'bodegas' if yy == 'y' else 'bodegas por 1 000 hab'}",
                      "n": len(Sv), "estadistico": rho, "p": p})
a_, b_ = Sv.loc[Sv["decil_superior"], "por_1000"], Sv.loc[~Sv["decil_superior"], "por_1000"]
if len(a_) >= 2 and len(b_) >= 2:
    u, p = stats.mannwhitneyu(a_, b_, alternative="two-sided")
    filas.append({"prueba": f"Mann-Whitney bodegas por 1 000 hab: decil superior (n={len(a_)}) vs resto (n={len(b_)})",
                  "n": len(Sv), "estadistico": u, "p": p})
else:
    filas.append({"prueba": f"Mann-Whitney: solo {len(a_)} celdas del decil superior en la muestra",
                  "n": len(Sv), "estadistico": np.nan, "p": np.nan})
SC = pd.DataFrame(filas)
SC.round(4).to_csv(f"{OUT}/score_vs_campo.csv", index=False, encoding="utf-8-sig")
print("[7] Score frente a campo")
print(SC.round(3).to_string(index=False))

# ── 8. Figura ───────────────────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(7.5, 5))
for z, col, etq in (("consolidada", PETROL, "Zona consolidada"), ("expansion", NARANJA, "Zona de expansión")):
    g = A[A["zona"] == z]
    ax.scatter(g["pob_celda"], g["y"], s=36, color=col, label=etq, zorder=3, edgecolor="white", lw=.6)
xs = np.linspace(0, A["pob_celda"].max() * 1.05, 100)
ax.plot(xs, xs / H_V7, color=GRIS, ls="--", lw=1.2, label="v7: 1 bodega cada 120 hab")
if VARIANTE == "global":
    ax.plot(xs, xs / h_tot, color="#2b2d33", lw=1.6, label=f"Campo: 1 cada {h_tot:.0f} hab")
elif VARIANTE == "zona":
    ax.plot(xs, xs / H["Consolidada"], color=PETROL, lw=1.6, label=f"Campo, consolidada: 1 cada {H['Consolidada']:.0f}")
    ax.plot(xs, xs / H["Expansión"], color=NARANJA, lw=1.6, label=f"Campo, expansión: 1 cada {H['Expansión']:.0f}")
else:
    for z, col, etq in ((0, PETROL, "consolidada"), (1, NARANJA, "expansión")):
        ax.plot(xs[1:], np.exp(PAR[0] + PAR[2] * z) * xs[1:] ** b1, color=col, lw=1.6,
                label=f"Campo, {etq}: elasticidad {num(b1, 2)}")
ax.set_xlabel("Habitantes de la celda (2025)")
ax.set_ylabel("Bodegas, minimarkets y tiendas de abarrotes")
ax.spines[["top", "right"]].set_visible(False)
ax.legend(frameon=False, fontsize=8)
ax.set_title("Conteo de campo: establecimientos frente a población por celda", loc="left", fontsize=11,
             weight="bold")
fig.savefig(f"{FIG}/campo_bodegas_poblacion.png", dpi=200, bbox_inches="tight", facecolor="white")
plt.close(fig)

# ── 9. Parametros para la aplicacion y resumen para la tesis ────────────────
json.dump({"fecha": date.today().isoformat(), "variante": VARIANTE, "familia": FAMILIA,
           "h": round(h_equiv, 2), "h_ic": [round(h_lo, 2), round(h_hi, 2)],
           "h_zona": {"consolidada": round(float(H["Consolidada"]), 2), "expansion": round(float(H["Expansión"]), 2)},
           "elasticidad": {"b0": PAR[0], "b1": b1, "b2": b2, "b1_ic": [b1_lo, b1_hi]},
           "celdas": int(len(A)), "establecimientos": int(A["y"].sum())},
          open(f"{OUT}/h_calibrado.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

s7, sc = SR.iloc[0], SR.iloc[1]
s15 = SR.iloc[2]
ind = A["y"].sum()
V = {
    "CELDAS": len(A), "RESERVAS_USADAS": reemplazos, "HORAS": num(A["minutos"].sum() / 60, 1),
    "EST_INDEP": int(ind), "EST_CADENAS": int(A["cadena"].sum()), "MERCADOS": int(A["mercado"].sum()),
    "PCT_VIVIENDA": num(100 * A["en_vivienda"].sum() / max(ind, 1), 0),
    "PCT_VENTANA": num(100 * A["por_ventana"].sum() / max(ind, 1), 0),
    "H": num(h_tot, 1), "H_IC": f"{num(h_lo, 1)} a {num(h_hi, 1)}", "B1000": num(1000 / h_tot, 2),
    "H_CONS": num(H["Consolidada"], 1), "H_EXP": num(H["Expansión"], 1),
    "DIF": num(dif_est, 2), "DIF_IC": f"{num(dif_lo, 2)} a {num(dif_hi, 2)}",
    "ELAST": num(b1, 2), "ELAST_IC": f"{num(b1_lo, 2)} a {num(b1_hi, 2)}", "FAMILIA": FAMILIA,
    "VARIANTE": TEXTO_VAR, "H_EQUIV": num(h_equiv, 1), "H_APP": num(round(h_equiv), 0),
    "COB_OSM": num(cob_strat, 1), "COB_OSM_IC": f"{num(cob_lo, 1)} a {num(cob_hi, 1)}",
    "BOD_UNIV": num(T_univ, 0), "OSM_UNIV": osm_univ, "RHO_OSM": num(rho_osm, 2),
    "P_JH": num(P1[J], 0), "N_JH": num(sc["JH_bodegas"], 1), "ATR_JH": num(sc["JH_atractividad_m2"], 0), "C_JH": num(sc["JH_cuota_%"], 2),
    "V_JH": num(sc["JH_ventas"], 0), "M_JH": num(sc["JH_margen"], 0), "PR_JH": num(sc["JH_recuperacion"], 1),
    "PR_JH_IC": f"{num(IC_SIM['JH_recuperacion'][0], 1)} a {num(IC_SIM['JH_recuperacion'][1], 1)}",
    "V_JH_15": num(s15["JH_ventas"], 0), "PCT_15": num(100 * (s15["JH_ventas"] / sc["JH_ventas"] - 1), 1),
    "V_MIN": num(sc["ventas_min"], 0), "V_MAX": num(sc["ventas_max"], 0), "V_P5": num(sc["ventas_p5"], 0),
    "V_P95": num(sc["ventas_p95"], 0), "CV_V": num(sc["ventas_cv_%"], 1), "CV_V_V7": num(s7["ventas_cv_%"], 1),
    "PR_MIN": num(sc["recup_min"], 1), "PR_MAX": num(sc["recup_max"], 1), "PR_MED": num(sc["recup_mediana"], 1),
    "PR_MED_IC": f"{num(IC_SIM['recup_mediana'][0], 1)} a {num(IC_SIM['recup_mediana'][1], 1)}",
    "TECHO": num(S0 * G_PC * h_tot / S_B, 0) if VARIANTE == "global" else
    (f"{num(S0 * G_PC * H['Consolidada'] / S_B, 0)} en zona consolidada y S/ {num(S0 * G_PC * H['Expansión'] / S_B, 0)} "
     "en zona de expansión" if VARIANTE == "zona" else "sin techo fijo"),
    "RHO_SCORE": num(SC.iloc[1]["estadistico"], 2), "P_SCORE": num(SC.iloc[1]["p"], 3),
    "B0": num(PAR[0], 3), "B2": num(b2, 3), "N_JH_ENT": num(sc["JH_bodegas"], 0),
    "POB_MIN": num(A["pob_celda"].min(), 0), "POB_MAX": num(A["pob_celda"].max(), 0),
    "VARIANTE_LETRA": TEXTO_VAR[0],
    "CRECEN": "en proporción a la población" if VARIANTE != "elasticidad" else
    ("menos que la población" if b1 < 1 else "más que la población"),
    "RANGO_JH": ("Dentro del rango" if 30000 <= sc["JH_ventas"] <= 80000 else
                 "Por debajo del rango" if sc["JH_ventas"] < 30000 else "Por encima del rango")
    + " S/ 30 000 – S/ 80 000",
    "LECTURA_SCORE": ("el score no se asocia con la densidad de bodegas independientes"
                      if not (SC.iloc[1]["p"] < 0.05) else
                      "las celdas mejor puntuadas tienen más bodegas por habitante, es decir, más competencia informal"
                      if SC.iloc[1]["estadistico"] > 0 else
                      "las celdas mejor puntuadas tienen menos bodegas por habitante"),
}
with open(f"{OUT}/RESUMEN_CAMPO.md", "w", encoding="utf-8") as f:
    f.write(f"# Conteo de campo: valores para la tesis ({date.today().isoformat()})\n\n")
    f.write(f"Forma elegida de la ecuación 1: **variante {TEXTO_VAR}** (familia {FAMILIA}).\n\n")
    f.write("| Marcador | Valor |\n|---|---|\n")
    for k, v in V.items():
        f.write(f"| [{k}] | {v} |\n")
    f.write("\n## Anexo J (tabla nueva)\n\n| h (hab./bodega) | Bodegas estimadas | Cuota | Ventas mensuales | "
            "Margen bruto | Recuperación (meses) | Recuperación mediana, celdas viables |\n|---|---|---|---|---|---|---|\n")
    for _, r in AJT.iterrows():
        f.write(f"| {r['h']} | {num(r['bodegas_JH'], 1)} | {num(r['cuota_JH_%'], 2)} % | S/ {num(r['ventas_JH'], 0)} | "
                f"S/ {num(r['margen_JH'], 0)} | {num(r['recuperacion_JH'], 1)} | "
                f"{num(r['recuperacion_mediana_viables'], 1)} |\n")
    f.write("\n## Habitantes por bodega por dominio\n\n| Dominio | Celdas | Establecimientos | h | IC 95 % |\n"
            "|---|---|---|---|---|\n")
    for _, r in EH[EH["variante"].str.startswith("Principal")].iterrows():
        f.write(f"| {r['dominio']} | {r['celdas']} | {r['bodegas']} | {num(r['h'], 0)} | "
                f"{num(r['h_ic_inf'], 0)} a {num(r['h_ic_sup'], 0)} |\n")
    f.write("\n## Sensibilidades (toda el área)\n\n")
    for _, r in EH[~EH["variante"].str.startswith("Principal")].iterrows():
        f.write(f"- {r['variante']}: h = {num(r['h'], 0)} (IC 95 %: {num(r['h_ic_inf'], 0)} a {num(r['h_ic_sup'], 0)})\n")
print(f"[9] Variante {TEXTO_VAR}; h equivalente = {h_equiv:.1f}")
print(f"  >> {OUT}/ (conteo_por_celda, estimacion_h, modelos_conteo, cobertura_osm, simulador_recalibrado, "
      f"anexo_j_campo, score_vs_campo, bodegas_k1_calibradas, h_calibrado.json, RESUMEN_CAMPO.md); "
      f"{FIG}/campo_bodegas_poblacion.png")
