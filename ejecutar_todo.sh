#!/usr/bin/env bash
# ejecutar_todo.sh
# Regenera todos los resultados, tablas y figuras de los Capitulos IV y V.
# Uso, desde la raiz del proyecto y con el entorno virtual activado:
#     bash ejecutar_todo.sh
set -euo pipefail
PY="${PY:-python}"
export PYTHONUNBUFFERED=1
mkdir -p resultados/base_censo2017 figuras

echo "== 1/14 Corrida de comparacion con la poblacion del Censo 2017"
"$PY" pipeline.py --poblacion 2017 --salida resultados/base_censo2017 > resultados/base_censo2017/log_pipeline.txt
echo "== 2/14 Modelo principal (poblacion actualizada al Censo 2025)"
"$PY" pipeline.py | tee resultados/log_pipeline.txt
echo "== 3/14 Comparacion entre ambas poblaciones";  "$PY" comparar_poblacion.py
echo "== 4/14 Integridad (Tabla 7)";                 "$PY" verificar_integridad.py
echo "== 5/14 Sensibilidad (Tabla 16, Figura 25)";   "$PY" sensibilidad_ranking.py
echo "== 6/14 Robustez de los parametros del score"; "$PY" robustez_parametros.py
echo "== 7/14 Figuras del Capitulo IV";              "$PY" figuras_capitulo4.py
echo "== 8/14 Figuras del Capitulo V";               "$PY" figuras_capitulo5.py
echo "== 9/14 Analisis complementarios";             "$PY" analisis_complementarios.py
echo "== 10/14 IC de la validacion espacial";        "$PY" ic_validacion_espacial.py
echo "== 11/14 Simulador con h = 120 (Tablas 6 y 13, Anexo J)"; "$PY" verificar_huff.py
# Conteo de campo (Anexo K), solo si ya existe. La muestra no se vuelve a sortear.
if [ -f data/campo/kobo/conteo_bodegas.xlsx ]; then
  echo "== 11b Conteo de campo (Anexo K)"
  "$PY" scripts/15_calibrar_bodegas.py --kobo data/campo/kobo/conteo_bodegas.xlsx
elif [ -f resultados/campo/conteo_por_celda.csv ]; then
  echo "== 11b Conteo de campo (Anexo K), desde los conteos publicados"
  "$PY" scripts/15_calibrar_bodegas.py --conteos resultados/campo/conteo_por_celda.csv
fi
echo "== 12/14 Datos de la aplicacion web";          "$PY" scripts/10_generar_json_app.py
echo "== 13/14 Figura 19 (datos servidos)";          "$PY" scripts/12_figura_datos_servidos.py
echo "== 14/14 Figuras 1, 2 y 4 (diagramas)";        "$PY" scripts/13_diagramas.py
# Capturas de la aplicacion (Figuras 5 a 11), opcional: requiere compilar la
# aplicacion (cd app_web && npm run build) y el paquete playwright:
#   python scripts/11_capturas_app.py
echo "== LISTO"
