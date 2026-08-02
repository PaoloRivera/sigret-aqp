#!/usr/bin/env python3
"""
05_empaquetar.py

Arma el paquete de datos para subir: convierte las capas OSM y la red vial a
parquet normalizando los tipos mixtos, copia los CSV, rasters y snapshots
generados por los demas scripts y comprime todo en tesis_data.zip.
"""

import os
import shutil
import zipfile

import geopandas as gpd
import pandas as pd

PAQ = "paquete"
if os.path.exists(PAQ):
    shutil.rmtree(PAQ)
for sub in ["osm", "sunat", "mass"]:
    os.makedirs(f"{PAQ}/{sub}", exist_ok=True)


def gj_a_parquet(origen, destino, cols=None):
    if not os.path.exists(origen):
        print(f"  [saltado] no existe {origen}")
        return
    g = gpd.read_file(origen)
    if cols:
        cols = [c for c in cols if c in g.columns]
        g = g[cols + ["geometry"]]
    g.to_parquet(destino, index=False)
    mb_o = os.path.getsize(origen) / 1e6
    mb_d = os.path.getsize(destino) / 1e6
    print(f"  {os.path.basename(origen)}: {mb_o:.1f} MB -> {mb_d:.1f} MB  ({len(g):,} filas)")


def copiar(origen, destino):
    if os.path.exists(origen):
        shutil.copy(origen, destino)
        print(f"  copiado {os.path.basename(origen)} "
              f"({os.path.getsize(origen)/1e6:.1f} MB)")
    else:
        print(f"  [saltado] no existe {origen}")


print("[1/4] Convirtiendo capas OSM de puntos...")
gj_a_parquet("out/osm_competencia.geojson", f"{PAQ}/osm/competencia.parquet")
gj_a_parquet("out/osm_poi_flujo.geojson", f"{PAQ}/osm/poi_flujo.parquet")
gj_a_parquet("out/osm_lugares.geojson", f"{PAQ}/osm/lugares.parquet")
gj_a_parquet("out/osm_distritos.geojson", f"{PAQ}/osm/distritos.parquet")

print("\n[2/4] Convirtiendo la red vial (esto es lo pesado)...")
if os.path.exists("out/osm_red_peatonal.graphml"):
    import osmnx as ox
    G = ox.load_graphml("out/osm_red_peatonal.graphml")
    nodes, edges = ox.graph_to_gdfs(G)

    nodes = nodes.reset_index()[["osmid", "y", "x", "street_count", "geometry"]]
    edges = edges.reset_index()
    keep = [c for c in ["u", "v", "key", "osmid", "highway", "name",
                        "length", "oneway"] if c in edges.columns]
    edges = edges[keep + ["geometry"]]

    def a_texto(v):
        if isinstance(v, (list, tuple, set)):
            return ";".join(map(str, v))
        if v is None:
            return ""
        try:
            if pd.isna(v):
                return ""
        except (TypeError, ValueError):
            pass
        return str(v)

    NUMERICAS_E = {"u", "v", "key", "length"}
    for c in edges.columns:
        if c == "geometry":
            continue
        if c in NUMERICAS_E:
            edges[c] = pd.to_numeric(edges[c], errors="coerce")
        else:
            edges[c] = edges[c].map(a_texto).astype(str)

    NUMERICAS_N = {"osmid", "x", "y", "street_count"}
    for c in nodes.columns:
        if c == "geometry":
            continue
        if c in NUMERICAS_N:
            nodes[c] = pd.to_numeric(nodes[c], errors="coerce")
        else:
            nodes[c] = nodes[c].map(a_texto).astype(str)

    edges = edges.dropna(subset=["u", "v"])
    edges["u"] = edges["u"].astype("int64")
    edges["v"] = edges["v"].astype("int64")
    if "key" in edges.columns:
        edges["key"] = edges["key"].fillna(0).astype("int64")

    nodes.to_parquet(f"{PAQ}/osm/red_nodes.parquet", index=False)
    edges.to_parquet(f"{PAQ}/osm/red_edges.parquet", index=False)
    print(f"  nodos: {len(nodes):,} -> {os.path.getsize(f'{PAQ}/osm/red_nodes.parquet')/1e6:.1f} MB")
    print(f"  aristas: {len(edges):,} -> {os.path.getsize(f'{PAQ}/osm/red_edges.parquet')/1e6:.1f} MB")
else:
    print("  [saltado] no existe out/osm_red_peatonal.graphml")

print("\n[3/4] Copiando CSV...")
os.makedirs(f"{PAQ}/inei", exist_ok=True)
copiar("out/worldpop_arequipa.tif", f"{PAQ}/inei/")
copiar("out/distritos_arequipa.geojson", f"{PAQ}/inei/")
copiar("out/manzanas_arequipa.parquet", f"{PAQ}/inei/")
import glob as _g
for _f in _g.glob("out/manzanas*.shp") + _g.glob("out/manzanas*.dbf") + \
          _g.glob("out/manzanas*.shx") + _g.glob("out/manzanas*.prj") + \
          _g.glob("out/*MANZANA*.*") + _g.glob("out/*Manzana*.*"):
    copiar(_f, f"{PAQ}/inei/")
copiar("out/mass_geocod.csv", f"{PAQ}/mass/")
copiar("out/bodegas_geocod.csv", f"{PAQ}/sunat/")
copiar("out/sunat_bodegas_arequipa.csv", f"{PAQ}/sunat/")
copiar("out/sunat_universo_arequipa.csv", f"{PAQ}/sunat/")
copiar("out/_diagnostico_columnas.txt", f"{PAQ}/sunat/")
copiar("out/mass_arequipa.csv", f"{PAQ}/mass/")
copiar("out/mass_todas.csv", f"{PAQ}/mass/")
copiar("out/mass_panel_historico.csv", f"{PAQ}/mass/")

copiar("raw/mass_ubicame.html", f"{PAQ}/mass/")

if os.path.isdir("raw/wayback"):
    os.makedirs(f"{PAQ}/mass/wayback", exist_ok=True)
    n = 0
    for f in os.listdir("raw/wayback"):
        if f.endswith(".html"):
            shutil.copy(f"raw/wayback/{f}", f"{PAQ}/mass/wayback/{f}")
            n += 1
    print(f"  copiados {n} snapshots de wayback")

print("\n[4/4] Comprimiendo...")
with zipfile.ZipFile("tesis_data.zip", "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
    for raiz, _, archivos in os.walk(PAQ):
        for a in archivos:
            ruta = os.path.join(raiz, a)
            z.write(ruta, os.path.relpath(ruta, PAQ))

mb = os.path.getsize("tesis_data.zip") / 1e6
print(f"\n=== LISTO ===")
print(f"  tesis_data.zip -> {mb:.1f} MB")
if mb > 100:
    print("  OJO: pesa mas de 100 MB. Borra la carpeta paquete/mass/wayback/")
