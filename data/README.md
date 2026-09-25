# Datos de entrada

Procedencia, licencia y volumen de cada fuente empleada por el pipeline.

## Incluidas en el repositorio

| Carpeta | Contenido | Origen | Licencia |
|---|---|---|---|
| `inei/` | Manzanas censales con población, Censo Nacional 2017 | INEI, distribución GEO GPS Perú | Uso público |
| `osm/competencia.parquet` | 182 comercios de abarrotes y conveniencia | Overpass API | ODbL |
| `osm/poi_flujo.parquet` | 3 072 puntos de interés generadores de flujo | Overpass API | ODbL |
| `osm/red_nodes.parquet` | Nodos de la red vial caminable | OSMnx | ODbL |
| `osm/red_edges.parquet` | Aristas de la red vial con longitud y jerarquía | OSMnx | ODbL |
| `osm/lugares.parquet` | Urbanizaciones, asentamientos y barrios con nombre | Overpass API | ODbL |
| `mass/mass_ubicame.html` | Snapshot actual del localizador de tiendas | Sitio web público | Público |
| `mass/wayback/*.html` | Snapshots anuales del mismo localizador (2023–2026) | Internet Archive | Público |
| `sunat/sunat_bodegas_arequipa.csv` | Establecimientos de abarrotes filtrados del padrón | SUNAT, datos abiertos | Datos abiertos |

> **Atribución obligatoria.** Los archivos de la carpeta `osm/` derivan de OpenStreetMap y deben acreditarse como *© colaboradores de OpenStreetMap*, conforme exige la Open Database License.

## No incluidas — cómo obtenerlas

### Padrón Reducido del RUC completo

El archivo `sunat_universo_arequipa.csv` (158 233 registros, ~17 MB) y el padrón nacional del que deriva (~1,6 GB) **no se versionan** en este repositorio, por dos razones: su volumen y el hecho de que constituye una extracción masiva de un registro de terceros que el Estado ya publica por canal propio.

Para regenerarlo:

1. Descargar el Padrón Reducido del RUC desde el portal de datos abiertos de la SUNAT.
2. Colocar el archivo descomprimido en `data_sunat/`.
3. Ejecutar `python scripts/04_filtrar_sunat.py`.

Este archivo se emplea únicamente como indicador de densidad de actividad económica formal por zona y **no es indispensable** para reproducir las métricas principales del modelo.

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
