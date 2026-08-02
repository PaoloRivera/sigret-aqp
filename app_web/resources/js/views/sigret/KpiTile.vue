<script setup>
defineProps({
  label: { type: String, required: true },
  value: { type: [String, Number], required: true },
  suffix: { type: String, default: '' },
  hint: { type: String, default: '' },
  icon: { type: String, default: '' },
  color: { type: String, default: 'primary' },
  dense: { type: Boolean, default: false },
})
</script>

<template>
  <VCard class="kpi-tile h-100">
    <VCardText :class="dense ? 'pa-4' : 'pa-5'">
      <div class="d-flex align-start justify-space-between mb-1">
        <span class="kpi-label">{{ label }}</span>
        <VAvatar
          v-if="icon"
          :color="color"
          variant="tonal"
          rounded
          size="34"
        >
          <VIcon :icon="icon" size="19" />
        </VAvatar>
      </div>

      <div class="kpi-value" :class="dense ? 'text-h5' : ''">
        {{ value }}<span v-if="suffix" class="kpi-suffix">{{ suffix }}</span>
      </div>

      <div v-if="hint" class="kpi-hint">{{ hint }}</div>
    </VCardText>
  </VCard>
</template>

<style lang="scss" scoped>
.kpi-tile { transition: box-shadow .22s ease, transform .22s ease; }
.kpi-tile:hover { box-shadow: 0 6px 20px rgb(27 42 50 / 11%); transform: translateY(-2px); }

.kpi-label {
  display: block;
  color: rgba(var(--v-theme-on-surface), .58);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: .075em;
  line-height: 1.35;
  text-transform: uppercase;
}

.kpi-value {
  margin-block-start: 6px;
  font-size: 1.85rem;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  letter-spacing: -.02em;
  line-height: 1.1;
}

.kpi-suffix {
  margin-inline-start: 3px;
  color: rgba(var(--v-theme-on-surface), .48);
  font-size: .82rem;
  font-weight: 500;
}

.kpi-hint {
  margin-block-start: 5px;
  color: rgba(var(--v-theme-on-surface), .52);
  font-size: 11.5px;
  line-height: 1.4;
}
</style>
