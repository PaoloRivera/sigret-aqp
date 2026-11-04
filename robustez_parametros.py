#!/usr/bin/env python3
"""
robustez_parametros.py

Estabilidad del ranking frente a otros juegos de parametros del score:
  1. Parametros provisionales del investigador (w_pot = 0,45; pen_mass = 0,60;
     radio = 800 m) frente a los elicitados por el panel AHP (seccion 5.1.2).
  2. Pesos recalculados sin los tres expertos que requirieron segunda ronda
     (w_pot = 0,298; pen_mass = 0,275), con el radio del panel (750 m) y con la
     mediana del radio de esos siete expertos (800 m) (seccion 5.1.3.1).
  3. Sensibilidad del Top-10 (+-20 %) tomando como base los parametros
     provisionales, para compararla con la de los elicitados (Tabla 16).
Los pesos sin segunda ronda provienen de ahp_rondas.py (matrices finales del
panel, Anexo E). Este script solo recalcula el ranking con esos pesos.

Uso (desde la raiz del proyecto, despues de pipeline.py):
    python robustez_parametros.py
"""
import numpy as np
import pandas as pd
from scipy import stats

RES = "resultados"
ELICITADO = dict(w=0.344, pen=0.261, radio=750)
ESCENARIOS = {
    "Provisional del investigador": dict(w=0.45, pen=0.60, radio=800),
    "Sin segunda ronda, radio 750 m": dict(w=0.298, pen=0.275, radio=750),
    "Sin segunda ronda, radio 800 m": dict(w=0.298, pen=0.275, radio=800),
}

R = pd.read_parquet(f"{RES}/resultado_final.parquet")
v = R["viable"]


def score(w, pen, radio):
    riesgo = np.clip(1 - R["d_mass_2026"] / radio, 0, 1)
    s = (w * R["p_potencial"] + (1 - w) * R["dem_res_n"]) * (1 - pen * riesgo)
    return s.where(v, 0.0)


s0 = score(**ELICITADO)
filas = []
for nombre, p in ESCENARIOS.items():
    s1 = score(**p)
    fila = {"escenario": nombre, **p, "spearman_viables": stats.spearmanr(s0[v], s1[v]).statistic}
    for k in (10, 20, 50):
        fila[f"top{k}_compartido_pct"] = len(set(s0[v].nlargest(k).index) & set(s1[v].nlargest(k).index)) / k
    filas.append(fila)
T = pd.DataFrame(filas)
pd.set_option("display.width", 200)
print(T.round(3).to_string(index=False))
T.to_csv(f"{RES}/robustez_parametros.csv", index=False, encoding="utf-8-sig")

# Sensibilidad del Top-10 con los parametros provisionales como base
PROV = dict(w=0.45, pen=0.60, radio=800)


def score_p(w, pen, radio, pob):
    riesgo = np.clip(1 - R["d_mass_2026"] / radio, 0, 1)
    s = (w * R["p_potencial"] + (1 - w) * R["dem_res_n"]) * (1 - pen * riesgo)
    return s.where((R["pob_k1"] >= pob) & (R["mass_2026"] == 0), 0.0)


filas = []
for nombre_base, base in (("Elicitado", dict(**ELICITADO, pob=1500)), ("Provisional", dict(**PROV, pob=1500))):
    top0 = set(R.assign(S=score_p(**base)).nlargest(10, "S")["h3"])
    for par, etiqueta in (("w", "Peso del perfil de sitio"), ("pen", "Penalizacion"),
                          ("radio", "Radio de amenaza"), ("pob", "Umbral de poblacion")):
        for v in np.arange(-0.20, 0.21, 0.05):
            args = dict(base); args[par] = args[par] * (1 + v)
            top = set(R.assign(S=score_p(**args)).nlargest(10, "S")["h3"])
            filas.append({"base": nombre_base, "parametro": etiqueta, "variacion_pct": round(v * 100),
                          "permanencia": len(top & top0) / 10})
S = pd.DataFrame(filas)
S.to_csv(f"{RES}/sensibilidad_base_provisional.csv", index=False, encoding="utf-8-sig")
print("\nPermanencia del Top-10 (+-20 %) segun la base de parametros:")
print(S.pivot_table(index=["base", "variacion_pct"], columns="parametro", values="permanencia").to_string())
