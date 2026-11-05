#!/usr/bin/env bash
# ejecutar_todo.sh
# Regenera todos los resultados, tablas y figuras de los Capitulos IV y V.
# Uso, desde la raiz del proyecto y con el entorno virtual activado:
#     bash ejecutar_todo.sh
set -euo pipefail
PY="${PY:-python}"
export PYTHONUNBUFFERED=1
mkdir -p resultados/base_censo2017 figuras

echo "== 1/15 Corrida de comparacion con la poblacion del Censo 2017"
"$PY" pipeline.py --poblacion 2017 --salida resultados/base_censo2017 > resultados/base_censo2017/log_pipeline.txt
echo "== 2/15 Modelo principal (poblacion actualizada al Censo 2025)"
"$PY" pipeline.py | tee resultados/log_pipeline.txt
echo "== 3/15 Comparacion entre ambas poblaciones";  "$PY" comparar_poblacion.py
echo "== 4/15 Integridad (Tabla 7)";                 "$PY" verificar_integridad.py
echo "== 5/15 Sensibilidad (Tabla 16, Figura 25)";   "$PY" sensibilidad_ranking.py
echo "== 6/15 Robustez de los parametros del score"; "$PY" robustez_parametros.py
echo "== 7/15 Figuras del Capitulo IV";              "$PY" figuras_capitulo4.py
echo "== 8/15 Figuras del Capitulo V";               "$PY" figuras_capitulo5.py
echo "== 9/15 Analisis complementarios";             "$PY" analisis_complementarios.py
echo "== 10/15 IC de la validacion espacial";        "$PY" ic_validacion_espacial.py
echo "== 11/15 Eleccion del modelo: pruebas formales y estabilidad (unos 7 min)"
"$PY" analisis_eleccion_modelo.py
echo "== 12/15 Simulador con h = 120 (Tablas 6 y 13, Anexo J)"; "$PY" verificar_huff.py
# Conteo de campo opcional, solo si ya existe. La muestra no se vuelve a sortear.
if [ -f data/campo/kobo/conteo_bodegas.xlsx ]; then
  echo "== 12b Conteo de campo"
  "$PY" scripts/15_calibrar_bodegas.py --kobo data/campo/kobo/conteo_bodegas.xlsx
elif [ -f resultados/campo/conteo_por_celda.csv ]; then
  echo "== 12b Conteo de campo, desde los conteos publicados"
  "$PY" scripts/15_calibrar_bodegas.py --conteos resultados/campo/conteo_por_celda.csv
fi
# Segunda ronda de evaluacion (observacion 5), solo si ya hay respuestas
if [ -f data/encuestas/kobo/ronda2.xlsx ]; then
  echo "== 12c Segunda ronda de evaluacion"
  "$PY" evaluacion_ronda2.py --kobo data/encuestas/kobo/ronda2.xlsx
elif [ -f data/encuestas/ronda2_respuestas.csv ]; then
  echo "== 12c Segunda ronda de evaluacion, desde las respuestas publicadas"
  "$PY" evaluacion_ronda2.py --respuestas data/encuestas/ronda2_respuestas.csv
fi
echo "== 13/15 Datos de la aplicacion web";          "$PY" scripts/10_generar_json_app.py
echo "== 14/15 Figura 19 (datos servidos)";          "$PY" scripts/12_figura_datos_servidos.py
echo "== 15/15 Figuras 1, 2 y 4 (diagramas)";        "$PY" scripts/13_diagramas.py
# Capturas de la aplicacion (Figuras 5 a 11), opcional: requiere compilar la
# aplicacion (cd app_web && npm run build) y el paquete playwright:
#   python scripts/11_capturas_app.py
echo "== LISTO"
