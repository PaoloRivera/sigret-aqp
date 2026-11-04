#!/usr/bin/env python3
"""
verificar_huff.py — Reproduce el calculo del simulador (misma formula que
app_web/resources/js/stores/sigret.js) y genera la sensibilidad al parametro h.
Uso (desde la raiz del repo):  python verificar_huff.py
"""
import numpy as np, pandas as pd
RES = "resultados"
S_B, S_C, ALPHA = 45, 175, 1.0                  # m2 bodega, m2 tienda de la cadena
BASE = dict(h=120, g=180, S0=100, m=0.22, I=160000)

def huff(df, h, g, S0, m, I, f_pob=1.0):
    P = df["pob_k1"] * f_pob
    N = np.maximum(df["n_comp_osm_k1"], P / h)                       # ec. 1-2
    A = N * S_B ** ALPHA + df["mass_k1_2026"] * S_C ** ALPHA         # ec. 3
    C = S0 ** ALPHA / (S0 ** ALPHA + A)                              # ec. 5
    V = C * P * g; Bm = m * V                                        # ec. 6-7
    return pd.DataFrame({"P": P, "N": N, "A_rival": A, "cuota": C, "ventas": V,
                         "margen": Bm, "payback": I / Bm})

R = pd.read_parquet(f"{RES}/resultado_final.parquet")
V = R[R["viable"]]
top = V.nlargest(10, "SCORE")
jh = top[top["DIST"] == "JACOBO HUNTER"].head(1)
if jh.empty:                                     # sin celda de Jacobo Hunter en el Top-10
    jh = top.head(1)
pos = int(top.index.get_loc(jh.index[0])) + 1

print(f"=== Celda representativa ({jh['DIST'].iloc[0].title()}, puesto {pos} del Top-10, "
      f"score {jh['SCORE'].iloc[0]:.3f}, h3 {jh['h3'].iloc[0]}) ===")
print(huff(jh, **BASE).round(4).T.to_string())
print("Con +15 % de poblacion:", round(float(huff(jh, **BASE, f_pob=1.15)["ventas"].iloc[0]), 0))

r = huff(V, **BASE)
print(f"\n=== Celdas viables (n = {len(V)}) ===")
print(r[["ventas", "payback"]].describe(percentiles=[.05, .5, .95]).round(1).to_string())
print("Techo teorico de ventas  S0*g*h/s_b =", BASE["S0"] * BASE["g"] * BASE["h"] / S_B)
print("Celdas viables donde el conteo OSM supera la estimacion:", int((V["n_comp_osm_k1"] > V["pob_k1"] / BASE["h"]).sum()))

filas = []
for h in (60, 90, 120, 150, 200):
    a = huff(jh, **{**BASE, "h": h}).iloc[0]
    b = huff(V, **{**BASE, "h": h})
    filas.append({"h": h, "bodegas_JH": a["N"], "cuota_JH_%": 100 * a["cuota"], "ventas_JH": a["ventas"],
                  "margen_JH": a["margen"], "payback_JH": a["payback"],
                  "payback_mediana_viables": b["payback"].median()})
T = pd.DataFrame(filas)
print("\n=== Sensibilidad a h (Anexo J) ===")
print(T.round(2).to_string(index=False))
T.to_csv(f"{RES}/sensibilidad_huff_h.csv", index=False)
