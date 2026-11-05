#!/usr/bin/env python3
"""
16_formulario_ronda2.py

Genera el formulario de la segunda ronda de evaluacion con propietarios de
minimarket (observacion 5) en formato XLSForm, para KoboToolbox:
    data/encuestas/formulario_ronda2.xlsx

Es la misma encuesta de la primera ronda (SUS de 10 items, Anexo B, y TAM de 15
items, Anexo C), con tres cambios:
  - se guarda la respuesta de cada pregunta, no solo el promedio;
  - es anonima: no pide nombre, telefono, correo ni datos del negocio, y no
    guarda el identificador del equipo;
  - dos items nombraban funciones de la version tecnica y se ajustan al modo
    comerciante: el SUS 5 (funciones integradas) y el TAM f3 (controles del
    modelo). Los otros 23 items quedan con el mismo texto.

Uso, desde la raiz del proyecto:
    python scripts/16_formulario_ronda2.py
"""
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

SALIDA = "data/encuestas/formulario_ronda2.xlsx"
VERSION = "2026110501"

SUS = [
    "Creo que me gustaría utilizar este sistema con frecuencia.",
    "Encontré el sistema innecesariamente complejo.",
    "Pensé que el sistema era fácil de usar.",
    "Creo que necesitaría el apoyo de una persona con conocimientos técnicos para poder utilizar este sistema.",
    # Primera ronda: "(mapa, ranking, simulador y controles del modelo)"
    "Encontré que las diversas funciones del sistema (elegir la zona, ver las mejores zonas, calcular mis números y la ficha) estaban bien integradas.",
    "Pensé que había demasiada inconsistencia en este sistema.",
    "Imagino que la mayoría de las personas aprenderían a usar este sistema muy rápidamente.",
    "Encontré el sistema muy engorroso de usar.",
    "Me sentí muy seguro utilizando el sistema.",
    "Necesité aprender muchas cosas antes de poder empezar a usar este sistema.",
]

TAM = [
    ("u1", "Usar este sistema me permitiría evaluar ubicaciones más rápido de lo que lo haría por mi cuenta."),
    ("u2", "Usar este sistema mejoraría la calidad de mi decisión sobre dónde abrir un local."),
    ("u3", "Usar este sistema aumentaría mi productividad al analizar oportunidades comerciales."),
    ("u4", "Usar este sistema reduciría el riesgo de elegir una mala ubicación."),
    ("u5", "Usar este sistema me facilitaría comparar varias alternativas de ubicación."),
    ("u6", "En general, considero que este sistema es útil para decidir dónde abrir un minimarket."),
    ("f1", "Aprender a manejar este sistema me resultaría fácil."),
    ("f2", "Me resultaría fácil lograr que el sistema me muestre lo que quiero ver."),
    # Primera ronda: "Los controles que permiten ajustar el modelo me resultaron comprensibles."
    ("f3", "Los pasos para elegir la zona y calcular mis números me resultaron comprensibles."),
    ("f4", "Me resultaría fácil volverme hábil en el uso de este sistema."),
    ("f5", "Mi interacción con el sistema fue clara y comprensible."),
    ("f6", "En general, considero que este sistema es fácil de usar."),
    ("i1", "Tengo la intención de usar este sistema si tuviera que evaluar una ubicación."),
    ("i2", "Recomendaría este sistema a otro comerciante que esté por abrir un local."),
    ("i3", "Usaría los resultados de este sistema para sustentar una decisión real de inversión."),
]

SIGUE = "${consentimiento} = 'si' and ${rol} != 'otro'"

survey = [
    ("start", "inicio", "", "", "", "", "", ""),
    ("end", "fin", "", "", "", "", "", ""),
    ("note", "presentacion",
     "Encuesta anónima sobre la aplicación SIGRET-AQP, parte de una tesis de la Universidad Católica de Santa María. "
     "No le pedimos su nombre, teléfono ni datos de su negocio. Responder toma unos 5 minutos y puede dejarla cuando quiera.",
     "", "", "", "", ""),
    ("select_one si_no", "consentimiento", "¿Acepta responder esta encuesta anónima?", "", "yes", "", "", ""),
    ("select_one rol", "rol", "¿Cuál es su relación con un minimarket o una bodega?",
     "Minimarket: el cliente toma los productos de los estantes. Bodega: se atiende en mostrador.",
     "yes", "${consentimiento} = 'si'", "", ""),
    ("note", "fuera", "Gracias. Esta encuesta es solo para dueños o administradores de un minimarket o una bodega.",
     "", "", "${rol} = 'otro'", "", ""),
    ("select_one anios", "anios", "¿Cuántos años tiene su negocio?", "", "yes", SIGUE, "", ""),
    ("select_one edad", "edad", "¿Qué edad tiene?", "", "yes", SIGUE, "", ""),
    ("select_one conocia", "conocia", "¿Conocía este proyecto antes de hoy?", "", "yes", SIGUE, "", ""),
    ("select_one dispositivo", "dispositivo", "¿En qué usó la aplicación?", "", "yes", SIGUE, "", ""),
    ("select_one tarea", "tarea",
     "¿Pudo hacer los tres pasos: elegir dónde buscar, ver las mejores zonas y calcular sus números?",
     "", "yes", SIGUE, "", ""),
    ("integer", "minutos", "¿Cuántos minutos usó la aplicación, más o menos?", "", "yes", SIGUE, "",
     ". >= 0 and . <= 240"),
    ("note", "intro_sus",
     "Ahora, diez frases sobre la aplicación. Marque qué tan de acuerdo está con cada una. "
     "No hay respuestas correctas; nos sirve su opinión sincera.", "", "", SIGUE, "", ""),
]
for i, t in enumerate(SUS, 1):
    survey.append(("select_one acuerdo", f"s{i}", f"{i}. {t}", "", "yes", SIGUE, "likert", ""))
survey.append(("note", "intro_tam", "Y quince frases más sobre lo útil y lo fácil que le pareció.", "", "", SIGUE, "", ""))
for i, (k, t) in enumerate(TAM, 11):
    survey.append(("select_one acuerdo", k, f"{i}. {t}", "", "yes", SIGUE, "likert", ""))
survey += [
    ("text", "dificil", "¿Qué fue lo más difícil o confuso? (opcional)",
     "No escriba nombres ni datos que lo identifiquen.", "", SIGUE, "multiline", ""),
    ("text", "agregar", "¿Qué le agregaría o cambiaría? (opcional)",
     "No escriba nombres ni datos que lo identifiquen.", "", SIGUE, "multiline", ""),
    ("note", "gracias", "Gracias por su tiempo. Ya puede enviar el formulario.", "", "", "${consentimiento} = 'si'", "", ""),
]

choices = [
    ("si_no", "si", "Sí"), ("si_no", "no", "No"),
    ("rol", "dueno_minimarket", "Soy dueño(a) de un minimarket"),
    ("rol", "dueno_bodega", "Soy dueño(a) de una bodega"),
    ("rol", "administra", "Administro un minimarket o una bodega, pero no soy el dueño"),
    ("rol", "otro", "Ninguna de las anteriores"),
    ("anios", "menos_1", "Menos de 1 año"), ("anios", "1_5", "De 1 a 5 años"),
    ("anios", "6_10", "De 6 a 10 años"), ("anios", "mas_10", "Más de 10 años"),
    ("edad", "18_29", "De 18 a 29 años"), ("edad", "30_44", "De 30 a 44 años"),
    ("edad", "45_59", "De 45 a 59 años"), ("edad", "60_mas", "60 años o más"),
    ("conocia", "panel", "Sí, participé en la encuesta de prioridades del proyecto (comparar criterios de a dos)"),
    ("conocia", "vio", "Sí, ya había visto la aplicación"),
    ("conocia", "no", "No"),
    ("dispositivo", "celular", "Celular"), ("dispositivo", "computadora", "Computadora"),
    ("dispositivo", "tablet", "Tablet"),
    ("tarea", "si", "Sí, los tres"), ("tarea", "en_parte", "Solo algunos"), ("tarea", "no", "No pude"),
    ("acuerdo", "1", "Totalmente en desacuerdo"), ("acuerdo", "2", "En desacuerdo"),
    ("acuerdo", "3", "Ni de acuerdo ni en desacuerdo"), ("acuerdo", "4", "De acuerdo"),
    ("acuerdo", "5", "Totalmente de acuerdo"),
]


def hoja(wb, titulo, cabecera, filas, anchos):
    ws = wb.create_sheet(titulo)
    ws.append(cabecera)
    for c in ws[1]:
        c.font = Font(bold=True)
    for f in filas:
        ws.append(list(f))
    for col, w in zip("ABCDEFGH", anchos):
        ws.column_dimensions[col].width = w
    for fila in ws.iter_rows(min_row=2):
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    return ws


wb = Workbook()
wb.remove(wb.active)
hoja(wb, "survey", ["type", "name", "label", "hint", "required", "relevant", "appearance", "constraint"],
     survey, [22, 16, 70, 40, 9, 34, 12, 18])
hoja(wb, "choices", ["list_name", "name", "label"], choices, [14, 18, 70])
hoja(wb, "settings", ["form_title", "form_id", "version", "default_language"],
     [("Evaluación de SIGRET-AQP · segunda ronda", "sigret_ronda2", VERSION, "es")], [44, 16, 14, 16])
os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
wb.save(SALIDA)
n_items = sum(1 for f in survey if f[1][:1] in "sufi" and f[1][1:].isdigit())
print(f"{SALIDA}: {len(survey)} filas, {n_items} items SUS/TAM, version {VERSION}")
