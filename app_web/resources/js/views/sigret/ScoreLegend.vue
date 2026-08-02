<script setup>
import { scoreScale } from '@/plugins/vuetify/theme'

defineProps({
  titulo: { type: String, default: 'Score de oportunidad' },
  compacta: { type: Boolean, default: false },
})

const gradiente = `linear-gradient(90deg, ${scoreScale.join(', ')})`
</script>

<template>
  <div class="legend" :class="{ 'legend--compact': compacta }">
    <div class="legend-title">{{ titulo }}</div>
    <div class="legend-bar" :style="{ background: gradiente }" />
    <div class="legend-ticks">
      <span>Menor</span>
      <span>Mayor prioridad</span>
    </div>
    <div v-if="!compacta" class="legend-note">
      Rampa secuencial perceptualmente uniforme, segura para daltonismo
    </div>
  </div>
</template>

<style lang="scss" scoped>
.legend-title {
  margin-block-end: 7px;
  color: rgba(var(--v-theme-on-surface), .62);
  font-size: 10.5px;
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
}

.legend-bar {
  border-radius: 3px;
  block-size: 9px;
}

.legend-ticks {
  display: flex;
  justify-content: space-between;
  margin-block-start: 5px;
  color: rgba(var(--v-theme-on-surface), .5);
  font-size: 10.5px;
}

.legend-note {
  margin-block-start: 7px;
  color: rgba(var(--v-theme-on-surface), .42);
  font-size: 10.5px;
  line-height: 1.4;
}

.legend--compact .legend-bar { block-size: 7px; }
</style>
