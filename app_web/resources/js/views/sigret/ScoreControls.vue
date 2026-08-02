<script setup>
import { useSigret } from '@/stores/sigret'

defineProps({
  mostrarFinanzas: { type: Boolean, default: false },
  mostrarCapas: { type: Boolean, default: true },
})

const store = useSigret()

const capas = defineModel('capas', {
  default: () => ({ extrusion: true, mass: true, competencia: false }),
})
</script>

<template>
  <VCard>
    <VCardItem class="pb-2">
      <VCardTitle class="text-body-1 font-weight-bold">
        Parámetros del modelo
      </VCardTitle>
      <template #append>
        <VBtn
          size="x-small"
          variant="text"
          color="secondary"
          @click="store.reset()"
        >
          Restablecer
        </VBtn>
      </template>
    </VCardItem>

    <VCardText>
      <!-- Ponderación entre criterios -->
      <div class="ctrl">
        <div class="ctrl-head">
          <span class="ctrl-label">Perfil de sitio · modelo ML</span>
          <span class="ctrl-val">{{ store.p.wPerfil.toFixed(2) }}</span>
        </div>
        <VSlider
          v-model="store.p.wPerfil"
          :min="0" :max="1" :step="0.05"
          color="primary" density="compact" hide-details thumb-size="14"
          track-size="4"
        />
        <p class="ctrl-help">
          Complemento en demanda residual: <strong>{{ (1 - store.p.wPerfil).toFixed(2) }}</strong>.
          Desplaza el criterio entre el patrón aprendido de localización y la
          demanda no atendida.
        </p>
      </div>

      <VDivider class="my-4" />

      <!-- Amenaza competitiva -->
      <div class="ctrl">
        <div class="ctrl-head">
          <span class="ctrl-label">Penalización por hard discount</span>
          <span class="ctrl-val">{{ store.p.penalizacion.toFixed(2) }}</span>
        </div>
        <VSlider
          v-model="store.p.penalizacion"
          :min="0" :max="1" :step="0.05"
          color="warning" density="compact" hide-details thumb-size="14"
          track-size="4"
        />
        <p class="ctrl-help">
          En 0 el mapa muestra la perspectiva de una cadena. Al subirlo, la de
          un independiente que no puede competir en precio.
        </p>
      </div>

      <div class="ctrl mt-4">
        <div class="ctrl-head">
          <span class="ctrl-label">Radio de amenaza</span>
          <span class="ctrl-val">{{ store.p.radioAmenaza }} m</span>
        </div>
        <VSlider
          v-model="store.p.radioAmenaza"
          :min="300" :max="1500" :step="50"
          color="warning" density="compact" hide-details thumb-size="14"
          track-size="4"
        />
      </div>

      <VDivider class="my-4" />

      <!-- Viabilidad -->
      <div class="ctrl">
        <div class="ctrl-head">
          <span class="ctrl-label">Población mínima a 500 m</span>
          <span class="ctrl-val">{{ store.p.pobMinima.toLocaleString('es-PE') }}</span>
        </div>
        <VSlider
          v-model="store.p.pobMinima"
          :min="500" :max="6000" :step="250"
          color="info" density="compact" hide-details thumb-size="14"
          track-size="4"
        />
        <p class="ctrl-help">
          Umbral de masa crítica alcanzable a pie.
        </p>
      </div>

      <template v-if="mostrarFinanzas">
        <VDivider class="my-4" />
        <div class="ctrl-section">Supuestos económicos</div>

        <VRow dense>
          <VCol cols="6">
            <VTextField
              v-model.number="store.p.gastoPerCapita"
              label="Gasto per cápita" prefix="S/" suffix="/mes"
              type="number" density="compact" variant="outlined" hide-details
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model.number="store.p.superficie"
              label="Superficie" suffix="m²"
              type="number" density="compact" variant="outlined" hide-details
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              v-model.number="store.p.inversion"
              label="Inversión" prefix="S/"
              type="number" density="compact" variant="outlined" hide-details
            />
          </VCol>
          <VCol cols="6">
            <VTextField
              :model-value="(store.p.margen * 100).toFixed(0)"
              label="Margen bruto" suffix="%"
              type="number" density="compact" variant="outlined" hide-details
              @update:model-value="v => store.p.margen = Number(v) / 100"
            />
          </VCol>
        </VRow>
      </template>

      <VDivider class="my-4" />

      <!-- Filtros territoriales -->
      <div class="ctrl-section">Filtros</div>

      <VSelect
        v-model="store.filtros.distritos"
        :items="store.districts"
        label="Distritos"
        multiple chips closable-chips
        density="compact" variant="outlined" hide-details
        class="mb-3"
      >
        <template #prepend-item>
          <VListItem
            title="Seleccionar todos"
            @click="store.filtros.distritos = [...store.districts]"
          />
          <VListItem
            title="Limpiar"
            @click="store.filtros.distritos = []"
          />
          <VDivider class="mt-2" />
        </template>
        <template #selection="{ item, index }">
          <VChip v-if="index < 2" size="x-small" label>
            {{ item.title }}
          </VChip>
          <span
            v-else-if="index === 2"
            class="text-caption text-disabled ms-1"
          >
            +{{ store.filtros.distritos.length - 2 }}
          </span>
        </template>
      </VSelect>

      <VSwitch
        v-model="store.filtros.soloViables"
        label="Solo ubicaciones viables"
        color="primary" density="compact" hide-details
      />

      <template v-if="mostrarCapas">
        <VDivider class="my-4" />
        <div class="ctrl-section">Capas del mapa</div>

        <VSwitch
          v-model="capas.extrusion"
          label="Extrusión 3D" color="primary"
          density="compact" hide-details
        />
        <VSwitch
          v-model="capas.mass"
          label="Tiendas Mass" color="info"
          density="compact" hide-details
        />
        <VSwitch
          v-model="capas.competencia"
          label="Competencia OSM" color="secondary"
          density="compact" hide-details
        />
      </template>
    </VCardText>
  </VCard>
</template>

<style lang="scss" scoped>
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

.ctrl-help {
  margin-block: 4px 0;
  color: rgba(var(--v-theme-on-surface), .5);
  font-size: 11px;
  line-height: 1.45;
}

.ctrl-section {
  margin-block-end: 10px;
  color: rgba(var(--v-theme-on-surface), .58);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
}
</style>
