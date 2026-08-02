<script setup>
import ScoreControls from '@/views/sigret/ScoreControls.vue'
import { useSigret } from '@/stores/sigret'

const store = useSigret()

onMounted(() => store.cargar())

const nf = new Intl.NumberFormat('es-PE')
const soles = n => new Intl.NumberFormat('es-PE', {
  style: 'currency', currency: 'PEN', maximumFractionDigits: 0,
}).format(n)

const cuantos = ref(20)
const busqueda = ref('')

const filas = computed(() => {
  let r = store.ranking.slice(0, cuantos.value)
  if (busqueda.value) {
    const q = busqueda.value.toLowerCase()
    r = r.filter(h => h.dist.toLowerCase().includes(q) || h.h3.includes(q))
  }

  return r.map((h, i) => ({ pos: i + 1, ...h }))
})

const cabeceras = [
  { title: '#', key: 'pos', width: 52, sortable: false },
  { title: 'Distrito', key: 'dist' },
  { title: 'Pob. 500 m', key: 'pob_k1', align: 'end' },
  { title: 'Compet.', key: 'n_comp_osm_k1', align: 'end' },
  { title: 'd Mass', key: 'd_mass_2026', align: 'end' },
  { title: 'POIs', key: 'n_poi_k1', align: 'end' },
  { title: 'Perfil ML', key: 'p_potencial', align: 'end' },
  { title: 'Captura/mes', key: 'captura', align: 'end' },
  { title: 'Payback', key: 'payback', align: 'end' },
  { title: 'Score', key: 'score', align: 'end', width: 150 },
]

const maxScore = computed(() => Math.max(...filas.value.map(f => f.score), 0.001))

function exportar() {
  const cols = ['pos', 'h3', 'dist', 'lat', 'lon', 'pob_k1', 'pob_k2',
    'n_comp_osm_k1', 'd_mass_2026', 'n_poi_k1', 'dens_hab_km2',
    'p_potencial', 'dem_res_n', 'score', 'captura', 'payback']

  const cab = ['Posicion', 'H3', 'Distrito', 'Latitud', 'Longitud',
    'Poblacion 500m', 'Poblacion 800m', 'Competidores 500m',
    'Distancia Mass (m)', 'POIs flujo', 'Densidad hab/km2',
    'Perfil ML', 'Demanda residual', 'Score', 'Captura mensual S/',
    'Payback meses']

  const cuerpo = filas.value.map(f => cols.map(c => {
    const v = f[c]
    if (v === null || v === undefined)
      return ''

    return typeof v === 'number' ? v.toFixed(4).replace(/\.?0+$/, '') : v
  }).join(';'))

  const csv = `\uFEFF${[cab.join(';'), ...cuerpo].join('\n')}`
  const a = document.createElement('a')

  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  a.download = `ranking_ubicaciones_${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(a.href)
}

function color(h) {
  if (h.d_mass_2026 < 500)
    return 'error'
  if (h.d_mass_2026 < 900)
    return 'warning'

  return 'success'
}
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-end justify-space-between gap-4 mb-5">
      <div>
        <div class="eyebrow">Resultados priorizados</div>
        <h1 class="page-title">Ranking de ubicaciones</h1>
        <p class="page-sub">
          {{ nf.format(store.ranking.length) }} celdas viables ordenadas por
          score de oportunidad
        </p>
      </div>

      <VBtn color="primary" variant="tonal" prepend-icon="bx-download" @click="exportar">
        Exportar CSV
      </VBtn>
    </div>

    <VRow>
      <VCol cols="12" lg="3" order="2" order-lg="1">
        <ScoreControls :mostrar-capas="false" mostrar-finanzas />
      </VCol>

      <VCol cols="12" lg="9" order="1" order-lg="2">
        <VCard>
          <VCardText class="d-flex flex-wrap align-center gap-4 pb-2">
            <VTextField
              v-model="busqueda"
              placeholder="Buscar distrito o índice H3"
              prepend-inner-icon="bx-search"
              density="compact" variant="outlined" hide-details
              style="max-inline-size: 280px"
              clearable
            />
            <VSpacer />
            <div class="d-flex align-center gap-2">
              <span class="text-caption text-disabled">Mostrar</span>
              <VBtnToggle
                v-model="cuantos"
                density="compact" variant="outlined" color="primary"
                mandatory divided
              >
                <VBtn :value="10" size="small">10</VBtn>
                <VBtn :value="20" size="small">20</VBtn>
                <VBtn :value="50" size="small">50</VBtn>
                <VBtn :value="100" size="small">100</VBtn>
              </VBtnToggle>
            </div>
          </VCardText>

          <VDivider />

          <VDataTable
            :headers="cabeceras"
            :items="filas"
            :items-per-page="cuantos"
            item-value="h3"
            density="comfortable"
            hover
            class="tabla-ranking"
            hide-default-footer
          >
            <template #item.pos="{ item }">
              <span class="pos">{{ item.pos }}</span>
            </template>

            <template #item.dist="{ item }">
              <div class="d-flex align-center gap-2">
                <VIcon icon="bx-map-pin" size="15" :color="color(item)" />
                <span class="font-weight-medium">{{ item.dist }}</span>
              </div>
            </template>

            <template #item.pob_k1="{ item }">
              <span class="num">{{ nf.format(Math.round(item.pob_k1)) }}</span>
            </template>

            <template #item.n_comp_osm_k1="{ item }">
              <span class="num">{{ item.n_comp_osm_k1 }}</span>
            </template>

            <template #item.d_mass_2026="{ item }">
              <VChip size="x-small" :color="color(item)" variant="tonal" label>
                {{ nf.format(Math.round(item.d_mass_2026)) }} m
              </VChip>
            </template>

            <template #item.n_poi_k1="{ item }">
              <span class="num">{{ item.n_poi_k1 }}</span>
            </template>

            <template #item.p_potencial="{ item }">
              <span class="num">{{ item.p_potencial.toFixed(2) }}</span>
            </template>

            <template #item.captura="{ item }">
              <span class="num">{{ soles(item.captura) }}</span>
            </template>

            <template #item.payback="{ item }">
              <span class="num" :class="{ 'text-error': item.payback > 36 }">
                {{ item.payback ? Math.round(item.payback) : '—' }}
              </span>
            </template>

            <template #item.score="{ item }">
              <div class="d-flex align-center justify-end gap-3">
                <VProgressLinear
                  :model-value="(item.score / maxScore) * 100"
                  color="primary" height="5" rounded
                  style="inline-size: 62px"
                />
                <span class="score-num">{{ item.score.toFixed(3) }}</span>
              </div>
            </template>
          </VDataTable>
        </VCard>

        <p class="nota mt-3">
          La captura mensual y el periodo de recuperación son estimaciones de
          orden de magnitud para comparar celdas entre sí, calculadas con los
          supuestos económicos del panel lateral. No constituyen una proyección
          financiera.
        </p>
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
  font-size: 1.6rem;
  font-weight: 700;
  letter-spacing: -.02em;
}

.page-sub {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), .56);
  font-size: 13px;
}

.pos {
  color: rgba(var(--v-theme-on-surface), .42);
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.num {
  font-size: 12.5px;
  font-variant-numeric: tabular-nums;
}

.score-num {
  color: rgb(var(--v-theme-primary));
  font-size: 12.5px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  inline-size: 42px;
  text-align: end;
}

.nota {
  max-inline-size: 78ch;
  color: rgba(var(--v-theme-on-surface), .5);
  font-size: 11.5px;
  line-height: 1.55;
}

.tabla-ranking :deep(th) {
  font-size: 10.5px !important;
  font-weight: 600 !important;
  letter-spacing: .05em;
  text-transform: uppercase;
  white-space: nowrap;
}
</style>
