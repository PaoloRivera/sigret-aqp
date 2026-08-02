#!/usr/bin/env python3
"""
04_filtrar_sunat.py

Procesa el padron reducido de RUC de SUNAT para Arequipa Metropolitana:
normaliza y mapea los encabezados, reconstruye la direccion completa a partir
de las columnas en que SUNAT la parte, une los locales anexos con el padron
principal y exporta el universo comercial activo y las bodegas identificables.
"""

import glob
import os
import re
import unicodedata

import pandas as pd

os.makedirs("out", exist_ok=True)

UBIGEOS = {
    "040101": "AREQUIPA (CERCADO)", "040102": "ALTO SELVA ALEGRE",
    "040103": "CAYMA", "040104": "CERRO COLORADO", "040105": "CHARACATO",
    "040107": "JACOBO HUNTER", "040109": "MARIANO MELGAR", "040110": "MIRAFLORES",
    "040112": "PAUCARPATA", "040116": "SABANDIA", "040117": "SACHACA",
    "040122": "SOCABAYA", "040123": "TIABAYA", "040124": "UCHUMAYO",
    "040126": "YANAHUARA", "040128": "YURA",
    "040129": "JOSE LUIS BUSTAMANTE Y RIVERO",
}

PATRON_BODEGA = (
    r"\bMINIMARKET|\bMINI\s*MARKET\b|\bMINIMARQUET|\bMINISUPER|"
    r"\bBODEGA|\bBODEGUITA\b|\bABARROTE|\bMARKET\b|\bMARKE\b|"
    r"\bAUTOSERVICIO\b|\bSUPERMERCADO\b|\bMERCADITO\b|\bDESPENSA\b|"
    r"\bTIENDA\b|\bCOMERCIAL\b|\bDISTRIBUIDORA\b"
)


def sin_tildes(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s))
                   if unicodedata.category(c) != "Mn")


def limpiar_encabezados(df):
    df.columns = [re.sub(r"[^A-Z0-9]+", "_", sin_tildes(c).upper()).strip("_")
                  for c in df.columns]
    return df


def mapear(df):
    ren = {}
    usados = set()

    def asigna(destino, condicion):
        if destino in usados:
            return
        for c in df.columns:
            if c in ren:
                continue
            if condicion(c):
                ren[c] = destino
                usados.add(destino)
                return

    asigna("VIA_TIPO",     lambda c: c.startswith("TIPO_DE_VIA") or c == "TIPO_VIA")
    asigna("VIA_NOMBRE",   lambda c: c.startswith("NOMBRE_DE_VIA") or c == "NOMBRE_VIA")
    asigna("ZONA_CODIGO",  lambda c: "CODIGO_DE_ZONA" in c or c == "COD_ZONA")
    asigna("ZONA_TIPO",    lambda c: "TIPO_DE_ZONA" in c or c == "TIPO_ZONA")
    asigna("NUMERO",       lambda c: c in ("NUMERO", "NRO", "NUM"))
    asigna("INTERIOR",     lambda c: c.startswith("INTERIOR"))
    asigna("LOTE",         lambda c: c.startswith("LOTE"))
    asigna("DPTO_EDIF",    lambda c: c.startswith("DEPARTAMENTO"))
    asigna("MANZANA",      lambda c: c.startswith("MANZANA") or c == "MZ")
    asigna("KILOMETRO",    lambda c: c.startswith("KILOMETRO") or c == "KM")

    asigna("RUC",          lambda c: c.startswith("RUC") or c == "NUMERO_RUC")
    asigna("RAZON_SOCIAL", lambda c: "RAZON_SOCIAL" in c or c.startswith("NOMBRE_O"))
    asigna("ESTADO",       lambda c: c.startswith("ESTADO"))
    asigna("CONDICION",    lambda c: c.startswith("CONDICION"))
    asigna("UBIGEO",       lambda c: c.startswith("UBIGEO"))
    asigna("COD_ANEXO",    lambda c: "ESTABLECIMIENTO_ANEXO" in c or "CODIGO_DE_ESTAB" in c)
    asigna("TIPO_ESTAB",   lambda c: c.startswith("TIPO_DE_ESTABLECIMIENTO"))

    return df.rename(columns=ren)


PARTES_DIR = ["VIA_TIPO", "VIA_NOMBRE", "NUMERO", "INTERIOR", "MANZANA",
              "LOTE", "DPTO_EDIF", "ZONA_TIPO", "ZONA_CODIGO", "KILOMETRO"]


def armar_direccion(df):
    presentes = [c for c in PARTES_DIR if c in df.columns]
    if not presentes:
        df["DIRECCION"] = ""
        return df
    tmp = df[presentes].fillna("").astype(str)
    tmp = tmp.apply(lambda col: col.str.strip().replace({"-": "", "nan": "", "NAN": ""}))
    df["DIRECCION"] = (tmp.agg(" ".join, axis=1)
                          .str.replace(r"\s+", " ", regex=True)
                          .str.strip())
    return df


def leer(ruta):
    for sep in ["|", "\t", ","]:
        for enc in ["latin-1", "utf-8"]:
            try:
                df = pd.read_csv(ruta, sep=sep, encoding=enc, dtype=str,
                                 low_memory=False, on_bad_lines="skip")
                if df.shape[1] >= 4:
                    print(f"      sep='{sep}' enc='{enc}' -> {df.shape[0]:,} filas x {df.shape[1]} cols")
                    return df
            except Exception:
                continue
    raise RuntimeError(f"No pude leer {ruta}")


def main():
    archivos = sorted(glob.glob("data_sunat/*.txt") + glob.glob("data_sunat/*.csv")
                      + glob.glob("data_sunat/*.TXT"))
    if not archivos:
        print("!!! No hay archivos en data_sunat/")
        return

    diag = []
    principal = None
    anexos = None

    for ruta in archivos:
        print(f"\n[+] {ruta}")
        df = mapear(limpiar_encabezados(leer(ruta)))
        diag.append(f"{ruta}\n  columnas -> {list(df.columns)}\n")
        print(f"      columnas mapeadas: {list(df.columns)}")

        if "UBIGEO" not in df.columns:
            print("      sin UBIGEO, se omite")
            continue

        df["UBIGEO"] = df["UBIGEO"].astype(str).str.strip().str.zfill(6)
        sub = df[df["UBIGEO"].isin(UBIGEOS)].copy()
        print(f"      en Arequipa Metropolitana: {len(sub):,}")

        sub = armar_direccion(sub)

        if "RAZON_SOCIAL" in sub.columns:
            principal = sub
        else:
            anexos = sub

    with open("out/_diagnostico_columnas.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(diag))

    if principal is None:
        print("\n!!! No encontre el padron principal (el que trae RAZON_SOCIAL).")
        print("    Mandame out/_diagnostico_columnas.txt")
        return

    if anexos is not None and "RUC" in anexos.columns:
        nombres = principal[["RUC", "RAZON_SOCIAL"]].drop_duplicates("RUC")
        anexos = anexos.merge(nombres, on="RUC", how="left")
        anexos["ES_ANEXO"] = 1
        principal["ES_ANEXO"] = 0
        cols = [c for c in ["RUC", "RAZON_SOCIAL", "UBIGEO", "DIRECCION",
                            "ESTADO", "CONDICION", "ES_ANEXO"]
                if c in principal.columns and c in anexos.columns]
        todo = pd.concat([principal[cols], anexos[cols]], ignore_index=True)
        print(f"\n[+] Principal + anexos unidos: {len(todo):,} establecimientos")
    else:
        todo = principal.copy()
        todo["ES_ANEXO"] = 0
        print(f"\n[+] Solo padron principal: {len(todo):,}")

    todo["DISTRITO"] = todo["UBIGEO"].map(UBIGEOS)
    todo["RAZON_SOCIAL"] = todo["RAZON_SOCIAL"].fillna("").astype(str).str.upper()
    todo["TIPO_PERSONA"] = todo["RUC"].astype(str).str[:2].map(
        {"10": "NATURAL", "15": "NATURAL", "17": "NATURAL", "20": "JURIDICA"}).fillna("OTRO")

    if "ESTADO" in todo.columns:
        antes = len(todo)
        todo = todo[todo["ESTADO"].fillna("").str.upper().str.contains("ACTIVO", na=False)]
        print(f"[+] Solo ACTIVOS: {len(todo):,} (de {antes:,})")

    todo.to_csv("out/sunat_universo_arequipa.csv", index=False, encoding="utf-8-sig")

    bod = todo[todo["RAZON_SOCIAL"].str.contains(PATRON_BODEGA, regex=True, na=False)].copy()
    bod.to_csv("out/sunat_bodegas_arequipa.csv", index=False, encoding="utf-8-sig")

    print("\n=== LISTO ===")
    print(f"  Universo comercial activo : {len(todo):,}  -> sunat_universo_arequipa.csv")
    print(f"  Bodegas/minimarkets       : {len(bod):,}  -> sunat_bodegas_arequipa.csv")
    if len(bod):
        print("\n  Por distrito:")
        print(bod["DISTRITO"].value_counts().to_string())
        print("\n  Ejemplos de direccion reconstruida:")
        for d in bod["DIRECCION"].head(5):
            print(f"    - {d}")




if __name__ == "__main__":
    main()
