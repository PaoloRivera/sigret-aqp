#!/usr/bin/env python3
"""
evaluacion_ronda2.py

Segunda ronda de evaluacion de usabilidad (SUS) y aceptacion (TAM) con
propietarios de minimarket, sobre el modo comerciante (observacion 5).

Entrada, una de dos:
  --kobo data/encuestas/kobo/ronda2.xlsx
        exportacion de KoboToolbox (Data > Downloads > XLS, "XML values and
        headers"). Esa carpeta no se publica: tiene las respuestas abiertas y la
        hora de cada envio. El script escribe la version publicable,
        data/encuestas/ronda2_respuestas.csv, sin texto libre ni horas.
  --respuestas data/encuestas/ronda2_respuestas.csv
        la version publicable, para reproducir el analisis.

Muestra principal: duenos de minimarket que aceptaron responder (rol =
dueno_minimarket). Se informan aparte, como sensibilidad, (a) sin quienes ya
conocian el proyecto y (b) con duenos de bodega y administradores.

Analisis, fijado antes de recoger los datos:
  - SUS de cada participante (Brooke, 1996): (impares - 1) + (5 - pares), x 2,5.
  - TAM: media de cada dimension (utilidad u1-u6, facilidad f1-f6, intencion
    i1-i3) y global.
  - Media, DE, mediana, IC 95 % t y bootstrap (10 000 remuestreos, semilla 42).
  - Shapiro-Wilk y Wilcoxon de una muestra, unilateral (mayor que): SUS frente a
    68 y a 75; cada dimension TAM frente a 4,0. Tamano de efecto: correlacion
    biserial por rangos.
  - Alfa de Cronbach del SUS (items orientados) y de cada dimension TAM.
  - Regla: el criterio se cumple con significacion si p < 0,05; se cumple solo en
    el valor puntual si la media llega al criterio con p >= 0,05; no se cumple si
    la media queda por debajo. Con menos de 15 participantes se informa, pero se
    advierte que la muestra es menor a la minima planificada.
  - Items con la media orientada mas baja: lo que mas les costo.

Salidas: resultados/ronda2/ (pruebas, items, participantes, perfil) y
resultados/ronda2/RESUMEN_RONDA2.md con los parrafos para la tesis. Las
respuestas abiertas van a data/encuestas/kobo/respuestas_abiertas.txt (no se
publica) para leerlas a mano.

Uso, desde la raiz del proyecto:
    python evaluacion_ronda2.py --kobo data/encuestas/kobo/ronda2.xlsx
    python evaluacion_ronda2.py --respuestas data/encuestas/ronda2_respuestas.csv
"""
import argparse
import os

import numpy as np
import pandas as pd
from scipy import stats

ap = argparse.ArgumentParser()
g = ap.add_mutually_exclusive_group(required=True)
g.add_argument("--kobo")
g.add_argument("--respuestas")
ap.add_argument("--salida", default="resultados/ronda2")
args = ap.parse_args()

SUS = [f"s{i}" for i in range(1, 11)]
U = [f"u{i}" for i in range(1, 7)]
F = [f"f{i}" for i in range(1, 7)]
I = [f"i{i}" for i in range(1, 4)]
ITEMS = SUS + U + F + I
PERFIL = ["rol", "anios", "edad", "conocia", "dispositivo", "tarea", "minutos"]
PUBLICO = "data/encuestas/ronda2_respuestas.csv"
N_MINIMO, N_PLAN = 15, 20
RONDA1 = {"n": 5, "SUS": 74.00, "Utilidad": 3.97, "Facilidad": 3.87, "Intencion": 3.87, "TAM_global": 3.90}
rng = np.random.default_rng(42)
os.makedirs(args.salida, exist_ok=True)


def coma(x, d=2):
    return f"{x:.{d}f}".replace(".", ",")


def pval(p):
    return "p < 0,001" if p < 0.001 else f"p = {coma(p, 3)}"


# ─────────────────────────── lectura ───────────────────────────
if args.kobo:
    K = pd.read_excel(args.kobo)
    K.columns = [str(c).split("/")[-1] for c in K.columns]   # quita prefijos de grupo, si los hubiera
    K = K[K["consentimiento"].astype(str) == "si"].copy()
    K = K[K["rol"].astype(str) != "otro"]
    K = K.dropna(subset=ITEMS)
    if "inicio" in K.columns:
        K = K.sort_values("inicio")
    K = K.reset_index(drop=True)
    abiertas = []
    for j, r in K.iterrows():
        for c in ("dificil", "agregar"):
            if c in K.columns and isinstance(r.get(c), str) and r[c].strip():
                abiertas.append(f"R2-{j + 1:02d} [{c}] {r[c].strip()}")
    with open(os.path.join(os.path.dirname(args.kobo), "respuestas_abiertas.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(abiertas) + "\n")
    D = K[PERFIL + ITEMS].copy()
    D.insert(0, "participante", [f"R2-{j + 1:02d}" for j in range(len(D))])
    D.to_csv(PUBLICO, index=False)
    print(f"{len(D)} formularios validos -> {PUBLICO}; {len(abiertas)} respuestas abiertas (no se publican)")
else:
    D = pd.read_csv(args.respuestas)

D[ITEMS] = D[ITEMS].astype(int)
assert D[ITEMS].isin([1, 2, 3, 4, 5]).all().all(), "Hay respuestas fuera de la escala 1-5"


def puntajes(X):
    X = X.copy()
    impares, pares = SUS[0::2], SUS[1::2]
    X["SUS"] = ((X[impares] - 1).sum(axis=1) + (5 - X[pares]).sum(axis=1)) * 2.5
    X["Utilidad"] = X[U].mean(axis=1)
    X["Facilidad"] = X[F].mean(axis=1)
    X["Intencion"] = X[I].mean(axis=1)
    X["TAM_global"] = X[U + F + I].mean(axis=1)
    return X


def alfa(M):
    M = np.asarray(M, float)
    k = M.shape[1]
    return k / (k - 1) * (1 - M.var(axis=0, ddof=1).sum() / M.sum(axis=1).var(ddof=1))


def prueba(x, mu0):
    x = np.asarray(x, float)
    n = len(x)
    d = x - mu0
    dd = d[d != 0]
    r = stats.rankdata(np.abs(dd))
    wp, wm = r[dd > 0].sum(), r[dd < 0].sum()
    p = stats.wilcoxon(d, alternative="greater", zero_method="wilcox").pvalue if len(dd) else 1.0
    sw = stats.shapiro(x) if n >= 3 and np.ptp(x) > 0 else None
    bm = [rng.choice(x, n).mean() for _ in range(10000)]
    t = stats.t.ppf(0.975, n - 1) * x.std(ddof=1) / np.sqrt(n)
    m = x.mean()
    estado = ("cumplido con significación" if (m >= mu0 and p < 0.05)
              else "cumplido solo en el valor puntual" if m >= mu0 else "no cumplido")
    return {"n": n, "media": m, "de": x.std(ddof=1), "mediana": np.median(x), "minimo": x.min(),
            "maximo": x.max(), "IC95_t_inf": m - t, "IC95_t_sup": m + t,
            "IC95_boot_inf": np.percentile(bm, 2.5), "IC95_boot_sup": np.percentile(bm, 97.5),
            "Shapiro_W": sw.statistic if sw else np.nan, "Shapiro_p": sw.pvalue if sw else np.nan,
            "criterio": mu0, "n_efectivo": len(dd), "W_mas": wp, "W_menos": wm,
            "Wilcoxon_p_unilateral": p, "r_rangos": (wp - wm) / (wp + wm) if len(dd) else 0.0,
            "estado": estado}


def analizar(X, nombre):
    X = puntajes(X)
    filas = [dict(muestra=nombre, variable="SUS", **prueba(X["SUS"], 68)),
             dict(muestra=nombre, variable="SUS", **prueba(X["SUS"], 75))]
    for v in ("Utilidad", "Facilidad", "Intencion", "TAM_global"):
        filas.append(dict(muestra=nombre, variable=v, **prueba(X[v], 4.0)))
    T = pd.DataFrame(filas)
    orient = X[SUS].copy()
    orient[SUS[1::2]] = 6 - orient[SUS[1::2]]
    al = {"SUS": alfa(orient), "Utilidad": alfa(X[U]), "Facilidad": alfa(X[F]), "Intencion": alfa(X[I])}
    T["alfa_Cronbach"] = T["variable"].map(al)
    return X, T, orient


principal = D[D["rol"] == "dueno_minimarket"].reset_index(drop=True)
muestras = {"principal": principal,
            "sin_conocimiento_previo": principal[principal["conocia"] == "no"].reset_index(drop=True),
            "todos_los_negocios": D.reset_index(drop=True)}
tablas, Xp, orient = [], None, None
for nombre, M in muestras.items():
    if len(M) < 3:
        print(f"  {nombre}: {len(M)} participantes, no alcanza para el analisis")
        continue
    X, T, o = analizar(M, nombre)
    tablas.append(T)
    if nombre == "principal":
        Xp, orient = X, o
if Xp is None:
    raise SystemExit("La muestra principal tiene menos de 3 duenos de minimarket.")
PR = pd.concat(tablas, ignore_index=True)
PR.to_csv(os.path.join(args.salida, "ronda2_pruebas.csv"), index=False)

# Items: media orientada (5 = la mejor respuesta posible) para ver que les costo.
# Textos breves de los items (los completos estan en scripts/16_formulario_ronda2.py)
textos = {
    "s1": "SUS 1 «me gustaría usarlo con frecuencia»", "s2": "SUS 2 «innecesariamente complejo»",
    "s3": "SUS 3 «fácil de usar»", "s4": "SUS 4 «necesitaría apoyo técnico»",
    "s5": "SUS 5 «funciones bien integradas»", "s6": "SUS 6 «demasiada inconsistencia»",
    "s7": "SUS 7 «se aprende rápido»", "s8": "SUS 8 «engorroso»", "s9": "SUS 9 «me sentí seguro»",
    "s10": "SUS 10 «tuve que aprender mucho antes»",
    "u1": "U1 «evaluar más rápido»", "u2": "U2 «mejor decisión»", "u3": "U3 «más productividad»",
    "u4": "U4 «menos riesgo»", "u5": "U5 «comparar alternativas»", "u6": "U6 «útil en general»",
    "f1": "F1 «fácil de aprender»", "f2": "F2 «muestra lo que quiero ver»",
    "f3": "F3 «pasos comprensibles»", "f4": "F4 «volverme hábil»", "f5": "F5 «interacción clara»",
    "f6": "F6 «fácil en general»", "i1": "I1 «intención de usarlo»", "i2": "I2 «lo recomendaría»",
    "i3": "I3 «lo usaría para invertir»",
}
NOMBRE = {"SUS": "SUS", "Utilidad": "Utilidad", "Facilidad": "Facilidad", "Intencion": "Intención",
          "TAM_global": "TAM global"}
it = pd.concat([orient, Xp[U + F + I]], axis=1)
IT = pd.DataFrame({"item": it.columns, "etiqueta": [textos[c] for c in it.columns],
                   "media_orientada": it.mean().values, "de": it.std(ddof=1).values,
                   "pct_favorable": (it >= 4).mean().values * 100}).sort_values("media_orientada")
IT.to_csv(os.path.join(args.salida, "ronda2_items.csv"), index=False)
Xp[["participante", "rol", "conocia", "dispositivo", "tarea", "SUS", "Utilidad", "Facilidad",
    "Intencion", "TAM_global"]].to_csv(os.path.join(args.salida, "ronda2_participantes.csv"), index=False)
perfil = {c: principal[c].value_counts().to_dict() for c in ("anios", "edad", "conocia", "dispositivo", "tarea")}
pd.DataFrame([(c, k, v) for c, d in perfil.items() for k, v in d.items()],
             columns=["variable", "valor", "n"]).to_csv(os.path.join(args.salida, "ronda2_perfil.csv"), index=False)

# ─────────────────────────── resumen y parrafos ───────────────────────────
P = PR[PR["muestra"] == "principal"].set_index(["variable", "criterio"])
n = len(Xp)
s68, s75 = P.loc[("SUS", 68)], P.loc[("SUS", 75)]
dims = {"Utilidad": "utilidad percibida", "Facilidad": "facilidad de uso percibida", "Intencion": "intención de uso"}
L = ["# Segunda ronda de evaluación (propietarios de minimarket)", "",
     f"Muestra principal: {n} dueños de minimarket (mínimo planificado {N_MINIMO}, objetivo {N_PLAN}). "
     f"Todos los formularios válidos: {len(D)}.", ""]
if n < N_MINIMO:
    L += [f"**Atención: la muestra ({n}) es menor que el mínimo planificado de {N_MINIMO}.**", ""]
L += ["## Resultados", "", "| Variable | Criterio | Media | DE | IC 95 % (t) | Wilcoxon | r | Alfa | Estado |",
      "|---|---|---|---|---|---|---|---|---|"]
for (v, c), r in P.iterrows():
    alf = "—" if pd.isna(r["alfa_Cronbach"]) else coma(r["alfa_Cronbach"], 3)
    L.append(f"| {NOMBRE[v]} | {coma(c, 1)} | {coma(r['media'])} | {coma(r['de'])} | {coma(r['IC95_t_inf'])} a "
             f"{coma(r['IC95_t_sup'])} | W+ = {coma(r['W_mas'], 1)}; {pval(r['Wilcoxon_p_unilateral'])} | "
             f"{coma(r['r_rangos'])} | {alf} | {r['estado']} |")
L += ["", "## Ítems con la media más baja (lo que más les costó)", ""]
for _, r in IT.head(5).iterrows():
    L.append(f"- {r['etiqueta']}: {coma(r['media_orientada'])} de 5 ({coma(r['pct_favorable'], 0)} % favorable)")
L += ["", "## Sensibilidad", ""]
for nombre in ("sin_conocimiento_previo", "todos_los_negocios"):
    S = PR[(PR["muestra"] == nombre) & (PR["variable"] == "SUS") & (PR["criterio"] == 75)]
    if len(S):
        r = S.iloc[0]
        L.append(f"- {nombre}: n = {r['n']}, SUS {coma(r['media'])}, Wilcoxon frente a 75 {pval(r['Wilcoxon_p_unilateral'])}")

# Parrafos para la tesis (5.1.4, subseccion nueva)
cumple75 = s75["estado"]
txt_sus = (f"Los {n} propietarios de minimarket que usaron el modo comerciante le dieron un puntaje SUS promedio "
           f"de {coma(s68['media'])} (DE = {coma(s68['de'])}; IC 95 %: {coma(s68['IC95_t_inf'])} a "
           f"{coma(s68['IC95_t_sup'])}), frente a 74,00 de los cinco propietarios de la primera ronda. ")
if s68["Wilcoxon_p_unilateral"] < 0.05 and s68["media"] >= 68:
    txt_sus += f"El puntaje supera de forma significativa el promedio histórico de 68 (Wilcoxon, {pval(s68['Wilcoxon_p_unilateral'])}). "
else:
    txt_sus += f"No se demuestra que supere el promedio histórico de 68 (Wilcoxon, {pval(s68['Wilcoxon_p_unilateral'])}). "
if cumple75 == "cumplido con significación":
    txt_sus += (f"También supera el criterio de 75 con significación (W+ = {coma(s75['W_mas'], 1)}; "
                f"{pval(s75['Wilcoxon_p_unilateral'])}; r = {coma(s75['r_rangos'])}), por lo que el criterio de "
                "usabilidad se cumple para el usuario objetivo.")
elif cumple75 == "cumplido solo en el valor puntual":
    txt_sus += (f"Llega al criterio de 75 en el valor promedio, pero la diferencia no es significativa "
                f"(W+ = {coma(s75['W_mas'], 1)}; {pval(s75['Wilcoxon_p_unilateral'])}), así que el criterio se cumple "
                "solo en el valor puntual.")
else:
    txt_sus += (f"No alcanza el criterio de 75 (Wilcoxon, {pval(s75['Wilcoxon_p_unilateral'])}): el criterio de "
                "usabilidad no se cumple para el usuario objetivo.")
txt_tam = "En el TAM, "
partes = []
for v, nom in dims.items():
    r = P.loc[(v, 4.0)]
    partes.append(f"la {nom} obtuvo {coma(r['media'])} ({r['estado']}; Wilcoxon frente a 4,0, "
                  f"{pval(r['Wilcoxon_p_unilateral'])}; alfa = {coma(r['alfa_Cronbach'], 3)})")
txt_tam += "; ".join(partes) + ". "
peor = IT.iloc[0]
txt_tam += (f"El ítem con la media más baja fue {peor['etiqueta']} ({coma(peor['media_orientada'])} de 5, "
            "con la escala de los ítems negativos invertida).")
L += ["", "## Párrafos para la tesis", "", txt_sus, "", txt_tam, ""]
with open(os.path.join(args.salida, "RESUMEN_RONDA2.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(L) + "\n")
print("\n".join(L))
