# Datos de entrada

Procedencia, licencia y volumen de cada fuente empleada por el pipeline.

## Incluidas en el repositorio

| Carpeta | Contenido | Origen | Licencia |
|---|---|---|---|
| `inei/` | Manzanas censales con población, Censo Nacional 2017 | INEI, distribución GEO GPS Perú | Uso público |
| `inei/poblacion_censada_distritos.csv` | Población censada 2017 y 2025 de los 17 distritos | INEI (2018) e INEI (2026) | Uso público |
| `inei/limites_distritales_aqp.geojson` | Límites de los 17 distritos (ubigeo INEI) | INEI, versión simplificada de juaneladio/peru-geojson | Uso público |
| `edificaciones/ob_temporal_aqp_50m.tif` | Edificaciones detectadas 2017 y 2023 (número, superficie y volumen; 50 m) | Google Open Buildings 2.5D Temporal (Sirko et al., 2023), exportado con `exportar_open_buildings.js` | CC BY 4.0 u ODbL |
| `edificaciones/edificaciones_h3.csv` | Resumen de la capa anterior por celda H3 r9 | Generado por `poblacion_actualizada.py` | — |
| `osm/competencia.parquet` | 182 comercios de abarrotes y conveniencia | Overpass API | ODbL |
| `osm/poi_flujo.parquet` | 3 072 puntos de interés generadores de flujo | Overpass API | ODbL |
| `osm/red_nodes.parquet` | Nodos de la red vial caminable | OSMnx | ODbL |
| `osm/red_edges.parquet` | Aristas de la red vial con longitud y jerarquía | OSMnx | ODbL |
| `osm_2024/` | Competencia, POIs y red vial al 31-12-2024 (predictores del backtesting) | Overpass API, consulta histórica | ODbL |
| `osm/lugares.parquet` | Urbanizaciones, asentamientos y barrios con nombre | Overpass API | ODbL |
| `mass/mass_ubicame.html` | Snapshot actual del localizador de tiendas | Sitio web público | Público |
| `mass/wayback/*.html` | Snapshots anuales del mismo localizador (2023–2026) | Internet Archive | Público |
| `sunat/sunat_bodegas_arequipa.csv` | 212 bodegas identificables en el padrón (evaluado; no se usa como predictor) | SUNAT, datos abiertos | Datos abiertos |
| `campo/muestra_campo.csv`, `.geojson`, `.kml` | Muestra del conteo de campo: 36 celdas y 12 reservas en seis estratos | Generado por `scripts/14_muestra_campo.py` (semilla 42) | — |
| `campo/plan_jornadas.csv`, `campo/precision_esperada.csv` | Orden sugerido de visita y precisión esperada de h con esta muestra | `scripts/14_muestra_campo.py` | — |
| `campo/formulario_kobo.xlsx` | Formulario XLSForm del conteo para KoboToolbox | `scripts/14_muestra_campo.py` | — |
| `encuestas/formulario_ronda2.xlsx` | Formulario XLSForm de la segunda ronda de evaluación (SUS y TAM por pregunta, anónimo) | `scripts/16_formulario_ronda2.py` | — |
| `encuestas/ronda2_respuestas.csv` | Respuestas de la segunda ronda, sin texto libre ni horas (cuando exista) | `evaluacion_ronda2.py --kobo` | — |

> **Atribución obligatoria.** Los archivos de la carpeta `osm/` derivan de OpenStreetMap y deben acreditarse como *© colaboradores de OpenStreetMap*, conforme exige la Open Database License.

## No incluidas — cómo obtenerlas

### Padrón Reducido del RUC completo

El archivo `sunat_universo_arequipa.csv` (158 233 registros, ~17 MB) y el padrón nacional del que deriva (~1,6 GB) **no se versionan** en este repositorio, por dos razones: su volumen y el hecho de que constituye una extracción masiva de un registro de terceros que el Estado ya publica por canal propio.

Para regenerarlo:

1. Descargar el Padrón Reducido del RUC desde el portal de datos abiertos de la SUNAT.
2. Colocar el archivo descomprimido en `data_sunat/`.
3. Ejecutar `python scripts/04_filtrar_sunat.py`.

Este archivo se emplea únicamente como indicador de densidad de actividad económica formal por zona y **no es indispensable** para reproducir las métricas principales del modelo.

### Exportación de la segunda ronda de evaluación

La exportación de KoboToolbox va en `data/encuestas/kobo/ronda2.xlsx`, que no se
publica porque trae las respuestas abiertas y la hora de cada envío.
`evaluacion_ronda2.py --kobo` escribe `encuestas/ronda2_respuestas.csv`, que sí
se publica y basta para reproducir el análisis. El procedimiento está en
`docs/evaluacion/protocolo_ronda2.md`.

### Exportación del conteo de campo

La exportación de KoboToolbox y las fotos van en `data/campo/kobo/`, que no se
publica: ubican bodegas que funcionan en viviendas. Los conteos por celda que
salen de ella están en `resultados/campo/conteo_por_celda.csv` y bastan para
reproducir la calibración (`scripts/15_calibrar_bodegas.py --conteos`). El
procedimiento está en `docs/campo/protocolo_campo.md`.

## Sobre los snapshots del Internet Archive

Los cuatro archivos de `mass/wayback/` son la **evidencia documental de la variable objetivo**: de ellos se obtiene el año de apertura de cada establecimiento. Se conservan en el repositorio porque el contenido archivado puede cambiar o dejar de estar disponible, lo que haría irreproducible el etiquetado.

El nombre de cada archivo codifica la marca temporal exacta del snapshot en formato `AAAAMMDDhhmmss`.

El snapshot de 2023 se conserva como evidencia, pero su marcado no incluye las
coordenadas de las tiendas y el pipeline no extrae registros de él. La serie
utilizable consta de cuatro cortes: los snapshots de 2024, 2025 y 2026 más la
versión vigente del localizador (`mass/mass_ubicame.html`).

## Estructura esperada por el pipeline

`pipeline.py` espera esta disposición exacta:

```
data/
├── inei/*Manzanas_Poblacion*.shp   (con .dbf, .shx, .prj acompañantes)
├── osm/red_nodes.parquet
├── osm/red_edges.parquet
├── osm/poi_flujo.parquet
├── osm/competencia.parquet
├── mass/mass_ubicame.html
└── mass/wayback/*.html
```

## Panel de expertos

`calcular_ahp.py` lee las comparaciones pareadas del panel desde
`panel/matrices_ahp.csv`, con una fila por comparación:

```
experto,criterio_a,criterio_b,valor
E01,C1,C2,3
E01,C1,C3,5
...
```

`criterio_a` y `criterio_b` son las claves C1 a C4 del Anexo D de la tesis y `valor`
es el juicio en la escala de Saaty (1 a 9, o su recíproco si pesa más `criterio_b`).
Cada experto aporta seis comparaciones.
