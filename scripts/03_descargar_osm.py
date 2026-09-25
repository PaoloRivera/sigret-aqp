#!/usr/bin/env python3
"""
03_descargar_osm.py

Descarga desde OpenStreetMap las capas base de Arequipa Metropolitana:
la competencia comercial y los POIs generadores de flujo via Overpass API,
y la red vial peatonal con OSMnx, exportando todo a GeoJSON y GraphML.

Con --corte AAAA-MM-DD reconstruye las capas tal como estaban en esa fecha
(consultas historicas de Overpass) y las deja directamente en data/osm_AAAA/,
con el mismo formato que data/osm/. Asi se obtienen predictores sin
informacion posterior al corte de entrenamiento del backtesting.

Uso (desde la raiz del proyecto):
    python scripts/03_descargar_osm.py                     # estado actual -> out/
    python scripts/03_descargar_osm.py --corte 2024-12-31  # historico -> data/osm_2024/
"""

import argparse
import json
import os
import time

import geopandas as gpd
import requests

os.makedirs("out", exist_ok=True)

SOUTH, WEST, NORTH, EAST = -16.62, -71.78, -16.22, -71.38
BBOX = f"{SOUTH},{WEST},{NORTH},{EAST}"

OVERPASS = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "tesis-ucsm-retail-arequipa/1.0"}


def overpass(query, nombre):
    print(f"  -> {nombre} ...", end=" ", flush=True)
    r = requests.post(OVERPASS, data={"data": query}, headers=HEADERS, timeout=300)
    r.raise_for_status()
    data = r.json()
    n = len(data.get("elements", []))
    print(f"{n} elementos")
    time.sleep(5)
    return data


def a_geodataframe(osm_json):
    feats = []
    for el in osm_json.get("elements", []):
        if el["type"] == "node":
            lon, lat = el.get("lon"), el.get("lat")
        else:
            c = el.get("center") or {}
            lon, lat = c.get("lon"), c.get("lat")
        if lon is None or lat is None:
            continue
        tags = el.get("tags", {})
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "osm_id": el["id"],
                "osm_type": el["type"],
                "name": tags.get("name"),
                "shop": tags.get("shop"),
                "amenity": tags.get("amenity"),
                "brand": tags.get("brand"),
                "operator": tags.get("operator"),
                "opening_hours": tags.get("opening_hours"),
            },
        })
    if not feats:
        return gpd.GeoDataFrame(columns=["geometry"], crs="EPSG:4326")
    return gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")


CABECERA = "[out:json][timeout:180];"

Q_COMPETENCIA = f"""
{{cabecera}}
(
  node["shop"~"^(convenience|supermarket|grocery|general|kiosk|department_store)$"]({BBOX});
  way ["shop"~"^(convenience|supermarket|grocery|general|kiosk|department_store)$"]({BBOX});
);
out center tags;
"""

Q_POI = f"""
{{cabecera}}
(
  node["amenity"~"^(pharmacy|bank|atm|marketplace|school|college|university|clinic|hospital|fast_food|restaurant|bus_station|place_of_worship|fuel)$"]({BBOX});
  way ["amenity"~"^(pharmacy|bank|marketplace|school|college|university|clinic|hospital|bus_station|place_of_worship|fuel)$"]({BBOX});
  node["shop"~"^(bakery|butcher|greengrocer|hairdresser|laundry)$"]({BBOX});
  node["highway"="bus_stop"]({BBOX});
);
out center tags;
"""


def red_a_parquet(G, destino):
    """Convierte el grafo vial a los parquet de nodos y aristas de data/osm/."""
    import osmnx as ox
    import pandas as pd
    nodes, edges = ox.graph_to_gdfs(G)
    nodes = nodes.reset_index()[["osmid", "y", "x", "street_count", "geometry"]]
    edges = edges.reset_index()
    keep = [c for c in ["u", "v", "key", "osmid", "highway", "name", "length", "oneway"]
            if c in edges.columns]
    edges = edges[keep + ["geometry"]]

    def a_texto(v):
        if isinstance(v, (list, tuple, set)):
            return ";".join(map(str, v))
        return "" if v is None or (not isinstance(v, str) and pd.isna(v)) else str(v)

    for c in edges.columns:
        if c == "geometry":
            continue
        if c in ("u", "v", "key", "length"):
            edges[c] = pd.to_numeric(edges[c], errors="coerce")
        else:
            edges[c] = edges[c].map(a_texto).astype(str)
    nodes["street_count"] = pd.to_numeric(nodes["street_count"], errors="coerce")
    nodes.to_parquet(f"{destino}/red_nodes.parquet", index=False)
    edges.to_parquet(f"{destino}/red_edges.parquet", index=False)
    return len(nodes), len(edges)


def corte_historico(fecha):
    anio = fecha[:4]
    destino = f"data/osm_{anio}"
    os.makedirs(destino, exist_ok=True)
    marca = f"{fecha}T23:59:59Z"
    cab = f'[out:json][timeout:180][date:"{marca}"];'
    print(f"[1/2] Capas de puntos al {fecha} (Overpass historico)...")
    comp = a_geodataframe(overpass(Q_COMPETENCIA.replace("{cabecera}", cab), "competencia"))
    poi = a_geodataframe(overpass(Q_POI.replace("{cabecera}", cab), "POIs de flujo"))
    comp.to_parquet(f"{destino}/competencia.parquet", index=False)
    poi.to_parquet(f"{destino}/poi_flujo.parquet", index=False)
    print(f"      competencia: {len(comp)} | poi_flujo: {len(poi)}")

    print(f"\n[2/2] Red vial peatonal al {fecha} con OSMnx...")
    import osmnx as ox
    ox.settings.use_cache = True
    ox.settings.log_console = False
    ox.settings.overpass_settings = f'[out:json][timeout:{{timeout}}][date:"{marca}"]{{maxsize}}'
    G = ox.graph_from_bbox(bbox=(WEST, SOUTH, EAST, NORTH), network_type="walk",
                           simplify=True, retain_all=False)
    n, e = red_a_parquet(G, destino)
    print(f"      nodos: {n:,} | aristas: {e:,}")
    with open(f"{destino}/CORTE.txt", "w") as f:
        f.write(f"{fecha}\n")
    print(f"\n=== LISTO === capas al {fecha} en {destino}/")


def main():
    print("[1/2] Descargando POIs desde Overpass API...")
    comp = a_geodataframe(overpass(Q_COMPETENCIA.replace("{cabecera}", CABECERA), "competencia"))
    poi = a_geodataframe(overpass(Q_POI.replace("{cabecera}", CABECERA), "POIs de flujo"))

    comp.to_file("out/osm_competencia.geojson", driver="GeoJSON")
    poi.to_file("out/osm_poi_flujo.geojson", driver="GeoJSON")
    print(f"      competencia: {len(comp)} | poi_flujo: {len(poi)}")

    print("\n[2/2] Descargando red vial peatonal con OSMnx (puede tardar ~5 min)...")
    import osmnx as ox
    ox.settings.use_cache = True
    ox.settings.log_console = False

    G = ox.graph_from_bbox(
        bbox=(WEST, SOUTH, EAST, NORTH),
        network_type="walk",
        simplify=True,
        retain_all=False,
    )
    ox.save_graphml(G, "out/osm_red_peatonal.graphml")
    nodes, edges = ox.graph_to_gdfs(G)
    edges[["geometry", "highway", "length", "name"]].to_file(
        "out/osm_red_edges.geojson", driver="GeoJSON")

    print(f"      nodos: {len(nodes):,} | aristas: {len(edges):,}")
    print("\n=== LISTO === ")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--corte", help="fecha AAAA-MM-DD para reconstruir el estado historico")
    args = ap.parse_args()
    if args.corte:
        corte_historico(args.corte)
    else:
        main()
