#!/usr/bin/env python3
"""
figuras_capitulo5.py

Genera las ocho figuras del Capitulo V en PNG a 200 dpi: importancia de
variables, comparacion de modelos, distribucion territorial del Top-50, pesos
elicitados por AHP, puntajes SUS, dimensiones TAM, resultados por perfil de
usuario y comparacion entre las dos estrategias de validacion.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

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
    fig.savefig(nombre, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  >> {nombre}")


var = ["Población del hexágono", "Densidad poblacional",
       "Población alcanzable a 500 m", "Población del anillo externo",
       "POIs generadores a 500 m", "Colegios a 500 m",
       "Población alcanzable a 800 m", "Número de manzanas",
       "Densidad de intersecciones", "Metros de vía principal"]
imp = [.1615, .1556, .0811, .0777, .0607, .0505, .0491, .0440, .0384, .0361]
fig, ax = plt.subplots(figsize=(7.5, 4.4))
y = np.arange(len(var))[::-1]
col = [PETROL if v >= .06 else GRIS for v in imp]
ax.barh(y, [v * 100 for v in imp], color=col, height=.68)
ax.set_yticks(y); ax.set_yticklabels(var)
ax.set_xlabel("Importancia relativa (%)")
ax.set_title("Variables más influyentes del modelo Random Forest", loc="left", weight="bold")
for yy, v in zip(y, imp):
    ax.text(v * 100 + .25, yy, f"{v*100:.2f} %", va="center", fontsize=8.5)
ax.set_xlim(0, 19)
ax.text(.99, .04, "Las tres primeras acumulan 39,8 %", transform=ax.transAxes,
        ha="right", fontsize=8.5, style="italic", color=GRIS)
guardar(fig, "fig23_importancia_variables.png")

mod = ["Baseline\ndensidad", "Baseline\npoblación", "Baseline\nPOIs",
       "Regresión\nlogística", "Random\nForest", "XGBoost", "Ensamble"]
pr = [.080, .092, .062, .101, .103, .089, .108]
lift = [2.066, 3.099, 2.324, 3.357, 3.616, 3.357, 3.874]
es_base = [True, True, True, False, False, False, False]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.2))
x = np.arange(len(mod))
c = [GRIS if b else PETROL for b in es_base]
c[-1] = NARANJA
a1.bar(x, pr, color=c)
a1.set_xticks(x); a1.set_xticklabels(mod, fontsize=8)
a1.set_ylabel("PR-AUC"); a1.set_title("Área bajo la curva precisión-recall", loc="left", weight="bold")
for xx, v in zip(x, pr): a1.text(xx, v + .002, f"{v:.3f}", ha="center", fontsize=8)
a1.set_ylim(0, .125)
a2.bar(x, lift, color=c)
a2.axhline(3, color=CARMIN, ls="--", lw=1.4)
a2.text(len(mod) - .4, 3.06, "Criterio: Lift ≥ 3", ha="right", color=CARMIN, fontsize=8.5)
a2.set_xticks(x); a2.set_xticklabels(mod, fontsize=8)
a2.set_ylabel("Lift en el decil superior")
a2.set_title("Concentración de aperturas en el decil superior", loc="left", weight="bold")
for xx, v in zip(x, lift): a2.text(xx, v + .06, f"{v:.2f}", ha="center", fontsize=8)
a2.set_ylim(0, 4.6)
guardar(fig, "fig24_comparacion_modelos.png")

dist = ["Jacobo Hunter", "Socabaya", "Cerro Colorado", "Miraflores", "Tiabaya",
        "Mariano Melgar", "Cayma", "Yura", "Uchumayo", "Yanahuara",
        "Sachaca", "Paucarpata", "Alto Selva Alegre"]
n = [10, 9, 8, 7, 3, 3, 2, 2, 2, 1, 1, 1, 1]
pob = [49454, 75145, 196909, 60361, 16065, 62051, 91197, 32926, 13978,
       25247, 23913, 131073, 85757]
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
ax.set_xlim(0, 15)
guardar(fig, "fig25_distribucion_territorial.png")

crit = ["Demanda\nalcanzable", "Perfil\nde sitio", "Amenaza de\nretail moderno",
        "Competencia\ninstalada"]
pes = [.377, .257, .257, .109]
fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.2),
                             gridspec_kw={"width_ratios": [1.15, 1]})
x = np.arange(len(crit))
a1.bar(x, [p * 100 for p in pes], color=[PETROL, AMBAR, NARANJA, GRIS])
a1.set_xticks(x); a1.set_xticklabels(crit, fontsize=8.5)
a1.set_ylabel("Peso elicitado (%)")
a1.set_title("Pesos del panel de expertos (n = 10)", loc="left", weight="bold")
for xx, p in zip(x, pes): a1.text(xx, p * 100 + .7, f"{p*100:.1f} %", ha="center", fontsize=9)
a1.set_ylim(0, 45)

par = ["w_pot\n(perfil de sitio)", "pen_mass\n(penalización)", "radio\n(m, escala ÷1000)"]
prov = [.450, .600, .800]
elic = [.346, .257, .750]
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
guardar(fig, "fig26_pesos_ahp.png")

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
guardar(fig, "fig27_sus_rangos.png")

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
guardar(fig, "fig28_tam_dimensiones.png")

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
guardar(fig, "fig29_perfil_usuario.png")

mods = ["Regresión\nlogística", "Random\nForest", "XGBoost", "Ensamble"]
roc_cv = [.875, .929, .920, .919]
roc_bt = [.787, .777, .780, .798]
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
guardar(fig, "fig30_validaciones.png")

print("\nOcho figuras generadas.")
