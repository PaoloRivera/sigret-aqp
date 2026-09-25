# SIGRET-AQP

**Sistema de soporte a la decisión basado en analítica geoespacial y aprendizaje automático para la localización de minimarkets independientes en Arequipa Metropolitana**

Tesis de Ingeniería de Sistemas · Universidad Católica de Santa María · 2026
Autores: Fernando Gabriel Casapia Loayza, Paolo Marcelo Rivera Salas

---

## Qué es

Un sistema que evalúa 3 717 celdas hexagonales que cubren Arequipa Metropolitana y produce un ranking priorizado de ubicaciones candidatas para abrir un minimarket independiente, construido **íntegramente con datos públicos y software libre**.

Responde a una pregunta con consecuencia económica medible: *si voy a invertir entre S/ 120 000 y S/ 200 000 en abrir un minimarket en Arequipa, ¿en qué celda de 175 metros de lado debo hacerlo?*

## El problema que resuelve

Los modelos de localización comercial de la literatura internacional requieren tres insumos que no existen como fuente pública en el Perú: series de ventas por local, censos comerciales georreferenciados y datos de flujo peatonal. Este trabajo los sustituye mediante:

| Insumo inaccesible | Sustitución adoptada |
|---|---|
| Series de ventas por local | **Preferencia revelada**: la apertura efectiva de una cadena con equipo profesional de geomarketing como verdad de campo |
| Censo comercial georreferenciado | Cartografía colaborativa + estimación de oferta informal por densidad poblacional |
| Datos de flujo peatonal | Proxies de accesibilidad: densidad de intersecciones, vía principal y puntos de interés generadores |

## Resultados principales

| Métrica | Valor |
|---|---|
| Validación cruzada espacial (5 particiones, 52 bloques H3 r6) | **ROC-AUC 0,929** (Random Forest) · PR-AUC 0,255 (ensamble) |
| Backtesting temporal (1 259 candidatos, 39 aperturas reales) | **Lift@10 % 3,87** · PR-AUC 0,109 |
| Mejora sobre el mejor criterio univariado | +25,0 % en lift · +18,3 % en PR-AUC |
| Usabilidad con usuarios (SUS, n = 15) | 77,83 |
| Aceptación tecnológica (TAM, n = 15) | 4,13 / 5 |
| Consistencia del panel de expertos (AHP, n = 10) | CR 0,052 |

**Costo de construcción:** S/ 0 en licencias · S/ 0 en compra de datos · 0 horas de trabajo de campo · ningún convenio institucional.

## Corrección metodológica documentada

La primera versión del modelo incluía entre sus predictores variables derivadas de la propia red de competencia, que acumulaban el **83,3 % de la importancia**. El modelo había aprendido la regla trivial *"hay tienda donde hay tienda cerca"* —autocorrelación espacial pura— y optimizaba en dirección contraria a la lógica del negocio, dado que una cadena evita abrir junto a sus propios locales.

| | Antes | Después |
|---|---|---|
| PR-AUC (backtesting) | 0,045 | 0,109 |
| ROC-AUC (backtesting) | 0,676 | 0,793 |
| Aciertos en Top-20 | 1 / 20 | 3 / 20 |
| Variable más importante | `mass_k1_2024` (0,4959) | `pob_2017` (0,1615) |

La exclusión de esas variables está verificada automáticamente por `verificar_integridad.py`.

---

## Estructura del repositorio

```
├── pipeline.py              Procesamiento y modelado completo (6 fases)
├── verificar_integridad.py  Controles de integridad del pipeline (Tabla 6)
├── sensibilidad_ranking.py  Análisis de sensibilidad del score (Tabla 15, Figura 25)
├── figuras_capitulo5.py     Figuras 20 a 24 y 26 a 28 del Capítulo V
├── calcular_ahp.py          Agregación del panel de expertos (Tablas 13 y 14)
├── requirements.txt         Versiones exactas de las dependencias de Python
│
├── scripts/                 Adquisición de datos (ejecución única) y exportación a la web
│   ├── 01_scrape_mass.py            Localizador público de la cadena
│   ├── 02_wayback_aperturas.py      Snapshots del Internet Archive
│   ├── 03_descargar_osm.py          Competencia, POIs y red vial
│   ├── 04_filtrar_sunat.py          Padrón tributario
│   ├── 05_empaquetar.py             Conversión a parquet y copia a data/
│   ├── 06_descargar_manzanas.py     Cartografía censal
│   ├── 07_geocodificar.py           Geocodificación de direcciones
│   ├── 08_osm_lugares.py            Urbanizaciones y límites distritales
│   ├── 09_poblacion.py              Población modelada de verificación
│   └── 10_generar_json_app.py       Resultados del pipeline → JSON de la aplicación web
│
├── data/                    Datos de entrada (ver data/README.md)
├── resultados/              Salidas del pipeline (tablas y matrices)
├── figuras/                 Figuras del Capítulo V
└── app_web/                 Aplicación web (Vue 3 + Vuetify + Laravel, ver app_web/README.md)
```

## Instalación

Requiere **Python 3.12**. En macOS, XGBoost necesita además la librería OpenMP
(`brew install libomp`).

```bash
git clone https://github.com/PaoloRivera/sigret-aqp.git
cd sigret-aqp
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Reproducir los resultados

Los datos de entrada ya están incluidos en `data/`. Desde la raíz del proyecto:

```bash
python pipeline.py                     # malla, características, modelos y ranking → resultados/
python verificar_integridad.py         # Tabla 6
python sensibilidad_ranking.py         # Tabla 15 y Figura 25
python figuras_capitulo5.py            # Figuras 20–24 y 26–28
python scripts/10_generar_json_app.py  # datos de la aplicación web
```

La ejecución completa tarda menos de un minuto en una computadora personal.

**Panel de expertos (AHP).** `calcular_ahp.py` lee las comparaciones pareadas de
`data/panel/matrices_ahp.csv` (columnas `experto,criterio_a,criterio_b,valor`) y
escribe las Tablas 13 y 14 en `resultados/`.

## Regenerar los datos desde las fuentes originales

Solo es necesario para actualizar los datos. Las rutinas escriben en `out/` y `raw/`,
y `05_empaquetar.py` deja el resultado en `data/`. Desde la raíz del proyecto:

```bash
python scripts/01_scrape_mass.py
python scripts/02_wayback_aperturas.py
python scripts/03_descargar_osm.py
python scripts/04_filtrar_sunat.py      # requiere el padrón de SUNAT en data_sunat/
python scripts/06_descargar_manzanas.py
python scripts/07_geocodificar.py
python scripts/08_osm_lugares.py
python scripts/09_poblacion.py
python scripts/05_empaquetar.py         # al final: consolida todo en data/
```

Los servicios externos (localizador, Internet Archive, OpenStreetMap) cambian con el
tiempo, por lo que una descarga nueva no reproduce exactamente los datos de la tesis.
Para eso se usan los datos incluidos en `data/`.

## Aplicación web

```bash
cd app_web
composer install
cp .env.example .env
php artisan key:generate
pnpm install
pnpm build
php artisan serve
```

Requiere PHP 8.2+, Composer, Node.js 20+ y pnpm 9. Detalles en `app_web/README.md`.

---

## Metodología en breve

1. **Malla de análisis.** Teselación de los 17 distritos metropolitanos en celdas hexagonales H3 de resolución 9 (0,105 km²), combinando relleno de polígono, centroides y vértices para garantizar cobertura completa. La población censal de 21 705 manzanas se transfiere por ponderación areal.

2. **Variable objetivo.** El año de apertura de cada establecimiento de retail moderno se obtiene comparando versiones archivadas del localizador público de la cadena, lo que produce una serie temporalmente ordenada sin acceder a información confidencial.

3. **Características.** 49 variables construidas en cinco familias —demanda poblacional, estructura territorial, morfología vial, puntos de interés y competencia—, de las cuales 37 constituyen predictores efectivos tras excluir las derivadas de la red de retail moderno.

4. **Modelado.** Comparación de regresión logística, Random Forest, XGBoost y un ensamble por promedio de rangos percentiles, con ponderación de clases inversa a su frecuencia.

5. **Validación.** Validación cruzada agrupada sobre 52 bloques H3 de resolución 6 —para evitar la sobreestimación que produce la partición aleatoria en datos espacialmente autocorrelacionados— y backtesting temporal contra aperturas no observadas durante el entrenamiento.

6. **Score de decisión.** Combinación del perfil aprendido y la demanda residual estimada mediante un modelo de interacción espacial, con penalización decreciente por proximidad a competidores de descuento duro. Los pesos (0,344 · 0,261 · 750 m) fueron elicitados de un panel de diez propietarios de minimarket mediante el Proceso Analítico Jerárquico.

## Reproducibilidad

- Semilla aleatoria fija en `42` para todos los procesos estocásticos
- Sistemas de referencia: EPSG:4326 (geográfico) y EPSG:32719 (proyectado, UTM 19S)
- Versiones exactas de las librerías en `requirements.txt`

**Advertencia:** la reejecución con versiones distintas de las librerías de geoprocesamiento produce variaciones menores en las métricas de backtesting, atribuibles a diferencias en la asignación de puntos situados en los bordes de las celdas. Para obtener resultados idénticos instale exactamente las versiones declaradas.

## Limitaciones declaradas

1. La competencia informal no es identificable de forma exhaustiva; se estima por densidad poblacional y se declara como parámetro ajustable desde la interfaz.
2. Los cálculos de proximidad emplean distancia euclidiana; la red vial se usa para caracterizar morfología pero no para enrutamiento peatonal.
3. La base demográfica es el Censo 2017, por lo que la población de los distritos de expansión reciente está subestimada.
4. La variable objetivo indica que un emplazamiento *opera*, no que *sea rentable*.
5. El modelo de interacción espacial opera con exponente de atractividad fijado en la unidad, dado que su calibración empírica requiere datos de afluencia inexistentes como fuente pública.
6. La ventana histórica comprende dos años, insuficiente para distinguir patrones estructurales de fluctuaciones coyunturales.

## Licencia

Código bajo licencia MIT (ver `LICENSE`).

Los datos de OpenStreetMap incluidos en `data/osm/` están sujetos a la **Open Database License (ODbL)** y deben acreditarse como *© colaboradores de OpenStreetMap*. La cartografía censal procede del INEI y es de uso público. Ver `data/README.md` para el detalle de procedencia de cada fuente.

## Cómo citar

> Casapia Loayza, F. G., & Rivera Salas, P. M. (2026). *Sistema de soporte a la decisión basado en analítica geoespacial y aprendizaje automático para la localización de minimarkets independientes en Arequipa Metropolitana* [Tesis de pregrado, Universidad Católica de Santa María].
