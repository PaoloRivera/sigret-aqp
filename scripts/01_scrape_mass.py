#!/usr/bin/env python3
"""
01_scrape_mass.py

Extrae el listado publico de tiendas de tiendasmass.com.pe: descarga y guarda
el HTML crudo, intenta recuperar la data desde JSON embebido o endpoints
wp-json, la parsea, infiere la ciudad por el sufijo del codigo de tienda y
exporta el listado nacional y el filtrado a Arequipa.
"""

import json
import os
import re
import sys

import pandas as pd
import requests
from bs4 import BeautifulSoup

URL = "https://www.tiendasmass.com.pe/ubicame/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "es-PE,es;q=0.9",
}

os.makedirs("raw", exist_ok=True)
os.makedirs("out", exist_ok=True)


def descargar():
    print(f"[1/4] Descargando {URL} ...")
    r = requests.get(URL, headers=HEADERS, timeout=60)
    r.raise_for_status()
    html = r.text
    with open("raw/mass_ubicame.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"      OK: {len(html):,} caracteres guardados en raw/mass_ubicame.html")
    return html


def buscar_json_embebido(html):
    print("[2/4] Buscando JSON embebido con coordenadas...")
    patrones = [
        r'var\s+\w*[Tt]iendas\w*\s*=\s*(\[.*?\]);',
        r'var\s+\w*[Ll]ocales\w*\s*=\s*(\[.*?\]);',
        r'"markers"\s*:\s*(\[.*?\])',
        r'window\.\w+\s*=\s*(\[\{.*?\}\]);',
    ]
    for p in patrones:
        for m in re.finditer(p, html, re.DOTALL):
            try:
                data = json.loads(m.group(1))
                if isinstance(data, list) and len(data) > 20:
                    print(f"      >>> ENCONTRADO: {len(data)} registros con posible lat/lng")
                    print(f"      >>> Ejemplo: {json.dumps(data[0], ensure_ascii=False)[:200]}")
                    with open("raw/mass_embebido.json", "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
                    return data
            except Exception:
                continue
    print("      No se encontro JSON embebido. Seguimos con parseo HTML.")
    return None


def probar_wp_json():
    print("[2b/4] Probando endpoints wp-json...")
    candidatos = [
        "https://www.tiendasmass.com.pe/wp-json/",
        "https://www.tiendasmass.com.pe/wp-json/wp/v2/tiendas?per_page=100",
        "https://www.tiendasmass.com.pe/wp-json/wp/v2/locales?per_page=100",
    ]
    for url in candidatos:
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code == 200 and r.text.strip().startswith(("{", "[")):
                print(f"      >>> RESPONDE: {url}")
                nombre = "raw/wpjson_" + re.sub(r"\W+", "_", url.split("wp-json/")[-1])[:40] + ".json"
                with open(nombre, "w", encoding="utf-8") as f:
                    f.write(r.text)
        except Exception:
            pass


def parsear_html(html):
    print("[3/4] Parseando HTML...")
    soup = BeautifulSoup(html, "lxml")

    distritos = []
    for sel in soup.find_all("select"):
        opciones = [o.get_text(strip=True) for o in sel.find_all("option")]
        opciones = [o for o in opciones if o and o.upper() not in ("DISTRITO", "CIUDAD", "SELECCIONE")]
        if len(opciones) > 100:
            distritos = opciones
            break
    print(f"      Distritos detectados: {len(distritos)}")

    filas = []
    for li in soup.find_all(["li", "div", "article"]):
        txt = li.get_text("\n", strip=True)
        lineas = [l for l in txt.split("\n") if l.strip()]
        if len(lineas) != 2:
            continue
        direccion, codigo = lineas
        if len(codigo) > 45 or len(direccion) < 8:
            continue
        if not re.search(r"\bMS\b|\bMS$", codigo, re.IGNORECASE):
            continue
        filas.append({"direccion": direccion, "codigo": codigo})

    vistos, limpias = set(), []
    for f in filas:
        k = (f["direccion"], f["codigo"])
        if k not in vistos:
            vistos.add(k)
            limpias.append(f)

    df = pd.DataFrame(limpias)
    print(f"      Tiendas parseadas: {len(df)}")

    if len(df) == len(distritos) and len(df) > 0:
        df["distrito"] = distritos
        print("      OK: distritos emparejados por posicion")
    else:
        df["distrito"] = None
        print(f"      AVISO: {len(df)} tiendas vs {len(distritos)} distritos -> no empareja.")
        print("      Se infiere el distrito por el sufijo del codigo mas abajo.")

    return df


SUFIJOS_CIUDAD = {
    "AQP": "AREQUIPA", "TRU": "TRUJILLO", "PIU": "PIURA", "CIX": "CHICLAYO",
    "HYO": "HUANCAYO", "CHB": "CHIMBOTE", "IC": "ICA", "PI": "PISCO",
    "CHI": "CHINCHA", "CUS": "CUSCO", "TBP": "TUMBES", "HCO": "HUANUCO",
    "NA": "NASCA", "PU": "PUNO", "BARR": "BARRANCA", "HUAC": "HUACHO",
    "HUAU": "HUAURA", "HUA": "HUARAL", "CHA": "CHANCAY", "CHS": "CHOSICA",
    "MP": "MI PERU", "PA": "PACHACAMAC", "LU": "LURIN", "SANT": "SAN ANTONIO",
}


def marcar_ciudad(df):
    print("[4/4] Clasificando por ciudad segun sufijo del codigo...")

    def ciudad(cod):
        if not isinstance(cod, str):
            return None
        tokens = re.split(r"[\s\-]+", cod.upper())
        for t in reversed(tokens):
            t = t.strip("()")
            if t in SUFIJOS_CIUDAD:
                return SUFIJOS_CIUDAD[t]
        return None

    df["ciudad_inferida"] = df["codigo"].apply(ciudad)
    return df


def main():
    html = descargar()
    buscar_json_embebido(html)
    probar_wp_json()

    df = parsear_html(html)
    if df.empty:
        print("\n[!] No se parseo nada. Revisa raw/mass_ubicame.html manualmente.")
        sys.exit(1)

    df = marcar_ciudad(df)
    df.insert(0, "id_tienda", range(1, len(df) + 1))
    df["fuente"] = "tiendasmass.com.pe/ubicame"
    df["fecha_captura"] = pd.Timestamp.today().strftime("%Y-%m-%d")

    df.to_csv("out/mass_todas.csv", index=False, encoding="utf-8-sig")

    mask = (df["ciudad_inferida"] == "AREQUIPA")
    if df["distrito"].notna().any():
        distritos_aqp = [
            "AREQUIPA", "ALTO SELVA ALEGRE", "CAYMA", "CERRO COLORADO", "CHARACATO",
            "JACOBO HUNTER", "HUNTER", "MARIANO MELGAR", "MIRAFLORES", "PAUCARPATA",
            "SACHACA", "SOCABAYA", "TIABAYA", "UCHUMAYO", "YANAHUARA", "YURA",
            "JOSE LUIS BUSTAMANTE Y RIVERO", "JOSÉ LUIS BUSTAMANTE Y RIVERO",
            "SABANDIA", "UMACOLLO", "MAJES", "LA JOYA",
        ]
        mask = mask | df["distrito"].str.upper().isin(distritos_aqp)

    aqp = df[mask].copy()
    aqp.to_csv("out/mass_arequipa.csv", index=False, encoding="utf-8-sig")

    print(f"\n=== LISTO ===")
    print(f"  Total nacional : {len(df)}")
    print(f"  Arequipa       : {len(aqp)}   <-- este archivo me subes")
    print(f"  -> out/mass_arequipa.csv")
    if len(aqp) < 30:
        print("\n  [!] Menos de 30 tiendas en Arequipa. Revisa el parseo antes de seguir.")


if __name__ == "__main__":
    main()
