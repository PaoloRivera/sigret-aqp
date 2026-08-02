<script setup>
import { useTheme } from 'vuetify'
import HexMap from '@/views/sigret/HexMap.vue'
import { useSigret } from '@/stores/sigret'

const store = useSigret()
const theme = useTheme()

onMounted(() => store.cargar())

const nf = new Intl.NumberFormat('es-PE')
const soles = n => new Intl.NumberFormat('es-PE', {
  style: 'currency', currency: 'PEN', maximumFractionDigits: 0,
}).format(n)

const candidatos = computed(() => store.ranking.slice(0, 60))
const elegido = ref(null)

watch(candidatos, v => {
  if (!elegido.value && v.length)
    elegido.value = v[0].h3
}, { immediate: true })

const h = computed(() =>
  store.hexesCalculados.find(x => x.h3 === elegido.value) ?? null)

// ── Modelo de interacción espacial de Huff ───────────────────────────────────
// La probabilidad de elección es proporcional a la atractividad del
// establecimiento e inversamente proporcional a la fricción de la distancia.
// Superficies asumidas: bodega tradicional 45 m², hard discount 175 m².
const M2_BODEGA = 45
const M2_MASS = 175
const ALPHA = 1.0

const huff = computed(() => {
  if (!h.value)
    return null

  const { superficie, gastoPerCapita, margen, inversion } = store.p

  const aNueva = superficie ** ALPHA
  const aRival = h.value.n_comp_osm_k1 * M2_BODEGA ** ALPHA
    + h.value.mass_k1_2026 * M2_MASS ** ALPHA

  const cuota = aNueva + aRival > 0 ? aNueva / (aNueva + aRival) : 1
  const ventas = h.value.pob_k1 * gastoPerCapita * cuota
  const bruto = ventas * margen
  const payback = bruto > 0 ? inversion / bruto : null

  return { cuota, ventas, bruto, payback, aNueva, aRival }
})

// Curva de sensibilidad: cómo varía la cuota con la superficie
const curva = computed(() => {
  if (!h.value)
    return []

  const aRival = h.value.n_comp_osm_k1 * M2_BODEGA ** ALPHA
    + h.value.mass_k1_2026 * M2_MASS ** ALPHA

  const pts = []
  for (let m2 = 40; m2 <= 300; m2 += 10) {
    const cuota = m2 ** ALPHA / (m2 ** ALPHA + aRival)
    pts.push({
      x: m2,
      y: +(h.value.pob_k1 * store.p.gastoPerCapita * cuota * store.p.margen).toFixed(0),
    })
  }

  return pts
})

const c = computed(() => theme.current.value.colors)

function hexToRgb(hex) {
  const s = hex.replace('#', '')
  const n = parseInt(s.length === 3 ? s.split('').map(x => x + x).join('') : s, 16)

  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`
}

const curvaOpts = computed(() => {
  const txt = `rgba(${hexToRgb(String(c.value['on-surface']))}, 0.5)`
  const borde = `rgba(${hexToRgb(String(c.value['on-surface']))}, 0.09)`

  return {
    chart: { type: 'area', toolbar: { show: false }, parentHeightOffset: 0 },
    colors: [c.value.primary],
    stroke: { curve: 'smooth', width: 2.5 },
    fill: {
      type: 'gradient',
      gradient: { shadeIntensity: 0.7, opacityFrom: 0.32, opacityTo: 0.02, stops: [0, 100] },
    },
    dataLabels: { enabled: false },
    grid: { borderColor: borde, padding: { left: 8, right: 8 } },
    xaxis: {
      type: 'numeric',
      title: { text: 'Superficie de venta (m²)', style: { color: txt, fontSize: '11px', fontWeight: 500 } },
      labels: { style: { colors: txt, fontSize: '11px' } },
      axisBorder: { show: false }, axisTicks: { show: false }, tickAmount: 6,
    },
    yaxis: {
      labels: {
        style: { colors: txt, fontSize: '11px' },
        formatter: v => `S/ ${Math.round(v / 1000)}k`,
      },
    },
    annotations: {
      xaxis: [{
        x: store.p.superficie,
        borderColor: c.value.warning,
        strokeDashArray: 4,
        label: {
          text: `${store.p.superficie} m²`,
          style: { background: c.value.warning, color: '#fff', fontSize: '10.5px' },
        },
      }],
    },
    tooltip: {
      theme: theme.global.name.value,
      y: { formatter: v => soles(v) },
      x: { formatter: v => `${v} m²` },
    },
  }
})

const curvaSerie = computed(() => [{ name: 'Margen bruto mensual', data: curva.value }])

const alertas = computed(() => {
  if (!h.value || !huff.value)
    return []

  const a = []

  if (h.value.d_mass_2026 < 500) {
    a.push({
      t: 'error', txt: `Hay una tienda Mass a ${Math.round(h.value.d_mass_2026)} m. `
        + 'Competir en precio contra un formato con marca propia y central de '
        + 'compras no es viable para un independiente.',
    })
  }
  else if (h.value.d_mass_2026 < 900) {
    a.push({
      t: 'warning', txt: `Mass a ${Math.round(h.value.d_mass_2026)} m. La `
        + 'diferenciación debe apoyarse en surtido fresco, horario extendido o '
        + 'crédito de barrio.',
    })
  }
  else {
    a.push({
      t: 'success', txt: `Sin hard discount en ${Math.round(h.value.d_mass_2026)} m `
        + 'a la redonda.',
    })
  }

  if (h.value.n_comp_osm_k1 >= 3) {
    a.push({
      t: 'warning',
      txt: `${h.value.n_comp_osm_k1} competidores registrados en el área de captación.`,
    })
  }
  if (h.value.pob_k1 < 2500) {
    a.push({
      t: 'warning',
      txt: 'Población baja para el área de captación. Verificar en campo si hay '
        + 'flujo de paso que compense.',
    })
  }
  if (huff.value.payback && huff.value.payback > 36) {
    a.push({
      t: 'error',
      txt: 'El periodo de recuperación supera 36 meses. Revisar el nivel de '
        + 'inversión o el formato.',
    })
  }

  return a
})
</script>

<template>
  <div>
    <div class="mb-5">
      <div class="eyebrow">Evaluación de escenarios</div>
      <h1 class="page-title">Simulador de apertura</h1>
      <p class="page-sub">
        Modelo de interacción espacial de Huff sobre la oferta instalada en el
        área de captación
      </p>
    </div>

    <VRow>
      <!-- Configuración -->
      <VCol cols="12" lg="4">
        <VCard>
          <VCardItem class="pb-2">
            <VCardTitle class="text-body-1 font-weight-bold">
              Escenario
            </VCardTitle>
          </VCardItem>

          <VCardText>
            <VSelect
              v-model="elegido"
              :items="candidatos"
              item-title="dist" item-value="h3"
              label="Ubicación candidata"
              density="comfortable" variant="outlined" hide-details
              class="mb-5"
            >
              <template #item="{ props: p, item, index }">
                <VListItem v-bind="p" :title="undefined">
                  <template #prepend>
                    <div class="rank-pill">{{ index + 1 }}</div>
                  </template>
                  <VListItemTitle class="text-body-2">
                    {{ item.raw.dist }}
                  </VListItemTitle>
                  <VListItemSubtitle class="text-caption">
                    score {{ item.raw.score.toFixed(3) }} ·
                    {{ nf.format(Math.round(item.raw.pob_k1)) }} hab
                  </VListItemSubtitle>
                </VListItem>
              </template>
              <template #selection="{ item }">
                <span class="text-body-2">
                  {{ item.raw.dist }}
                  <span class="text-disabled">
                    · {{ item.raw.score.toFixed(3) }}
                  </span>
                </span>
              </template>
            </VSelect>

            <div class="ctrl mb-4">
              <div class="ctrl-head">
                <span class="ctrl-label">Superficie de venta</span>
                <span class="ctrl-val">{{ store.p.superficie }} m²</span>
              </div>
              <VSlider
                v-model="store.p.superficie"
                :min="40" :max="300" :step="10"
                color="primary" density="compact" hide-details
                thumb-size="14" track-size="4"
              />
            </div>

            <VRow dense>
              <VCol cols="6">
                <VTextField
                  v-model.number="store.p.inversion"
                  label="Inversión" prefix="S/" type="number"
                  density="compact" variant="outlined" hide-details
                />
              </VCol>
              <VCol cols="6">
                <VTextField
                  v-model.number="store.p.gastoPerCapita"
                  label="Gasto/persona" prefix="S/" type="number"
                  density="compact" variant="outlined" hide-details
                />
              </VCol>
            </VRow>

            <div class="ctrl mt-4">
              <div class="ctrl-head">
                <span class="ctrl-label">Margen bruto</span>
                <span class="ctrl-val">{{ (store.p.margen * 100).toFixed(0) }} %</span>
              </div>
              <VSlider
                v-model="store.p.margen"
                :min="0.10" :max="0.40" :step="0.01"
                color="success" density="compact" hide-details
                thumb-size="14" track-size="4"
              />
            </div>
          </VCardText>
        </VCard>

        <!-- Alertas -->
        <VCard v-if="alertas.length" class="mt-4">
          <VCardItem class="pb-1">
            <VCardTitle class="text-body-2 font-weight-bold">
              Diagnóstico
            </VCardTitle>
          </VCardItem>
          <VCardText class="pt-2">
            <VAlert
              v-for="(a, i) in alertas" :key="i"
              :type="a.t" variant="tonal" density="compact"
              class="mb-2 text-body-2"
            >
              {{ a.txt }}
            </VAlert>
          </VCardText>
        </VCard>
      </VCol>

      <!-- Resultados -->
      <VCol cols="12" lg="8">
        <VRow v-if="huff && h">
          <VCol cols="6" md="3">
            <VCard class="res-card res-card--acc h-100">
              <VCardText class="pa-4">
                <div class="res-lbl">Cuota de mercado</div>
                <div class="res-val">{{ (huff.cuota * 100).toFixed(1) }}<span>%</span></div>
              </VCardText>
            </VCard>
          </VCol>
          <VCol cols="6" md="3">
            <VCard class="res-card h-100">
              <VCardText class="pa-4">
                <div class="res-lbl">Ventas estimadas</div>
                <div class="res-val res-val--sm">{{ soles(huff.ventas) }}</div>
                <div class="res-sub">al mes</div>
              </VCardText>
            </VCard>
          </VCol>
          <VCol cols="6" md="3">
            <VCard class="res-card h-100">
              <VCardText class="pa-4">
                <div class="res-lbl">Margen bruto</div>
                <div class="res-val res-val--sm">{{ soles(huff.bruto) }}</div>
                <div class="res-sub">al mes</div>
              </VCardText>
            </VCard>
          </VCol>
          <VCol cols="6" md="3">
            <VCard class="res-card h-100">
              <VCardText class="pa-4">
                <div class="res-lbl">Recuperación</div>
                <div
                  class="res-val"
                  :class="huff.payback > 36 ? 'text-error' : ''"
                >
                  {{ huff.payback ? Math.round(huff.payback) : '—' }}<span>meses</span>
                </div>
              </VCardText>
            </VCard>
          </VCol>

          <!-- Curva de sensibilidad -->
          <VCol cols="12" md="7">
            <VCard class="h-100">
              <VCardItem class="pb-0">
                <VCardTitle class="text-body-1 font-weight-bold">
                  Sensibilidad a la superficie
                </VCardTitle>
                <VCardSubtitle class="text-caption">
                  Margen bruto mensual proyectado según metros cuadrados de sala
                </VCardSubtitle>
              </VCardItem>
              <VCardText>
                <VueApexCharts
                  type="area" :height="248"
                  :options="curvaOpts" :series="curvaSerie"
                />
              </VCardText>
            </VCard>
          </VCol>

          <!-- Contexto -->
          <VCol cols="12" md="5">
            <VCard class="h-100">
              <VCardItem class="pb-1">
                <VCardTitle class="text-body-1 font-weight-bold">
                  Contexto de la celda
                </VCardTitle>
              </VCardItem>
              <VCardText>
                <VTable density="compact" class="tabla-ctx">
                  <tbody>
                    <tr v-for="r in [
                      ['Distrito', h.dist],
                      ['Población a 500 m', `${nf.format(Math.round(h.pob_k1))} hab`],
                      ['Población a 800 m', `${nf.format(Math.round(h.pob_k2))} hab`],
                      ['Competidores', h.n_comp_osm_k1],
                      ['Tiendas Mass a 500 m', h.mass_k1_2026],
                      ['Mass más cercano', `${nf.format(Math.round(h.d_mass_2026))} m`],
                      ['POIs generadores', h.n_poi_k1],
                      ['Colegios a 500 m', h.n_colegio_k1],
                      ['Densidad de intersecciones', `${Math.round(h.dens_intersec_km2)} /km²`],
                      ['Perfil ML', h.p_potencial.toFixed(3)],
                      ['Score final', h.score.toFixed(3)],
                    ]" :key="r[0]">
                      <td class="ctx-k">{{ r[0] }}</td>
                      <td class="ctx-v">{{ r[1] }}</td>
                    </tr>
                  </tbody>
                </VTable>
              </VCardText>
            </VCard>
          </VCol>

          <!-- Mapa de detalle -->
          <VCol cols="12">
            <VCard class="overflow-hidden">
              <HexMap
                height="340px"
                :extrusion="false"
                mostrar-mass
                mostrar-competencia
                :centrar-en="{ lat: h.lat, lon: h.lon }"
                :interactivo="false"
              />
            </VCard>
          </VCol>
        </VRow>

        <VCard v-else>
          <VCardText class="text-center py-12 text-disabled">
            Selecciona una ubicación candidata para simular el escenario.
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <VCard variant="tonal" color="secondary" class="mt-5">
      <VCardText class="text-body-2">
        <strong>Sobre el modelo.</strong> La cuota de mercado se estima con un
        modelo de Huff donde la atractividad es proporcional a la superficie de
        venta. Se asume 45 m² para la bodega tradicional y 175 m² para el
        formato de descuento. El exponente de atractividad se fija en 1.0; su
        calibración contra la red existente, así como el uso de tiempos de
        caminata en lugar de vecindades hexagonales, están pendientes y se
        declaran como limitación.
      </VCardText>
    </VCard>
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
  font-size: 1.6rem;
  font-weight: 700;
  letter-spacing: -.02em;
}

.page-sub {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), .56);
  font-size: 13px;
}

.ctrl-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  margin-block-end: 2px;
}

.ctrl-label {
  color: rgba(var(--v-theme-on-surface), .78);
  font-size: 12.5px;
  font-weight: 500;
}

.ctrl-val {
  color: rgb(var(--v-theme-primary));
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.rank-pill {
  display: grid;
  border-radius: 6px;
  margin-inline-end: 11px;
  background: rgba(var(--v-theme-primary), .1);
  block-size: 24px;
  color: rgb(var(--v-theme-primary));
  font-size: 11.5px;
  font-weight: 700;
  inline-size: 24px;
  place-items: center;
}

.res-card--acc {
  border-inline-start: 3px solid rgb(var(--v-theme-primary));
}

.res-lbl {
  color: rgba(var(--v-theme-on-surface), .56);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .07em;
  text-transform: uppercase;
}

.res-val {
  margin-block-start: 6px;
  font-size: 1.62rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -.022em;
  line-height: 1.1;

  span {
    margin-inline-start: 4px;
    color: rgba(var(--v-theme-on-surface), .46);
    font-size: .78rem;
    font-weight: 500;
  }
}

.res-val--sm { font-size: 1.24rem; }

.res-sub {
  margin-block-start: 2px;
  color: rgba(var(--v-theme-on-surface), .46);
  font-size: 11px;
}

.tabla-ctx {
  .ctx-k {
    padding-inline-start: 0 !important;
    color: rgba(var(--v-theme-on-surface), .58);
    font-size: 12px;
  }

  .ctx-v {
    padding-inline-end: 0 !important;
    font-size: 12.5px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    text-align: end;
  }
}
</style>
