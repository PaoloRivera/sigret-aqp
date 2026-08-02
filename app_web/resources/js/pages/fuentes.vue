<script setup>
import { useSigret } from '@/stores/sigret'

const store = useSigret()

onMounted(() => store.cargar())

const nf = new Intl.NumberFormat('es-PE')

const fases = [
  {
    n: '01', t: 'Construcción de la malla',
    d: 'Relleno de polígono, centroides y vértices de las 21,705 manzanas censales, más un anillo de expansión k=1. La población se transfiere por ponderación areal con 0 % de pérdida.',
    o: '3,717 hexágonos H3 r9',
    ic: 'bx-grid-alt',
  },
  {
    n: '02', t: 'Red histórica de competencia',
    d: 'Extracción de coordenadas desde los atributos de datos del localizador público y consolidación de snapshots del Internet Archive para reconstruir la serie temporal.',
    o: '128 tiendas · 4 cortes anuales',
    ic: 'bx-time-five',
  },
  {
    n: '03', t: 'Ingeniería de características',
    d: 'Demanda en vecindades concéntricas, morfología de la red vial, nueve categorías de POIs generadores de flujo, competencia e índices de saturación.',
    o: '51 variables por celda',
    ic: 'bx-slider-alt',
  },
  {
    n: '04', t: 'Modelado supervisado',
    d: 'Regresión logística, Random Forest y XGBoost sobre 36 predictores. Ensamble por promedio de rangos percentiles para normalizar escalas heterogéneas.',
    o: '4 modelos comparados',
    ic: 'bx-brain',
  },
  {
    n: '05', t: 'Validación',
    d: 'Validación cruzada espacial en bloques H3 r6 y backtesting temporal contra aperturas no vistas durante el entrenamiento.',
    o: 'ROC-AUC 0.929',
    ic: 'bx-check-shield',
  },
  {
    n: '06', t: 'Score de decisión',
    d: 'Combinación del perfil aprendido con la demanda residual, penalizada por la amenaza de entrada de un hard discount y filtrada por viabilidad.',
    o: 'Ranking accionable',
    ic: 'bx-target-lock',
  },
]

const stack = [
  { g: 'Geoprocesamiento', i: ['GeoPandas', 'Shapely', 'h3-py', 'SciPy'] },
  { g: 'Aprendizaje automático', i: ['scikit-learn', 'XGBoost'] },
  { g: 'Interfaz', i: ['Vue 3', 'Vuetify', 'Pinia', 'ApexCharts'] },
  { g: 'Cartografía', i: ['MapLibre GL', 'h3-js', 'CARTO'] },
  { g: 'Backend', i: ['Laravel', 'Vite'] },
  { g: 'Formatos', i: ['Apache Parquet', 'GeoJSON'] },
]
</script>

<template>
  <div>
    <div class="mb-5">
      <div class="eyebrow">Procedencia y método</div>
      <h1 class="page-title">Fuentes de datos</h1>
      <p class="page-sub">
        Todo el sistema se construyó con información de acceso público y
        software libre: sin licencias, sin compra de datos y sin trabajo de
        campo
      </p>
    </div>

    <!-- Fuentes -->
    <VRow class="mb-2">
      <VCol
        v-for="f in (store.meta?.fuentes ?? [])" :key="f.n"
        cols="12" md="6" lg="4"
      >
        <VCard class="fuente h-100">
          <VCardText class="pa-5">
            <div class="d-flex align-start justify-space-between mb-2">
              <div class="fuente-t">{{ f.n }}</div>
              <VChip size="x-small" variant="tonal" color="secondary" label>
                {{ f.l }}
              </VChip>
            </div>
            <div class="fuente-d">{{ f.t }}</div>
            <div class="fuente-v">{{ f.v }}</div>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <VRow>
      <!-- Pipeline -->
      <VCol cols="12" lg="8">
        <VCard>
          <VCardItem>
            <VCardTitle class="text-body-1 font-weight-bold">
              Arquitectura del procesamiento
            </VCardTitle>
            <VCardSubtitle class="text-caption">
              Seis fases reproducibles · aproximadamente 4 minutos de ejecución
            </VCardSubtitle>
          </VCardItem>
          <VCardText>
            <div class="fases">
              <div v-for="f in fases" :key="f.n" class="fase">
                <div class="fase-icono">
                  <VIcon :icon="f.ic" size="19" />
                </div>
                <div class="fase-cuerpo">
                  <div class="d-flex align-center gap-2 flex-wrap">
                    <span class="fase-n">{{ f.n }}</span>
                    <span class="fase-t">{{ f.t }}</span>
                    <VChip size="x-small" color="primary" variant="tonal" label>
                      {{ f.o }}
                    </VChip>
                  </div>
                  <p class="fase-d">{{ f.d }}</p>
                </div>
              </div>
            </div>
          </VCardText>
        </VCard>
      </VCol>

      <VCol cols="12" lg="4">
        <!-- Separación de capas -->
        <VCard class="mb-4">
          <VCardItem class="pb-1">
            <VCardTitle class="text-body-1 font-weight-bold">
              Decisión arquitectónica
            </VCardTitle>
          </VCardItem>
          <VCardText>
            <p class="cuerpo mb-4">
              El cálculo pesado y la presentación están estrictamente separados.
              El overlay geométrico y el entrenamiento se ejecutan fuera de
              línea; la interfaz solo lee resultados y hace aritmética
              vectorizada.
            </p>
            <div class="capa">
              <div class="capa-t">Fuera de línea · Python</div>
              <div class="capa-d">Overlay de 21,705 manzanas, entrenamiento con validación cruzada</div>
              <div class="capa-m">≈ 4 min</div>
            </div>
            <div class="capa capa--on">
              <div class="capa-t">En línea · navegador</div>
              <div class="capa-d">Recálculo del score sobre 3,717 celdas al mover un control</div>
              <div class="capa-m">&lt; 10 ms</div>
            </div>
            <p class="nota mt-3">
              Los datos servidos pesan 555 KB. La aplicación funciona sin
              backend de cálculo.
            </p>
          </VCardText>
        </VCard>

        <!-- Stack -->
        <VCard>
          <VCardItem class="pb-1">
            <VCardTitle class="text-body-1 font-weight-bold">
              Tecnologías
            </VCardTitle>
          </VCardItem>
          <VCardText>
            <div v-for="s in stack" :key="s.g" class="stack-g">
              <div class="stack-t">{{ s.g }}</div>
              <div class="d-flex flex-wrap gap-1">
                <VChip
                  v-for="i in s.i" :key="i"
                  size="x-small" variant="outlined" label
                >
                  {{ i }}
                </VChip>
              </div>
            </div>
          </VCardText>
        </VCard>
      </VCol>

      <!-- Cobertura -->
      <VCol cols="12">
        <VCard>
          <VCardItem>
            <VCardTitle class="text-body-1 font-weight-bold">
              Cobertura territorial
            </VCardTitle>
            <VCardSubtitle class="text-caption">
              17 distritos de Arequipa Metropolitana · Censo Nacional 2017
            </VCardSubtitle>
          </VCardItem>
          <VCardText>
            <VRow dense>
              <VCol
                v-for="d in (store.meta?.poblacion_distrito ?? [])" :key="d.d"
                cols="6" sm="4" md="3" lg="2"
              >
                <div class="dist">
                  <div class="dist-n">{{ d.d }}</div>
                  <div class="dist-p">{{ nf.format(d.p) }}</div>
                  <VProgressLinear
                    :model-value="(d.p / 196909) * 100"
                    color="primary" height="3" rounded class="mt-2"
                  />
                </div>
              </VCol>
            </VRow>
          </VCardText>
        </VCard>
      </VCol>
    </VRow>

    <VCard variant="tonal" color="secondary" class="mt-5">
      <VCardText class="text-body-2">
        <strong>Declaración.</strong> Este es un trabajo académico
        independiente. No existe vínculo contractual, patrocinio ni endoso por
        parte de ninguna de las empresas mencionadas. Las tiendas se utilizan
        como objeto de estudio observable para inferir criterios de localización
        de retail moderno, del mismo modo en que la literatura analiza las
        decisiones de cadenas internacionales a partir de datos públicos.
        Los datos de OpenStreetMap se emplean bajo licencia ODbL.
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
  max-inline-size: 74ch;
  margin: 0;
  color: rgba(var(--v-theme-on-surface), .56);
  font-size: 13px;
  line-height: 1.6;
}

.cuerpo {
  color: rgba(var(--v-theme-on-surface), .72);
  font-size: 13px;
  line-height: 1.65;
}

.fuente {
  border-block-start: 3px solid rgb(var(--v-theme-primary));
  transition: transform .2s ease, box-shadow .2s ease;

  &:hover {
    box-shadow: 0 6px 20px rgb(27 42 50 / 10%);
    transform: translateY(-2px);
  }
}

.fuente-t {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.3;
}

.fuente-d {
  margin-block: 3px 9px;
  color: rgba(var(--v-theme-on-surface), .6);
  font-size: 12px;
}

.fuente-v {
  color: rgb(var(--v-theme-primary));
  font-size: 12.5px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.fase {
  display: flex;
  padding-block-end: 20px;
  gap: 15px;

  &:not(:last-child) {
    border-inline-start: 2px solid rgba(var(--v-theme-primary), .16);
    margin-inline-start: 19px;
    padding-inline-start: 21px;
  }

  &:last-child { margin-inline-start: 19px; padding-inline-start: 23px; }
}

.fase-icono {
  display: grid;
  flex-shrink: 0;
  border-radius: 9px;
  margin-inline-start: -42px;
  background: rgb(var(--v-theme-surface));
  block-size: 38px;
  box-shadow: inset 0 0 0 2px rgba(var(--v-theme-primary), .18);
  color: rgb(var(--v-theme-primary));
  inline-size: 38px;
  place-items: center;
}

.fase-cuerpo { padding-inline-start: 12px; }

.fase-n {
  color: rgba(var(--v-theme-primary), .5);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: .06em;
}

.fase-t {
  font-size: 13.5px;
  font-weight: 700;
}

.fase-d {
  max-inline-size: 82ch;
  margin-block: 5px 0;
  color: rgba(var(--v-theme-on-surface), .62);
  font-size: 12.5px;
  line-height: 1.6;
}

.capa {
  position: relative;
  padding: 13px 15px;
  border-radius: 8px;
  margin-block-end: 9px;
  background: rgba(var(--v-theme-on-surface), .035);
}

.capa--on {
  background: rgba(var(--v-theme-primary), .07);
  margin-block-end: 0;
}

.capa-t {
  font-size: 12px;
  font-weight: 700;
}

.capa-d {
  margin-block-start: 3px;
  color: rgba(var(--v-theme-on-surface), .58);
  font-size: 11.5px;
  line-height: 1.5;
  padding-inline-end: 52px;
}

.capa-m {
  position: absolute;
  color: rgb(var(--v-theme-primary));
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  inset-block-start: 13px;
  inset-inline-end: 15px;
}

.stack-g:not(:last-child) { margin-block-end: 13px; }

.stack-t {
  margin-block-end: 5px;
  color: rgba(var(--v-theme-on-surface), .54);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .07em;
  text-transform: uppercase;
}

.dist {
  padding: 12px 13px;
  border-radius: 8px;
  background: rgba(var(--v-theme-on-surface), .032);
  block-size: 100%;
}

.dist-n {
  color: rgba(var(--v-theme-on-surface), .62);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .03em;
  line-height: 1.3;
  text-transform: uppercase;
}

.dist-p {
  margin-block-start: 5px;
  font-size: 1.02rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.nota {
  color: rgba(var(--v-theme-on-surface), .5);
  font-size: 11.5px;
  line-height: 1.55;
}
</style>
