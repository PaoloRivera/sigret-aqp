<script setup>
import { cellToBoundary } from 'h3-js'
import {
  AttributionControl,
  Map as MlMap,
  NavigationControl,
  Popup,
  ScaleControl,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import { scoreScale } from '@/plugins/vuetify/theme'
import { useSigret } from '@/stores/sigret'

// ─────────────────────────────────────────────────────────────────────────────
// Mapa de oportunidad
//
// Basemap oscuro deliberado: la rampa Inferno sobre fondo claro pierde
// contraste en el extremo inferior. Sobre fondo oscuro los hexágonos se leen
// como una superficie luminosa y el mapa deja de ser decoración para
// convertirse en el instrumento principal de lectura.
// ─────────────────────────────────────────────────────────────────────────────

const props = defineProps({
  height: { type: String, default: '620px' },
  extrusion: { type: Boolean, default: true },
  mostrarMass: { type: Boolean, default: true },
  mostrarCompetencia: { type: Boolean, default: false },
  centrarEn: { type: Object, default: null },
  interactivo: { type: Boolean, default: true },
})

const store = useSigret()
const contenedor = ref(null)
let map = null
let popup = null

// OpenFreeMap: teselas vectoriales de OpenStreetMap sin clave de API, sin
// registro y sin límite de vistas. La atribución la aporta el propio estilo.
const ESTILO_BASE = 'https://tiles.openfreemap.org/styles/dark'

// Construye el GeoJSON de hexágonos con el score ya normalizado
function construirGeoJSON() {
  const hs = store.hexesVisibles
  if (!hs.length)
    return { type: 'FeatureCollection', features: [] }

  const max = Math.max(...hs.map(h => h.score)) || 1

  return {
    type: 'FeatureCollection',
    features: hs.map(h => ({
      type: 'Feature',
      geometry: {
        type: 'Polygon',
        coordinates: [cellToBoundary(h.h3, true)],
      },
      properties: {
        h3: h.h3,
        s: h.score / max,
        score: +h.score.toFixed(3),
        dist: h.dist,
        pob: Math.round(h.pob_k1),
        comp: h.n_comp_osm_k1,
        dmass: Math.round(h.d_mass_2026),
        poi: h.n_poi_k1,
        captura: Math.round(h.captura),
      },
    })),
  }
}

function puntos(lista, keyLat = 'lat', keyLon = 'lon') {
  return {
    type: 'FeatureCollection',
    features: lista.map(p => ({
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [p[keyLon], p[keyLat]] },
      properties: { ...p },
    })),
  }
}

// Interpolación de la rampa Inferno según score normalizado
const expresionColor = [
  'interpolate', ['linear'], ['get', 's'],
  0.00, scoreScale[0],
  0.20, scoreScale[1],
  0.40, scoreScale[2],
  0.58, scoreScale[3],
  0.74, scoreScale[4],
  0.88, scoreScale[5],
  1.00, scoreScale[6],
]

function pintarCapas() {
  if (!map || !map.isStyleLoaded())
    return

  const gj = construirGeoJSON()

  if (map.getSource('hex')) {
    map.getSource('hex').setData(gj)
  }
  else {
    map.addSource('hex', { type: 'geojson', data: gj })

    map.addLayer({
      id: 'hex-fill',
      type: 'fill-extrusion',
      source: 'hex',
      paint: {
        'fill-extrusion-color': expresionColor,
        'fill-extrusion-height': props.extrusion
          ? ['*', ['get', 's'], 900]
          : 0,
        'fill-extrusion-base': 0,
        'fill-extrusion-opacity': 0.86,
        'fill-extrusion-vertical-gradient': true,
      },
    })

    map.addLayer({
      id: 'hex-borde',
      type: 'line',
      source: 'hex',
      paint: {
        'line-color': '#F7C948',
        'line-width': 0,
        'line-opacity': 0.9,
      },
    })
  }

  // Competencia moderna
  if (map.getSource('mass'))
    map.getSource('mass').setData(puntos(store.mass))
  else
    map.addSource('mass', { type: 'geojson', data: puntos(store.mass) })

  if (!map.getLayer('mass-pt')) {
    map.addLayer({
      id: 'mass-pt',
      type: 'circle',
      source: 'mass',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 3, 15, 7],
        'circle-color': '#5FD4FF',
        'circle-stroke-width': 1.2,
        'circle-stroke-color': '#0A2A3A',
        'circle-opacity': 0.95,
      },
    })
  }

  if (map.getSource('comp'))
    map.getSource('comp').setData(puntos(store.competencia))
  else
    map.addSource('comp', { type: 'geojson', data: puntos(store.competencia) })

  if (!map.getLayer('comp-pt')) {
    map.addLayer({
      id: 'comp-pt',
      type: 'circle',
      source: 'comp',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 10, 2, 15, 5],
        'circle-color': '#9FB3BF',
        'circle-stroke-width': 0.8,
        'circle-stroke-color': '#1B2A32',
        'circle-opacity': 0.8,
      },
    })
  }

  actualizarVisibilidad()
}

function actualizarVisibilidad() {
  if (!map || !map.getLayer('mass-pt'))
    return

  map.setLayoutProperty('mass-pt', 'visibility', props.mostrarMass ? 'visible' : 'none')
  map.setLayoutProperty('comp-pt', 'visibility', props.mostrarCompetencia ? 'visible' : 'none')
  map.setPaintProperty(
    'hex-fill',
    'fill-extrusion-height',
    props.extrusion ? ['*', ['get', 's'], 900] : 0,
  )
}

function moneda(n) {
  return new Intl.NumberFormat('es-PE', {
    style: 'currency', currency: 'PEN', maximumFractionDigits: 0,
  }).format(n)
}

function montarInteraccion() {
  if (!props.interactivo)
    return

  popup = new Popup({
    closeButton: false,
    closeOnClick: false,
    className: 'sigret-popup',
    offset: 12,
  })

  map.on('mousemove', 'hex-fill', e => {
    map.getCanvas().style.cursor = 'pointer'

    const p = e.features[0].properties

    popup.setLngLat(e.lngLat).setHTML(`
      <div class="pop">
        <div class="pop-dist">${p.dist}</div>
        <div class="pop-score">${Number(p.score).toFixed(3)}<span>score</span></div>
        <dl>
          <dt>Población 500 m</dt><dd>${Number(p.pob).toLocaleString('es-PE')}</dd>
          <dt>Competidores</dt><dd>${p.comp}</dd>
          <dt>Mass más cercano</dt><dd>${Number(p.dmass).toLocaleString('es-PE')} m</dd>
          <dt>POIs de flujo</dt><dd>${p.poi}</dd>
          <dt>Captura estimada</dt><dd>${moneda(p.captura)}</dd>
        </dl>
      </div>`).addTo(map)
  })

  map.on('mouseleave', 'hex-fill', () => {
    map.getCanvas().style.cursor = ''
    popup?.remove()
  })

  map.on('click', 'hex-fill', e => {
    store.seleccionar(e.features[0].properties.h3)
  })
}

onMounted(async () => {
  if (!store.ready)
    await store.cargar()

  map = new MlMap({
    container: contenedor.value,
    style: ESTILO_BASE,
    center: props.centrarEn
      ? [props.centrarEn.lon, props.centrarEn.lat]
      : [-71.545, -16.400],
    zoom: props.centrarEn ? 14.4 : 11.2,
    pitch: props.extrusion ? 47 : 0,
    bearing: -12,
    attributionControl: false,
  })

  map.addControl(new NavigationControl({ showCompass: true }), 'top-right')
  map.addControl(new AttributionControl({ compact: true }), 'bottom-right')
  map.addControl(new ScaleControl({ maxWidth: 110, unit: 'metric' }), 'bottom-left')

  map.on('load', () => {
    pintarCapas()
    montarInteraccion()
  })
})

onBeforeUnmount(() => {
  popup?.remove()
  map?.remove()
  map = null
})

watch(() => store.hexesVisibles, () => pintarCapas(), { deep: false })
watch(() => [props.extrusion, props.mostrarMass, props.mostrarCompetencia], () => {
  actualizarVisibilidad()
  if (map)
    map.easeTo({ pitch: props.extrusion ? 47 : 0, duration: 500 })
})
watch(() => props.centrarEn, v => {
  if (v && map)
    map.flyTo({ center: [v.lon, v.lat], zoom: 14.6, duration: 900 })
})

defineExpose({
  volar(lon, lat, zoom = 14.6) {
    map?.flyTo({ center: [lon, lat], zoom, duration: 900 })
  },
})
</script>

<template>
  <div
    ref="contenedor"
    class="sigret-map"
    :style="{ blockSize: height }"
  />
</template>

<style lang="scss">
.sigret-map {
  position: relative;
  border-radius: 10px;
  background: #0d1418;
  inline-size: 100%;
  overflow: hidden;

  .maplibregl-ctrl-group {
    border: 1px solid rgba(255, 255, 255, 12%);
    background: rgba(20, 30, 36, 92%);

    button {
      + button { border-block-start: 1px solid rgba(255, 255, 255, 10%); }

      .maplibregl-ctrl-icon { filter: invert(1) brightness(1.6); }
    }
  }

  .maplibregl-ctrl-attrib,
  .maplibregl-ctrl-scale {
    border-color: rgba(255, 255, 255, 20%);
    background: rgba(20, 30, 36, 78%);
    color: rgba(255, 255, 255, 62%);

    a { color: rgba(255, 255, 255, 78%); }
  }
}

.sigret-popup {
  .maplibregl-popup-content {
    padding: 0;
    border: 1px solid rgba(255, 255, 255, 12%);
    border-radius: 10px;
    background: rgba(16, 25, 30, 96%);
    box-shadow: 0 12px 32px rgb(0 0 0 / 45%);
    color: #e6eef2;
  }

  .maplibregl-popup-tip { display: none; }

  .pop {
    min-inline-size: 232px;
    padding: 14px 16px;
    font-family: "Public Sans", sans-serif;
  }

  .pop-dist {
    color: #7fd3dd;
    font-size: 10.5px;
    font-weight: 600;
    letter-spacing: 0.09em;
    text-transform: uppercase;
  }

  .pop-score {
    display: flex;
    align-items: baseline;
    gap: 7px;
    margin-block: 3px 11px;
    color: #f7c948;
    font-size: 27px;
    font-weight: 700;
    line-height: 1;

    span {
      color: rgba(255, 255, 255, 42%);
      font-size: 10.5px;
      font-weight: 500;
      letter-spacing: 0.07em;
      text-transform: uppercase;
    }
  }

  dl {
    display: grid;
    margin: 0;
    gap: 5px 12px;
    grid-template-columns: 1fr auto;
  }

  dt {
    color: rgba(255, 255, 255, 52%);
    font-size: 11.5px;
  }

  dd {
    margin: 0;
    font-size: 11.5px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    text-align: end;
  }
}
</style>
