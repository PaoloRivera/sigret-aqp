#!/usr/bin/env python3
"""
analisis_transferibilidad.py

Segundo estudio: ¿se transfiere el modelo de localizacion de minimarkets a otros
servicios urbanos? Reutiliza la malla H3 r9, los 37 predictores y la misma
configuracion de modelos (LR, RF, XGBoost y ensamble por rangos) y la misma
validacion cruzada espacial en bloques H3 r6 del estudio principal.

Para cada componente (farmacias, grifos, bancos y cajeros, colegios,
restaurantes, clinicas y hospitales, mercados) la variable objetivo es la
presencia de al menos un establecimiento mapeado en OpenStreetMap dentro de la
celda. El minimarket (celdas con una tienda de la cadena en 2026) se incluye
como referencia: es el objetivo del estudio principal.

Control de fuga: los predictores incluyen conteos de OSM por categoria. Para
cada objetivo se retiran los conteos de su propia categoria (celda y vecindad)
y el total de POIs de la vecindad (que la contiene).

Salidas (resultados/):
  transfer_resumen.csv      objetivos, positivos y tasa base
  transfer_metricas.csv     metricas por objetivo y modelo (media de semillas)
  transfer_baseline.csv     lineas base univariadas
  transfer_cruzada.csv      matriz de transferencia entre objetivos
  transfer_familias.csv     importancia por familia de predictores
  transfer_jaccard.csv      solapamiento entre objetivos

Uso (desde la raiz del proyecto, tras ejecutar pipeline.py):
    python analisis_transferibilidad.py
"""
import warnings

import geopandas as gpd
import h3
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings("ignore")
DATA, OUT = "data", "resultados"
SEMILLAS = [100, 101, 102, 103, 104]
UMBRAL_VIABLE = 1500

F = pd.read_parquet(f"{OUT}/features.parquet")
F["bloque"] = [h3.cell_to_parent(c, 6) for c in F["h3"]]
PRED = [c for c in F.columns if c not in ("h3", "DIST", "es_nucleo", "bloque")
        and not c.startswith(("mass_", "d_mass_"))]

# amenity de OSM -> componente; categoria de predictores que se retira por fuga
COMPONENTES = {
    "Farmacias":    (["pharmacy"], ["salud"]),
    "Grifos":       (["fuel"], ["grifo"]),
    "Bancos y cajeros": (["bank", "atm"], ["banco"]),
    "Colegios":     (["school"], ["colegio"]),
    "Restaurantes": (["restaurant", "fast_food"], ["comida"]),
    "Clínicas y hospitales": (["clinic", "hospital"], ["salud"]),
    "Mercados":     (["marketplace"], ["mercado"]),
}

FAMILIAS = {
    "Demanda poblacional": ["pob_celda", "area_km2", "dens_hab_km2", "n_mz", "pob_k1",
                            "pob_k2", "pob_k3", "pob_k1_ext"],
    "Morfología vial": ["n_nodos", "n_intersec", "long_vial_m", "long_princ_m",
                        "dens_intersec_km2", "long_vial_km_km2", "pct_vial_princ"],
    "Competencia": ["n_comp_osm", "n_comp_osm_k1", "hab_por_comp_k1"],
}


def predictores(excluir_cat):
    quitar = {"n_poi_k1"}
    for c in excluir_cat:
        quitar |= {f"n_{c}", f"n_{c}_k1"}
    return [c for c in PRED if c not in quitar]


CATS = ["colegio", "salud", "banco", "mercado", "comida", "transp", "culto", "grifo", "panader"]


def estructurales():
    """Perfil sin ningun conteo de POIs (demanda + morfologia vial + competencia): al no contener
    categorias de servicios, un modelo entrenado con el no puede filtrar informacion de otro objetivo."""
    return predictores(CATS)


def demografico_vial():
    """Control de sesgo de cobertura: sin POIs ni competencia de OSM, solo censo y red vial. Las
    etiquetas de los objetivos tambien salen de OSM, asi que un perfil que comparta el esfuerzo de
    mapeo con ellas podria transferirse por esa via y no por la logica de localizacion."""
    return [c for c in estructurales() if familia(c) != "Competencia"]


def familia(col):
    for fam, cols in FAMILIAS.items():
        if col in cols:
            return fam
    return "Puntos de interés"


def objetivos():
    poi = gpd.read_parquet(f"{DATA}/osm/poi_flujo.parquet")
    pt = poi.geometry.representative_point()
    poi["h3"] = [h3.latlng_to_cell(p.y, p.x, 9) for p in pt]
    celdas = set(F["h3"])
    Y = {}
    for nombre, (amen, _) in COMPONENTES.items():
        hx = set(poi.loc[poi["amenity"].isin(amen), "h3"]) & celdas
        Y[nombre] = F["h3"].isin(hx).astype(int).values
    Y["Minimarket (cadena)"] = (F["mass_2026"] > 0).astype(int).values
    return Y


def lift(y, s, frac=0.10):
    k = max(int(round(len(y) * frac)), 1)
    top = np.argsort(-s)[:k]
    base = y.mean()
    return y[top].mean() / base if base > 0 else np.nan


def metricas(y, s, viable):
    m = {"roc": roc_auc_score(y, s), "pr": average_precision_score(y, s),
         "lift10": lift(y, s)}
    yv, sv = y[viable], s[viable]
    m["roc_viables"] = roc_auc_score(yv, sv) if yv.sum() >= 5 else np.nan
    m["lift10_viables"] = lift(yv, sv) if yv.sum() >= 5 else np.nan
    return m


def ajustar(Xtr, ytr, semilla):
    pw = (ytr == 0).sum() / max((ytr == 1).sum(), 1)
    sc = StandardScaler().fit(Xtr)
    lr = LogisticRegression(max_iter=5000, class_weight="balanced", C=0.5).fit(sc.transform(Xtr), ytr)
    rf = RandomForestClassifier(n_estimators=800, min_samples_leaf=5, max_features="sqrt",
                                class_weight="balanced_subsample", n_jobs=-1,
                                random_state=semilla).fit(Xtr, ytr)
    xg = xgb.XGBClassifier(n_estimators=400, max_depth=3, learning_rate=0.05, subsample=0.8,
                           colsample_bytree=0.7, reg_lambda=3.0, min_child_weight=5,
                           scale_pos_weight=pw, eval_metric="aucpr",
                           random_state=semilla, n_jobs=4).fit(Xtr, ytr)
    return sc, lr, rf, xg


def rango(v):
    return pd.Series(v).rank(pct=True).values


def cv_espacial(X, y, semilla):
    """Predicciones fuera de muestra de LR, RF, XGB, ensamble; devuelve tambien la importancia de RF."""
    oof = {k: np.zeros(len(y)) for k in ("LR", "RF", "XGB")}
    imp = np.zeros(X.shape[1])
    gkf = GroupKFold(n_splits=5)
    for tr, te in gkf.split(X, y, groups=F["bloque"].values):
        sc, lr, rf, xg = ajustar(X[tr], y[tr], semilla)
        oof["LR"][te] = lr.predict_proba(sc.transform(X[te]))[:, 1]
        oof["RF"][te] = rf.predict_proba(X[te])[:, 1]
        oof["XGB"][te] = xg.predict_proba(X[te])[:, 1]
        imp += rf.feature_importances_ / 5
    oof["Ensamble"] = (rango(oof["LR"]) + rango(oof["RF"]) + rango(oof["XGB"])) / 3
    return oof, imp


def main():
    Y = objetivos()
    viable = (F["pob_k1"].values >= UMBRAL_VIABLE)
    print(f"celdas viables (pob_k1 >= {UMBRAL_VIABLE}): {viable.sum()}")

    resumen, filas, base, fam_rows = [], [], [], []
    OOF = {}
    for nombre, y in Y.items():
        cat = COMPONENTES.get(nombre, (None, []))[1]
        conjuntos = {"completo": predictores(cat), "estructural": estructurales(),
                     "demografico_vial": demografico_vial()}
        resumen.append({"objetivo": nombre, "positivos": int(y.sum()),
                        "tasa_base": y.mean(), "positivos_viables": int(y[viable].sum()),
                        "predictores_completo": len(conjuntos["completo"]),
                        "predictores_estructural": len(conjuntos["estructural"])})
        print(f"\n== {nombre}: {int(y.sum())} positivos")
        for conj, cols in conjuntos.items():
            X = F[cols].replace([np.inf, -np.inf], 0).fillna(0).values
            res_sem, oofs, imps = [], [], []
            for sem in SEMILLAS:
                oof, imp = cv_espacial(X, y, sem)
                oofs.append(oof)
                imps.append(imp)
                for mod, sc_ in oof.items():
                    res_sem.append({"objetivo": nombre, "conjunto": conj, "modelo": mod,
                                    "semilla": sem, **metricas(y, sc_, viable)})
            R = pd.DataFrame(res_sem)
            filas.append(R)
            OOF[(nombre, conj)] = {m: np.mean([o[m] for o in oofs], axis=0) for m in oofs[0]}
            imp = np.mean(imps, axis=0)
            fam = pd.DataFrame({"familia": [familia(c) for c in cols], "imp": imp}).groupby("familia")["imp"].sum()
            for f_, v in (fam / fam.sum()).items():
                fam_rows.append({"objetivo": nombre, "conjunto": conj, "familia": f_, "importancia": v})
            top = pd.Series(imp, index=cols).sort_values(ascending=False).head(3)
            print(f"   [{conj}] top RF:", ", ".join(f"{k} {v:.3f}" for k, v in top.items()))
            print(R.groupby("modelo")[["roc", "pr", "lift10", "roc_viables"]].mean().round(3).to_string())
        for bn, col in (("Densidad poblacional", "dens_hab_km2"), ("Población alcanzable", "pob_k1")):
            base.append({"objetivo": nombre, "linea_base": bn,
                         **metricas(y, F[col].values.astype(float), viable)})

    # puntuaciones fuera de muestra (media de semillas) para las pruebas de significancia
    oof_df = pd.DataFrame({"h3": F["h3"].values, "bloque": F["bloque"].values})
    for nombre in Y:
        oof_df[f"y|{nombre}"] = Y[nombre]
        for conj in ("completo", "estructural", "demografico_vial"):
            oof_df[f"oof|{nombre}|{conj}"] = OOF[(nombre, conj)]["Ensamble"]
    oof_df.to_parquet(f"{OUT}/transfer_oof.parquet")

    pd.DataFrame(resumen).to_csv(f"{OUT}/transfer_resumen.csv", index=False)
    M = pd.concat(filas)
    M.to_csv(f"{OUT}/transfer_metricas_semillas.csv", index=False)
    agg = M.groupby(["objetivo", "conjunto", "modelo"]).agg(["mean", "std"]).drop(columns="semilla", level=0)
    agg.columns = ["_".join(c) for c in agg.columns]
    agg.reset_index().to_csv(f"{OUT}/transfer_metricas.csv", index=False)
    pd.DataFrame(base).to_csv(f"{OUT}/transfer_baseline.csv", index=False)
    pd.DataFrame(fam_rows).to_csv(f"{OUT}/transfer_familias.csv", index=False)

    # transferencia: la puntuacion fuera de muestra del objetivo A (ensamble, perfil estructural)
    # evaluada contra las celdas positivas de B
    nombres = list(Y)
    T = pd.DataFrame(index=nombres, columns=nombres, dtype=float)
    TV = pd.DataFrame(index=nombres, columns=nombres, dtype=float)
    J = pd.DataFrame(index=nombres, columns=nombres, dtype=float)
    for a_ in nombres:
        sa = OOF[(a_, "estructural")]["Ensamble"]
        for b_ in nombres:
            T.loc[a_, b_] = roc_auc_score(Y[b_], sa)
            TV.loc[a_, b_] = roc_auc_score(Y[b_][viable], sa[viable]) if Y[b_][viable].sum() >= 5 else np.nan
            inter = ((Y[a_] == 1) & (Y[b_] == 1)).sum()
            J.loc[a_, b_] = inter / max(((Y[a_] == 1) | (Y[b_] == 1)).sum(), 1)
    T2 = pd.DataFrame(index=nombres, columns=nombres, dtype=float)
    T2V = pd.DataFrame(index=nombres, columns=nombres, dtype=float)
    for a_ in nombres:
        sa = OOF[(a_, "demografico_vial")]["Ensamble"]
        for b_ in nombres:
            T2.loc[a_, b_] = roc_auc_score(Y[b_], sa)
            T2V.loc[a_, b_] = roc_auc_score(Y[b_][viable], sa[viable]) if Y[b_][viable].sum() >= 5 else np.nan
    T2.to_csv(f"{OUT}/transfer_cruzada_demovial.csv")
    T2V.to_csv(f"{OUT}/transfer_cruzada_demovial_viables.csv")
    T.to_csv(f"{OUT}/transfer_cruzada.csv")
    TV.to_csv(f"{OUT}/transfer_cruzada_viables.csv")
    J.to_csv(f"{OUT}/transfer_jaccard.csv")
    print("\nTransferencia, perfil estructural (ROC-AUC; fila = entrenado en A, columna = evaluado en B):")
    print(T.round(3).to_string())
    print("\nSolo celdas viables:")
    print(TV.round(3).to_string())


if __name__ == "__main__":
    main()
