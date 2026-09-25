<script setup>
import { useTheme } from 'vuetify'
import { useSigret } from '@/stores/sigret'
import { dataViz } from '@/plugins/vuetify/theme'

const store = useSigret()
const theme = useTheme()

onMounted(() => store.cargar())

const c = computed(() => theme.current.value.colors)

function hexToRgb(hex) {
  const s = hex.replace('#', '')
  const n = parseInt(s.length === 3 ? s.split('').map(x => x + x).join('') : s, 16)

  return `${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}`
}

const txt = computed(() => `rgba(${hexToRgb(String(c.value['on-surface']))}, 0.62)`)
const borde = computed(() => `rgba(${hexToRgb(String(c.value['on-surface']))}, 0.09)`)

// ── Importancia de variables ─────────────────────────────────────────────────
const impSerie = computed(() => [{
  name: 'Importancia',
  data: (store.meta?.importancias ?? []).map(x => +(x.i * 100).toFixed(2)),
}])

const impOpts = computed(() => ({
  chart: { type: 'bar', toolbar: { show: false } },
  plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: '64%' } },
  colors: [c.value.primary],
  dataLabels: {
    enabled: true,
    formatter: v => `${v}%`,
    style: { fontSize: '10.5px', fontWeight: 600, colors: [txt.value] },
    offsetX: 26,
  },
  grid: { borderColor: borde.value, padding: { left: 0 } },
  xaxis: {
    categories: (store.meta?.importancias ?? []).map(x => x.v),
    axisBorder: { show: false }, axisTicks: { show: false },
    labels: { style: { colors: txt.value, fontSize: '10.5px' }, formatter: v => `${v}%` },
  },
  yaxis: { labels: { style: { colors: txt.value, fontSize: '11.5px' } } },
  tooltip: { theme: theme.global.name.value, y: { formatter: v => `${v} %` } },
}))

// ── Comparativa de modelos ───────────────────────────────────────────────────
const cvSerie = computed(() => {
  const d = store.meta?.cv_espacial ?? []

  return [
    { name: 'PR-AUC', data: d.map(x => x.pr_auc) },
    { name: 'ROC-AUC', data: d.map(x => x.roc_auc) },
  ]
})

const cvOpts = computed(() => ({
  chart: { type: 'bar', toolbar: { show: false } },
  plotOptions: { bar: { borderRadius: 4, columnWidth: '58%' } },
  colors: [c.value.primary, c.value.info],
  dataLabels: { enabled: false },
  legend: { position: 'top', horizontalAlign: 'left', fontSize: '12px', markers: { radius: 4 }, labels: { colors: txt.value } },
  grid: { borderColor: borde.value },
  xaxis: {
    categories: (store.meta?.cv_espacial ?? []).map(x => x.modelo),
    axisBorder: { show: false }, axisTicks: { show: false },
    labels: { style: { colors: txt.value, fontSize: '11px' }, rotate: -18, trim: false },
  },
  yaxis: {
    max: 1,
    labels: { style: { colors: txt.value, fontSize: '11px' }, formatter: v => v.toFixed(1) },
  },
  annotations: {
    yaxis: [{
      y: store.kpis.tasaBaseCv,
      borderColor: c.value.error,
      strokeDashArray: 4,
      label: {
        text: `Tasa base ${(store.kpis.tasaBaseCv * 100).toFixed(1)} %`,
        position: 'left',
        textAnchor: 'start',
        style: { background: c.value.error, color: '#fff', fontSize: '10px' },
      },
    }],
  },
  tooltip: { theme: theme.global.name.value },
}))

const bt = computed(() => store.meta?.backtesting ?? [])

const limitaciones = [
  {
    t: 'Cobertura de la bodega tradicional',
    d: 'El Padrón Reducido del RUC no incluye código CIIU y la mayoría de bodegueros se inscribe como persona natural con su nombre propio. De 158,233 establecimientos activos, solo 208 son identificables. El universo competitivo modelado es el retail moderno organizado.',
    s: 'Solicitud de acceso a la información pública a las municipalidades para obtener el padrón de licencias con giro 4711.',
  },
  {
    t: 'Distancias euclidianas',
    d: 'La red peatonal está descargada (59,674 nodos, 176,196 aristas) pero las métricas de proximidad usan línea recta. En el relieve del cono norte esto subestima la fricción real de desplazamiento.',
    s: 'Montar OSRM con perfil peatonal y recalcular las matrices sobre la red.',
  },
  {
    t: 'Base censal de 2017',
    d: 'Es el último censo con desagregación a manzana disponible. Las áreas de expansión posteriores están subrepresentadas, lo que afecta sobre todo a Cerro Colorado y Yura.',
    s: 'Incorporar el Censo 2025 cuando publique el nivel de manzana.',
  },
  {
    t: 'Proxy de éxito comercial',
    d: 'La variable objetivo indica que una tienda existe y sigue operando, no que sea rentable. El modelo aprende el criterio de la cadena, incluidos sus posibles errores.',
    s: 'Atenuado por el hecho de que una cadena con más de 1,600 locales cierra las ubicaciones que no funcionan.',
  },
  {
    t: 'Ventana histórica corta',
    d: 'El Internet Archive solo conserva snapshots útiles desde agosto de 2024, lo que limita el backtesting a dos años y 39 aperturas.',
    s: 'Reconstruir la serie con registros de licencias municipales y notas de prensa.',
  },
  {
    t: 'Pesos del score sin validar',
    d: 'Los valores por defecto son provisionales y no provienen de un ejercicio formal de elicitación de preferencias.',
    s: 'Aplicar AHP con panel de 8 a 10 propietarios de minimarket, verificando CR < 0.10.',
  },
]
</script>

<template>
  <div>
    <div class="mb-5">
      <div class="eyebrow">Transparencia metodológica</div>
      <h1 class="page-title">Validación del modelo</h1>
      <p class="page-sub">
        Sin acceso a datos de ventas, la variable objetivo es la preferencia
        revelada: dónde una cadena con equipo profesional de geomarketing
        decidió efectivamente abrir
      </p>
    </div>

    <VRow>
      <!-- Diseño de validación -->
      <VCol cols="12">
        <VCard class="dis-card">
          <VCardText class="pa-6">
            <VRow>
              <VCol cols="12" md="7">
                <h2 class="text-h6 font-weight-bold mb-3">
                  Cómo se valida un modelo sin datos de ventas
                </h2>
                <p class="cuerpo mb-4">
                  El sistema se entrena con la red de tiendas existente hasta
                  2024 y se evalúa contra las aperturas de 2025 y 2026, que
                  nunca vio durante el entrenamiento. Es un diseño de
                  <strong>backtesting temporal</strong>: no mide cuánto vende
                  una tienda sino si el modelo habría anticipado dónde se
                  abriría.
                </p>
                <p class="cuerpo mb-0">
                  A esto se suma <strong>validación cruzada espacial</strong> en
                  bloques H3 de resolución 6. Una partición aleatoria pondría
                  celdas vecinas en entrenamiento y prueba al mismo tiempo,
                  permitiendo que el modelo vea información del conjunto de
                  prueba a través de sus vecinos e inflando las métricas.
                </p>
              </VCol>

              <VCol cols="12" md="5">
                <div class="flujo">
                  <div class="flujo-paso">
                    <span class="flujo-n">1</span>
                    <div>
                      <div class="flujo-t">Entrenar con datos ≤ 2024</div>
                      <div class="flujo-d">83 celdas con presencia observada</div>
                    </div>
                  </div>
                  <div class="flujo-linea" />
                  <div class="flujo-paso">
                    <span class="flujo-n">2</span>
                    <div>
                      <div class="flujo-t">Rankear 1,259 candidatos</div>
                      <div class="flujo-d">Celdas viables sin tienda en 2024</div>
                    </div>
                  </div>
                  <div class="flujo-linea" />
                  <div class="flujo-paso">
                    <span class="flujo-n">3</span>
                    <div>
                      <div class="flujo-t">Contrastar con 39 aperturas reales</div>
                      <div class="flujo-d">Ocurridas entre 2025 y 2026</div>
                    </div>
                  </div>
                </div>
              </VCol>
            </VRow>
          </VCardText>
        </VCard>
      </VCol>

      <!-- Validación cruzada -->
      <VCol cols="12" lg="6">
        <VCard class="h-100">
          <VCardItem>
            <VCardTitle class="text-body-1 font-weight-bold">
              Validación cruzada espacial
            </VCardTitle>
            <VCardSubtitle class="text-caption">
              5 particiones sobre 52 bloques H3 r6
            </VCardSubtitle>
          </VCardItem>
          <VCardText>
            <VueApexCharts
              v-if="store.ready"
              type="bar" :height="290"
              :options="cvOpts" :series="cvSerie"
            />
            <p class="nota">
              Con una tasa base de {{ (store.kpis.tasaBaseCv * 100).toFixed(1) }} %,
              un PR-AUC de {{ store.kpis.prAuc.toFixed(3) }} equivale a
              <strong>{{ store.kpis.prSobreBase.toFixed(1) }} veces</strong> el desempeño de una asignación
              aleatoria en la región de alta precisión, que es la única
              relevante cuando se evalúan 20 ubicaciones y no 3,717.
            </p>
          </VCardText>
        </VCard>
      </VCol>

      <!-- Backtesting -->
      <VCol cols="12" lg="6">
        <VCard class="h-100">
          <VCardItem>
            <VCardTitle class="text-body-1 font-weight-bold">
              Backtesting temporal
            </VCardTitle>
            <VCardSubtitle class="text-caption">
              39 aperturas reales entre 1,259 candidatos · tasa base 3.10 %
            </VCardSubtitle>
          </VCardItem>
          <VCardText class="pt-0">
            <VTable density="compact" class="tabla-bt">
              <thead>
                <tr>
                  <th>Modelo</th>
                  <th class="text-end">PR-AUC</th>
                  <th class="text-end">P@20</th>
                  <th class="text-end">Aciertos</th>
                  <th class="text-end">Lift@10%</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="r in bt" :key="r.modelo"
                  :class="{ destacado: r.modelo.includes('Ensamble') }"
                >
                  <td>
                    <span :class="r.modelo.startsWith('Baseline') ? 'text-disabled' : 'font-weight-medium'">
                      {{ r.modelo }}
                    </span>
                  </td>
                  <td class="text-end num">{{ r.PR_AUC?.toFixed(3) }}</td>
                  <td class="text-end num">{{ r['P@20']?.toFixed(2) }}</td>
                  <td class="text-end">
                    <VChip
                      size="x-small" label
                      :color="r['acierto@20'] >= 4 ? 'success' : r['acierto@20'] >= 2 ? 'warning' : 'default'"
                      :variant="r['acierto@20'] >= 2 ? 'tonal' : 'text'"
                    >
                      {{ r['acierto@20'] }} / 20
                    </VChip>
                  </td>
                  <td class="text-end num">{{ r['Lift@10%']?.toFixed(2) }}×</td>
                </tr>
              </tbody>
            </VTable>
            <p class="nota">
              El ensamble ubicó <strong>{{ store.kpis.aciertos20 }} de las 39 aperturas reales</strong> en
              su Top-20, igual que el mejor baseline, pero concentra
              {{ store.kpis.lift.toFixed(2) }} veces más aperturas que el azar en su
              decil superior. Es un resultado modesto y realista dadas las condiciones:
              83 casos de entrenamiento y ausencia de variables de alquiler y
              disponibilidad de locales. Un resultado de 18 sobre 20 debería
              despertar sospecha de fuga de información, no confianza.
            </p>
          </VCardText>
        </VCard>
      </VCol>

      <!-- Importancias -->
      <VCol cols="12" lg="7">
        <VCard class="h-100">
          <VCardItem>
            <VCardTitle class="text-body-1 font-weight-bold">
              Variables más influyentes
            </VCardTitle>
            <VCardSubtitle class="text-caption">
              Random Forest · reducción media de impureza
            </VCardSubtitle>
          </VCardItem>
          <VCardText>
            <VueApexCharts
              v-if="store.ready"
              type="bar" :height="400"
              :options="impOpts" :series="impSerie"
            />
          </VCardText>
        </VCard>
      </VCol>

      <!-- Corrección metodológica -->
      <VCol cols="12" lg="5">
        <VCard class="h-100 correccion">
          <VCardText class="pa-6">
            <VChip size="small" color="warning" variant="tonal" label class="mb-3">
              Corrección metodológica
            </VChip>
            <h3 class="text-h6 font-weight-bold mb-3">
              El error que hubo que diagnosticar
            </h3>
            <p class="cuerpo mb-4">
              La primera versión incluía la distancia a la tienda más cercana
              entre los predictores. El modelo le asignó el
              <strong>83 % de la importancia</strong> y colapsó: aprendió la
              regla trivial «hay tienda donde hay tienda cerca».
            </p>
            <p class="cuerpo mb-4">
              El efecto fue contraproducente. Al evaluar celdas vacías, el
              modelo favorecía las adyacentes a tiendas existentes. Pero una
              cadena <em>evita</em> abrir junto a sus propios locales para no
              canibalizar su demanda: estaba optimizando en dirección contraria
              a la lógica del negocio.
            </p>

            <div class="antes-despues">
              <div class="ad-col">
                <div class="ad-lbl">Antes</div>
                <div class="ad-val ad-val--mal">0.045</div>
                <div class="ad-sub">PR-AUC · 1 acierto</div>
              </div>
              <VIcon icon="bx-right-arrow-alt" size="20" class="ad-flecha" />
              <div class="ad-col">
                <div class="ad-lbl">Después</div>
                <div class="ad-val ad-val--bien">0.109</div>
                <div class="ad-sub">PR-AUC · 3 aciertos</div>
              </div>
            </div>

            <p class="cuerpo mt-4 mb-0">
              Excluidas esas variables, las importancias pasaron a ser
              interpretables y consistentes con la teoría de localización
              comercial: población, densidad, actividad urbana y colegios.
            </p>
          </VCardText>
        </VCard>
      </VCol>

      <!-- Limitaciones -->
      <VCol cols="12">
        <VCard>
          <VCardItem>
            <VCardTitle class="text-body-1 font-weight-bold">
              Limitaciones declaradas
            </VCardTitle>
            <VCardSubtitle class="text-caption">
              Cada una con su vía de solución identificada
            </VCardSubtitle>
          </VCardItem>
          <VCardText>
            <VRow>
              <VCol
                v-for="(l, i) in limitaciones" :key="l.t"
                cols="12" md="6" lg="4"
              >
                <div class="lim h-100">
                  <div class="lim-n">{{ String(i + 1).padStart(2, '0') }}</div>
                  <div class="lim-t">{{ l.t }}</div>
                  <p class="lim-d">{{ l.d }}</p>
                  <div class="lim-s">
                    <VIcon icon="bx-wrench" size="13" class="me-1" />
                    {{ l.s }}
                  </div>
                </div>
              </VCol>
            </VRow>
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
  font-size: 1.6rem;
  font-weight: 700;
  letter-spacing: -.02em;
}

.page-sub {
  max-inline-size: 76ch;
  margin: 0;
  color: rgba(var(--v-theme-on-surface), .56);
  font-size: 13px;
  line-height: 1.6;
}

.cuerpo {
  color: rgba(var(--v-theme-on-surface), .74);
  font-size: 13.5px;
  line-height: 1.68;
}

.dis-card { border-inline-start: 3px solid rgb(var(--v-theme-primary)); }

.flujo { padding-inline-start: 4px; }

.flujo-paso {
  display: flex;
  align-items: flex-start;
  gap: 13px;
}

.flujo-n {
  display: grid;
  flex-shrink: 0;
  border-radius: 50%;
  background: rgba(var(--v-theme-primary), .11);
  block-size: 26px;
  color: rgb(var(--v-theme-primary));
  font-size: 12px;
  font-weight: 700;
  inline-size: 26px;
  place-items: center;
}

.flujo-t {
  font-size: 13px;
  font-weight: 600;
}

.flujo-d {
  color: rgba(var(--v-theme-on-surface), .52);
  font-size: 11.5px;
}

.flujo-linea {
  border-inline-start: 2px dashed rgba(var(--v-theme-primary), .26);
  block-size: 18px;
  margin-inline-start: 13px;
}

.nota {
  max-inline-size: 72ch;
  margin-block: 10px 0;
  color: rgba(var(--v-theme-on-surface), .56);
  font-size: 11.8px;
  line-height: 1.6;
}

.tabla-bt {
  th {
    font-size: 10.5px !important;
    font-weight: 600 !important;
    letter-spacing: .05em;
    text-transform: uppercase;
  }

  td { font-size: 12.5px; }

  .num { font-variant-numeric: tabular-nums; }

  .destacado {
    background: rgba(var(--v-theme-primary), .05);
    font-weight: 600;
  }
}

.correccion { border-inline-start: 3px solid rgb(var(--v-theme-warning)); }

.antes-despues {
  display: flex;
  align-items: center;
  padding: 15px;
  border-radius: 9px;
  gap: 16px;
  background: rgba(var(--v-theme-on-surface), .035);
}

.ad-col { flex: 1; text-align: center; }

.ad-lbl {
  color: rgba(var(--v-theme-on-surface), .5);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.ad-val {
  margin-block-start: 3px;
  font-size: 1.5rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.ad-val--mal { color: rgb(var(--v-theme-error)); }
.ad-val--bien { color: rgb(var(--v-theme-success)); }

.ad-sub {
  margin-block-start: 3px;
  color: rgba(var(--v-theme-on-surface), .5);
  font-size: 10.5px;
}

.ad-flecha { color: rgba(var(--v-theme-on-surface), .3); }

.lim {
  padding: 17px;
  border: 1px solid rgba(var(--v-theme-on-surface), .09);
  border-radius: 9px;
  transition: border-color .2s ease;

  &:hover { border-color: rgba(var(--v-theme-primary), .38); }
}

.lim-n {
  color: rgba(var(--v-theme-primary), .42);
  font-size: 1.4rem;
  font-weight: 700;
  line-height: 1;
}

.lim-t {
  margin-block: 7px 6px;
  font-size: 13.5px;
  font-weight: 700;
}

.lim-d {
  margin: 0;
  color: rgba(var(--v-theme-on-surface), .64);
  font-size: 12px;
  line-height: 1.6;
}

.lim-s {
  display: flex;
  align-items: flex-start;
  padding-block-start: 9px;
  border-block-start: 1px solid rgba(var(--v-theme-on-surface), .07);
  margin-block-start: 11px;
  color: rgb(var(--v-theme-primary));
  font-size: 11.5px;
  line-height: 1.5;
}
</style>
