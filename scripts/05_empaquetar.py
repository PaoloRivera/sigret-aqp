#!/usr/bin/env python3
"""
05_empaquetar.py

Deja los datos de entrada en data/, con la estructura que espera pipeline.py:
convierte las capas OSM y la red vial a parquet normalizando los tipos mixtos
y copia la cartografia censal, los CSV y los snapshots generados por las
rutinas 01 a 09 (que escriben en out/ y raw/).

Uso (desde la raiz del proyecto):
    python scripts/05_empaquetar.py
"""

import os
import shutil

import geopandas as gpd
import pandas as pd

PAQ = "data"
for sub in ["osm", "sunat", "mass", "inei"]:
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


print("[1/3] Convirtiendo capas OSM de puntos...")
gj_a_parquet("out/osm_competencia.geojson", f"{PAQ}/osm/competencia.parquet")
gj_a_parquet("out/osm_poi_flujo.geojson", f"{PAQ}/osm/poi_flujo.parquet")
gj_a_parquet("out/osm_lugares.geojson", f"{PAQ}/osm/lugares.parquet")
gj_a_parquet("out/osm_distritos.geojson", f"{PAQ}/osm/distritos.parquet")

print("\n[2/3] Convirtiendo la red vial (esto es lo pesado)...")
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

print("\n[3/3] Copiando cartografia censal, CSV y snapshots...")
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

print("\n=== LISTO ===")
print(f"  datos de entrada en {PAQ}/  ->  siguiente paso: python pipeline.py")
