# Protocolo del conteo de campo de bodegas

Objetivo: contar todas las bodegas, minimarkets y tiendas de abarrotes abiertas
en 36 celdas H3 sorteadas, para medir cuántos habitantes hay por bodega (h) y
reemplazar el valor supuesto de 120 en el simulador (ecuación 1). El conteo no
cambia el modelo predictivo ni el ranking.

Materiales del repositorio:

| Archivo | Para qué |
|---|---|
| `data/campo/muestra_campo.csv` | Las 36 celdas (C01 a C36) y las 12 reservas (R01 a R12) |
| `data/campo/plan_jornadas.csv` | Orden sugerido de visita por jornada |
| `data/campo/muestra_campo.kml` | Hexágonos para Organic Maps o Google My Maps (punto azul del GPS) |
| `docs/campo/mapas_campo.pdf` | Mapa general, plan de jornadas y una página por celda |
| `data/campo/formulario_kobo.xlsx` | Formulario XLSForm para KoboToolbox |

## 1. Antes de salir

1. Crea una cuenta gratuita en KoboToolbox (plan Community: 5 000 envíos al mes
   y 1 GB de almacenamiento, de sobra para unos 300 registros con foto).
2. En KoboToolbox: *New* > *Upload an XLSForm* > `formulario_kobo.xlsx` >
   *Deploy*.
3. En cada celular:
   - Android: instala KoboCollect, configúralo con el servidor de tu cuenta y
     descarga el formulario (*Download form*). Funciona sin conexión.
   - iPhone: abre el enlace del formulario web (*Collect data* > *Online-Offline
     (multiple submission)*) con conexión, espera a que cargue completo y
     agrégalo a la pantalla de inicio; después funciona sin conexión. No borres
     la caché ni los datos del navegador mientras haya registros sin enviar.
4. Importa `muestra_campo.kml` en Organic Maps o en Google My Maps para ver los
   bordes de las celdas con tu ubicación.
5. Haz una prueba en tu calle: un registro de establecimiento y uno de cierre.
   Bórralos después en KoboToolbox (*Data* > seleccionar > *Delete*).
6. Lleva batería externa. Sal de día, entre 9:00 y 18:00, de lunes a sábado.

## 2. En cada celda

1. Ubica el borde de la celda en el mapa. Recorre **todas las calles dentro del
   borde** y **las dos veredas de las calles que forman el borde**. El GPS
   decide después a qué celda pertenece cada registro.
2. Por cada establecimiento abierto, párate frente a la entrada y crea un
   registro *Un establecimiento*:
   - espera a que la precisión del GPS baje de 10 m;
   - toma la foto de la fachada sin personas en primer plano y sin enfocar el
     interior de la vivienda;
   - elige el tipo y responde las preguntas (son menos de un minuto).
3. Al terminar la celda, crea un registro *Cierre de la celda*: si recorriste
   todo, los minutos que tomó y cuántas bodegas estaban **cerradas** pero se
   reconocen por su letrero (esas no se registran como establecimiento).

### Qué se registra

| Tipo | Se registra | Ejemplos |
|---|---|---|
| Bodega o tienda de barrio | Sí | Vende abarrotes envasados para el hogar: arroz, azúcar, aceite, fideos, conservas, bebidas, limpieza. Incluye las que atienden por ventana o reja |
| Minimarket independiente | Sí | Autoservicio sin marca de cadena |
| Tienda de abarrotes | Sí | Abarrotes al por menor, aunque también venda por mayor |
| Cadena o supermercado | Sí, con su tipo | Mass, Tambo, Oxxo, Listo, Repshop, Plaza Vea, Tottus, Metro, Franco |
| Mercado o galería | Una sola vez, con su número de puestos de abarrotes | Mercado de abastos, galería comercial |
| No estoy seguro | Sí, como «dudoso» | Se decide después con la foto |
| No se registra | — | Solo pan, solo licores, farmacia, ferretería, restaurante, ambulante sin local, kiosco de golosinas |

### Cuándo usar una reserva

Solo si la celda **no puede recorrerse**: inseguridad, condominio o calles
cerradas en la mayor parte de la celda, u obra que la bloquea. Usa la primera
reserva del mismo estrato y, si tampoco se puede, la segunda:

| Estrato | Celdas | Reservas |
|---|---|---|
| Densidad baja, consolidada | C01 a C06 | R01, R02 |
| Densidad baja, expansión | C07 a C12 | R03, R04 |
| Densidad media, consolidada | C13 a C18 | R05, R06 |
| Densidad media, expansión | C19 a C24 | R07, R08 |
| Densidad alta, consolidada | C25 a C30 | R09, R10 |
| Densidad alta, expansión | C31 a C36 | R11, R12 |

Si recorriste parte de la celda, envía el cierre con *No* y anota las calles
que faltaron: la celda queda fuera del cálculo y se reemplaza con su reserva.

### Seguridad y trato

- En zonas que no conoces, vayan juntos.
- No muestres el celular más de lo necesario.
- Si alguien pregunta: «Es un estudio universitario sobre las tiendas de
  barrio; solo contamos las tiendas, no hacemos preguntas ni tomamos datos de
  personas».
- No entres a condominios ni a pasajes cerrados sin permiso: anótalo como
  recorrido incompleto.

## 3. Al terminar cada jornada

1. Con wifi, envía los registros (*Send finalized forms*).
2. En KoboToolbox, revisa que cada celda visitada tenga su cierre.
3. Anota en `plan_jornadas.csv` los minutos reales si difieren mucho de los
   estimados, para replanificar las jornadas siguientes.

## 4. Al terminar el conteo

1. En KoboToolbox: *Data* > *Downloads* > tipo **XLS**, formato de valores y
   encabezados **XML values and headers** > *Export*. Guarda el archivo como
   `data/campo/kobo/conteo_bodegas.xlsx`. Esa carpeta no se sube al
   repositorio: tiene la ubicación de bodegas que funcionan en viviendas.
2. Descarga también *Media Attachments (ZIP)* y guárdalo en `data/campo/kobo/`.
3. Revisa con las fotos los registros «dudoso» y los pares que el script marque
   en `data/campo/kobo/posibles_duplicados.csv`. Anota la decisión en
   `data/campo/kobo/revision_registros.csv`, con dos columnas: `_uuid` y
   `tipo_final` (`bodega`, `minimarket`, `abarrotes`, `cadena`, `mercado` o
   `excluir`).
4. Corre, desde la raíz del proyecto:

   ```bash
   python scripts/15_calibrar_bodegas.py --kobo data/campo/kobo/conteo_bodegas.xlsx
   bash ejecutar_todo.sh
   ```

   El primero escribe `resultados/campo/`, con `RESUMEN_CAMPO.md` y los valores
   para la tesis; el segundo regenera los datos de la aplicación con el h de
   campo.

## 5. Qué se calcula

- **h y su IC 95 %:** estimador de razón separado por estrato, ponderado por
  la población de cada estrato, con bootstrap estratificado (n − 1 celdas por
  estrato).
- **Diferencias entre zonas:** h en zonas consolidadas y de expansión, y por
  tercil de densidad.
- **Modelo de conteo:** bodegas ~ log(población) + zona (Poisson o binomial
  negativa). Si la elasticidad es 1, las bodegas crecen en proporción a la
  población y la ecuación 1 se mantiene con el h de campo.
- **Cobertura de OpenStreetMap:** parte de las bodegas reales que tienen un
  comercio de OSM a 30 m o menos.
- **Simulador:** ventas y recuperación de la inversión entre celdas con el h de
  campo frente al 120 de la versión 7.

La regla para elegir la forma de la ecuación 1 está fijada en el encabezado de
`scripts/15_calibrar_bodegas.py` desde antes del conteo.
