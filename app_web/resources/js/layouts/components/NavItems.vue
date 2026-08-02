<script setup>
import VerticalNavLink from '@layouts/components/VerticalNavLink.vue'
import VerticalNavSectionTitle from '@layouts/components/VerticalNavSectionTitle.vue'
</script>

<template>
  <VerticalNavSectionTitle :item="{ heading: 'Análisis' }" />

  <VerticalNavLink
    :item="{
      title: 'Resumen',
      icon: 'bx-bar-chart-alt-2',
      to: '/panel',
    }"
  />
  <VerticalNavLink
    :item="{
      title: 'Mapa de oportunidad',
      icon: 'bx-map-alt',
      to: '/mapa',
    }"
  />
  <VerticalNavLink
    :item="{
      title: 'Ranking',
      icon: 'bx-list-ol',
      to: '/ranking',
    }"
  />
  <VerticalNavLink
    :item="{
      title: 'Simulador',
      icon: 'bx-calculator',
      to: '/simulador',
    }"
  />

  <VerticalNavSectionTitle :item="{ heading: 'Metodología' }" />

  <VerticalNavLink
    :item="{
      title: 'Validación del modelo',
      icon: 'bx-check-shield',
      to: '/modelo',
    }"
  />
  <VerticalNavLink
    :item="{
      title: 'Fuentes de datos',
      icon: 'bx-data',
      to: '/fuentes',
    }"
  />
</template>
