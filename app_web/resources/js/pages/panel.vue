<script setup>
import { useTheme } from 'vuetify'
import KpiTile from '@/views/sigret/KpiTile.vue'
import ScoreLegend from '@/views/sigret/ScoreLegend.vue'
import { dataViz, scoreScale } from '@/plugins/vuetify/theme'
import { useSigret } from '@/stores/sigret'

const store = useSigret()
const theme = useTheme()

onMounted(() => store.cargar())

const nf = new Intl.NumberFormat('es-PE')

const kpis = computed(() => store.kpis)

const c = computed(() => theme.current.value.colors)
const txt = computed(() => `rgba(${hexToRgb(String(c.value['on-surface']))}, 0.72)`)
const txtSuave = computed(() => `rgba(${hexToRgb(String(c.value['on-surface']))}, 0.48)`)
const borde = computed(() => `rgba(${hexToRgb(String(c.value['on-surface']))}, 0.09)`)

function hexToRgb(hex) {
  const h = hex.replace('#', '')
  const n = parseInt(h.length === 3 ? h.split('').map(x => x + x).join('') : h, 16)

  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`
}

// ── Top-50 por distrito ──────────────────────────────────────────────────────
const distSerie = computed(() => [{
  name: 'Ubicaciones en el Top-50',
  data: store.topPorDistrito.map(d => d.n),
}])

const distOpts = computed(() => ({
  chart: { type: 'bar', toolbar: { show: false }, parentHeightOffset: 0 },
  plotOptions: {
    bar: { horizontal: true, borderRadius: 4, barHeight: '62%', distributed: true },
  },
  colors: store.topPorDistrito.map((_, i) =>
    scoreScale[Math.max(0, scoreScale.length - 1 - Math.floor(i * 0.7))]),
  dataLabels: {
    enabled: true,
    style: { fontSize: '11px', fontWeight: 600, colors: [txt.value] },
    offsetX: 20,
  },
  legend: { show: false },
  grid: { borderColor: borde.value, xaxis: { lines: { show: true } }, padding: { left: 0 } },
  xaxis: {
    categories: store.topPorDistrito.map(d => d.distrito),
    axisBorder: { show: false }, axisTicks: { show: false },
    labels: { style: { colors: txtSuave.value, fontSize: '11px' } },
  },
  yaxis: { labels: { style: { colors: txt.value, fontSize: '11.5px' } } },
  tooltip: { theme: theme.global.name.value },
}))

// ── Población vs saturación ──────────────────────────────────────────────────
const dispersion = computed(() => {
  const porDist = {}

  store.hexesCalculados.forEach(h => {
    if (!porDist[h.dist])
      porDist[h.dist] = { pob: 0, mass: 0 }
    porDist[h.dist].pob += h.pob_2017
    porDist[h.dist].mass += h.mass_k1_2026 > 0 ? 1 : 0
  })

  return [{
    name: 'Distritos',
    data: Object.entries(porDist).map(([d, v]) => ({
      x: Math.round(v.pob),
      y: v.mass,
      nombre: d,
    })),
  }]
})

const dispOpts = computed(() => ({
  chart: { type: 'scatter', toolbar: { show: false }, zoom: { enabled: false } },
  colors: [c.value.primary],
  markers: { size: 8, strokeWidth: 0, fillOpacity: 0.75 },
  grid: { borderColor: borde.value },
  xaxis: {
    title: { text: 'Población del distrito', style: { color: txtSuave.value, fontSize: '11px', fontWeight: 500 } },
    labels: {
      style: { colors: txtSuave.value, fontSize: '11px' },
      formatter: v => `${Math.round(v / 1000)}k`,
    },
    axisBorder: { show: false }, axisTicks: { show: false },
    tickAmount: 5,
  },
  yaxis: {
    title: { text: 'Celdas con presencia Mass', style: { color: txtSuave.value, fontSize: '11px', fontWeight: 500 } },
    labels: { style: { colors: txtSuave.value, fontSize: '11px' } },
  },
  tooltip: {
    theme: theme.global.name.value,
    custom: ({ seriesIndex, dataPointIndex, w }) => {
      const p = w.config.series[seriesIndex].data[dataPointIndex]

      return `<div style="padding:8px 11px">
        <strong>${p.nombre}</strong><br>
        ${nf.format(p.x)} hab · ${p.y} celdas con Mass</div>`
    },
  },
}))

// ── Aperturas por año ────────────────────────────────────────────────────────
const apert = computed(() => {
  const a = store.meta?.aperturas ?? {}

  return [{ name: 'Aperturas observadas', data: Object.values(a) }]
})

const apertOpts = computed(() => ({
  chart: { type: 'bar', toolbar: { show: false }, sparkline: { enabled: false } },
  plotOptions: { bar: { borderRadius: 5, columnWidth: '44%' } },
  colors: [c.value.primary],
  dataLabels: {
    enabled: true,
    style: { fontSize: '11px', fontWeight: 700, colors: [txt.value] },
    offsetY: -18,
  },
  grid: { borderColor: borde.value, padding: { top: -6 } },
  xaxis: {
    categories: Object.keys(store.meta?.aperturas ?? {}),
    axisBorder: { show: false }, axisTicks: { show: false },
    labels: { style: { colors: txtSuave.value, fontSize: '11.5px' } },
  },
  yaxis: { show: false },
  tooltip: { theme: theme.global.name.value },
}))
</script>

<template>
  <div>
    <!-- Encabezado -->
    <div class="d-flex flex-wrap align-end justify-space-between gap-4 mb-6">
      <div>
        <div class="eyebrow">Sistema de soporte a la decisión</div>
        <h1 class="page-title">
          Localización óptima de minimarkets
        </h1>
        <p class="page-sub">
          Arequipa Metropolitana · malla H3 resolución 9 · Censo INEI 2017 ·
          OpenStreetMap · SUNAT
        </p>
      </div>

      <div class="d-flex gap-2">
        <VBtn to="/mapa" color="primary" prepend-icon="bx-map-alt">
          Abrir el mapa
        </VBtn>
        <VBtn to="/ranking" variant="tonal" color="primary" prepend-icon="bx-list-ol">
          Ver ranking
        </VBtn>
      </div>
    </div>

    <VProgressLinear
      v-if="store.loading"
      indeterminate color="primary" class="mb-4" rounded
    />

    <VAlert
      v-if="store.error"
      type="error" variant="tonal" class="mb-4"
    >
      {{ store.error }}
    </VAlert>

    <!-- Indicadores -->
    <VRow class="mb-1">
      <VCol cols="6" md="4" lg="2">
        <KpiTile
          label="Celdas analizadas" :value="nf.format(kpis.hexagonos)"
          icon="bx-grid-alt" hint="Hexágonos de 0.105 km²"
        />
      </VCol>
      <VCol cols="6" md="4" lg="2">
        <KpiTile
          label="Viables" :value="nf.format(kpis.viables)"
          icon="bx-target-lock" color="success"
          hint="Cumplen umbral y sin Mass"
        />
      </VCol>
      <VCol cols="6" md="4" lg="2">
        <KpiTile
          label="Población" :value="(kpis.poblacion / 1e6).toFixed(2)" suffix="M"
          icon="bx-group" color="info" hint="Censo 2017 a manzana"
        />
      </VCol>
      <VCol cols="6" md="4" lg="2">
        <KpiTile
          label="Competencia" :value="nf.format(kpis.competencia)"
          icon="bx-store" color="warning" hint="Retail moderno georreferenciado"
        />
      </VCol>
      <VCol cols="6" md="4" lg="2">
        <KpiTile
          label="ROC-AUC" :value="kpis.rocAuc.toFixed(3)"
          icon="bx-check-shield" color="success"
          hint="Validación cruzada espacial"
        />
      </VCol>
      <VCol cols="6" md="4" lg="2">
        <KpiTile
          label="PR-AUC" :value="kpis.prAuc.toFixed(3)"
          icon="bx-line-chart" color="primary"
          hint="7.5× sobre la tasa base"
        />
      </VCol>
    </VRow>

    <VRow>
      <!-- Hallazgo principal -->
      <VCol cols="12" lg="8">
        <VCard class="hallazgo h-100">
          <VCardText class="pa-6">
            <div class="eyebrow mb-2">Hallazgo principal</div>
            <h2 class="hallazgo-title mb-3">
              La oportunidad forma un anillo alrededor del centro
            </h2>
            <p class="hallazgo-body mb-4">
              El retail moderno se concentra en el núcleo urbano y en los
              corredores viales principales. Al penalizar la cercanía de un
              hard discount —contra el que un independiente no puede competir en
              precio— la prioridad se desplaza hacia la periferia densa:
              <strong>Jacobo Hunter</strong>, <strong>Socabaya</strong>,
              <strong>Cerro Colorado</strong> y <strong>Miraflores</strong>
              concentran 34 de las 50 mejores ubicaciones.
            </p>

            <div class="d-flex flex-wrap gap-6">
              <div class="stat-inline">
                <span class="stat-num">5</span>
                <span class="stat-lbl">de 39 aperturas reales<br>acertadas en el Top-20</span>
              </div>
              <div class="stat-inline">
                <span class="stat-num">4.1×</span>
                <span class="stat-lbl">Lift en el decil<br>superior del ranking</span>
              </div>
              <div class="stat-inline">
                <span class="stat-num">S/ 0</span>
                <span class="stat-lbl">en licencias, datos<br>y trabajo de campo</span>
              </div>
            </div>

            <VDivider class="my-5" />
            <ScoreLegend />
          </VCardText>
        </VCard>
      </VCol>

      <!-- Aperturas -->
      <VCol cols="12" lg="4">
        <VCard class="h-100">
          <VCardItem>
            <VCardTitle class="text-body-1 font-weight-bold">
              Expansión observada
            </VCardTitle>
            <VCardSubtitle class="text-caption">
              Tiendas nuevas por año en Arequipa
            </VCardSubtitle>
          </VCardItem>
          <VCardText>
            <VueApexCharts
              type="bar" :height="188"
              :options="apertOpts" :series="apert"
            />
            <p class="nota mt-2">
              Serie reconstruida desde snapshots del Internet Archive. Es la
              fuente de la variable objetivo y del backtesting temporal.
            </p>
          </VCardText>
        </VCard>
      </VCol>

      <!-- Distribución territorial -->
      <VCol cols="12" lg="7">
        <VCard>
          <VCardItem>
            <VCardTitle class="text-body-1 font-weight-bold">
              Dónde están las oportunidades
            </VCardTitle>
            <VCardSubtitle class="text-caption">
              Distribución del Top-50 por distrito
            </VCardSubtitle>
          </VCardItem>
          <VCardText>
            <VueApexCharts
              v-if="store.ready"
              type="bar" :height="360"
              :options="distOpts" :series="distSerie"
            />
          </VCardText>
        </VCard>
      </VCol>

      <!-- Saturación -->
      <VCol cols="12" lg="5">
        <VCard class="h-100">
          <VCardItem>
            <VCardTitle class="text-body-1 font-weight-bold">
              Población frente a saturación
            </VCardTitle>
            <VCardSubtitle class="text-caption">
              Distritos poblados con poca presencia de cadena son el objetivo
            </VCardSubtitle>
          </VCardItem>
          <VCardText>
            <VueApexCharts
              v-if="store.ready"
              type="scatter" :height="300"
              :options="dispOpts" :series="dispersion"
            />
            <p class="nota">
              Los distritos en el cuadrante inferior derecho concentran
              demanda no atendida: mucha población, poca cadena instalada.
            </p>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>
  </div>
</template>

<style lang="scss" scoped>
.eyebrow {
  color: rgb(var(--v-theme-primary));
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .1em;
  text-transform: uppercase;
}

.page-title {
  margin-block: 4px 2px;
  font-size: 1.72rem;
  font-weight: 700;
  letter-spacing: -.022em;
  line-height: 1.18;
}

.page-sub {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), .56);
  font-size: 13px;
}

.hallazgo {
  border-inline-start: 3px solid rgb(var(--v-theme-primary));
}

.hallazgo-title {
  font-size: 1.32rem;
  font-weight: 700;
  letter-spacing: -.015em;
  line-height: 1.3;
}

.hallazgo-body {
  max-inline-size: 62ch;
  color: rgba(var(--v-theme-on-surface), .74);
  font-size: 13.8px;
  line-height: 1.68;
}

.stat-inline {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.stat-num {
  color: rgb(var(--v-theme-primary));
  font-size: 1.9rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -.025em;
  line-height: 1;
}

.stat-lbl {
  color: rgba(var(--v-theme-on-surface), .58);
  font-size: 11.5px;
  line-height: 1.4;
}

.nota {
  margin-block: 6px 0;
  color: rgba(var(--v-theme-on-surface), .5);
  font-size: 11.5px;
  line-height: 1.5;
}
</style>
