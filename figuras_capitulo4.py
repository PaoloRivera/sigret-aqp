#!/usr/bin/env python3
"""
figuras_capitulo4.py

Genera las figuras del Capitulo IV que dependen de los resultados del pipeline:
  Figura 16  Importancia de variables con y sin las variables de la propia red
             de tiendas (control de fuga de informacion), con el backtesting de
             cada version (resultados/control_fuga.csv).
  Figura 17  Salida de consola del entrenamiento y la validacion (texto real
             del registro de pipeline.py).
  Figura 18  Curvas ROC y precision-recall de la validacion cruzada espacial y
             del backtesting temporal.
  Anexo I    Mapa de la poblacion 2025 por celda y de su crecimiento desde 2017.

Uso (desde la raiz del proyecto, despues de pipeline.py; ejecutar_todo.sh
guarda la salida de consola en resultados/log_pipeline.txt):
    python figuras_capitulo4.py
"""
import os
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, roc_curve

warnings.filterwarnings("ignore")
RES = "resultados"
FIG = "figuras"
os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({
    "font.size": 10, "figure.dpi": 200, "savefig.dpi": 200,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.22, "grid.linestyle": "-",
})
PETROL, NARANJA, AMBAR, GRIS, CARMIN = "#0E7C86", "#DE5D3F", "#F08F2E", "#8A8A8A", "#B23A5B"
COLORES = {"LR": CARMIN, "RF": AMBAR, "XGB": "#3B7D3B", "ENS": PETROL}
NOMBRES = {"LR": "Regresión logística", "RF": "Random Forest", "XGB": "XGBoost", "ENS": "Ensamble"}


def guardar(fig, nombre):
    fig.tight_layout()
    fig.savefig(f"{FIG}/{nombre}", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  >> {nombre}")


# ═══════════════ Figura 16: control de fuga ═══════════════
# Se repite el backtesting (modelos entrenados con el estado al 31-12-2024)
# agregando las dos variables de la propia red que tenia la primera version:
# distancia a la tienda mas cercana y tiendas en el anillo de vecindad.
import xgboost as xgb
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

F = pd.read_parquet(f"{RES}/features.parquet")
F24 = pd.read_parquet(f"{RES}/features_2024.parquet").set_index("h3").loc[F["h3"]].reset_index()
PRED = [c for c in F.columns if c not in ("h3", "DIST", "es_nucleo", "bloque")
        and not c.startswith(("mass_", "d_mass_"))]
FUGA = ["d_mass_2024", "mass_k1_2024"]
y24 = F["mass_2024"].values
abrio = ((F["mass_2026"] == 1) & (F["mass_2024"] == 0)).astype(int).values
cand = (F24["pob_k1"].values >= 1500) & (y24 == 0)


def entrenar(cols):
    X = F24[cols].replace([np.inf, -np.inf], 0).fillna(0).values
    pw = (y24 == 0).sum() / max((y24 == 1).sum(), 1)
    sc = StandardScaler().fit(X)
    lr = LogisticRegression(max_iter=5000, class_weight="balanced", C=0.5).fit(sc.transform(X), y24)
    rf = RandomForestClassifier(n_estimators=800, min_samples_leaf=5, max_features="sqrt",
                                class_weight="balanced_subsample", n_jobs=-1, random_state=42).fit(X, y24)
    xg = xgb.XGBClassifier(n_estimators=400, max_depth=3, learning_rate=0.05, subsample=0.8,
                           colsample_bytree=0.7, reg_lambda=3.0, min_child_weight=5,
                           scale_pos_weight=pw, eval_metric="aucpr", random_state=42).fit(X, y24)
    p = [lr.predict_proba(sc.transform(X))[:, 1], rf.predict_proba(X)[:, 1], xg.predict_proba(X)[:, 1]]
    ens = np.mean([pd.Series(v).rank(pct=True) for v in p], axis=0)
    s, t = ens[cand], abrio[cand]
    o = np.argsort(-s)
    n10 = max(int(0.10 * len(s)), 1)
    met = {"ROC_AUC": roc_auc_score(t, s), "PR_AUC": average_precision_score(t, s),
           "P@20": t[o[:20]].mean(), "aciertos@20": int(t[o[:20]].sum()),
           "Lift@10%": t[o[:n10]].mean() / t.mean()}
    return pd.Series(rf.feature_importances_, index=cols).sort_values(ascending=False), met


antes, m_antes = entrenar(PRED + FUGA)
despues, m_despues = entrenar(PRED)
cuota = antes[FUGA].sum()
pd.DataFrame([{"version": "Con distancia y tiendas vecinas (fuga)", "cuota_importancia_fuga": cuota,
               "variable_principal": antes.index[0], **m_antes},
              {"version": "Sin esas variables (pipeline)", "cuota_importancia_fuga": 0.0,
               "variable_principal": despues.index[0], **m_despues}]
             ).to_csv(f"{RES}/control_fuga.csv", index=False, encoding="utf-8-sig")
print(f"Con fuga: {', '.join(f'{v} {antes[v]:.3f}' for v in FUGA)} = {cuota:.1%} de la importancia | "
      f"backtesting ROC-AUC {m_antes['ROC_AUC']:.3f}, P@20 {m_antes['P@20']:.2f} ({m_antes['aciertos@20']} aciertos)")
print(f"Sin fuga: principal {despues.index[0]} {despues.iloc[0]:.3f} | backtesting ROC-AUC "
      f"{m_despues['ROC_AUC']:.3f}, P@20 {m_despues['P@20']:.2f} ({m_despues['aciertos@20']} aciertos)")

fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 4.6))
for ax, s, titulo in ((a1, antes.head(10), "Con distancia y tiendas vecinas"),
                      (a2, despues.head(10), "Sin esas variables (corregido)")):
    y = np.arange(len(s))[::-1]
    col = [NARANJA if v in FUGA else (PETROL if ax is a2 and i < 3 else GRIS)
           for i, v in enumerate(s.index)]
    ax.barh(y, s.values, color=col, height=.68)
    ax.set_yticks(y); ax.set_yticklabels(s.index, fontsize=8.5)
    ax.set_xlabel("Importancia relativa")
    ax.set_title(titulo, loc="left", weight="bold", fontsize=10)
    for yy, v in zip(y, s.values):
        ax.text(v + s.max() * .015, yy, f"{v:.3f}", va="center", fontsize=8)
    ax.set_xlim(0, s.max() * 1.22)
a1.text(.98, .05, f"Dos variables de la propia red: {cuota*100:.1f} %".replace(".", ","),
        transform=a1.transAxes, ha="right", fontsize=8.5, style="italic", color=NARANJA)
fig.text(.01, -.02, "Random Forest del backtesting (estado al 31-12-2024), con la misma configuración del pipeline.",
         fontsize=7.5, color=GRIS)
guardar(fig, "figura16_importancia_fuga.png")

# ═══════════════ Figura 17: salida de consola ═══════════════
log = f"{RES}/log_pipeline.txt"
if os.path.exists(log):
    txt = open(log, encoding="utf-8").read().splitlines()
    i0 = next(i for i, l in enumerate(txt) if l.startswith("[4]"))
    i1 = next(i for i, l in enumerate(txt) if "Top-50 por distrito" in l)
    lineas = [l.rstrip() for l in txt[i0:i1] if l.strip() or True]
    while lineas and not lineas[-1].strip():
        lineas.pop()
    n = len(lineas)
    alto = 0.165 * n + 0.5
    fig = plt.figure(figsize=(7.4, alto))
    ax = fig.add_axes([0, 0, 1, 1]); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.005, 0.003), 0.99, 0.994, boxstyle="round,pad=0,rounding_size=0.012",
                                transform=ax.transAxes, facecolor="#2B2D33", edgecolor="#2B2D33"))
    for k, l in enumerate(lineas):
        ax.text(0.02, 1 - (k + 0.9) / (n + 0.6), l, transform=ax.transAxes, family="monospace",
                fontsize=8.1, color="#E6E6E6", va="baseline")
    fig.savefig(f"{FIG}/figura17_consola_entrenamiento.png", dpi=200, facecolor="white")
    plt.close(fig)
    print("  >> figura17_consola_entrenamiento.png")
else:
    print(f"  (sin {log}: ejecute pipeline.py con: python pipeline.py | tee {log})")

# ═══════════════ Figura 18: curvas ROC y precision-recall ═══════════════
CV = pd.read_parquet(f"{RES}/predicciones_cv.parquet")
BT = pd.read_parquet(f"{RES}/predicciones_backtesting.parquet")
fig, axs = plt.subplots(2, 2, figsize=(10.5, 8.6))
for fila, (D, ycol, nombre) in enumerate(((CV, "y", "Validación cruzada espacial"),
                                         (BT, "abrio", "Backtesting temporal"))):
    y = D[ycol].values
    a_roc, a_pr = axs[fila]
    for k in ("ENS", "XGB", "RF", "LR"):
        fpr, tpr, _ = roc_curve(y, D[k].values)
        pr, rc, _ = precision_recall_curve(y, D[k].values)
        a_roc.plot(fpr, tpr, color=COLORES[k], lw=2.2 if k == "ENS" else 1.4,
                   label=f"{NOMBRES[k]} (ROC-AUC = {roc_auc_score(y, D[k].values):.3f})")
        a_pr.plot(rc, pr, color=COLORES[k], lw=2.2 if k == "ENS" else 1.4, drawstyle="steps-post",
                  label=f"{NOMBRES[k]} (PR-AUC = {average_precision_score(y, D[k].values):.3f})")
    a_roc.plot([0, 1], [0, 1], color=GRIS, ls=":", lw=1.2)
    a_pr.axhline(y.mean(), color=GRIS, ls=":", lw=1.2)
    a_pr.text(.02, y.mean() + .015, f"Tasa base {y.mean()*100:.1f} %".replace(".", ","),
              ha="left", fontsize=8, color=GRIS, transform=a_pr.get_yaxis_transform())
    a_roc.set(xlim=(0, 1), ylim=(0, 1.01), xlabel="Tasa de falsos positivos",
              ylabel="Tasa de verdaderos positivos")
    a_pr.set(xlim=(0, 1), ylim=(0, 1.01), xlabel="Exhaustividad (recall)", ylabel="Precisión")
    n_txt = (f"{len(y):,} celdas · {int(y.sum())} con tienda" if fila == 0 else
             f"{len(y):,} candidatos · {int(y.sum())} aperturas").replace(",", " ")
    a_roc.set_title(f"{nombre}\nCurva ROC ({n_txt})", loc="left", weight="bold", fontsize=9.5)
    a_pr.set_title(f"{nombre}\nCurva precisión-recall", loc="left", weight="bold", fontsize=9.5)
    a_roc.legend(frameon=False, fontsize=7.8, loc="lower right")
    a_pr.legend(frameon=False, fontsize=7.8, loc="upper right")
guardar(fig, "figura18_curvas_roc_pr.png")

# ═══════════════ Anexo I: poblacion 2025 y crecimiento por celda ═══════════════
if os.path.exists(f"{RES}/poblacion_celdas.parquet"):
    import geopandas as gpd
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    G = gpd.read_parquet(f"{RES}/grid.parquet")[["h3", "geometry"]]
    P = pd.read_parquet(f"{RES}/poblacion_celdas.parquet")
    G = G.merge(P[P["en_malla"]][["h3", "DIST", "pob_2017", "pob_2025"]], on="h3").to_crs(32719)
    G["crec"] = G["pob_2025"] - G["pob_2017"]
    L = gpd.read_file("data/inei/limites_distritales_aqp.geojson").to_crs(32719)
    # Encuadre: zona urbana continua (percentiles 1-99 de la poblacion 2025)
    c = G.geometry.centroid
    w = G["pob_2025"].values
    def q(v, a):
        o = np.argsort(v); cw = np.cumsum(w[o]) / w.sum()
        return v[o][np.searchsorted(cw, a)]
    x0, x1 = q(c.x.values, .005) - 1500, q(c.x.values, .995) + 1500
    y0, y1 = q(c.y.values, .005) - 1500, q(c.y.values, .995) + 1500
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.5, 6.0))
    cm_pob = LinearSegmentedColormap.from_list("pob", ["#F2F2F2", "#9FD3D6", PETROL, "#08484E"])
    cm_crec = LinearSegmentedColormap.from_list(
        "crec", [(0, "#3B6FB6"), (0.5, "#EFEFEF"), (0.68, "#F6C08A"), (0.84, NARANJA), (1, "#7A2614")])
    G.plot(column="pob_2025", ax=a1, cmap=cm_pob, linewidth=0, legend=True,
           legend_kwds={"shrink": .55, "label": "Habitantes por celda (2025)"})
    vmax = float(G["crec"].quantile(.99))
    G.plot(column="crec", ax=a2, cmap=cm_crec, norm=TwoSlopeNorm(0, -vmax, vmax), linewidth=0,
           legend=True, legend_kwds={"shrink": .55, "label": "Cambio de habitantes 2017-2025",
                                     "extend": "max"})
    cen_d = (G.assign(x=c.x * G["pob_2025"], y=c.y * G["pob_2025"]).groupby("DIST")[["x", "y", "pob_2025"]].sum())
    for ax, t in ((a1, "Población 2025 por celda"), (a2, "Crecimiento 2017-2025 por celda")):
        L.boundary.plot(ax=ax, color="#555555", linewidth=.45)
        ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
        ax.set_axis_off(); ax.set_title(t, loc="left", weight="bold")
    for d, r in cen_d.iterrows():
        if isinstance(d, str) and d in set(P["DIST"]):
            a2.text(r.x / r.pob_2025, r.y / r.pob_2025, d.title().replace("Jlbr", "JLByR"),
                    fontsize=5.6, ha="center", va="center", color="#222222",
                    bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=.65))
    fig.text(.01, .03, "Malla H3 r9 del modelo y límites distritales del INEI. El crecimiento censal de cada "
             "distrito (INEI, 2018 y 2026) se reparte según las edificaciones nuevas 2017-2023 "
             "(Google Open Buildings).", fontsize=7.2, color=GRIS)
    guardar(fig, "anexo_i_poblacion_2025.png")
