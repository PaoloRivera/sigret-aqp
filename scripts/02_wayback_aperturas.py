#!/usr/bin/env python3
"""
02_wayback_aperturas.py

Reconstruye la red historica de Tiendas Mass con snapshots del Internet
Archive: consulta el indice CDX, descarga un snapshot por anio, extrae las
tiendas de cada uno y arma el panel tienda x anio con el anio de primera y
ultima aparicion, del que salen las aperturas y los cierres.
"""

import os
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

CDX = "http://web.archive.org/cdx/search/cdx"
TARGET = "tiendasmass.com.pe/ubicame*"
HEADERS = {"User-Agent": "Mozilla/5.0 (tesis-academica; contacto: tu-correo@ejemplo.com)"}

ANIOS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]

os.makedirs("raw/wayback", exist_ok=True)
os.makedirs("out", exist_ok=True)


def listar_snapshots():
    print("[1/3] Consultando el indice CDX del Internet Archive...")
    params = {
        "url": TARGET,
        "output": "json",
        "fl": "timestamp,original,statuscode,digest",
        "filter": "statuscode:200",
        "collapse": "digest",
        "limit": "5000",
    }
    r = requests.get(CDX, params=params, headers=HEADERS, timeout=120)
    r.raise_for_status()
    data = r.json()
    if len(data) < 2:
        print("      [!] Sin snapshots. Prueba con TARGET = 'tiendasmass.com.pe*'")
        return pd.DataFrame()
    df = pd.DataFrame(data[1:], columns=data[0])
    df["fecha"] = pd.to_datetime(df["timestamp"], format="%Y%m%d%H%M%S", errors="coerce")
    df["anio"] = df["fecha"].dt.year
    df = df.dropna(subset=["fecha"]).sort_values("fecha")
    print(f"      Snapshots unicos encontrados: {len(df)}")
    print(f"      Rango: {df['fecha'].min().date()} -> {df['fecha'].max().date()}")
    print("      Por anio:")
    print(df.groupby("anio").size().to_string())
    return df


def elegir_uno_por_anio(df):
    sel = df[df["anio"].isin(ANIOS)].sort_values("fecha").groupby("anio").tail(1)
    return sel.reset_index(drop=True)


def descargar_snapshot(timestamp, original):
    url = f"http://web.archive.org/web/{timestamp}id_/{original}"
    destino = f"raw/wayback/mass_{timestamp}.html"
    if os.path.exists(destino):
        return open(destino, encoding="utf-8", errors="ignore").read()
    r = requests.get(url, headers=HEADERS, timeout=120)
    r.raise_for_status()
    with open(destino, "w", encoding="utf-8") as f:
        f.write(r.text)
    time.sleep(3)
    return r.text


def extraer_tiendas(html):
    soup = BeautifulSoup(html, "lxml")
    filas = []
    for el in soup.find_all(["li", "div", "article"]):
        txt = el.get_text("\n", strip=True)
        lineas = [l for l in txt.split("\n") if l.strip()]
        if len(lineas) != 2:
            continue
        direccion, codigo = lineas
        if len(codigo) > 45 or len(direccion) < 8:
            continue
        if not re.search(r"\bMS\b|\bMS$", codigo, re.IGNORECASE):
            continue
        filas.append({"direccion": direccion.strip(), "codigo": codigo.strip()})
    vistos, out = set(), []
    for f in filas:
        k = (f["direccion"], f["codigo"])
        if k not in vistos:
            vistos.add(k)
            out.append(f)
    return out


def main():
    idx = listar_snapshots()
    if idx.empty:
        return
    sel = elegir_uno_por_anio(idx)
    print(f"\n[2/3] Descargando {len(sel)} snapshots (uno por anio)...")

    registros = []
    for _, row in sel.iterrows():
        ts, orig, anio = row["timestamp"], row["original"], int(row["anio"])
        print(f"      {anio}  ts={ts} ...", end=" ", flush=True)
        try:
            html = descargar_snapshot(ts, orig)
            tiendas = extraer_tiendas(html)
            print(f"{len(tiendas)} tiendas")
            for t in tiendas:
                registros.append({**t, "anio": anio, "timestamp": ts})
        except Exception as e:
            print(f"ERROR: {e}")

    if not registros:
        print("\n[!] No se extrajo nada. Revisa raw/wayback/*.html a mano.")
        return

    df = pd.DataFrame(registros)

    print("\n[3/3] Construyendo panel historico...")
    df["clave"] = df["codigo"].str.upper().str.replace(r"\s+", " ", regex=True).str.strip()

    panel = (df.pivot_table(index=["clave", "direccion"], columns="anio",
                            values="codigo", aggfunc="size", fill_value=0)
               .clip(upper=1)
               .reset_index())

    anios_col = [c for c in panel.columns if isinstance(c, int)]
    panel["anio_primera_aparicion"] = panel[anios_col].apply(
        lambda r: min([a for a in anios_col if r[a] == 1], default=None), axis=1)
    panel["anio_ultima_aparicion"] = panel[anios_col].apply(
        lambda r: max([a for a in anios_col if r[a] == 1], default=None), axis=1)
    panel["sigue_abierta"] = panel[max(anios_col)] == 1

    panel.to_csv("out/mass_panel_historico.csv", index=False, encoding="utf-8-sig")

    print(f"\n=== LISTO ===")
    print(f"  Tiendas unicas historicas : {len(panel)}")
    print(f"  Aperturas por anio:")
    print(panel.groupby('anio_primera_aparicion').size().to_string())
    print(f"  Cierres detectados        : {(~panel['sigue_abierta']).sum()}")
    print(f"  -> out/mass_panel_historico.csv   <-- me lo subes")


if __name__ == "__main__":
    main()
