#!/usr/bin/env python3
"""
03_descargar_osm.py

Descarga desde OpenStreetMap las capas base de Arequipa Metropolitana:
la competencia comercial y los POIs generadores de flujo via Overpass API,
y la red vial peatonal con OSMnx, exportando todo a GeoJSON y GraphML.
"""

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


Q_COMPETENCIA = f"""
[out:json][timeout:180];
(
  node["shop"~"^(convenience|supermarket|grocery|general|kiosk|department_store)$"]({BBOX});
  way ["shop"~"^(convenience|supermarket|grocery|general|kiosk|department_store)$"]({BBOX});
);
out center tags;
"""

Q_POI = f"""
[out:json][timeout:180];
(
  node["amenity"~"^(pharmacy|bank|atm|marketplace|school|college|university|clinic|hospital|fast_food|restaurant|bus_station|place_of_worship|fuel)$"]({BBOX});
  way ["amenity"~"^(pharmacy|bank|marketplace|school|college|university|clinic|hospital|bus_station|place_of_worship|fuel)$"]({BBOX});
  node["shop"~"^(bakery|butcher|greengrocer|hairdresser|laundry)$"]({BBOX});
  node["highway"="bus_stop"]({BBOX});
);
out center tags;
"""


def main():
    print("[1/2] Descargando POIs desde Overpass API...")
    comp = a_geodataframe(overpass(Q_COMPETENCIA, "competencia"))
    poi = a_geodataframe(overpass(Q_POI, "POIs de flujo"))

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
    main()
