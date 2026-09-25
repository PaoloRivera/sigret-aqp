#!/usr/bin/env python3
"""
sensibilidad_ranking.py

Genera la Figura 25: mide cuanto permanece el Top-10 de
ubicaciones cuando se varian los pesos y umbrales del score entre -20 % y
+20 %, y guarda la curva de sensibilidad junto con la tabla de datos crudos.
"""
import os

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Parametros elicitados por el panel de expertos (AHP)
W_POT = 0.344
PEN_MASS = 0.261
RADIO = 750
POB_MIN = 1500
UMBRAL = 0.70

F = gpd.read_parquet("resultados/resultado_final.parquet")


def calcular_score(w_pot=W_POT, pen_mass=PEN_MASS, radio=RADIO, pob_min=POB_MIN):
    riesgo = np.clip(1 - F["d_mass_2026"] / radio, 0, 1)
    s = ((w_pot * F["p_potencial"] + (1 - w_pot) * F["dem_res_n"])
         * (1 - pen_mass * riesgo))
    viable = (F["pob_k1"] >= pob_min) & (F["mass_2026"] == 0)
    return s.where(viable, 0.0)


base_top10 = set(F.assign(S=calcular_score()).nlargest(10, "S")["h3"])

variaciones = np.arange(-0.20, 0.21, 0.05)
parametros = {
    "Peso del perfil de sitio": lambda v: calcular_score(w_pot=W_POT * (1 + v)),
    "Penalizacion hard discount": lambda v: calcular_score(pen_mass=PEN_MASS * (1 + v)),
    "Radio de amenaza": lambda v: calcular_score(radio=RADIO * (1 + v)),
    "Umbral de poblacion": lambda v: calcular_score(pob_min=POB_MIN * (1 + v)),
}

filas = []
for nombre, fn in parametros.items():
    for v in variaciones:
        top = set(F.assign(S=fn(v)).nlargest(10, "S")["h3"])
        filas.append({"parametro": nombre,
                      "variacion_pct": round(v * 100),
                      "permanencia": len(top & base_top10) / 10})

T = pd.DataFrame(filas)
T.to_csv("resultados/tabla_sensibilidad.csv", index=False, encoding="utf-8-sig")

plt.rcParams.update({"font.size": 11, "figure.dpi": 150})
fig, ax = plt.subplots(figsize=(8, 5))
marcadores = ["o", "s", "^", "D"]
for (nombre, g), m in zip(T.groupby("parametro", sort=False), marcadores):
    ax.plot(g["variacion_pct"], g["permanencia"] * 100,
            marker=m, linewidth=2, markersize=6, label=nombre)

ax.axhline(UMBRAL * 100, color="crimson", linestyle="--", linewidth=1.5,
           label=f"Criterio de aceptacion ({UMBRAL:.0%})")
ax.axvline(0, color="grey", linewidth=0.8, alpha=0.5)
ax.set_xlabel("Variacion del parametro (%)")
ax.set_ylabel("Permanencia del Top-10 (%)")
ax.set_title("Sensibilidad del ranking ante variacion de los pesos del score")
ax.set_ylim(0, 105)
ax.set_xticks(range(-20, 21, 5))
ax.grid(alpha=0.25)
ax.legend(frameon=False, loc="lower center", fontsize=9)
fig.tight_layout()
os.makedirs("figuras", exist_ok=True)
fig.savefig("figuras/figura25_sensibilidad_ranking.png", bbox_inches="tight")

print(T.pivot(index="variacion_pct", columns="parametro",
              values="permanencia").round(2).to_string())
minimo = T["permanencia"].min()
print(f"\nPermanencia minima observada: {minimo:.0%}")
print(f"Criterio (>= {UMBRAL:.0%}): {'CUMPLE' if minimo >= UMBRAL else 'NO CUMPLE'}")
print("\n>> figura25_sensibilidad_ranking.png y tabla_sensibilidad.csv generadas")
