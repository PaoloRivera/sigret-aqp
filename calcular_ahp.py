#!/usr/bin/env python3
"""
calcular_ahp.py

Calcula los pesos del score a partir de las matrices de comparacion pareada
del panel de expertos: obtiene el vector propio principal de cada matriz,
verifica la consistencia de cada experto, agrega los pesos validos por media
geometrica y los traduce a los parametros del score del pipeline.
"""
import itertools
import os
import sys

import numpy as np
import pandas as pd

CRITERIOS = {
    "C1": "Demanda alcanzable",
    "C2": "Perfil de sitio",
    "C3": "Competencia instalada",
    "C4": "Amenaza de retail moderno",
}
RI = {1: 0.00, 2: 0.00, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32}
UMBRAL_CR = 0.10
ARCHIVO = "matrices_ahp.csv"

W_POT_ACTUAL = 0.45
PEN_MASS_ACTUAL = 0.60


def matriz_desde_filas(sub, claves):
    n = len(claves)
    idx = {c: i for i, c in enumerate(claves)}
    A = np.ones((n, n))
    for r in sub.itertuples():
        i, j = idx[r.criterio_a], idx[r.criterio_b]
        A[i, j] = float(r.valor)
        A[j, i] = 1.0 / float(r.valor)
    return A


def pesos_y_cr(A):
    val, vec = np.linalg.eig(A)
    k = int(np.argmax(val.real))
    lmax = val.real[k]
    w = vec[:, k].real
    w = np.abs(w) / np.abs(w).sum()
    n = A.shape[0]
    CI = (lmax - n) / (n - 1) if n > 1 else 0.0
    CR = CI / RI.get(n, 1.0) if RI.get(n, 0) else 0.0
    return w, lmax, CI, CR


if not os.path.exists(ARCHIVO):
    print(f"[!] No se encontro {ARCHIVO}.")
    print("    Crea el archivo con las comparaciones del panel y vuelve a ejecutar.")
    print("    La cabecera es: experto,criterio_a,criterio_b,valor")
    sys.exit(1)

D = pd.read_csv(ARCHIVO)
claves = list(CRITERIOS)
filas, cons = [], []

for exp, sub in D.groupby("experto"):
    A = matriz_desde_filas(sub, claves)
    w, lmax, CI, CR = pesos_y_cr(A)
    cons.append({"experto": exp, "lambda_max": round(lmax, 4),
                 "CI": round(CI, 4), "CR": round(CR, 4),
                 "aceptable": "Si" if CR < UMBRAL_CR else "NO"})
    filas.append(dict({"experto": exp}, **{c: w[i] for i, c in enumerate(claves)}))

P = pd.DataFrame(filas)
C = pd.DataFrame(cons)

validos = C.loc[C["aceptable"] == "Si", "experto"]
Pv = P[P["experto"].isin(validos)]
if Pv.empty:
    print("[!] Ningun experto alcanzo CR < 0.10. Devuelve el ejercicio al panel.")
    sys.exit(1)

agg = {c: float(np.exp(np.log(Pv[c]).mean())) for c in claves}
tot = sum(agg.values())
agg = {c: v / tot for c, v in agg.items()}

aditivos = agg["C1"] + agg["C2"] + agg["C3"]
w_pot = agg["C2"] / aditivos
pen_mass = agg["C4"]

T = pd.DataFrame([
    {"Criterio": CRITERIOS[c], "Peso elicitado (AHP)": round(agg[c], 4)}
    for c in claves
])
T.to_csv("tabla11_ahp.csv", index=False, encoding="utf-8-sig")
C.to_csv("ahp_consistencia.csv", index=False, encoding="utf-8-sig")

print("=== PESOS AGREGADOS (media geometrica del panel) ===")
print(T.to_string(index=False))
print()
print("=== CONSISTENCIA POR EXPERTO ===")
print(C.to_string(index=False))
print()
print(f"Expertos evaluados        : {len(C)}")
print(f"Expertos con CR < 0.10    : {len(validos)}")
print(f"CR promedio del panel     : {C.loc[C['experto'].isin(validos),'CR'].mean():.4f}")
print()
print("=== PARAMETROS DEL SCORE DERIVADOS ===")
print(f"  w_pot     : {W_POT_ACTUAL:.2f} (provisional)  ->  {w_pot:.4f} (elicitado)")
print(f"  pen_mass  : {PEN_MASS_ACTUAL:.2f} (provisional)  ->  {pen_mass:.4f} (elicitado)")
print()
print("NOTA: el radio de amenaza NO se obtiene por AHP. Se elicita por pregunta")
print("      directa al panel y se reporta la mediana de las respuestas.")
print()
print(">> tabla11_ahp.csv y ahp_consistencia.csv generadas")
