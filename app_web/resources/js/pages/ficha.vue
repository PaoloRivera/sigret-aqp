<script setup>
import { useSigret } from '@/stores/sigret'
import {
  ANTES_DE_DECIDIR,
  TAMANOS,
  avisos,
  distancia,
  enlaceMapa,
  entero,
  nivel,
  nombreDistrito,
  numeros,
  soles,
} from '@/utils/comerciante'

// Ficha imprimible de una zona: una hoja A4 con los datos, los números del
// comerciante y lo que debe verificar antes de decidir.

const store = useSigret()
const route = useRoute()

onMounted(() => store.cargar())

const num = (v, d) => {
  const x = Number(v)

  return Number.isFinite(x) && x > 0 ? x : d
}

const supuestos = computed(() => ({
  inversion: num(route.query.inv, 160000),
  superficie: num(route.query.m2, 100),
  margen: num(route.query.mg, 22),
  gastos: route.query.gf ? num(route.query.gf, null) : null,
}))

const zona = computed(() => store.rankingPanel.find(h => h.h3 === route.params.h3) ?? null)
const n = computed(() => zona.value ? numeros(zona.value, supuestos.value, store.p.hCampo) : null)
const alertas = computed(() => zona.value && n.value ? avisos(zona.value, n.value) : [])
const tamano = computed(() => TAMANOS.find(t => t.m2 === supuestos.value.superficie))

const hoy = new Date().toLocaleDateString('es-PE', { day: 'numeric', month: 'long', year: 'numeric' })
const coord = h => `${h.lat.toFixed(5)}, ${h.lon.toFixed(5)}`

function imprimir() {
  window.print()
}
</script>

<template>
  <div class="ficha-fondo">
    <div class="ficha-barra no-print">
      <VBtn
        :to="{ name: 'comerciante' }"
        variant="text" prepend-icon="bx-left-arrow-alt"
      >
        Volver
      </VBtn>
      <VBtn color="primary" prepend-icon="bx-printer" @click="imprimir">
        Imprimir o guardar en PDF
      </VBtn>
    </div>

    <div v-if="!store.ready" class="text-center py-12 no-print">
      <VProgressCircular indeterminate color="primary" />
    </div>

    <p v-else-if="!zona" class="text-center py-12">
      Esta zona no está entre las evaluadas.
      <RouterLink :to="{ name: 'comerciante' }">Volver al inicio</RouterLink>.
    </p>

    <article v-else class="ficha">
      <header class="f-cab">
        <div>
          <div class="f-marca">SIGRET-AQP · Ficha de ubicación</div>
          <h1>{{ nombreDistrito(zona.dist) }}</h1>
          <div class="f-sub">
            Puesto {{ entero(zona.puesto) }} de {{ entero(store.rankingPanel.length) }} zonas evaluadas ·
            oportunidad {{ nivel(zona).texto.toLowerCase() }}: {{ nivel(zona).detalle }}
          </div>
        </div>
        <div class="f-fecha">{{ hoy }}</div>
      </header>

      <section>
        <h2>Dónde queda</h2>
        <p>
          Coordenadas: <strong>{{ coord(zona) }}</strong>. Escríbelas en el buscador de
          Google Maps o abre este enlace:
          <a :href="enlaceMapa(zona)" target="_blank" rel="noopener">{{ enlaceMapa(zona) }}</a>
        </p>
        <p class="f-nota">La zona es un hexágono de unos 300 m de ancho con centro en ese punto.</p>
      </section>

      <section>
        <h2>La zona</h2>
        <table class="f-tabla">
          <tbody>
            <tr><td>Personas que viven a unos 500 m</td><td>{{ entero(zona.pob_k1) }}</td></tr>
            <tr><td>Bodegas y tiendas que las atienden (estimado)</td><td>{{ entero(n.bodegas) }}</td></tr>
            <tr><td>Tienda de descuento más cercana</td><td>a {{ distancia(zona.d_mass_2026) }}</td></tr>
            <tr><td>Colegios, mercados, paraderos y otros lugares con movimiento cerca</td><td>{{ entero(zona.n_poi_k1) }}</td></tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>Tus números</h2>
        <table class="f-tabla">
          <tbody>
            <tr><td>Inversión</td><td>{{ soles(supuestos.inversion) }}</td></tr>
            <tr><td>Tamaño de la tienda</td><td>{{ tamano ? `${tamano.texto} (${tamano.detalle})` : `${supuestos.superficie} m²` }}</td></tr>
            <tr><td>De cada S/ 100 vendidos, te queda tras pagar la mercadería</td><td>S/ {{ supuestos.margen }}</td></tr>
            <tr v-if="n.conGastos"><td>Gastos fijos al mes</td><td>{{ soles(supuestos.gastos) }}</td></tr>
            <tr class="f-fuerte"><td>Ventas que podrías tener al mes</td><td>{{ soles(n.ventas) }}</td></tr>
            <tr class="f-fuerte">
              <td>{{ n.conGastos ? 'Te quedaría al mes, ya pagados tus gastos fijos' : 'Te quedaría al mes para pagar alquiler, sueldos y servicios' }}</td>
              <td>{{ soles(n.conGastos ? n.neto : n.bruto) }}</td>
            </tr>
            <tr class="f-fuerte">
              <td>Tiempo para recuperar lo que inviertes {{ n.conGastos ? '(con tus gastos fijos)' : '(sin contar alquiler ni sueldos)' }}</td>
              <td>{{ n.recupera ? `${entero(n.recupera)} meses` : 'no se recupera' }}</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section>
        <h2>Atención</h2>
        <ul class="f-lista">
          <li v-for="(a, i) in alertas" :key="i">{{ a.txt }}</li>
        </ul>
      </section>

      <section>
        <h2>Antes de decidir, verifica</h2>
        <ul class="f-check">
          <li v-for="t in ANTES_DE_DECIDIR" :key="t">{{ t }}</li>
        </ul>
      </section>

      <footer class="f-pie">
        Estimación hecha con datos públicos: población del Censo 2017 actualizada al Censo
        2025, OpenStreetMap y las aperturas de una cadena de descuento entre 2024 y 2026.
        No es una garantía de ventas. Sirve para comparar zonas, no para reemplazar la
        visita al lugar. SIGRET-AQP, proyecto de tesis.
      </footer>
    </article>
  </div>
</template>

<style lang="scss" scoped>
.ficha-fondo {
  min-block-size: 100vh;
  padding-block: 16px 40px;
  padding-inline: 16px;
  background: rgb(var(--v-theme-background));
}

.ficha-barra {
  display: flex;
  justify-content: space-between;
  margin-block-end: 12px;
  margin-inline: auto;
  max-inline-size: 794px;
}

.ficha {
  padding-block: 36px;
  padding-inline: 40px;
  border-radius: 8px;
  margin-inline: auto;
  background: #fff;
  box-shadow: 0 2px 10px rgba(0, 0, 0, .12);
  color: #1d2329;
  font-size: 14px;
  line-height: 1.5;
  max-inline-size: 794px;

  h1 {
    margin-block: 2px;
    font-size: 26px;
    font-weight: 800;
  }

  h2 {
    padding-block-end: 4px;
    border-block-end: 1px solid #d5dadf;
    margin-block: 20px 8px;
    color: #0e7c86;
    font-size: 16px;
    font-weight: 700;
  }

  a { color: #0e7c86; word-break: break-all; }
}

.f-cab {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.f-marca {
  color: #0e7c86;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
}

.f-sub, .f-fecha, .f-nota {
  color: #4d5761;
  font-size: 13px;
}

.f-fecha { white-space: nowrap; }

.f-tabla {
  border-collapse: collapse;
  inline-size: 100%;

  td {
    padding-block: 6px;
    padding-inline: 0 8px;
    border-block-end: 1px solid #eceff2;
    vertical-align: top;
  }

  td:last-child {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
    text-align: end;
    white-space: nowrap;
  }

  .f-fuerte td { font-weight: 700; }
}

.f-lista {
  padding-inline-start: 18px;
  margin: 0;

  li { margin-block-end: 4px; }
}

.f-check {
  padding: 0;
  margin: 0;
  list-style: none;

  li {
    position: relative;
    padding-inline-start: 26px;
    margin-block-end: 6px;
  }

  li::before {
    position: absolute;
    border: 1.5px solid #4d5761;
    border-radius: 3px;
    block-size: 14px;
    content: "";
    inline-size: 14px;
    inset-block-start: 3px;
    inset-inline-start: 0;
  }
}

.f-pie {
  padding-block-start: 10px;
  border-block-start: 1px solid #d5dadf;
  color: #4d5761;
  font-size: 11.5px;
  margin-block-start: 22px;
}

@media print {
  .ficha-fondo {
    padding: 0;
    background: #fff;
  }

  .ficha {
    padding: 0;
    box-shadow: none;
    max-inline-size: none;
  }

  section { break-inside: avoid; }
}
</style>

<style lang="scss">
@media print {
  @page { margin: 16mm 14mm; }

  .no-print { display: none !important; }

  html, body, .v-application { background: #fff !important; }
}
</style>
