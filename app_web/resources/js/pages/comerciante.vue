<script setup>
import HexMap from '@/views/sigret/HexMap.vue'
import { useSigret } from '@/stores/sigret'
import {
  ANTES_DE_DECIDIR,
  TAMANOS,
  avisos,
  cadena,
  distancia,
  enlaceMapa,
  entero,
  nivel,
  nombreDistrito,
  numeros,
  soles,
} from '@/utils/comerciante'

// ─────────────────────────────────────────────────────────────────────────────
// Modo comerciante: tres pasos en lenguaje simple, sin métricas del modelo.
// El ranking es el de la versión técnica con los pesos del panel de
// propietarios (store.rankingPanel); los controles del modelo no se muestran.
// ─────────────────────────────────────────────────────────────────────────────

const store = useSigret()
const router = useRouter()

onMounted(() => store.cargar())

// Paso 1
const distrito = ref(null)

const distritos = computed(() => [...new Set(store.rankingPanel.map(h => h.dist))]
  .filter(d => d && d !== 'SIN_DATO')
  .map(d => ({ title: nombreDistrito(d), value: d }))
  .sort((a, b) => a.title.localeCompare(b.title, 'es')))

// Paso 2
const cuantos = ref(5)

const zonas = computed(() => store.rankingPanel
  .filter(h => !distrito.value || h.dist === distrito.value))

const lista = computed(() => zonas.value.slice(0, cuantos.value))
const elegida = ref(null)

watch(distrito, () => {
  cuantos.value = 5
  elegida.value = null
})

watch(lista, v => {
  if (v.length && !v.some(h => h.h3 === elegida.value))
    elegida.value = v[0].h3
}, { immediate: true })

const zona = computed(() => store.rankingPanel.find(h => h.h3 === elegida.value) ?? null)

// Paso 3: supuestos del comerciante (no cambian la versión técnica)
const supuestos = reactive({ inversion: 160000, superficie: 100, margen: 22, gastos: null })

const n = computed(() => zona.value
  ? numeros(zona.value, supuestos, store.p.hCampo)
  : null)

const alertas = computed(() => zona.value && n.value ? avisos(zona.value, n.value) : [])

const paso3 = ref(null)

function calcular(h3) {
  elegida.value = h3
  nextTick(() => paso3.value?.$el?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
}

function verFicha() {
  router.push({
    name: 'ficha',
    params: { h3: elegida.value },
    query: {
      inv: supuestos.inversion,
      m2: supuestos.superficie,
      mg: supuestos.margen,
      ...(supuestos.gastos ? { gf: supuestos.gastos } : {}),
    },
  })
}
</script>

<template>
  <div class="com">
    <header class="com-bar no-print">
      <RouterLink to="/comerciante" class="com-marca">
        SIGRET <span class="d-none d-sm-inline">· Para comerciantes</span>
      </RouterLink>
      <VBtn to="/panel" variant="text" size="small" append-icon="bx-right-arrow-alt">
        Versión técnica
      </VBtn>
    </header>

    <main class="com-main">
      <section class="com-hero">
        <h1>¿Dónde conviene abrir tu minimarket?</h1>
        <p>
          Te mostramos las zonas de Arequipa con más gente cerca y menos tiendas
          para atenderla. Son tres pasos y no necesitas saber de computadoras.
        </p>
      </section>

      <div v-if="store.error" class="com-aviso">
        <VAlert type="error" variant="tonal">
          No se pudieron cargar los datos. Revisa tu conexión y vuelve a abrir la página.
        </VAlert>
      </div>

      <div v-else-if="!store.ready" class="text-center py-12">
        <VProgressCircular indeterminate color="primary" />
        <p class="mt-3 text-medium-emphasis">Cargando las zonas…</p>
      </div>

      <template v-else>
        <!-- Paso 1 -->
        <VCard class="com-paso">
          <VCardText>
            <div class="paso-tit">
              <span class="paso-num">1</span>
              <h2>Elige dónde buscar</h2>
            </div>
            <VAutocomplete
              v-model="distrito"
              :items="distritos"
              label="Distrito"
              placeholder="Todos los distritos"
              variant="outlined"
              clearable
              hide-details
              class="mt-4"
              prepend-inner-icon="bx-map"
            />
            <p class="paso-ayuda">
              Déjalo vacío para ver las mejores zonas de toda Arequipa.
            </p>
          </VCardText>
        </VCard>

        <!-- Paso 2 -->
        <VCard class="com-paso">
          <VCardText>
            <div class="paso-tit">
              <span class="paso-num">2</span>
              <h2>Mira las mejores zonas</h2>
            </div>
            <p class="paso-ayuda mb-4">
              Ordenadas de mejor a peor
              {{ distrito ? `en ${nombreDistrito(distrito)}` : 'en Arequipa' }}.
              Toca «Ver en Google Maps» para ubicar la calle.
            </p>

            <p v-if="!lista.length" class="text-medium-emphasis">
              En este distrito no hay zonas con la gente suficiente para un minimarket.
            </p>

            <div
              v-for="(h, i) in lista"
              :key="h.h3"
              class="zona"
              :class="{ 'zona--elegida': h.h3 === elegida }"
              @click="elegida = h.h3"
            >
              <div class="zona-cab">
                <span class="zona-pos">{{ i + 1 }}</span>
                <div class="flex-grow-1">
                  <div class="zona-dist">{{ nombreDistrito(h.dist) }}</div>
                  <VChip :color="nivel(h).color" size="small" label variant="tonal">
                    Oportunidad {{ nivel(h).texto.toLowerCase() }}
                  </VChip>
                </div>
              </div>

              <ul class="zona-datos">
                <li>
                  <VIcon icon="bx-group" size="20" />
                  <span><strong>{{ entero(h.pob_k1) }} personas</strong> viven a unos 500 m (5 a 7 minutos a pie)</span>
                </li>
                <li>
                  <VIcon icon="bx-store-alt" size="20" />
                  <span>Unas <strong>{{ entero(h.bodegas) }} bodegas y tiendas</strong> atienden a esa gente (estimado)</span>
                </li>
                <li>
                  <VIcon icon="bx-cart" size="20" :color="cadena(h).color" />
                  <span>{{ cadena(h).texto }}</span>
                </li>
                <li>
                  <VIcon icon="bx-buildings" size="20" />
                  <span><strong>{{ entero(h.n_poi_k1) }}</strong> colegios, mercados, paraderos y otros lugares con movimiento cerca</span>
                </li>
              </ul>

              <div class="zona-acc">
                <VBtn
                  :href="enlaceMapa(h)" target="_blank" rel="noopener"
                  variant="outlined" size="small" prepend-icon="bx-map-pin"
                  @click.stop
                >
                  Ver en Google Maps
                </VBtn>
                <VBtn
                  color="primary" size="small" prepend-icon="bx-calculator"
                  @click.stop="calcular(h.h3)"
                >
                  Calcular mis números
                </VBtn>
              </div>
            </div>

            <div v-if="zonas.length > cuantos && cuantos < 20" class="text-center mt-2">
              <VBtn variant="text" prepend-icon="bx-plus" @click="cuantos += 5">
                Ver 5 zonas más
              </VBtn>
            </div>

            <div v-if="zona" class="com-mapa">
              <HexMap
                height="300px"
                :extrusion="false"
                mostrar-mass
                :centrar-en="{ lat: zona.lat, lon: zona.lon }"
                :destacar="zona.h3"
                :interactivo="false"
              />
              <p class="paso-ayuda">
                La zona elegida tiene el borde blanco. Los colores más claros son
                mejores zonas; los puntos celestes son tiendas de descuento.
              </p>
            </div>
          </VCardText>
        </VCard>

        <!-- Paso 3 -->
        <VCard v-if="zona && n" ref="paso3" class="com-paso">
          <VCardText>
            <div class="paso-tit">
              <span class="paso-num">3</span>
              <h2>Calcula tus números</h2>
            </div>
            <p class="paso-ayuda mb-4">
              Zona elegida: {{ nombreDistrito(zona.dist) }}, puesto {{ entero(zona.puesto) }}
              de {{ entero(store.rankingPanel.length) }} zonas evaluadas.
            </p>

            <VRow>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model.number="supuestos.inversion"
                  label="¿Cuánto vas a invertir?"
                  prefix="S/" type="number" min="0" step="5000"
                  variant="outlined" hide-details
                />
              </VCol>
              <VCol cols="12" sm="6">
                <VTextField
                  v-model.number="supuestos.gastos"
                  label="Gastos fijos al mes (opcional)"
                  hint="Alquiler, sueldos, luz y agua"
                  persistent-hint
                  prefix="S/" type="number" min="0" step="100"
                  variant="outlined"
                />
              </VCol>
            </VRow>

            <div class="mt-5">
              <div class="campo-tit">¿De qué tamaño será tu tienda?</div>
              <div class="tamanos mt-2" role="radiogroup" aria-label="Tamaño de la tienda">
                <VBtn
                  v-for="t in TAMANOS" :key="t.m2"
                  :variant="supuestos.superficie === t.m2 ? 'flat' : 'outlined'"
                  :color="supuestos.superficie === t.m2 ? 'primary' : undefined"
                  role="radio" :aria-checked="supuestos.superficie === t.m2"
                  class="tamano"
                  @click="supuestos.superficie = t.m2"
                >
                  <span class="tamano-txt">
                    <strong>{{ t.texto }}</strong>
                    <span>{{ t.detalle }}</span>
                  </span>
                </VBtn>
              </div>
            </div>

            <div class="mt-5">
              <div class="campo-tit">
                De cada S/ 100 que vendes, ¿cuánto te queda después de pagar la mercadería?
                <strong class="text-primary">S/ {{ supuestos.margen }}</strong>
              </div>
              <VSlider
                v-model="supuestos.margen"
                :min="10" :max="40" :step="1"
                color="primary" hide-details thumb-label
              />
            </div>

            <div class="res">
              <div class="res-item">
                <div class="res-lbl">Podrías vender</div>
                <div class="res-val">{{ soles(n.ventas) }}</div>
                <div class="res-sub">al mes</div>
              </div>
              <div class="res-item">
                <div class="res-lbl">{{ n.conGastos ? 'Te quedaría, ya pagados tus gastos fijos' : 'Te quedaría para pagar alquiler, sueldos y servicios' }}</div>
                <div class="res-val" :class="n.conGastos && n.neto <= 0 ? 'text-error' : ''">
                  {{ soles(n.conGastos ? n.neto : n.bruto) }}
                </div>
                <div class="res-sub">al mes</div>
              </div>
              <div class="res-item">
                <div class="res-lbl">Recuperarías lo que inviertes en</div>
                <div class="res-val" :class="n.recupera && n.recupera > 36 ? 'text-error' : ''">
                  {{ n.recupera ? `${entero(n.recupera)} meses` : 'no se recupera' }}
                </div>
                <div class="res-sub">{{ n.conGastos ? 'con tus gastos fijos' : 'sin contar alquiler ni sueldos' }}</div>
              </div>
            </div>

            <VAlert
              v-for="(a, i) in alertas" :key="i"
              :type="a.t" variant="tonal" density="comfortable"
              class="mt-3"
            >
              {{ a.txt }}
            </VAlert>

            <div class="d-flex flex-wrap gap-3 mt-5">
              <VBtn color="primary" size="large" prepend-icon="bx-printer" @click="verFicha">
                Ver e imprimir la ficha
              </VBtn>
              <VBtn
                :href="enlaceMapa(zona)" target="_blank" rel="noopener"
                variant="outlined" size="large" prepend-icon="bx-map-pin"
              >
                Ver en Google Maps
              </VBtn>
            </div>
          </VCardText>
        </VCard>

        <VCard class="com-paso" variant="tonal" color="secondary">
          <VCardText>
            <h3 class="mb-2">Antes de decidir</h3>
            <ul class="lista-antes">
              <li v-for="t in ANTES_DE_DECIDIR" :key="t">{{ t }}</li>
            </ul>
            <p class="mt-3 mb-0">
              Estos números son una estimación hecha con datos públicos, no una
              garantía de ventas. Sirven para comparar zonas, no para reemplazar
              la visita al lugar.
            </p>
          </VCardText>
        </VCard>

        <VExpansionPanels class="com-paso" variant="accordion">
          <VExpansionPanel title="¿Cómo elegimos estas zonas?">
            <VExpansionPanelText>
              <p>
                Damos más puntos a las zonas donde vive más gente a unos 500 m y
                hay menos tiendas para atenderla, y a las que se parecen a los
                lugares donde una cadena de tiendas de descuento decidió abrir.
                Quitamos puntos si hay una tienda de descuento cerca. Cuánto pesa
                cada cosa lo decidieron diez dueños de minimarket de Arequipa.
              </p>
              <p class="mb-0">
                Solo mostramos zonas donde viven al menos 1 500 personas a 500 m
                y donde todavía no hay una tienda de la cadena. Usamos el censo,
                OpenStreetMap y las aperturas de la cadena entre 2024 y 2026.
              </p>
            </VExpansionPanelText>
          </VExpansionPanel>
        </VExpansionPanels>
      </template>
    </main>
  </div>
</template>

<style lang="scss" scoped>
.com {
  min-block-size: 100vh;
  background: rgb(var(--v-theme-background));
}

.com-bar {
  position: sticky;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-block: 10px;
  padding-inline: 16px;
  background: rgb(var(--v-theme-surface));
  border-block-end: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  inset-block-start: 0;
}

.com-marca {
  color: rgb(var(--v-theme-primary));
  font-size: 1.05rem;
  font-weight: 800;
  letter-spacing: .02em;
  text-decoration: none;

  span {
    color: rgba(var(--v-theme-on-surface), .7);
    font-weight: 600;
  }
}

.com-main {
  max-inline-size: 860px;
  margin-inline: auto;
  padding-block: 20px 48px;
  padding-inline: 16px;
}

.com-hero {
  margin-block: 8px 20px;

  h1 {
    margin-block-end: 8px;
    font-size: clamp(1.5rem, 4.6vw, 2.1rem);
    font-weight: 800;
    letter-spacing: -.02em;
    line-height: 1.15;
  }

  p {
    margin: 0;
    color: rgba(var(--v-theme-on-surface), .75);
    font-size: 1.05rem;
    line-height: 1.5;
  }
}

.com-paso {
  margin-block-end: 18px;
}

.paso-tit {
  display: flex;
  align-items: center;
  gap: 12px;

  h2 {
    margin: 0;
    font-size: 1.3rem;
    font-weight: 700;
  }
}

.paso-num {
  display: grid;
  flex: none;
  border-radius: 50%;
  background: rgb(var(--v-theme-primary));
  block-size: 34px;
  color: rgb(var(--v-theme-on-primary));
  font-size: 1.05rem;
  font-weight: 800;
  inline-size: 34px;
  place-items: center;
}

.paso-ayuda {
  margin-block: 8px 0;
  color: rgba(var(--v-theme-on-surface), .68);
  font-size: .98rem;
}

.zona {
  padding: 14px;
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 10px;
  cursor: pointer;
  margin-block-end: 12px;
  transition: border-color .15s;
}

.zona--elegida {
  border-width: 2px;
  border-color: rgb(var(--v-theme-primary));
  background: rgba(var(--v-theme-primary), .04);
}

.zona-cab {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.zona-pos {
  display: grid;
  flex: none;
  border-radius: 8px;
  background: rgba(var(--v-theme-primary), .12);
  block-size: 32px;
  color: rgb(var(--v-theme-primary));
  font-weight: 800;
  inline-size: 32px;
  place-items: center;
}

.zona-dist {
  font-size: 1.12rem;
  font-weight: 700;
  margin-block-end: 4px;
}

.zona-datos {
  padding: 0;
  margin-block: 12px;
  list-style: none;

  li {
    display: flex;
    align-items: flex-start;
    gap: 10px;
    font-size: 1rem;
    line-height: 1.4;
    margin-block-end: 7px;
  }

  .v-icon {
    flex: none;
    margin-block-start: 1px;
  }
}

.zona-acc {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.com-mapa {
  overflow: hidden;
  border-radius: 10px;
  margin-block-start: 8px;
}

.campo-tit {
  font-size: 1rem;
  font-weight: 600;
}

.tamanos {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(3, 1fr);
}

.tamano {
  block-size: 56px !important;
  text-transform: none;
}

.tamano-txt {
  display: flex;
  flex-direction: column;
  align-items: center;
  line-height: 1.2;

  strong { font-size: 1rem; }

  span { font-size: .8rem; opacity: .8; }
}

// Texto de los avisos en el color normal: el naranja sobre fondo claro se lee mal
:deep(.v-alert--variant-tonal .v-alert__content) {
  color: rgba(var(--v-theme-on-surface), .9);
  font-size: 1rem;
}

.res {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  margin-block: 24px 8px;
}

.res-item {
  padding: 14px;
  border-radius: 10px;
  background: rgba(var(--v-theme-primary), .06);
}

.res-lbl {
  color: rgba(var(--v-theme-on-surface), .72);
  font-size: .92rem;
  line-height: 1.3;
}

.res-val {
  margin-block-start: 6px;
  font-size: 1.6rem;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  letter-spacing: -.02em;
}

.res-sub {
  color: rgba(var(--v-theme-on-surface), .6);
  font-size: .85rem;
}

.lista-antes {
  padding-inline-start: 20px;

  li {
    font-size: 1rem;
    margin-block-end: 6px;
  }
}
</style>
