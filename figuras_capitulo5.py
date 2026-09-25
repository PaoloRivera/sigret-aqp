#!/usr/bin/env python3
"""
figuras_capitulo5.py

Genera las ocho figuras del Capitulo V en PNG a 200 dpi: importancia de
variables, comparacion de modelos, distribucion territorial del Top-50, pesos
elicitados por AHP, puntajes SUS, dimensiones TAM, resultados por perfil de
usuario y comparacion entre las dos estrategias de validacion.
"""
import glob
import os

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

RES = "resultados"
FIG = "figuras"
os.makedirs(FIG, exist_ok=True)

plt.rcParams.update({
    "font.size": 10, "figure.dpi": 200, "savefig.dpi": 200,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.22, "grid.linestyle": "-",
})
PETROL = "#0E7C86"
NARANJA = "#DE5D3F"
AMBAR = "#F08F2E"
GRIS = "#8A8A8A"
CARMIN = "#B23A5B"


def guardar(fig, nombre):
    fig.tight_layout()
    fig.savefig(f"{FIG}/{nombre}", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  >> {nombre}")


ETIQUETAS = {
    "pob_2017": "Población del hexágono", "dens_hab_km2": "Densidad poblacional",
    "pob_k1": "Población alcanzable a 500 m", "pob_k1_ext": "Población del anillo externo",
    "n_poi_k1": "POIs generadores a 500 m", "n_colegio_k1": "Colegios a 500 m",
    "pob_k2": "Población alcanzable a 800 m", "n_mz": "Número de manzanas",
    "dens_intersec_km2": "Densidad de intersecciones", "long_princ_m": "Metros de vía principal",
}
I = pd.read_csv(f"{RES}/importancia_variables.csv").head(10)
var = [ETIQUETAS.get(v, v) for v in I["variable"]]
imp = I["importancia"].tolist()
fig, ax = plt.subplots(figsize=(7.5, 4.4))
y = np.arange(len(var))[::-1]
col = [PETROL if v >= .06 else GRIS for v in imp]
ax.barh(y, [v * 100 for v in imp], color=col, height=.68)
ax.set_yticks(y); ax.set_yticklabels(var)
ax.set_xlabel("Importancia relativa (%)")
ax.set_title("Variables más influyentes del modelo Random Forest", loc="left", weight="bold")
for yy, v in zip(y, imp):
    ax.text(v * 100 + .25, yy, f"{v*100:.2f} %", va="center", fontsize=8.5)
ax.set_xlim(0, max(imp) * 100 + 3)
ax.text(.99, .04, f"Las tres primeras acumulan {sum(imp[:3])*100:.1f} %".replace(".", ","), transform=ax.transAxes,
        ha="right", fontsize=8.5, style="italic", color=GRIS)
guardar(fig, "figura20_importancia_variables.png")

NOMBRES_BT = {
    "Baseline densidad": "Baseline\ndensidad", "Baseline pob. k1": "Baseline\npoblación",
    "Baseline POIs k1": "Baseline\nPOIs", "Regresion logistica": "Regresión\nlogística",
    "Random Forest": "Random\nForest", "XGBoost": "XGBoost", "Ensamble (rank avg)": "Ensamble",
}
BT = pd.read_csv(f"{RES}/resultados_backtesting.csv").set_index("modelo").loc[list(NOMBRES_BT)]
mod = list(NOMBRES_BT.values())
pr = BT["PR_AUC"].tolist()
lift = BT["Lift@10%"].tolist()
es_base = [m.startswith("Baseline") for m in BT.index]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.2))
x = np.arange(len(mod))
c = [GRIS if b else PETROL for b in es_base]
c[-1] = NARANJA
a1.bar(x, pr, color=c)
a1.set_xticks(x); a1.set_xticklabels(mod, fontsize=8)
a1.set_ylabel("PR-AUC"); a1.set_title("Área bajo la curva precisión-recall", loc="left", weight="bold")
for xx, v in zip(x, pr): a1.text(xx, v + .002, f"{v:.3f}", ha="center", fontsize=8)
a1.set_ylim(0, max(pr) * 1.15)
a2.bar(x, lift, color=c)
a2.axhline(3, color=CARMIN, ls="--", lw=1.4)
a2.text(-.4, max(max(lift), 3) * 1.12, "- - Criterio: Lift ≥ 3", ha="left", color=CARMIN, fontsize=8.5)
a2.set_xticks(x); a2.set_xticklabels(mod, fontsize=8)
a2.set_ylabel("Lift en el decil superior")
a2.set_title("Concentración de aperturas en el decil superior", loc="left", weight="bold")
for xx, v in zip(x, lift): a2.text(xx, v + .06, f"{v:.2f}", ha="center", fontsize=8)
a2.set_ylim(0, max(max(lift), 3) * 1.18)
guardar(fig, "figura21_comparacion_modelos.png")

UBIGEOS = {
    "040101": "AREQUIPA", "040102": "ALTO SELVA ALEGRE", "040103": "CAYMA",
    "040104": "CERRO COLORADO", "040105": "CHARACATO", "040107": "JACOBO HUNTER",
    "040109": "MARIANO MELGAR", "040110": "MIRAFLORES", "040112": "PAUCARPATA",
    "040116": "SABANDIA", "040117": "SACHACA", "040122": "SOCABAYA",
    "040123": "TIABAYA", "040124": "UCHUMAYO", "040126": "YANAHUARA",
    "040128": "YURA", "040129": "JLBR",
}
mz = gpd.read_file(glob.glob("data/inei/*Manzanas_Poblacion*.dbf")[0], ignore_geometry=True)
pob_dist = mz.groupby(mz["UBIGEO"].map(UBIGEOS))["T_TOTAL"].sum()
R = pd.read_parquet(f"{RES}/resultado_final.parquet")
top50 = R[R["viable"]].nlargest(50, "SCORE")["DIST"].value_counts()
dist = [d.title() for d in top50.index]
n = top50.tolist()
pob = [int(pob_dist[d]) for d in top50.index]
fig, ax = plt.subplots(figsize=(8.4, 4.6))
y = np.arange(len(dist))[::-1]
col = [NARANJA if v >= 7 else PETROL for v in n]
ax.barh(y, n, color=col, height=.68)
ax.set_yticks(y); ax.set_yticklabels(dist)
ax.set_xlabel("Ubicaciones en el Top-50")
ax.set_title("Distribución territorial de las oportunidades identificadas",
             loc="left", weight="bold")
for yy, v, p in zip(y, n, pob):
    ax.text(v + .18, yy, f"{v}   ({p:,} hab.)".replace(",", " "), va="center", fontsize=8)
ax.set_xlim(0, max(n) + 5)
guardar(fig, "figura23_distribucion_territorial.png")

crit = ["Demanda\nalcanzable", "Amenaza de\nretail moderno", "Perfil\nde sitio",
        "Competencia\ninstalada"]
pes = [.377, .261, .254, .108]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.2),
                             gridspec_kw={"width_ratios": [1.15, 1]})
x = np.arange(len(crit))
a1.bar(x, [p * 100 for p in pes], color=[PETROL, NARANJA, AMBAR, GRIS])
a1.set_xticks(x); a1.set_xticklabels(crit, fontsize=8.5)
a1.set_ylabel("Peso elicitado (%)")
a1.set_title("Pesos del panel de expertos (n = 10)", loc="left", weight="bold")
for xx, p in zip(x, pes): a1.text(xx, p * 100 + .7, f"{p*100:.1f} %", ha="center", fontsize=9)
a1.set_ylim(0, 45)

par = ["w_pot\n(perfil de sitio)", "pen_mass\n(penalización)", "radio\n(m, escala ÷1000)"]
prov = [.450, .600, .800]
elic = [pes[2] / (pes[0] + pes[2] + pes[3]), pes[1], .750]
x = np.arange(len(par)); w = .36
a2.bar(x - w/2, prov, w, label="Provisional", color=GRIS)
a2.bar(x + w/2, elic, w, label="Elicitado (AHP)", color=PETROL)
a2.set_xticks(x); a2.set_xticklabels(par, fontsize=8.5)
a2.set_title("Parámetros del score antes y después", loc="left", weight="bold")
a2.legend(frameon=False, fontsize=8.5)
for xx, a, b in zip(x, prov, elic):
    a2.text(xx - w/2, a + .015, f"{a:.3f}", ha="center", fontsize=8)
    a2.text(xx + w/2, b + .015, f"{b:.3f}", ha="center", fontsize=8)
a2.set_ylim(0, .95)
guardar(fig, "figura24_pesos_ahp.png")

S = np.array([77.5, 85.0, 65.0, 80.0, 72.5, 82.5, 67.5, 87.5, 75.0, 80.0,
              70.0, 90.0, 75.0, 77.5, 82.5])
rangos = ["Pobre\n(< 50)", "Aceptable\n(50 – 70)", "Buena\n(70 – 85)", "Excelente\n(> 85)"]
cnt = [int((S < 50).sum()), int(((S >= 50) & (S < 70)).sum()),
       int(((S >= 70) & (S <= 85)).sum()), int((S > 85).sum())]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.2))
x = np.arange(4)
a1.bar(x, cnt, color=[CARMIN, AMBAR, PETROL, "#0A5B63"])
a1.set_xticks(x); a1.set_xticklabels(rangos, fontsize=8.5)
a1.set_ylabel("N.º de participantes")
a1.set_title("Distribución de puntajes SUS por rango cualitativo", loc="left", weight="bold")
for xx, v in zip(x, cnt):
    if v: a1.text(xx, v + .12, f"{v}  ({v/15*100:.1f} %)", ha="center", fontsize=8.5)
a1.set_ylim(0, 13)

a2.hist(S, bins=np.arange(60, 95, 5), color=PETROL, edgecolor="white")
a2.axvline(68, color=GRIS, ls=":", lw=1.6)
a2.text(68.4, 4.6, "Promedio\nhistórico: 68", fontsize=8, color=GRIS)
a2.axvline(75, color=CARMIN, ls="--", lw=1.6)
a2.text(75.4, 3.4, "Criterio: 75", fontsize=8, color=CARMIN)
a2.axvline(S.mean(), color=NARANJA, lw=2)
a2.text(S.mean() + .4, 2.2, f"M = {S.mean():.2f}", fontsize=8.5, color=NARANJA, weight="bold")
a2.set_xlabel("Puntaje SUS"); a2.set_ylabel("Frecuencia")
a2.set_title("Histograma de puntajes individuales", loc="left", weight="bold")
guardar(fig, "figura26_distribucion_sus.png")

dim = ["Utilidad\npercibida", "Facilidad de uso\npercibida", "Intención\nde uso"]
m = [4.16, 4.09, 4.16]
de = [0.35, 0.35, 0.49]
fig, ax = plt.subplots(figsize=(7.2, 4.3))
x = np.arange(3)
ax.bar(x, m, yerr=de, capsize=7, color=[PETROL, AMBAR, NARANJA],
       error_kw={"ecolor": "#444", "lw": 1.3})
ax.axhline(4.0, color=CARMIN, ls="--", lw=1.5)
ax.text(2.42, 4.03, "Criterio: 4,0", ha="right", color=CARMIN, fontsize=8.5)
ax.set_xticks(x); ax.set_xticklabels(dim)
ax.set_ylabel("Puntuación media (escala 1 – 5)")
ax.set_ylim(1, 5.2)
ax.set_title("Aceptación tecnológica por dimensión (n = 15)", loc="left", weight="bold")
for xx, v, s in zip(x, m, de):
    ax.text(xx, v + s + .09, f"{v:.2f}", ha="center", fontsize=9.5, weight="bold")
guardar(fig, "figura27_dimensiones_tam.png")

perfiles = ["Corredores\ninmobiliarios", "Estudiantes\nde posgrado",
            "Docentes\ndel área", "Propietarios\nde minimarket"]
sus_p = [84.38, 77.50, 75.83, 74.00]
tam_p = [4.49, 4.11, 4.07, 3.90]
nn = [4, 3, 3, 5]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.3))
x = np.arange(4)
c = [PETROL, PETROL, PETROL, NARANJA]
a1.bar(x, sus_p, color=c)
a1.axhline(75, color=CARMIN, ls="--", lw=1.4)
a1.text(3.42, 75.4, "Criterio: 75", ha="right", color=CARMIN, fontsize=8.5)
a1.set_xticks(x); a1.set_xticklabels(perfiles, fontsize=8)
a1.set_ylabel("Puntaje SUS"); a1.set_ylim(60, 92)
a1.set_title("Usabilidad percibida por perfil", loc="left", weight="bold")
for xx, v, k in zip(x, sus_p, nn):
    a1.text(xx, v + .7, f"{v:.2f}\n(n={k})", ha="center", fontsize=8.5)
a2.bar(x, tam_p, color=c)
a2.axhline(4.0, color=CARMIN, ls="--", lw=1.4)
a2.text(3.42, 4.02, "Criterio: 4,0", ha="right", color=CARMIN, fontsize=8.5)
a2.set_xticks(x); a2.set_xticklabels(perfiles, fontsize=8)
a2.set_ylabel("TAM global (1 – 5)"); a2.set_ylim(3.2, 4.8)
a2.set_title("Aceptación tecnológica por perfil", loc="left", weight="bold")
for xx, v in zip(x, tam_p): a2.text(xx, v + .03, f"{v:.2f}", ha="center", fontsize=8.5)
guardar(fig, "figura28_resultados_perfil.png")

mods = ["Regresión\nlogística", "Random\nForest", "XGBoost", "Ensamble"]
CV = pd.read_csv(f"{RES}/resultados_cv.csv").set_index("modelo")
roc_cv = CV.loc[["LR", "RF", "XGB", "ENS"], "ROC_AUC"].tolist()
roc_bt = BT.loc[["Regresion logistica", "Random Forest", "XGBoost", "Ensamble (rank avg)"],
                "ROC_AUC"].tolist()
fig, ax = plt.subplots(figsize=(7.6, 4.3))
x = np.arange(4); w = .36
ax.bar(x - w/2, roc_cv, w, label="Validación cruzada espacial", color=PETROL)
ax.bar(x + w/2, roc_bt, w, label="Backtesting temporal", color=AMBAR)
ax.axhline(.5, color=GRIS, ls=":", lw=1.4)
ax.text(3.45, .515, "Azar", ha="right", color=GRIS, fontsize=8.5)
ax.set_xticks(x); ax.set_xticklabels(mods, fontsize=9)
ax.set_ylabel("ROC-AUC"); ax.set_ylim(.4, 1.0)
ax.set_title("Desempeño bajo las dos estrategias de validación",
             loc="left", weight="bold")
ax.legend(frameon=False, fontsize=8.5, loc="lower right")
for xx, a, b in zip(x, roc_cv, roc_bt):
    ax.text(xx - w/2, a + .01, f"{a:.3f}", ha="center", fontsize=8)
    ax.text(xx + w/2, b + .01, f"{b:.3f}", ha="center", fontsize=8)
guardar(fig, "figura22_desempeno_validaciones.png")

print("\nOcho figuras generadas.")
