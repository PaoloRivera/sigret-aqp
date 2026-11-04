#!/bin/zsh
# Doble clic en Finder (macOS): regenera todos los resultados de la tesis con el
# entorno .venv del proyecto. Equivale a: source .venv/bin/activate && bash ejecutar_todo.sh
cd "$(dirname "$0")"
source .venv/bin/activate
echo "Python: $(python --version) en $(which python)"
bash ejecutar_todo.sh 2>&1 | tee resultados/ejecucion_mac.log
echo "Terminado. Puedes cerrar esta ventana."
