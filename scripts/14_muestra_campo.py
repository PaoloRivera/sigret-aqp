#!/usr/bin/env python3
"""
14_muestra_campo.py

Selecciona la muestra del conteo de campo de bodegas y prepara sus materiales.
El conteo calibra el numero de habitantes por bodega (h) de la ecuacion 1, que
solo usa el simulador economico.

Diseno: muestreo aleatorio estratificado de 36 celdas H3 r9 entre las celdas
viables del ranking con al menos 100 habitantes en 2025.
  - Densidad: terciles de habitantes por km2 en 2025 (baja, media, alta).
  - Zona: "expansion" si sus edificaciones crecieron 20 % o mas entre 2017 y
    2023 segun Google Open Buildings (resultados/poblacion_celdas.parquet);
    "consolidada" en otro caso.
  - 3 x 2 = 6 estratos, 6 celdas por estrato y 2 reservas por estrato,
    sorteadas con semilla 42 sobre la lista ordenada por codigo H3.
Una reserva reemplaza a una celda solo si esta no puede recorrerse (acceso
cerrado o inseguridad); se usa la primera reserva del mismo estrato y el
cambio se anota en el formulario.

Salidas:
  data/campo/muestra_campo.csv       lista de celdas con estrato y tiempos
  data/campo/muestra_campo.geojson   hexagonos (para QGIS o geojson.io)
  data/campo/muestra_campo.kml       hexagonos (Google My Maps, Organic Maps)
  data/campo/plan_jornadas.csv       orden sugerido de visita por jornada
  data/campo/precision_esperada.csv  amplitud esperada del IC de h con esta muestra
  data/campo/formulario_kobo.xlsx    formulario XLSForm para KoboToolbox
  docs/campo/mapas_campo.pdf         mapa general, plan de jornadas y una pagina por celda
  figuras/campo_muestra.png  mapa general de la muestra

Si data/campo/muestra_campo.csv ya existe, el script comprueba que el sorteo
da las mismas celdas y no lo sobrescribe si cambiaron (por ejemplo, tras
rehacer el pipeline con otros datos). --rehacer lo fuerza; usalo solo antes
de empezar el campo.

Uso, desde la raiz del proyecto (despues de pipeline.py):
    python scripts/14_muestra_campo.py
"""
import argparse
import os
import sys
from xml.sax.saxutils import escape

import geopandas as gpd
import h3
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from shapely.geometry import Polygon

SEMILLA = 42
POR_ESTRATO, RESERVAS = 6, 2
POB_MINIMA = 100              # habitantes de la celda en 2025
UMBRAL_EXPANSION = 0.20       # crecimiento de edificaciones 2017-2023
VELOCIDAD_KMH = 3.0           # caminata con registro
MIN_POR_REGISTRO = 1.5        # GPS, foto y cuatro preguntas
H_REFERENCIA = 120            # solo para estimar cuantos registros habra
JORNADA_MIN = 390             # 6,5 h por jornada, traslados incluidos
TRASLADO_FIJO_MIN, TRASLADO_KMH, RODEO = 10, 18, 1.4   # combi o taxi con esperas
CENTRO = (-16.39889, -71.53694)                         # Plaza de Armas de Arequipa
UTM = "EPSG:32719"
OUT_DATA, OUT_DOCS, OUT_FIG = "data/campo", "docs/campo", "figuras"
ap = argparse.ArgumentParser()
ap.add_argument("--rehacer", action="store_true", help="sobrescribe una muestra ya sorteada")
ARGS = ap.parse_args()
for d in (OUT_DATA, OUT_DOCS, OUT_FIG):
    os.makedirs(d, exist_ok=True)

# ── Universo y estratos ─────────────────────────────────────────────────────
R = pd.read_parquet("resultados/resultado_final.parquet",
                    columns=["h3", "DIST", "pob_celda", "dens_hab_km2", "viable", "lat", "lon"])
C = pd.read_parquet("resultados/poblacion_celdas.parquet", columns=["h3", "cnt_2017", "cnt_2023", "dB"])
U = R[R["viable"] & (R["pob_celda"] >= POB_MINIMA)].merge(C, on="h3", how="left")
U["crec_edif"] = np.where(U["cnt_2017"] > 0, U["dB"] / U["cnt_2017"].clip(lower=1e-9),
                          np.where(U["dB"] > 0, np.inf, 0.0))
U["zona"] = np.where(U["crec_edif"] >= UMBRAL_EXPANSION, "expansion", "consolidada")
U["densidad"] = pd.qcut(U["dens_hab_km2"], 3, labels=["baja", "media", "alta"]).astype(str)
cortes = U.groupby("densidad")["dens_hab_km2"].agg(["min", "max"]).reindex(["baja", "media", "alta"])
U["estrato"] = U["densidad"] + "-" + U["zona"]
U = U.sort_values("h3").reset_index(drop=True)

rng = np.random.default_rng(SEMILLA)
ORDEN = [f"{d}-{z}" for d in ("baja", "media", "alta") for z in ("consolidada", "expansion")]
filas = []
for e in ORDEN:
    g = U[U["estrato"] == e]
    idx = rng.permutation(len(g))[: POR_ESTRATO + RESERVAS]
    sel = g.iloc[idx].copy()
    sel["rol"] = ["muestra"] * POR_ESTRATO + ["reserva"] * RESERVAS
    sel["orden_en_estrato"] = range(1, len(sel) + 1)
    sel["N_estrato"] = len(g)
    sel["pob_estrato"] = g["pob_celda"].sum()
    filas.append(sel)
M = pd.concat(filas, ignore_index=True)
M["id"] = ""
M.loc[M["rol"] == "muestra", "id"] = [f"C{i:02d}" for i in range(1, (M["rol"] == "muestra").sum() + 1)]
M.loc[M["rol"] == "reserva", "id"] = [f"R{i:02d}" for i in range(1, (M["rol"] == "reserva").sum() + 1)]
PREVIA = f"{OUT_DATA}/muestra_campo.csv"
if os.path.exists(PREVIA) and not ARGS.rehacer:
    prev = pd.read_csv(PREVIA, encoding="utf-8-sig")[["id", "h3"]]
    if not prev.reset_index(drop=True).equals(M[["id", "h3"]].reset_index(drop=True)):
        print(f"[x] El sorteo ya no coincide con {PREVIA}: cambiaron los datos del pipeline. "
              "No se sobrescribe la muestra del campo. Usa --rehacer solo si aun no empezo el conteo.")
        sys.exit(1)

# ── Geometria de las celdas y longitud de calles ────────────────────────────
def nombre_dist(d):
    return "J. L. Bustamante y Rivero" if d == "JLBR" else str(d).title()


def hexagono(c):
    return Polygon([(lon, lat) for lat, lon in h3.cell_to_boundary(c)])


G = gpd.GeoDataFrame(M, geometry=[hexagono(c) for c in M["h3"]], crs="EPSG:4326")
Gu = G.to_crs(UTM)
E = gpd.read_parquet("data/osm/red_edges.parquet")
E = E.cx[G.total_bounds[0] - .01:G.total_bounds[2] + .01, G.total_bounds[1] - .01:G.total_bounds[3] + .01]
# El grafo peatonal tiene cada calle de doble sentido dos veces (u-v y v-u)
par = np.sort(E[["u", "v"]].to_numpy(), axis=1)
E = E.assign(a=par[:, 0], b=par[:, 1]).drop_duplicates(["a", "b", "key"]).to_crs(UTM)
largo = []
for poly in Gu.geometry:
    sub = E[E.intersects(poly)]
    largo.append(sub.intersection(poly).length.sum() / 1000)
G["calles_km"] = np.round(largo, 2)
G["registros_esperados"] = np.round(G["pob_celda"] / H_REFERENCIA, 1)
G["minutos_estimados"] = np.round(G["calles_km"] / VELOCIDAD_KMH * 60
                                  + MIN_POR_REGISTRO * G["registros_esperados"]).astype(int)
G["maps"] = [f"https://www.google.com/maps?q={la:.6f},{lo:.6f}" for la, lo in zip(G["lat"], G["lon"])]
ETQ = {"baja": "densidad baja", "media": "densidad media", "alta": "densidad alta",
       "consolidada": "consolidada", "expansion": "expansión"}
G["estrato_texto"] = G["densidad"].map(ETQ) + ", " + G["zona"]

cols = ["id", "rol", "estrato", "orden_en_estrato", "h3", "DIST", "lat", "lon", "pob_celda",
        "dens_hab_km2", "crec_edif", "calles_km", "registros_esperados", "minutos_estimados",
        "N_estrato", "pob_estrato", "maps"]
G[cols].round({"lat": 6, "lon": 6, "pob_celda": 0, "dens_hab_km2": 0, "crec_edif": 3, "pob_estrato": 0}) \
    .to_csv(f"{OUT_DATA}/muestra_campo.csv", index=False, encoding="utf-8-sig")
G[cols + ["geometry"]].to_file(f"{OUT_DATA}/muestra_campo.geojson", driver="GeoJSON")

# KML sencillo: muestra en petroleo, reservas en gris
kml = ['<?xml version="1.0" encoding="UTF-8"?>', '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
       '<name>Conteo de bodegas SIGRET-AQP</name>',
       '<Style id="m"><LineStyle><color>ff867c0e</color><width>3</width></LineStyle>'
       '<PolyStyle><color>330e7c86</color></PolyStyle></Style>',
       '<Style id="r"><LineStyle><color>ff8a8a8a</color><width>2</width></LineStyle>'
       '<PolyStyle><color>228a8a8a</color></PolyStyle></Style>']
for _, f in G.iterrows():
    coords = " ".join(f"{x:.6f},{y:.6f},0" for x, y in f.geometry.exterior.coords)
    desc = (f"{nombre_dist(f['DIST'])} · {f['estrato_texto']} · {f['calles_km']} km de calles · "
            f"unos {f['minutos_estimados']} min · {f['maps']}")
    kml.append(f"<Placemark><name>{f['id']}</name><description>{escape(desc)}</description>"
               f"<styleUrl>#{'m' if f['rol'] == 'muestra' else 'r'}</styleUrl><Polygon><outerBoundaryIs>"
               f"<LinearRing><coordinates>{coords}</coordinates></LinearRing></outerBoundaryIs></Polygon></Placemark>")
kml.append("</Document></kml>")
open(f"{OUT_DATA}/muestra_campo.kml", "w", encoding="utf-8").write("\n".join(kml))

# ── Plan de jornadas ────────────────────────────────────────────────────────
# Barrido angular desde el centro de la ciudad: se recorren las celdas en orden
# de angulo y se cierra la jornada cuando el recorrido y los traslados superan
# 6,5 h; dentro de cada jornada se visita primero la celda mas cercana.
Gm = Gu[Gu["rol"] == "muestra"]
cx, cy = gpd.GeoSeries.from_xy([CENTRO[1]], [CENTRO[0]], crs="EPSG:4326").to_crs(UTM).iloc[0].coords[0]
XY = {i: (p.x, p.y) for i, p in zip(Gm["id"], Gm.geometry.centroid)}
MIN = dict(zip(G["id"], G["minutos_estimados"]))


def traslado(p, q):
    return TRASLADO_FIJO_MIN + np.hypot(p[0] - q[0], p[1] - q[1]) / 1000 * RODEO / TRASLADO_KMH * 60


def vecino_mas_cercano(ids):
    resto, orden, p = list(ids), [], (cx, cy)
    while resto:
        k = min(resto, key=lambda i: np.hypot(XY[i][0] - p[0], XY[i][1] - p[1]))
        orden.append(k)
        resto.remove(k)
        p = XY[k]
    return orden


def duracion(ids):
    pts = [(cx, cy)] + [XY[i] for i in ids]
    return sum(traslado(pts[k], pts[k + 1]) for k in range(len(ids))) + sum(MIN[i] for i in ids)


ang = {i: np.arctan2(y - cy, x - cx) for i, (x, y) in XY.items()}
orden_ang = sorted(XY, key=ang.get)
a_s = np.array([ang[i] for i in orden_ang])
inicio = int((np.argmax(np.diff(np.r_[a_s, a_s[0] + 2 * np.pi])) + 1) % len(a_s))
orden_ang = orden_ang[inicio:] + orden_ang[:inicio]
jornadas, actual = [], []
for i in orden_ang:
    if actual and duracion(vecino_mas_cercano(actual + [i])) > JORNADA_MIN:
        jornadas.append(vecino_mas_cercano(actual))
        actual = [i]
    else:
        actual.append(i)
jornadas.append(vecino_mas_cercano(actual))
plan = []
for j, ids in enumerate(jornadas, 1):
    p, acum = (cx, cy), 0.0
    for k, i in enumerate(ids, 1):
        t = traslado(p, XY[i])
        acum += t + MIN[i]
        plan.append({"jornada": j, "orden": k, "id": i, "DIST": nombre_dist(G.loc[G["id"] == i, "DIST"].iloc[0]),
                     "traslado_min": round(t), "minutos_estimados": MIN[i], "acumulado_min": round(acum)})
        p = XY[i]
PLAN = pd.DataFrame(plan)
PLAN.to_csv(f"{OUT_DATA}/plan_jornadas.csv", index=False, encoding="utf-8-sig")
TOTAL_H = PLAN.groupby("jornada")["acumulado_min"].max().sum() / 60

# ── Precision esperada del estimador de h ───────────────────────────────────
# Si las bodegas fueran 1 cada 120 habitantes, cuanto variaria h de una muestra
# a otra solo por azar (Poisson) o con variacion extra entre celdas
# (binomial negativa con dispersion alpha).
rs = np.random.default_rng(SEMILLA)
P_EST = U.groupby("estrato")["pob_celda"].sum().reindex(ORDEN)
Gs = G[G["rol"] == "muestra"]
prec = []
for alpha in (0.0, 0.3, 0.6):
    hs = []
    for _ in range(2000):
        tot = 0.0
        for e in ORDEN:
            pv = Gs.loc[Gs["estrato"] == e, "pob_celda"].to_numpy(float)
            mu = pv / H_REFERENCIA
            yb = rs.poisson(mu) if alpha == 0 else rs.negative_binomial(1 / alpha, 1 / (1 + alpha * mu))
            tot += P_EST[e] * yb.sum() / pv.sum()
        hs.append(P_EST.sum() / tot)
    lo, hi = np.percentile(hs, [2.5, 97.5])
    prec.append({"dispersion_alpha": alpha, "h_supuesto": H_REFERENCIA, "ic95_inf": round(lo, 1),
                 "ic95_sup": round(hi, 1), "semiamplitud_%": round(100 * (hi - lo) / 2 / H_REFERENCIA, 1)})
pd.DataFrame(prec).to_csv(f"{OUT_DATA}/precision_esperada.csv", index=False, encoding="utf-8-sig")

# ── Mapas ───────────────────────────────────────────────────────────────────
D = gpd.read_file("data/inei/limites_distritales_aqp.geojson").to_crs(UTM)
PETROL, GRIS = "#0E7C86", "#8A8A8A"


def mapa_general(ax):
    x0, y0, x1, y1 = Gu.total_bounds
    vista = gpd.GeoSeries.from_xy([x0 - 2500, x1 + 2500], [y0 - 2500, y1 + 2500], crs=UTM).union_all().envelope
    Dv = D.assign(geometry=D.intersection(vista))
    Dv.boundary.plot(ax=ax, color="#9aa3a8", lw=.6)
    for _, d in Dv[~Dv.is_empty].iterrows():
        p = d.geometry.representative_point()
        ax.text(p.x, p.y, d["NOMBDIST"].title(), fontsize=6, color="#6b7378", ha="center", clip_on=True)
    for rol, col, ms in (("reserva", GRIS, 18), ("muestra", PETROL, 30)):
        s = Gu[Gu["rol"] == rol]
        ax.scatter(s.geometry.centroid.x, s.geometry.centroid.y, s=ms, color=col, zorder=3,
                   label="Celda de la muestra" if rol == "muestra" else "Reserva")
        for _, f in s.iterrows():
            c = f.geometry.centroid
            ax.text(c.x + 120, c.y + 120, f["id"], fontsize=5.5, color=col, zorder=4)
    ax.set_xlim(x0 - 2500, x1 + 2500); ax.set_ylim(y0 - 2500, y1 + 2500)
    ax.set_aspect("equal"); ax.axis("off")
    ax.legend(loc="lower left", fontsize=7, frameon=False)


fig, ax = plt.subplots(figsize=(8.5, 8.5))
mapa_general(ax)
ax.set_title("Muestra del conteo de campo: 36 celdas y 12 reservas", loc="left", fontsize=11, weight="bold")
fig.savefig(f"{OUT_FIG}/campo_muestra.png", dpi=200, bbox_inches="tight", facecolor="white")
plt.close(fig)

PRINC = {"primary", "secondary", "tertiary", "trunk", "primary_link", "secondary_link"}
with PdfPages(f"{OUT_DOCS}/mapas_campo.pdf") as pdf:
    fig, ax = plt.subplots(figsize=(8.27, 11.69))
    mapa_general(ax)
    ax.set_title("Conteo de bodegas SIGRET-AQP: mapa general", loc="left", fontsize=12, weight="bold")
    pdf.savefig(fig); plt.close(fig)
    fig = plt.figure(figsize=(8.27, 11.69))
    fig.text(.08, .95, "Plan de jornadas sugerido", fontsize=13, weight="bold")
    fig.text(.08, .925, f"{len(jornadas)} jornadas de hasta 6,5 h con traslados (unas {TOTAL_H:.0f} h). Dos personas "
             f"juntas: {len(jornadas)} días; cada una por su lado: unos {int(np.ceil(len(jornadas) / 2))} días.\n"
             "Traslado estimado: 10 min fijos + distancia en línea recta × 1,4 a 18 km/h. Ajusta tras la primera jornada.",
             fontsize=8, color="#333", va="top")
    y = .875
    for j, g in PLAN.groupby("jornada"):
        fig.text(.08, y, f"Jornada {j} · unas {g['acumulado_min'].max() / 60:.1f} h".replace(".", ","),
                 fontsize=9, weight="bold")
        y -= .018
        for _, r in g.iterrows():
            fig.text(.11, y, f"{r['orden']}. {r['id']} · {r['DIST']} · traslado {r['traslado_min']} min · "
                     f"recorrido {r['minutos_estimados']} min", fontsize=8)
            y -= .016
        y -= .008
    pdf.savefig(fig); plt.close(fig)
    for i, f in Gu.iterrows():
        poly = f.geometry
        caja = poly.buffer(90)
        sub = E[E.intersects(caja)].copy()
        sub["geometry"] = sub.intersection(caja)
        fig, ax = plt.subplots(figsize=(8.27, 11.69))
        gpd.GeoSeries([caja], crs=UTM).plot(ax=ax, color="#f7f7f5")
        es_p = sub["highway"].astype(str).isin(PRINC)
        if (~es_p).any():
            sub[~es_p].plot(ax=ax, color="#b9bfc3", lw=1.6)
        if es_p.any():
            sub[es_p].plot(ax=ax, color="#8c969c", lw=3.0)
        gpd.GeoSeries([poly], crs=UTM).boundary.plot(ax=ax, color=PETROL, lw=3)
        # Un rotulo por calle, en su tramo mas largo dentro de la celda
        dentro = sub[sub.intersects(poly)].copy()
        dentro["geometry"] = dentro.intersection(poly)
        dentro["L"] = dentro.length
        dentro = dentro[dentro["name"].notna()]
        dentro["name"] = dentro["name"].astype(str).str.strip("[]").str.replace("'", "")
        for _, s in dentro.sort_values("L", ascending=False).drop_duplicates("name").head(10).iterrows():
            if s["L"] < 40:
                continue
            p = s.geometry.interpolate(.5, normalized=True)
            ax.text(p.x, p.y, s["name"], fontsize=7, color="#2b2d33", ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=.8))
        x0, y0, x1, y1 = caja.bounds
        ax.plot([x0 + 20, x0 + 120], [y0 + 20, y0 + 20], color="black", lw=2)
        ax.text(x0 + 70, y0 + 28, "100 m", ha="center", fontsize=7)
        ax.annotate("N", xy=(x1 - 25, y1 - 20), xytext=(x1 - 25, y1 - 70), ha="center",
                    arrowprops=dict(arrowstyle="-|>", color="black"), fontsize=9, weight="bold")
        ax.set_aspect("equal"); ax.axis("off")
        ax.set_title(f"{f['id']} · {nombre_dist(f['DIST'])} · {G.loc[i, 'estrato_texto']}"
                     + (" · RESERVA" if f["rol"] == "reserva" else ""), loc="left", fontsize=12, weight="bold")
        fig.text(.08, .06, f"Centro: {G.loc[i, 'lat']:.6f}, {G.loc[i, 'lon']:.6f}   ·   {G.loc[i, 'maps']}\n"
                 f"{G.loc[i, 'calles_km']} km de calles · unos {G.loc[i, 'minutos_estimados']} min · "
                 f"{int(G.loc[i, 'pob_celda'])} habitantes (2025) · celda H3 {f['h3']}\n"
                 "Recorre todas las calles dentro del borde y las dos veredas de las calles del borde. Registra cada "
                 "bodega,\nminimarket o tienda de abarrotes abierta; cadenas y supermercados con su tipo; un mercado "
                 "una sola vez,\ncon su número de puestos. Al terminar, envía el registro de cierre de la celda.",
                 fontsize=8, color="#333")
        pdf.savefig(fig); plt.close(fig)

# ── Formulario XLSForm para KoboToolbox ─────────────────────────────────────
try:
    import openpyxl  # noqa: F401
    survey = pd.DataFrame([
        ["start", "inicio", "", "", "", "", "", "", ""],
        ["end", "fin", "", "", "", "", "", "", ""],
        ["select_one personas", "registrador", "¿Quién registra?", "", "yes", "", "", "", ""],
        ["select_one celdas", "celda", "Celda", "Código del mapa (C01 a C36; R01 a R12 solo si reemplaza a una celda)",
         "yes", "", "minimal", "", ""],
        ["select_one tipos_registro", "tipo_registro", "¿Qué vas a registrar?", "", "yes", "", "", "", ""],
        ["geopoint", "ubicacion", "Ubicación", "Párate frente a la entrada y espera a que la precisión baje de 10 m",
         "yes", "${tipo_registro} = 'establecimiento'", "", "10", ""],
        ["image", "foto", "Foto de la fachada", "Sin personas en primer plano", "yes",
         "${tipo_registro} = 'establecimiento'", "", "", "max-pixels=1280"],
        ["select_one tipos_est", "tipo_est", "Tipo de establecimiento", "", "yes",
         "${tipo_registro} = 'establecimiento'", "", "", ""],
        ["select_one cadenas", "cadena", "¿Qué cadena?", "", "yes", "${tipo_est} = 'cadena'", "", "", ""],
        ["integer", "puestos", "¿Cuántos puestos de abarrotes tiene?", "Cuenta aproximada", "yes",
         "${tipo_est} = 'mercado'", "", "", ""],
        ["select_one accesos", "acceso", "¿Cómo se atiende?", "", "yes",
         "${tipo_registro} = 'establecimiento' and ${tipo_est} != 'cadena' and ${tipo_est} != 'mercado'",
         "", "", ""],
        ["select_one sino", "en_vivienda", "¿Funciona dentro de una vivienda?", "", "yes",
         "${tipo_registro} = 'establecimiento' and ${tipo_est} != 'cadena' and ${tipo_est} != 'mercado'",
         "", "", ""],
        ["select_one sino", "letrero", "¿Tiene letrero con nombre?", "", "yes",
         "${tipo_registro} = 'establecimiento'", "", "", ""],
        ["text", "nombre", "Nombre del letrero", "Opcional", "", "${letrero} = 'si'", "", "", ""],
        ["text", "nota_est", "Observación", "Opcional", "", "${tipo_registro} = 'establecimiento'", "", "", ""],
        ["select_one sino", "recorrido_completo", "¿Recorriste todas las calles de la celda?", "", "yes",
         "${tipo_registro} = 'cierre'", "", "", ""],
        ["select_multiple motivos", "motivo", "¿Por qué no se completó?", "", "yes",
         "${recorrido_completo} = 'no'", "", "", ""],
        ["text", "calles_pendientes", "Calles que faltaron", "", "", "${recorrido_completo} = 'no'", "", "", ""],
        ["integer", "minutos", "Minutos que tomó la celda", "", "yes", "${tipo_registro} = 'cierre'", "", "", ""],
        ["integer", "cerradas", "Bodegas cerradas en la visita pero identificables por su letrero",
         "Se anotan aquí y no como establecimiento", "yes", "${tipo_registro} = 'cierre'", "", "", ""],
        ["text", "obs_celda", "Observaciones de la celda", "Opcional", "", "${tipo_registro} = 'cierre'", "", "", ""],
    ], columns=["type", "name", "label", "hint", "required", "relevant", "appearance",
                "body::accuracyThreshold", "parameters"])
    survey["constraint"] = ""
    survey["constraint_message"] = ""
    survey.loc[survey["name"] == "minutos", ["constraint", "constraint_message"]] = [". > 0 and . < 600", "Entre 1 y 599"]
    survey.loc[survey["name"] == "cerradas", ["constraint", "constraint_message"]] = [". >= 0", "Cero o más"]
    survey.loc[survey["name"] == "puestos", ["constraint", "constraint_message"]] = [". >= 0", "Cero o más"]
    ch = [["personas", "a", "Persona A"], ["personas", "b", "Persona B"]]
    for _, f in G.sort_values("id").iterrows():
        ch.append(["celdas", f["id"].lower(), f"{f['id']} · {nombre_dist(f['DIST'])} · {f['estrato_texto']}"])
    ch += [["tipos_registro", "establecimiento", "Un establecimiento"],
           ["tipos_registro", "cierre", "Cierre de la celda (al terminar)"],
           ["tipos_est", "bodega", "Bodega o tienda de barrio"],
           ["tipos_est", "minimarket", "Minimarket independiente (autoservicio)"],
           ["tipos_est", "abarrotes", "Tienda de abarrotes"],
           ["tipos_est", "cadena", "Tienda de una cadena o supermercado (Mass, Tambo, Oxxo…)"],
           ["tipos_est", "mercado", "Mercado o galería con puestos de abarrotes (una sola vez)"],
           ["tipos_est", "dudoso", "No estoy seguro (se decide por la foto)"],
           ["cadenas", "mass", "Mass"], ["cadenas", "tambo", "Tambo"], ["cadenas", "oxxo", "Oxxo"],
           ["cadenas", "listo", "Listo"], ["cadenas", "repshop", "Repshop"],
           ["cadenas", "supermercado", "Supermercado (Plaza Vea, Tottus, Metro, Franco u otro)"],
           ["cadenas", "otra", "Otra"],
           ["accesos", "puerta", "Puerta abierta a la calle"],
           ["accesos", "ventana", "Ventana o reja de una vivienda"],
           ["sino", "si", "Sí"], ["sino", "no", "No"],
           ["motivos", "inseguridad", "Inseguridad"],
           ["motivos", "acceso_privado", "Condominio o calle cerrada"],
           ["motivos", "obra", "Obra o calle bloqueada"],
           ["motivos", "otro", "Otro"]]
    choices = pd.DataFrame(ch, columns=["list_name", "name", "label"])
    settings = pd.DataFrame([{"form_title": "Conteo de bodegas · SIGRET-AQP", "form_id": "conteo_bodegas_sigret",
                              "version": "2026110302", "instance_name": "concat(${celda}, ' · ', ${tipo_registro})"}])
    with pd.ExcelWriter(f"{OUT_DATA}/formulario_kobo.xlsx") as xw:
        survey.to_excel(xw, sheet_name="survey", index=False)
        choices.to_excel(xw, sheet_name="choices", index=False)
        settings.to_excel(xw, sheet_name="settings", index=False)
    print(f"  >> {OUT_DATA}/formulario_kobo.xlsx")
except ImportError:
    print("  (sin openpyxl: no se genero formulario_kobo.xlsx)")

# ── Resumen ─────────────────────────────────────────────────────────────────
m = G[G["rol"] == "muestra"]
print(f"Universo: {len(U)} celdas viables con >= {POB_MINIMA} habitantes")
print("Cortes de densidad (hab/km2):", {k: (round(a), round(b)) for k, (a, b) in cortes.iterrows()})
print(U.groupby("estrato").agg(celdas=("h3", "size"), pob=("pob_celda", "sum")).reindex(ORDEN).to_string())
print(f"Muestra: {len(m)} celdas, {m['calles_km'].sum():.1f} km de calles, "
      f"{m['minutos_estimados'].sum() / 60:.1f} h estimadas "
      f"(mediana {m['minutos_estimados'].median():.0f} min por celda)")
print(m.groupby("estrato")[["calles_km", "minutos_estimados"]].sum().reindex(ORDEN).to_string())
print(f"Plan: {len(jornadas)} jornadas, {TOTAL_H:.1f} h con traslados "
      f"(dos personas juntas: {len(jornadas)} dias; por separado: unos {int(np.ceil(len(jornadas) / 2))})")
print("Precision esperada de h si fuera 120:")
print(pd.DataFrame(prec).to_string(index=False))
print(f"  >> {OUT_DATA}/muestra_campo.csv, .geojson, .kml, plan_jornadas.csv, precision_esperada.csv; "
      f"{OUT_DOCS}/mapas_campo.pdf; {OUT_FIG}/campo_muestra.png")
