<script setup>
import HexMap from '@/views/sigret/HexMap.vue'
import ScoreControls from '@/views/sigret/ScoreControls.vue'
import ScoreLegend from '@/views/sigret/ScoreLegend.vue'
import { useSigret } from '@/stores/sigret'

const store = useSigret()
const nf = new Intl.NumberFormat('es-PE')

const capas = ref({ extrusion: true, mass: true, competencia: false })
const mapa = ref(null)

onMounted(() => store.cargar())

const sel = computed(() => store.seleccionado)

const soles = n => new Intl.NumberFormat('es-PE', {
  style: 'currency', currency: 'PEN', maximumFractionDigits: 0,
}).format(n)

function irA(h) {
  store.seleccionar(h.h3)
  mapa.value?.volar(h.lon, h.lat)
}

const top5 = computed(() => store.ranking.slice(0, 5))
</script>

<template>
  <div>
    <div class="d-flex flex-wrap align-end justify-space-between gap-4 mb-5">
      <div>
        <div class="eyebrow">Exploración territorial</div>
        <h1 class="page-title">Mapa de oportunidad</h1>
        <p class="page-sub">
          {{ nf.format(store.hexesVisibles.length) }} celdas en pantalla ·
          altura y color proporcionales al score
        </p>
      </div>

      <VChipGroup>
        <VChip size="small" variant="tonal" color="primary" prepend-icon="bx-grid-alt">
          H3 r9 · 0.105 km²
        </VChip>
        <VChip size="small" variant="tonal" color="info" prepend-icon="bx-store">
          {{ store.mass.length }} tiendas Mass
        </VChip>
      </VChipGroup>
    </div>

    <VRow>
      <!-- Controles -->
      <VCol cols="12" lg="3" order="2" order-lg="1">
        <ScoreControls v-model:capas="capas" />

        <VCard class="mt-4">
          <VCardText class="pa-4">
            <ScoreLegend compacta />
          </VCardText>
        </VCard>

        <VCard class="mt-4">
          <VCardItem class="pb-1">
            <VCardTitle class="text-body-2 font-weight-bold">
              Mejores 5 ahora
            </VCardTitle>
          </VCardItem>
          <VList density="compact" class="pt-0">
            <VListItem
              v-for="(h, i) in top5" :key="h.h3"
              class="px-4" @click="irA(h)"
            >
              <template #prepend>
                <div class="rank-pill">{{ i + 1 }}</div>
              </template>
              <VListItemTitle class="text-body-2 font-weight-medium">
                {{ h.dist }}
              </VListItemTitle>
              <VListItemSubtitle class="text-caption">
                {{ nf.format(Math.round(h.pob_k1)) }} hab · {{ h.n_comp_osm_k1 }} comp.
              </VListItemSubtitle>
              <template #append>
                <span class="rank-score">{{ h.score.toFixed(3) }}</span>
              </template>
            </VListItem>
          </VList>
        </VCard>
      </VCol>

      <!-- Mapa -->
      <VCol cols="12" lg="9" order="1" order-lg="2">
        <VCard class="overflow-hidden">
          <HexMap
            ref="mapa"
            height="640px"
            :extrusion="capas.extrusion"
            :mostrar-mass="capas.mass"
            :mostrar-competencia="capas.competencia"
          />
        </VCard>

        <!-- Detalle de la celda seleccionada -->
        <VExpandTransition>
          <VCard v-if="sel" class="mt-4">
            <VCardText class="pa-5">
              <div class="d-flex flex-wrap align-center justify-space-between gap-3 mb-4">
                <div>
                  <div class="eyebrow">Celda seleccionada</div>
                  <h3 class="text-h6 font-weight-bold mb-0">{{ sel.dist }}</h3>
                  <code class="text-caption text-disabled">{{ sel.h3 }}</code>
                </div>
                <div class="d-flex align-center gap-4">
                  <div class="text-end">
                    <div class="detalle-num">{{ sel.score.toFixed(3) }}</div>
                    <div class="detalle-lbl">Score</div>
                  </div>
                  <VBtn
                    icon="bx-x" variant="text" size="small"
                    @click="store.seleccionar(null)"
                  />
                </div>
              </div>

              <VRow dense>
                <VCol v-for="m in [
                  { l: 'Población 500 m', v: nf.format(Math.round(sel.pob_k1)), s: 'hab' },
                  { l: 'Competidores', v: sel.n_comp_osm_k1, s: 'en 500 m' },
                  { l: 'Mass más cercano', v: nf.format(Math.round(sel.d_mass_2026)), s: 'm' },
                  { l: 'POIs de flujo', v: sel.n_poi_k1, s: 'en 500 m' },
                  { l: 'Captura estimada', v: soles(sel.captura), s: 'al mes' },
                  { l: 'Recuperación', v: sel.payback ? Math.round(sel.payback) : '—', s: 'meses' },
                ]" :key="m.l" cols="6" md="4" lg="2">
                  <div class="metrica">
                    <div class="metrica-lbl">{{ m.l }}</div>
                    <div class="metrica-val">
                      {{ m.v }}<span>{{ m.s }}</span>
                    </div>
                  </div>
                </VCol>
              </VRow>

              <VAlert
                v-if="sel.d_mass_2026 < 500"
                type="error" variant="tonal" density="compact" class="mt-4"
              >
                Hay una tienda Mass a {{ Math.round(sel.d_mass_2026) }} m.
                Competir en precio contra un formato con marca propia y central
                de compras no es viable para un independiente.
              </VAlert>
              <VAlert
                v-else-if="sel.d_mass_2026 < 900"
                type="warning" variant="tonal" density="compact" class="mt-4"
              >
                Mass a {{ Math.round(sel.d_mass_2026) }} m. La diferenciación
                debe apoyarse en surtido fresco, horario extendido o crédito de
                barrio, no en precio.
              </VAlert>
              <VAlert
                v-else
                type="success" variant="tonal" density="compact" class="mt-4"
              >
                Sin presencia de hard discount en
                {{ Math.round(sel.d_mass_2026) }} m a la redonda.
              </VAlert>

              <div class="d-flex gap-2 mt-4">
                <VBtn
                  size="small" color="primary" variant="tonal"
                  prepend-icon="bx-calculator" to="/simulador"
                >
                  Simular escenario
                </VBtn>
                <VBtn
                  size="small" variant="text" color="secondary"
                  prepend-icon="bx-link-external"
                  :href="`https://www.openstreetmap.org/#map=17/${sel.lat}/${sel.lon}`"
                  target="_blank"
                >
                  Ver en OpenStreetMap
                </VBtn>
              </div>
            </VCardText>
          </VCard>
        </VExpandTransition>
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

.rank-score {
  color: rgb(var(--v-theme-primary));
  font-size: 12.5px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.detalle-num {
  color: rgb(var(--v-theme-primary));
  font-size: 1.7rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -.02em;
  line-height: 1;
}

.detalle-lbl {
  color: rgba(var(--v-theme-on-surface), .5);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.metrica {
  padding: 11px 13px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), .035);
  block-size: 100%;
}

.metrica-lbl {
  color: rgba(var(--v-theme-on-surface), .54);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .05em;
  text-transform: uppercase;
}

.metrica-val {
  margin-block-start: 4px;
  font-size: 1.02rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;

  span {
    margin-inline-start: 4px;
    color: rgba(var(--v-theme-on-surface), .46);
    font-size: 11px;
    font-weight: 500;
  }
}
</style>
