#!/usr/bin/env python3
"""
11_capturas_app.py

Toma las capturas de la aplicacion web usadas en la tesis (Figuras 5 a 11) con
los datos actuales de app_web/public/data. Levanta un servidor local que sirve
app_web/public (la compilacion de Vite) y fotografia cada vista con Playwright
y el Google Chrome instalado, a 1710 px de ancho y densidad 2x (3420 px).

Requisitos: compilar antes la aplicacion (cd app_web && npm run build), tener
Google Chrome instalado y el paquete playwright (pip install playwright).
Uso, desde la raiz del proyecto:
    python scripts/11_capturas_app.py            # Figuras 5 a 11
    python scripts/11_capturas_app.py --anexo-l  # solo el modo comerciante (Anexo L)
Salida: docs/capturas/figura05_resumen.png ... figura11_fuentes.png y, con
--anexo-l, docs/capturas/anexo_l_pasos.png, anexo_l_calculo.png,
anexo_l_celular.png y anexo_l_ficha.png
"""
import http.server
import json
import os
import re
import socketserver
import sys
import threading

from playwright.sync_api import sync_playwright

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PUBLIC = os.path.join(RAIZ, "app_web", "public")
VISTA = os.path.join(RAIZ, "app_web", "resources", "views", "application.blade.php")
SALIDA = os.path.join(RAIZ, "docs", "capturas")
PUERTO = 8765
VENTANA = {"width": 1710, "height": 930}


def html():
    """Pagina de entrada equivalente a la vista Blade de Laravel."""
    man = json.load(open(os.path.join(PUBLIC, "build", "manifest.json"), encoding="utf-8"))
    e = man["resources/js/main.js"]
    tags = "".join(f'<link rel="stylesheet" href="/build/{c}" />' for c in e.get("css", []))
    tags += f'<script type="module" src="/build/{e["file"]}"></script>'
    b = open(VISTA, encoding="utf-8").read()
    b = b.replace("{{ asset('favicon.svg') }}", "/favicon.svg").replace("{{ asset('loader.css') }}", "/loader.css")
    return re.sub(r"@vite\(\[[^\]]*\]\)", tags, b).encode("utf-8")


class Manejador(http.server.SimpleHTTPRequestHandler):
    """Sirve app_web/public y responde la pagina de entrada en las rutas de la aplicacion."""

    def __init__(self, *a, **k):
        super().__init__(*a, directory=PUBLIC, **k)

    def log_message(self, *a):
        pass

    def do_GET(self):
        ruta = self.path.split("?")[0]
        if ruta != "/" and os.path.isfile(os.path.join(PUBLIC, ruta.lstrip("/"))):
            return super().do_GET()
        cuerpo = html()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


def abrir(pg, ruta, senal, espera=4000, desplazar=0):
    """Abre la vista, espera a que aparezca su contenido y la desplaza si se indica."""
    pg.goto(f"http://127.0.0.1:{PUERTO}{ruta}", wait_until="networkidle")
    pg.wait_for_selector(senal, timeout=60000)
    pg.wait_for_timeout(espera)
    if desplazar:
        pg.mouse.wheel(0, desplazar)
        pg.wait_for_timeout(1500)


def caja(pg, texto):
    """Rectangulo de la tarjeta (v-card) que contiene el titulo indicado."""
    xp = "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' v-card ')][1]"
    return pg.get_by_text(texto, exact=True).first.locator(xp).bounding_box()


def anexo_l(p, nav):
    """Modo comerciante (Anexo L): pasos 1 y 2, paso 3, celular y ficha."""
    pg = nav.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2, color_scheme="light")
    abrir(pg, "/comerciante", "text=Mira las mejores zonas", 8000)
    pg.screenshot(path=os.path.join(SALIDA, "anexo_l_pasos.png"))
    print("  >> anexo_l_pasos.png")
    pg.get_by_text("Calcular mis números").first.click()
    pg.wait_for_timeout(6000)
    pg.screenshot(path=os.path.join(SALIDA, "anexo_l_calculo.png"))
    print("  >> anexo_l_calculo.png")
    pg.get_by_text("Ver e imprimir la ficha").click()
    pg.wait_for_selector("text=Tus números", timeout=60000)
    pg.wait_for_timeout(1500)
    pg.screenshot(path=os.path.join(SALIDA, "anexo_l_ficha.png"), full_page=True)
    print("  >> anexo_l_ficha.png")
    cel = nav.new_context(**p.devices["iPhone 13"], color_scheme="light").new_page()
    abrir(cel, "/comerciante", "text=Mira las mejores zonas", 6000)
    cel.screenshot(path=os.path.join(SALIDA, "anexo_l_celular.png"))
    print("  >> anexo_l_celular.png")


def main():
    os.makedirs(SALIDA, exist_ok=True)
    socketserver.TCPServer.allow_reuse_address = True
    srv = socketserver.ThreadingTCPServer(("127.0.0.1", PUERTO), Manejador)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            try:
                nav = p.chromium.launch(channel="chrome")
            except Exception:
                nav = p.chromium.launch()
            if "--anexo-l" in sys.argv:
                anexo_l(p, nav)
                nav.close()
                return
            pg = nav.new_page(viewport=VENTANA, device_scale_factor=2, color_scheme="light")
            abrir(pg, "/panel", "text=Hallazgo principal", 6000)          # carga inicial de los datos
            for nombre, ruta, senal, espera, alto, desplazar in (
                    ("figura05_resumen", "/panel", "text=Hallazgo principal", 4000, 930, 0),
                    ("figura06_mapa", "/mapa", ".maplibregl-canvas", 12000, 930, 0),
                    ("figura08_ranking", "/ranking", "text=Exportar CSV", 4000, 900, 70),
                    ("figura10_validacion", "/modelo", "text=Backtesting temporal", 4000, 1000, 70),
                    ("figura11_fuentes", "/fuentes", "text=Arquitectura del procesamiento", 4000, 930, 70)):
                pg.set_viewport_size({"width": VENTANA["width"], "height": alto})
                abrir(pg, ruta, senal, espera, desplazar)
                pg.screenshot(path=os.path.join(SALIDA, f"{nombre}.png"))
                print(f"  >> {nombre}.png")
            # Simulador (Figura 9) y ficha de la celda con su mapa (Figura 7)
            pg.set_viewport_size(VENTANA)
            abrir(pg, "/simulador", "text=Contexto de la celda", 12000)
            pg.screenshot(path=os.path.join(SALIDA, "figura09_simulador.png"), full_page=True)
            print("  >> figura09_simulador.png")
            a, b = caja(pg, "Sensibilidad a la superficie"), caja(pg, "Contexto de la celda")
            mapa = pg.locator(".maplibregl-map").last.bounding_box()
            x0, y0 = max(min(a["x"], b["x"]) - 16, 0), max(min(a["y"], b["y"]) - 16, 0)
            x1 = max(a["x"] + a["width"], b["x"] + b["width"], mapa["x"] + mapa["width"]) + 16
            y1 = max(a["y"] + a["height"], b["y"] + b["height"], mapa["y"] + mapa["height"]) + 16
            pg.screenshot(path=os.path.join(SALIDA, "figura07_ficha_celda.png"), full_page=True,
                          clip={"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})
            print("  >> figura07_ficha_celda.png")
            nav.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    sys.exit(main())
