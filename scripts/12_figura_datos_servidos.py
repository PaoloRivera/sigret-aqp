#!/usr/bin/env python3
"""
12_figura_datos_servidos.py

Genera la Figura 19 (esquema de la estructura de datos servida) a partir de los
cuatro JSON reales de app_web/public/data: tamano de cada archivo, columnas de
la matriz de celdas y las tres primeras filas del ranking tal como se sirven.

Uso (desde la raiz del proyecto, despues de scripts/10_generar_json_app.py):
    python scripts/12_figura_datos_servidos.py
Salida: figuras/figura19_datos_servidos.png
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

D = "app_web/public/data"
FIG = "figuras"
os.makedirs(FIG, exist_ok=True)
PETROL, GRIS, FONDO = "#0E7C86", "#5F6B73", "#F4F6F7"

kb = {f: os.path.getsize(f"{D}/{f}") / 1024 for f in ("hexes.json", "mass.json", "competencia.json", "meta.json")}
H = json.load(open(f"{D}/hexes.json", encoding="utf-8"))
M = json.load(open(f"{D}/mass.json", encoding="utf-8"))
C = json.load(open(f"{D}/competencia.json", encoding="utf-8"))
T = json.load(open(f"{D}/meta.json", encoding="utf-8"))

# Tres primeras celdas del ranking con los parametros por defecto (misma formula que la aplicacion)
cols = H["cols"]
ix = {c: cols.index(c) for c in cols}


def score(r):
    if r[ix["pob_k1"]] < 1500 or r[ix["mass_2026"]] > 0:
        return 0.0
    riesgo = min(max(1 - r[ix["d_mass_2026"]] / 750, 0), 1)
    return (0.344 * r[ix["p_potencial"]] + 0.656 * r[ix["dem_res_n"]]) * (1 - 0.261 * riesgo)


filas = sorted(H["rows"], key=lambda r: -score(r))[:3]
mostrar = ["h3", "dist", "lat", "lon", "pob", "pob_k1", "n_comp_osm_k1", "d_mass_2026", "p_potencial"]


def fmt(c, v):
    return f'"{v[:7]}…"' if c == "h3" else f"{v:g}"


# Ahorro frente a un JSON convencional de objetos (nombre de columna repetido en cada fila)
objetos = [dict(zip(cols, [H["districts"][v] if c == "dist" else v for c, v in zip(cols, r)])) for r in H["rows"]]
ahorro = 1 - len(json.dumps(H, ensure_ascii=False, separators=(",", ":")).encode()) / \
    len(json.dumps(objetos, ensure_ascii=False, separators=(",", ":")).encode())

lineas = ["{", '  "cols": [' + ", ".join(f'"{c}"' for c in cols[:7]) + ", …],",
          '  "districts": [' + ", ".join(f'"{d.title()}"' for d in H["districts"][:3]) + ", …],", '  "rows": [']
for r in filas:
    lineas.append("    [" + ", ".join(fmt(c, r[ix[c]]) for c in mostrar) + f", …],  // {H['districts'][r[ix['dist']]].title()}")
lineas += [f"    …  ({len(H['rows']):,} filas)".replace(",", " "), "  ]", "}"]

fig = plt.figure(figsize=(10.5, 4.9))
ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off"); ax.set_xlim(0, 100); ax.set_ylim(0, 49)


def caja(x, y, w, h, titulo, cuerpo, tam=8.2, mono=True):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2,rounding_size=0.8", fc="white", ec=PETROL, lw=1.4))
    ax.add_patch(FancyBboxPatch((x, y + h - 4), w, 4, boxstyle="round,pad=0.2,rounding_size=0.8", fc=PETROL, ec=PETROL, lw=1.4))
    ax.text(x + 1, y + h - 2, titulo, color="white", weight="bold", fontsize=8.8, va="center")
    ax.text(x + 1, y + h - 5.4, cuerpo, color="#222", fontsize=tam, va="top", family="monospace" if mono else None,
            linespacing=1.5)


total = sum(kb.values())
ax.text(50, 47.3, f"{total:.0f} KB servidos · sin backend de cómputo", ha="center", fontsize=11, weight="bold", color=GRIS)
caja(1, 13, 61, 31, f"hexes.json · {kb['hexes.json']:.0f} KB · {len(H['rows']):,} celdas × {len(cols)} columnas".replace(",", " "),
     "\n".join(lineas), tam=6.9)
ax.text(2, 15.2, f"Las columnas se declaran una sola vez: {ahorro*100:.0f} % menos peso que un JSON de objetos.",
        fontsize=7.8, color=GRIS, style="italic")
caja(64, 30, 17, 14, f"mass.json · {kb['mass.json']:.0f} KB", f"{len(M)} tiendas:\ncódigo, dirección,\ndistrito, lat, lon,\naño de apertura", tam=7.4)
caja(83, 30, 16, 14, f"competencia · {kb['competencia.json']:.0f} KB", f"{len(C)} comercios:\nnombre, tipo,\nlat, lon", tam=7.4)
caja(64, 13, 35, 15, f"meta.json · {kb['meta.json']:.0f} KB",
     f"backtesting ({len(T['backtesting'])} modelos) y validación\ncruzada espacial; importancias de\n{len(T['importancias'])} variables; población de "
     f"{len(T['poblacion_distrito'])} distritos;\nprocedencia de {len(T['fuentes'])} fuentes", tam=7.4)
ax.plot([20, 82], [10.5, 10.5], color=GRIS, lw=1)
for x in (20, 82):
    ax.plot([x, x], [10.5, 13], color=GRIS, lw=1)
ax.annotate("", xy=(50, 7.6), xytext=(50, 10.5), arrowprops=dict(arrowstyle="-|>", color=GRIS, lw=1.2))
ax.add_patch(FancyBboxPatch((24, 1.4), 52, 5.8, boxstyle="round,pad=0.2,rounding_size=0.8", fc=FONDO, ec=GRIS, lw=1))
ax.text(50, 4.3, "Navegador: hidratación a objetos + recálculo vectorizado del score (< 10 ms)",
        ha="center", va="center", fontsize=8.8, color="#222")
fig.savefig(f"{FIG}/figura19_datos_servidos.png", dpi=200, facecolor="white", bbox_inches="tight")
print(f"  >> figura19_datos_servidos.png ({total:.0f} KB servidos; ahorro {ahorro*100:.1f} %)")
