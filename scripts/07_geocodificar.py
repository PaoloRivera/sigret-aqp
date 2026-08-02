#!/usr/bin/env python3
"""
07_geocodificar.py

Geocodifica con Nominatim las direcciones de las tiendas Mass y de las bodegas
del padron SUNAT, cacheando en disco para poder retomar la corrida, y reintenta
la descarga de las manzanas del censo desde el servicio ArcGIS de SIGRID.
"""

import json
import os
import re
import time

import pandas as pd
import requests

os.makedirs("out", exist_ok=True)
CACHE = "out/_cache_geocod.json"
cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}

NOMINATIM = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "tesis-ucsm-retail-arequipa/1.0 (paolo.rivera@example.com)"}

VIEWBOX = "-71.78,-16.22,-71.38,-16.62"


def limpiar(direccion):
    d = str(direccion)
    d = re.split(r"\(", d)[0]
    d = re.sub(r"\s*-\s*\d+\s*$", "", d)
    d = re.sub(r"\bCl\.", "Calle", d)
    d = re.sub(r"\bAv\.", "Avenida", d)
    d = re.sub(r"\bJr\.", "Jiron", d)
    d = re.sub(r"\bPsje\.", "Pasaje", d)
    return re.sub(r"\s+", " ", d).strip()


def geocodificar(direccion, distrito=None):
    q = limpiar(direccion)
    if not q or len(q) < 5:
        return None
    partes = [q]
    if distrito and str(distrito) != "nan":
        partes.append(str(distrito))
    partes += ["Arequipa", "Peru"]
    consulta = ", ".join(partes)

    if consulta in cache:
        return cache[consulta]

    try:
        r = requests.get(NOMINATIM, headers=HEADERS, timeout=30, params={
            "q": consulta, "format": "json", "limit": 1,
            "countrycodes": "pe", "viewbox": VIEWBOX, "bounded": 1,
        })
        r.raise_for_status()
        js = r.json()
        res = ({"lat": float(js[0]["lat"]), "lon": float(js[0]["lon"]),
                "tipo": js[0].get("type"), "clase": js[0].get("class")}
               if js else None)
    except Exception as e:
        print(f"    error: {e}")
        res = None

    cache[consulta] = res
    time.sleep(1.1)
    return res


def lote(df, col_dir, col_dist, etiqueta):
    print(f"\n[+] Geocodificando {etiqueta}: {len(df)} direcciones")
    lats, lons, tipos = [], [], []
    for i, row in enumerate(df.itertuples(), 1):
        d = getattr(row, col_dir)
        dist = getattr(row, col_dist) if col_dist else None
        res = geocodificar(d, dist)
        lats.append(res["lat"] if res else None)
        lons.append(res["lon"] if res else None)
        tipos.append(res["tipo"] if res else None)
        if i % 25 == 0:
            hit = sum(x is not None for x in lats)
            print(f"    {i}/{len(df)}  encontradas: {hit}")
            json.dump(cache, open(CACHE, "w", encoding="utf-8"))
    df = df.copy()
    df["lat"], df["lon"], df["osm_tipo"] = lats, lons, tipos
    hit = df["lat"].notna().sum()
    print(f"    RESULTADO: {hit}/{len(df)} ({100*hit/len(df):.0f}%)")
    return df


print("=" * 60)
print("PARTE A - GEOCODIFICACION")
print("=" * 60)

if os.path.exists("out/mass_arequipa.csv"):
    m = pd.read_csv("out/mass_arequipa.csv")
    m = lote(m, "direccion", "distrito", "tiendas Mass")
    m.to_csv("out/mass_geocod.csv", index=False, encoding="utf-8-sig")
else:
    print("[!] falta out/mass_arequipa.csv")

if os.path.exists("out/sunat_universo_arequipa.csv"):
    u = pd.read_csv("out/sunat_universo_arequipa.csv", dtype=str)
    FORMA = (r"SOCIEDAD\s+COMERCIAL\s+DE\s+RESPONSABILIDAD\s+LIMITADA|"
             r"SOCIEDAD\s+ANONIMA(\s+CERRADA|\s+ABIERTA)?|"
             r"EMPRESA\s+INDIVIDUAL\s+DE\s+RESPONSABILIDAD\s+LIMITADA|"
             r"SOCIEDAD\s+DE\s+RESPONSABILIDAD\s+LIMITADA|"
             r"\bS\.?\s?R\.?\s?L(TDA)?\.?|\bS\.?\s?A\.?\s?C\.?|\bE\.?\s?I\.?\s?R\.?\s?L\.?")
    lim = (u["RAZON_SOCIAL"].fillna("").str.upper()
             .str.replace(FORMA, " ", regex=True)
             .str.replace(r"\s+", " ", regex=True).str.strip())
    NUCLEO = (r"\bMINIMARKET|\bMINI\s?MARKET\b|\bMINIMARQUET|\bMINISUPER|\bBODEGA|"
              r"\bABARROTE|\bAUTOSERVICIO\b|\bSUPERMERCADO|\bMARKET\b|\bDESPENSA\b")
    EXCL = (r"CONSTRUCCION|FERRETER|IMPRENTA|TRANSPORT|TOURS|SOFTWARE|INDUSTRIAL|"
            r"AUTOMOTRIZ|REPUESTO|TEXTIL|FARMAC|VETERINAR|MINER|PLASTICO|COMBUSTIBLE")
    bod = u[lim.str.contains(NUCLEO, regex=True) & ~lim.str.contains(EXCL, regex=True)].copy()
    bod["NOMBRE_LIMPIO"] = lim[bod.index]
    print(f"\n[+] Bodegas tras filtro corregido: {len(bod)}")
    bod = lote(bod, "DIRECCION", "DISTRITO", "bodegas SUNAT")
    bod.to_csv("out/bodegas_geocod.csv", index=False, encoding="utf-8-sig")
else:
    print("[!] falta out/sunat_universo_arequipa.csv")

json.dump(cache, open(CACHE, "w", encoding="utf-8"))

print("\n" + "=" * 60)
print("PARTE B - MANZANAS DEL CENSO (reintento)")
print("=" * 60)

SERVICIOS = [
    "https://sigrid.cenepred.gob.pe/arcgis/rest/services/Elementos_Expuestos/MapServer/2100300/query",
    "https://sigrid.cenepred.gob.pe/arcgis/rest/services/Elementos_Expuestos/MapServer/2100300/query",
]
XMIN, YMIN, XMAX, YMAX = -71.78, -16.62, -71.38, -16.22


def bajar_manzanas():
    feats, offset = [], 0
    while True:
        params = {
            "where": "1=1", "outFields": "*", "returnGeometry": "true",
            "outSR": "4326", "f": "geojson",
            "resultOffset": offset, "resultRecordCount": 500,
            "geometry": json.dumps({"xmin": XMIN, "ymin": YMIN,
                                    "xmax": XMAX, "ymax": YMAX,
                                    "spatialReference": {"wkid": 4326}}),
            "geometryType": "esriGeometryEnvelope", "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
        }
        try:
            r = requests.get(SERVICIOS[0], params=params,
                             headers={"User-Agent": "tesis-ucsm/1.0"},
                             timeout=180, verify=False)
            r.raise_for_status()
            js = r.json()
        except Exception as e:
            print(f"    fallo en offset {offset}: {e}")
            break
        f = js.get("features", [])
        if not f:
            break
        feats += f
        print(f"    offset {offset:>6} -> +{len(f):>4} (total {len(feats):,})")
        if len(f) < 500:
            break
        offset += 500
        time.sleep(1)
    return feats


import urllib3
urllib3.disable_warnings()

feats = bajar_manzanas()
if feats:
    import geopandas as gpd
    g = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
    for c in g.columns:
        if c != "geometry" and g[c].dtype == object:
            conv = pd.to_numeric(g[c], errors="coerce")
            if conv.notna().mean() > 0.8:
                g[c] = conv
    g.to_parquet("out/manzanas_arequipa.parquet", index=False)
    print(f"\n  OK: {len(g):,} manzanas -> out/manzanas_arequipa.parquet")
    if "pob_total" in g.columns:
        print(f"  Poblacion sumada: {g['pob_total'].sum():,.0f}")
else:
    print("\n  [!] No se pudo. Plan B manual:")
    print("      https://www.geogpsperu.com/2020/09/manzanas-y-poblacion-de-todo-el-peru.html")
    print("      Descarga el shapefile de AREQUIPA y ponlo en out/ como manzanas_arequipa.shp")

print("\n=== FIN ===")
