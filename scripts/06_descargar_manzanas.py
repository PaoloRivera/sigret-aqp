#!/usr/bin/env python3
"""
06_descargar_manzanas.py

Descarga las manzanas del Censo 2017 con poblacion para Arequipa Metropolitana
desde el servicio ArcGIS REST de SIGRID / CENEPRED: pagina la consulta por
bounding box (o por atributo si falla), convierte los campos numericos y
exporta la capa a GeoJSON y parquet.
"""

import json
import os
import time

import geopandas as gpd
import pandas as pd
import requests

SERVICIO = ("https://sigrid.cenepred.gob.pe/arcgis/rest/services/"
            "Elementos_Expuestos/MapServer/2100300/query")

XMIN, YMIN, XMAX, YMAX = -71.78, -16.62, -71.38, -16.22

HEADERS = {"User-Agent": "tesis-ucsm-retail/1.0"}
PASO = 500

os.makedirs("out", exist_ok=True)


def pedir(offset, usar_bbox=True):
    params = {
        "outFields": "*",
        "returnGeometry": "true",
        "outSR": "4326",
        "f": "geojson",
        "resultOffset": offset,
        "resultRecordCount": PASO,
    }
    if usar_bbox:
        params.update({
            "geometry": json.dumps({
                "xmin": XMIN, "ymin": YMIN, "xmax": XMAX, "ymax": YMAX,
                "spatialReference": {"wkid": 4326},
            }),
            "geometryType": "esriGeometryEnvelope",
            "inSR": "4326",
            "spatialRel": "esriSpatialRelIntersects",
            "where": "1=1",
        })
    else:
        params["where"] = "provincia = 'AREQUIPA'"

    r = requests.get(SERVICIO, params=params, headers=HEADERS, timeout=180)
    r.raise_for_status()
    return r.json()


def descargar(usar_bbox=True):
    feats, offset = [], 0
    etiqueta = "bbox" if usar_bbox else "where provincia"
    print(f"[+] Descargando por {etiqueta} ...")
    while True:
        try:
            data = pedir(offset, usar_bbox)
        except Exception as e:
            print(f"    error en offset {offset}: {e}")
            break

        lote = data.get("features", [])
        if not lote:
            break
        feats.extend(lote)
        print(f"    offset {offset:>6} -> +{len(lote):>4}  (acumulado {len(feats):,})")
        if len(lote) < PASO:
            break
        offset += PASO
        time.sleep(1)
    return feats


def main():
    feats = descargar(usar_bbox=True)
    if len(feats) < 100:
        print("\n[!] Pocos resultados por bbox. Reintentando por atributo...")
        feats = descargar(usar_bbox=False)

    if not feats:
        print("\n!!! No se descargo nada. Rutas alternativas:")
        print("    1) https://www.geogpsperu.com/2020/09/manzanas-y-poblacion-de-todo-el-peru.html")
        print("    2) https://www.geogpsperu.com/2024/09/manzanas-urbanas-censo-2017-gratis.html")
        return

    gdf = gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")
    print(f"\n[+] Manzanas descargadas: {len(gdf):,}")
    print(f"    Columnas: {list(gdf.columns)}")

    gdf = gdf.cx[XMIN:XMAX, YMIN:YMAX]

    for c in ["pob_total", "num_viv_part", "c5_p2_1", "c5_p2_2",
              "grupos_edad_1", "grupos_edad_2", "grupos_edad_3",
              "grupos_edad_4", "grupos_edad_5"]:
        if c in gdf.columns:
            gdf[c] = pd.to_numeric(gdf[c], errors="coerce")

    if "distrito" in gdf.columns:
        print("\n    Manzanas por distrito:")
        print(gdf["distrito"].value_counts().head(25).to_string())
    if "pob_total" in gdf.columns:
        print(f"\n    Poblacion total sumada: {gdf['pob_total'].sum():,.0f}")

    gdf.to_file("out/manzanas_arequipa.geojson", driver="GeoJSON")
    gdf.to_parquet("out/manzanas_arequipa.parquet", index=False)

    mb = os.path.getsize("out/manzanas_arequipa.parquet") / 1e6
    print(f"\n=== LISTO ===")
    print(f"  out/manzanas_arequipa.parquet  ({mb:.1f} MB)")


if __name__ == "__main__":
    main()
