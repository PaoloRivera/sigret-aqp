#!/usr/bin/env python3
"""
13_diagramas.py

Dibuja los diagramas del Capitulo IV con los valores reales del repositorio:
  Figura 1  Fuentes de datos y su encadenamiento.
  Figura 2  Arquitectura fisica del sistema (fuera de linea / en linea).
  Figura 4  Flujo de modelado (predictores, modelos y validacion).
Los conteos se leen de data/, resultados/ y app_web/public/data/, de modo que
el diagrama no puede contradecir los datos.

Uso (desde la raiz del proyecto, despues de ejecutar_todo.sh):
    python scripts/13_diagramas.py
"""
import glob
import os

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch

FIG = "figuras"
os.makedirs(FIG, exist_ok=True)
PETROL, NARANJA, AMBAR, GRIS, CARMIN, VERDE = "#0E7C86", "#DE5D3F", "#F08F2E", "#5F6B73", "#B23A5B", "#3B7D3B"
FONDO = "#F4F6F7"


def num(n):
    return f"{n:,.0f}".replace(",", " ")


# ── Valores reales ──────────────────────────────────────────────────────────
grid = pd.read_parquet("resultados/grid.parquet", columns=["h3", "pob_2017", "es_nucleo"])
F = pd.read_parquet("resultados/features.parquet")
PRED = [c for c in F.columns if c not in ("h3", "DIST", "es_nucleo", "bloque") and not c.startswith(("mass_", "d_mass_"))]
n_fuga = len([c for c in F.columns if c.startswith(("mass_", "d_mass_"))])
mass = pd.read_parquet("resultados/mass_panel.parquet", columns=["codigo"])
comp = gpd.read_parquet("data/osm/competencia.parquet")
poi = gpd.read_parquet("data/osm/poi_flujo.parquet")
cen = pd.read_csv("data/inei/poblacion_censada_distritos.csv")
edif = pd.read_csv("data/edificaciones/edificaciones_h3.csv")
PB = pd.read_parquet("resultados/predicciones_backtesting.parquet", columns=["abrio"])
kb = {f: os.path.getsize(f"app_web/public/data/{f}") / 1024
      for f in ("hexes.json", "mass.json", "competencia.json", "meta.json")}
UBIGEOS = {"040101", "040102", "040103", "040104", "040105", "040107", "040109", "040110", "040112",
           "040116", "040117", "040122", "040123", "040124", "040126", "040128", "040129"}
mz = gpd.read_file(glob.glob("data/inei/*Manzanas_Poblacion*.dbf")[0], ignore_geometry=True, columns=["UBIGEO"])
n_mz = int(mz["UBIGEO"].isin(UBIGEOS).sum())


def caja(ax, x, y, w, h, titulo, cuerpo="", color=PETROL, tam=7.6, ttam=8.6, fondo="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=0.9", fc=fondo, ec=color, lw=1.4))
    ax.text(x + w / 2, y + h - 1.9, titulo, ha="center", va="top", fontsize=ttam, weight="bold", color=color)
    if cuerpo:
        ax.text(x + w / 2, y + h - 5.2, cuerpo, ha="center", va="top", fontsize=tam, color="#222", linespacing=1.4)


def flecha(ax, x0, y0, x1, y1, color=GRIS):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.2))


def lienzo(w, h, xmax=100, ymax=60):
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, xmax); ax.set_ylim(0, ymax)
    return fig, ax


# ═══════════════ Figura 1: fuentes de datos y su encadenamiento ═══════════════
fig, ax = lienzo(10.5, 5.6, ymax=56)
fuentes = [
    ("Censo Nacional 2017\n(INEI)", f"{num(n_mz)} manzanas\n{num(grid['pob_2017'].sum())} hab."),
    ("Censo Nacional 2025\n(INEI)", f"17 distritos\n{num(cen['pob_2025_censada'].sum())} hab."),
    ("Google Open Buildings\n2.5D Temporal", f"edificaciones\n2017 y 2023"),
    ("OpenStreetMap", f"{num(len(comp))} comercios\n{num(len(poi))} POIs · red vial"),
    ("Localizador de\nla cadena", f"{num(mass['codigo'].nunique())} tiendas\ncon coordenadas"),
    ("Internet Archive", "4 versiones\narchivadas"),
]
w = 15.2
for i, (t, c) in enumerate(fuentes):
    x = 1 + i * 16.4
    caja(ax, x, 43, w, 11.5, t, c, color=PETROL if i < 3 else AMBAR, tam=7.4, ttam=8)
caja(ax, 4, 24, 28, 12, "Población por celda", "ponderación areal 2017 +\nreparto del crecimiento 2025\nsegún edificaciones nuevas", tam=7.4)
caja(ax, 36, 24, 28, 12, "Variables del entorno", "demanda, accesibilidad,\nmorfología vial, POIs\ny competencia observada", tam=7.4)
caja(ax, 68, 24, 28, 12, "Variable objetivo", f"apertura de la cadena por año\n(2024, 2025, 2026);\n{int(PB['abrio'].sum())} aperturas 2025-2026", tam=7.4)
for i in range(3):
    flecha(ax, 1 + i * 16.4 + w / 2, 43, 18, 36.3)
flecha(ax, 1 + 3 * 16.4 + w / 2, 43, 50, 36.3)
flecha(ax, 1 + 4 * 16.4 + w / 2, 43, 82, 36.3)
flecha(ax, 1 + 5 * 16.4 + w / 2, 43, 82, 36.3)
caja(ax, 18, 6, 64, 10.5, f"Malla H3 r9 · {num(len(grid))} celdas · {F.shape[1]} columnas",
     f"{len(PRED)} predictores (se excluyen {n_fuga} variables derivadas de la red de la cadena)\n"
     "→ modelos supervisados, score de decisión y aplicación web", color=CARMIN, tam=7.6)
for x in (18, 50, 82):
    flecha(ax, x, 24, 50 if x == 50 else (34 if x == 18 else 66), 16.8)
ax.text(50, 1.6, "Padrón Reducido del RUC (SUNAT): evaluado y descartado como predictor (Tabla 8, E3).",
        ha="center", fontsize=7.4, color=GRIS, style="italic")
fig.savefig(f"{FIG}/figura01_fuentes_datos.png", dpi=200, facecolor="white", bbox_inches="tight")
plt.close(fig)
print("  >> figura01_fuentes_datos.png")

# ═══════════════ Figura 2: arquitectura fisica ═══════════════
fig, ax = lienzo(8.4, 8.6, ymax=82)
ax.add_patch(FancyBboxPatch((1, 39), 98, 42, boxstyle="round,pad=0.3,rounding_size=1.2", fc=FONDO, ec=GRIS, lw=0.8))
ax.text(3, 79.5, "FUERA DE LÍNEA · Python (una sola ejecución)", fontsize=8.6, weight="bold", color=GRIS, va="top")
caja(ax, 4, 64, 92, 11, "1. Datos de entrada (data/)",
     f"INEI 2017 ({num(n_mz)} manzanas) · INEI 2025 (17 distritos) · Open Buildings (2017 y 2023)\n"
     f"OpenStreetMap ({num(len(comp))} comercios, {num(len(poi))} POIs, red vial) · localizador ({num(mass['codigo'].nunique())} tiendas) · Internet Archive",
     tam=7.2)
caja(ax, 4, 50, 92, 10.5, "2. Procesamiento (pipeline.py y scripts de análisis)",
     "malla H3 y población · red histórica · características · modelos y validación · score\n"
     "→ resultados/ (parquet y CSV) y figuras/", tam=7.4)
caja(ax, 4, 40.5, 92, 7, "3. Serialización (scripts/10_generar_json_app.py)", "", tam=7.4)
ax.text(50, 42.4, f"hexes.json {kb['hexes.json']:.0f} KB · mass.json {kb['mass.json']:.0f} KB · "
        f"competencia.json {kb['competencia.json']:.0f} KB · meta.json {kb['meta.json']:.0f} KB",
        ha="center", fontsize=7.4, color="#222")
flecha(ax, 50, 64, 50, 60.8); flecha(ax, 50, 50, 50, 47.8)
ax.add_patch(FancyBboxPatch((1, 1), 98, 34, boxstyle="round,pad=0.3,rounding_size=1.2", fc="white", ec=PETROL, lw=0.8))
ax.text(3, 33.5, f"EN LÍNEA · navegador ({sum(kb.values()):.0f} KB de datos, sin backend de cómputo)",
        fontsize=8.6, weight="bold", color=PETROL, va="top")
flecha(ax, 88, 40.5, 88, 27.6)
caja(ax, 4, 18, 92, 9.2, "4. Aplicación web (Vue 3 + Vuetify + Pinia + MapLibre GL, servida con Laravel y Vite)",
     "carga de los cuatro JSON · hidratación a objetos · recálculo vectorizado del score (< 10 ms)", tam=7.4)
rutas = [("/panel", "Resumen"), ("/mapa", "Mapa"), ("/ranking", "Ranking"), ("/simulador", "Simulador"),
         ("/modelo", "Validación"), ("/fuentes", "Fuentes")]
for i, (r, n) in enumerate(rutas):
    caja(ax, 4 + i * 15.5, 3.5, 14, 8.5, n, r, color=AMBAR, tam=7.6, ttam=8.2)
flecha(ax, 50, 18, 50, 12.4)
fig.savefig(f"{FIG}/figura02_arquitectura.png", dpi=200, facecolor="white", bbox_inches="tight")
plt.close(fig)
print("  >> figura02_arquitectura.png")

# ═══════════════ Figura 4: flujo de modelado ═══════════════
fig, ax = lienzo(10.5, 6.2, ymax=62)
caja(ax, 30, 52, 40, 8, "Entrada", f"matriz de {num(len(F))} celdas × {F.shape[1]} columnas", tam=7.6)
caja(ax, 30, 40, 40, 9, "Filtro de fuga de información",
     f"se excluyen {n_fuga} variables de la red de la cadena\n→ {len(PRED)} predictores", color=CARMIN, tam=7.4)
flecha(ax, 50, 52, 50, 49.3)
modelos = [("Regresión logística", "estandarización\nC = 0,5\npesos de clase balanceados"),
           ("Random Forest", "800 árboles\nhoja mínima = 5 · √p atributos\npesos de clase por submuestra"),
           ("XGBoost", "400 árboles · profundidad 3\ntasa 0,05 · submuestreo 0,8\ncolumnas 0,7 · λ = 3")]
for i, (t, c) in enumerate(modelos):
    x = 2 + i * 33
    caja(ax, x, 22, 30, 13, t, c, color=VERDE, tam=7.2)
    flecha(ax, 50, 40, x + 15, 35.3)
caja(ax, 30, 8, 40, 9.5, "Ensamble por promedio de rangos", "p_potencial (0 a 1)\n→ score de decisión con pesos AHP", color=NARANJA, tam=7.4)
for i in range(3):
    flecha(ax, 2 + i * 33 + 15, 22, 50, 17.8)
ax.text(2, 3.8, f"Validación cruzada espacial: 5 particiones agrupadas en 52 bloques H3 r6 (objetivo: tienda en 2026).",
        fontsize=7.4, color=GRIS)
ax.text(2, 1.0, f"Backtesting temporal: entrenamiento con el estado al 31-12-2024; evaluación en {num(len(PB))} candidatos "
        f"contra {int(PB['abrio'].sum())} aperturas de 2025-2026.", fontsize=7.4, color=GRIS)
fig.savefig(f"{FIG}/figura04_flujo_modelado.png", dpi=200, facecolor="white", bbox_inches="tight")
plt.close(fig)
print("  >> figura04_flujo_modelado.png")
