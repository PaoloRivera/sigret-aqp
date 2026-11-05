# Protocolo de la segunda ronda de evaluación

Objetivo: medir la usabilidad (SUS) y la aceptación (TAM) del modo comerciante
con el usuario objetivo del sistema, propietarios de minimarket de Arequipa, y
guardar la respuesta de cada pregunta. Es la iteración de la fase de evaluación
de la DSRM: se diseñó el modo comerciante a partir de la primera ronda y se
vuelve a evaluar.

| Qué | Dónde |
|---|---|
| Aplicación, modo comerciante | `https://paolorivera.github.io/sigret-aqp/#/comerciante` (ver paso 1) |
| Formulario anónimo | `data/encuestas/formulario_ronda2.xlsx`, para KoboToolbox (paso 2) |
| Análisis | `evaluacion_ronda2.py` (paso 6) |

## Muestra

- Solo propietarios de minimarket. Si responde un dueño de bodega o un
  administrador, se guarda, pero va en el análisis de sensibilidad, no en el
  principal.
- Objetivo: 20 respuestas válidas. Mínimo: 15. Con 20, el promedio SUS se
  estima con un margen de ±3,4 puntos (IC 95 %, con la desviación estándar de
  7,19 de la primera ronda); con 15, ±4,0; con los 5 de la primera ronda, ±8,9.
- Reclutamiento: los 10 propietarios del panel AHP más propietarios nuevos. El
  formulario pregunta si ya conocían el proyecto, y el análisis se repite sin
  ellos.

## 1. Publicar la aplicación (una sola vez)

1. Haz `git push` del repositorio.
2. En GitHub: *Settings* > *Pages* > *Build and deployment* > *Source*:
   **GitHub Actions**.
3. Si el repositorio aún no tiene `.github/workflows/sitio.yml`, créalo en
   GitHub con *Add file* > *Create new file* y luego haz `git pull`. Sin ese
   archivo no se publica nada.
4. En la pestaña *Actions*, abre «Sitio de la aplicación» y espera la marca
   verde (unos 3 minutos). Si no arrancó, *Run workflow*.
5. Abre `https://paolorivera.github.io/sigret-aqp/#/comerciante` en tu
   celular y prueba los tres pasos.

## 2. Preparar el formulario (una sola vez)

1. En KoboToolbox: *New* > *Upload an XLSForm* > `formulario_ronda2.xlsx` >
   *Deploy*.
2. En el proyecto: *Settings* > *Sharing* > activa **Allow submissions to this
   form without a username and password**. Sin esto, Kobo pide usuario y
   contraseña.
3. *Form* > *Collect data* > **Online-Only (multiple submissions)** > *Copy*.
   Ese es el enlace del formulario.
4. Responde una vez de prueba desde tu celular y bórrala (*Data* > selecciona >
   *Delete*).

## 3. La tarea (igual para todos)

> Imagine que quiere abrir un minimarket nuevo.
> 1. En «Elige dónde buscar», elija el distrito donde vive o trabaja.
> 2. Mire las tres primeras zonas y abra una en Google Maps.
> 3. En «Calcula tus números», ponga S/ 120 000 de inversión, una tienda
>    mediana, y abra la ficha.
>
> Después responda la encuesta.

## 4. Invitación

Envíala tú, por WhatsApp, a cada propietario. No estés presente mientras usan
la aplicación ni mientras responden. Si alguien pregunta cómo se usa, responde
«úsela como le parezca; su opinión es justo lo que necesitamos» y nada más:
explicarle cambia la medición.

> Hola, [nombre]. Soy [tu nombre], estoy terminando mi tesis en la UCSM sobre
> dónde conviene abrir un minimarket en Arequipa. ¿Me ayuda con 15 minutos?
>
> 1. Abra este enlace en su celular y haga lo que dice al final del mensaje:
>    [enlace de la aplicación]
> 2. Después responda esta encuesta anónima (5 minutos): [enlace del
>    formulario]
>
> No le pido su nombre ni datos de su negocio.
> Tarea: imagine que quiere abrir un minimarket nuevo. Elija su distrito, mire
> las tres primeras zonas y abra una en Google Maps; luego calcule sus números
> con S/ 120 000 y una tienda mediana, y abra la ficha. ¡Gracias!

Para los 10 del panel AHP, agrega al inicio: «Usted ya nos ayudó a definir los
criterios; ahora queremos su opinión sobre la versión nueva de la aplicación.»

## 5. Mientras dura la recolección

- Revisa en Kobo cuántas respuestas válidas hay (rol «dueño de un minimarket»).
- A la semana, un solo recordatorio a quienes no respondieron.
- Cierra cuando llegues a 20 o a las tres semanas. Si no llegas a 15, el
  resultado se informa igual, como descriptivo, y se dice que la muestra quedó
  por debajo del mínimo.

## 6. Analizar

1. En Kobo: *Data* > *Downloads* > **XLS**, valores y encabezados **XML values
   and headers** > *Export*. Guarda el archivo como
   `data/encuestas/kobo/ronda2.xlsx`. Esa carpeta no se publica: tiene las
   respuestas abiertas y la hora de cada envío.
2. Desde la raíz del proyecto:

   ```bash
   python evaluacion_ronda2.py --kobo data/encuestas/kobo/ronda2.xlsx
   ```

   Escribe `data/encuestas/ronda2_respuestas.csv` (publicable: sin texto libre
   ni horas), `resultados/ronda2/` y `resultados/ronda2/RESUMEN_RONDA2.md`, con
   los párrafos para la tesis. Las respuestas abiertas quedan en
   `data/encuestas/kobo/respuestas_abiertas.txt` para leerlas a mano.
3. Si no se llega al criterio, se escribe así: la regla está fijada en el
   encabezado del script antes de recoger los datos.

## Cuidado de los datos

- La encuesta es anónima: no pide nombre, teléfono, correo ni datos del
  negocio, y el formulario no guarda el identificador del equipo.
- Las respuestas abiertas no se publican; si alguien escribe un dato que lo
  identifique, se borra antes de citarla.
- Dos ítems cambian de texto respecto de la primera ronda porque nombraban
  funciones de la versión técnica: SUS 5 (funciones integradas) y TAM f3
  (controles del modelo). Los otros 23 son iguales.
