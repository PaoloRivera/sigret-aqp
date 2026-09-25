# Aplicación web de SIGRET-AQP

Interfaz de soporte a la decisión construida con Vue 3, Vuetify, Pinia, MapLibre GL
y h3-js, servida por Laravel. Todo el cálculo pesado ocurre fuera de línea en el
pipeline de Python: la aplicación solo lee los cuatro JSON de `public/data/` y
recalcula el score en el navegador. No usa base de datos.

## Requisitos

- PHP 8.2 o superior y Composer
- Node.js 20 o superior y pnpm 9 (`npm install -g pnpm@9`)

## Puesta en marcha

```bash
composer install
cp .env.example .env
php artisan key:generate
pnpm install
pnpm build
php artisan serve
```

La aplicación queda en http://localhost:8000. Para desarrollo con recarga en caliente,
ejecutar `pnpm dev` en otra terminal en lugar de `pnpm build`.

## Actualizar los datos

Los JSON de `public/data/` se generan desde la raíz del proyecto, después de ejecutar
`pipeline.py`:

```bash
python scripts/10_generar_json_app.py
```

## Estructura relevante

```
resources/js/
├── pages/            Resumen, mapa, ranking, simulador, validación y fuentes
├── stores/sigret.js  Carga de datos, score y modelo de Huff (estado central)
└── views/sigret/     Mapa de hexágonos, controles del modelo y componentes propios
public/data/          Datos servidos (generados por el pipeline)
```

La interfaz parte de la plantilla libre Sneat 2.1.0 de ThemeSelection (licencia MIT).
El mapa base es OpenFreeMap, con datos © colaboradores de OpenStreetMap.
