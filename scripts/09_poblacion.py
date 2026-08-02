#!/usr/bin/env python3
"""
09_poblacion.py

Resuelve las capas de limites y poblacion sin depender de portales que fallan:
descarga los limites distritales de Arequipa Metropolitana desde GADM 4.1 y
recorta al area de estudio el raster de poblacion WorldPop 2020 a 100 m
leyendolo de forma remota y parcial.
"""

import os

import requests

os.makedirs("out", exist_ok=True)

WEST, SOUTH, EAST, NORTH = -71.78, -16.62, -71.38, -16.22

DISTRITOS_AQP = [
    "Arequipa", "Alto Selva Alegre", "Cayma", "Cerro Colorado", "Characato",
    "Jacobo Hunter", "Mariano Melgar", "Miraflores", "Paucarpata", "Sabandia",
    "Sachaca", "Socabaya", "Tiabaya", "Uchumayo", "Yanahuara", "Yura",
    "Jose Luis Bustamante Y Rivero", "José Luis Bustamante Y Rivero",
]


def parte_a():
    print("=" * 60)
    print("PARTE A - LIMITES DISTRITALES (GADM 4.1)")
    print("=" * 60)

    import geopandas as gpd

    url = "https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_PER_3.json.zip"
    destino = "out/_gadm_per3.json.zip"

    if not os.path.exists(destino):
        print(f"[+] Descargando {url}")
        r = requests.get(url, timeout=300, stream=True)
        r.raise_for_status()
        total = 0
        with open(destino, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
                total += len(chunk)
                print(f"\r    {total/1e6:.1f} MB", end="", flush=True)
        print()
    else:
        print("[+] Ya descargado, reutilizando")

    g = gpd.read_file(f"zip://{destino}")
    print(f"[+] Distritos del Peru: {len(g):,}")

    col_dist = "NAME_3" if "NAME_3" in g.columns else g.columns[-2]
    col_prov = "NAME_2" if "NAME_2" in g.columns else None

    sel = g[g[col_dist].isin(DISTRITOS_AQP)]
    if col_prov:
        sel = sel[sel[col_prov].str.contains("Arequipa", case=False, na=False)]
    if len(sel) < 5:
        sel = g.cx[WEST:EAST, SOUTH:NORTH]

    sel = sel.copy()
    sel.to_file("out/distritos_arequipa.geojson", driver="GeoJSON")
    print(f"[+] Distritos de Arequipa Metropolitana: {len(sel)}")
    print("    " + ", ".join(sorted(sel[col_dist].astype(str).unique())))
    print("    -> out/distritos_arequipa.geojson")


CANDIDATOS = [
    "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/PER/per_ppp_2020_constrained.tif",
    "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/maxar_v1/PER/per_ppp_2020_constrained.tif",
    "https://data.worldpop.org/GIS/Population/Global_2000_2020/2020/PER/per_ppp_2020.tif",
]


def parte_b():
    print("\n" + "=" * 60)
    print("PARTE B - POBLACION WORLDPOP 100 m")
    print("=" * 60)

    import rasterio
    from rasterio.windows import from_bounds
    from rasterio.transform import from_origin

    os.environ["GDAL_DISABLE_READDIR_ON_OPEN"] = "EMPTY_DIR"
    os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = ".tif"

    for url in CANDIDATOS:
        print(f"\n[+] Probando lectura remota parcial:\n    {url}")
        try:
            with rasterio.open(f"/vsicurl/{url}") as src:
                print(f"    abierto: {src.width}x{src.height} px, CRS {src.crs}")
                win = from_bounds(WEST, SOUTH, EAST, NORTH, src.transform)
                data = src.read(1, window=win)
                trans = src.window_transform(win)
                perfil = src.profile.copy()

            nod = perfil.get("nodata")
            valid = data[(data != nod) & (data > 0)] if nod is not None else data[data > 0]
            print(f"    recorte: {data.shape[1]}x{data.shape[0]} px")
            print(f"    poblacion sumada en el AOI: {float(valid.sum()):,.0f} hab")

            perfil.update(height=data.shape[0], width=data.shape[1],
                          transform=trans, compress="lzw", driver="GTiff")
            with rasterio.open("out/worldpop_arequipa.tif", "w", **perfil) as dst:
                dst.write(data, 1)

            mb = os.path.getsize("out/worldpop_arequipa.tif") / 1e6
            print(f"    -> out/worldpop_arequipa.tif  ({mb:.1f} MB)")
            return True
        except Exception as e:
            print(f"    fallo: {type(e).__name__}: {str(e)[:120]}")

    print("\n[!] La lectura remota no funciono en ninguna URL.")
    print("    Instala GDAL con soporte curl")
    return False


if __name__ == "__main__":
    try:
        parte_a()
    except Exception as e:
        print(f"[!] Parte A fallo: {e}")

    try:
        parte_b()
    except Exception as e:
        print(f"[!] Parte B fallo: {e}")

    print("\n" + "=" * 60)
    print("SIGUIENTE PASO")
    print("=" * 60)
    print("  python 05_empaquetar.py     y subeme el zip")
