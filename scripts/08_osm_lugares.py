#!/usr/bin/env python3
"""
08_osm_lugares.py

Descarga desde Overpass las dos capas que permiten geocodificar sin servicios
externos: los lugares con nombre (urbanizaciones, asentamientos humanos y
barrios) y los limites distritales, y las exporta a GeoJSON.
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


def consultar(query, etiqueta):
    print(f"  -> {etiqueta} ...", end=" ", flush=True)
    for intento in range(3):
        try:
            r = requests.post(OVERPASS, data={"data": query},
                              headers=HEADERS, timeout=300)
            r.raise_for_status()
            data = r.json()
            print(f"{len(data.get('elements', []))} elementos")
            time.sleep(5)
            return data
        except Exception as e:
            print(f"[reintento {intento+1}: {e}]", end=" ")
            time.sleep(15)
    print("FALLO")
    return {"elements": []}


def a_gdf(osm_json, poligonos=False):
    from shapely.geometry import Point, Polygon
    feats = []
    for el in osm_json.get("elements", []):
        tags = el.get("tags", {})
        nombre = tags.get("name")
        if not nombre:
            continue

        geom = None
        if poligonos and el.get("geometry"):
            coords = [(p["lon"], p["lat"]) for p in el["geometry"]]
            if len(coords) >= 4:
                try:
                    geom = Polygon(coords)
                except Exception:
                    geom = None
        if geom is None:
            if el["type"] == "node":
                geom = Point(el.get("lon"), el.get("lat"))
            else:
                c = el.get("center") or {}
                if c.get("lon") is None:
                    continue
                geom = Point(c["lon"], c["lat"])

        feats.append({
            "type": "Feature",
            "geometry": geom.__geo_interface__,
            "properties": {
                "osm_id": el["id"], "osm_type": el["type"], "name": nombre,
                "place": tags.get("place"), "landuse": tags.get("landuse"),
                "boundary": tags.get("boundary"),
                "admin_level": tags.get("admin_level"),
            },
        })
    if not feats:
        return gpd.GeoDataFrame(columns=["name", "geometry"], crs="EPSG:4326")
    return gpd.GeoDataFrame.from_features(feats, crs="EPSG:4326")


Q_LUGARES = f"""
[out:json][timeout:240];
(
  node["place"~"^(neighbourhood|suburb|quarter|village|town|hamlet|city|locality|isolated_dwelling)$"]({BBOX});
  way ["place"~"^(neighbourhood|suburb|quarter|village|town|hamlet|locality)$"]({BBOX});
  way ["landuse"="residential"]["name"]({BBOX});
  relation["place"~"^(neighbourhood|suburb|quarter|village|town)$"]({BBOX});
);
out geom tags;
"""

Q_DISTRITOS = f"""
[out:json][timeout:240];
(
  relation["boundary"="administrative"]["admin_level"~"^(6|7|8)$"]({BBOX});
  way     ["boundary"="administrative"]["admin_level"~"^(6|7|8)$"]({BBOX});
);
out geom tags;
"""

print("[1/2] Lugares con nombre (urbanizaciones, AAHH, barrios)...")
lug = a_gdf(consultar(Q_LUGARES, "lugares"), poligonos=True)
if len(lug):
    lug.to_file("out/osm_lugares.geojson", driver="GeoJSON")
    print(f"      guardados: {len(lug)} lugares con nombre")
    print("      tipos:")
    print("      " + lug["place"].fillna(lug["landuse"]).value_counts().head(8).to_string().replace("\n", "\n      "))
    print("      muestra:", ", ".join(lug["name"].head(6).tolist()))
else:
    print("      [!] sin resultados")

print("\n[2/2] Limites distritales...")
dis = a_gdf(consultar(Q_DISTRITOS, "distritos"), poligonos=True)
if len(dis):
    dis.to_file("out/osm_distritos.geojson", driver="GeoJSON")
    print(f"      guardados: {len(dis)} unidades administrativas")
    print("      nombres:", ", ".join(sorted(dis["name"].unique())[:20]))
else:
    print("      [!] sin resultados")

print("\n=== LISTO ===")
print("  Ahora corre:  python 05_empaquetar.py")

